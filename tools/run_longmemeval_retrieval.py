#!/usr/bin/env python3
"""Run a matched LongMemEval-S evidence-session retrieval campaign.

This optional runner deliberately keeps third-party dependencies out of AtMem's
base install. Invoke it once with the AtMem environment and once with an
isolated, pinned Mem0 environment. Both backends receive the same raw chunks,
embedding model, cases, query text, cutoff, and scoring implementation.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Iterable


FORMAT = "atmem-benchmark-external-results-v1"
SCORING = "atmem-memory-quality-scoring-v1"
SELECTION = "sha256-question-id-stratified-v1"


def _digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


def _load_cases(
    path: Path,
    cases_per_type: int,
    case_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("LongMemEval-S input must be a JSON array")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    eligible_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("question_id") or "")
        # The official retrieval evaluator omits the 30 abstention variants.
        if not case_id or case_id.endswith("_abs"):
            continue
        if not row.get("answer_session_ids"):
            continue
        grouped[str(row["question_type"])].append(row)
        eligible_by_id[case_id] = row
    requested = list(dict.fromkeys(str(value) for value in case_ids if str(value)))
    if requested:
        missing = [value for value in requested if value not in eligible_by_id]
        if missing:
            raise ValueError(
                "requested LongMemEval case is unavailable or ineligible: "
                + ", ".join(missing)
            )
        return [eligible_by_id[value] for value in requested]
    selected: list[dict[str, Any]] = []
    for question_type in sorted(grouped):
        ordered = sorted(
            grouped[question_type],
            key=lambda row: sha256(str(row["question_id"]).encode("utf-8")).hexdigest(),
        )
        selected.extend(ordered[:cases_per_type])
    if not selected:
        raise ValueError("no eligible LongMemEval-S cases were selected")
    return selected


def _session_text(session: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{str(message.get('role') or 'unknown')}: {str(message.get('content') or '')}"
        for message in session
    )


def _chunks(text: str, maximum: int) -> Iterable[str]:
    remaining = text.strip()
    while remaining:
        if len(remaining) <= maximum:
            yield remaining
            return
        split = remaining.rfind("\n", 0, maximum + 1)
        if split < maximum // 2:
            split = remaining.rfind(" ", 0, maximum + 1)
        if split < maximum // 2:
            split = maximum
        yield remaining[:split].strip()
        remaining = remaining[split:].strip()


def _corpus(case: dict[str, Any], chunk_chars: int) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    session_ids = case["haystack_session_ids"]
    sessions = case["haystack_sessions"]
    if len(session_ids) != len(sessions):
        raise ValueError(f"session ID mismatch in {case['question_id']}")
    for session_id, session in zip(session_ids, sessions):
        for chunk in _chunks(_session_text(session), chunk_chars):
            # AtMem's trusted interpreted-fact path canonically adds this
            # prefix; applying it to both inputs keeps embedded bytes matched.
            entries.append((str(session_id), f"Explicit note: {chunk}"))
    return entries


def _dedupe_sessions(rows: Iterable[tuple[str, float]], limit: int) -> list[str]:
    best: dict[str, float] = {}
    for session_id, score in rows:
        best[session_id] = max(best.get(session_id, float("-inf")), float(score))
    return [item[0] for item in sorted(best.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _aggregate_atmem_chunks(
    found: list[dict[str, Any]],
    record_sessions: dict[str, str],
    limit: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    from atmem.retrieve import aggregate_supporting_evidence

    candidates = aggregate_supporting_evidence(
        [
            {
                "record_id": str(item["record_id"]),
                "score": float(item["similarity"]),
                "source_session_id": record_sessions[str(item["record_id"])],
            }
            for item in found
        ],
        subject_id="longmemeval-user",
        workspace_id="longmemeval-benchmark",
        agent_id="retrieval-runner",
    )
    sessions: list[str] = []
    evidence: list[dict[str, Any]] = []
    for row in candidates:
        session_id = record_sessions[str(row["record_id"])]
        evidence.append(
            {
                "record_id": row["record_id"],
                "session_id": session_id,
                "score": row["score"],
                "signals": row["signals"],
            }
        )
        if session_id not in sessions:
            sessions.append(session_id)
        if len(sessions) >= limit and len(evidence) >= max(20, limit):
            break
    return sessions[:limit], evidence


def _run_atmem(
    case: dict[str, Any],
    entries: list[tuple[str, str]],
    work: Path,
    model: str,
    limit: int,
) -> tuple[list[str], float, list[dict[str, Any]], list[str]]:
    from atmem import Memory
    from atmem.semantic import OllamaEmbedder, SemanticIndex, default_index_path

    subject = "longmemeval-user"
    database = work / f"{case['question_id']}.db"
    memory = Memory(database, auto_vectors=False)
    record_sessions: dict[str, str] = {}
    try:
        for index, (session_id, text) in enumerate(entries):
            result = memory.remember(
                subject,
                text,
                source_type="user_message",
                session_id=session_id,
                turn_id=index,
                interpreted_fact=text.removeprefix("Explicit note: "),
                interpreted_fact_key=f"benchmark.{case['question_id']}.{index}",
                raw={"interpreter": "longmemeval-raw-corpus-v1"},
            )
            for record in result["records"]:
                record_sessions[str(record["id"])] = session_id
        embedder = OllamaEmbedder(model)
        index = SemanticIndex(default_index_path(database), policy=memory.policy)
        try:
            index.build(memory, subject, embedder, batch_size=64)
            started = time.perf_counter()
            found = index.search(memory, subject, str(case["question"]), embedder, limit=max(100, limit * 20), min_similarity=-1.0)
            latency = (time.perf_counter() - started) * 1000
        finally:
            index.close()
        sessions, evidence = _aggregate_atmem_chunks(found, record_sessions, limit)
        baseline = _dedupe_sessions(
            (
                (
                    record_sessions[str(item["record_id"])],
                    float(item["similarity"]),
                )
                for item in found
            ),
            limit,
        )
        return sessions, latency, evidence, baseline
    finally:
        memory.close()


def _run_mem0(
    case: dict[str, Any],
    entries: list[tuple[str, str]],
    work: Path,
    model: str,
    limit: int,
) -> tuple[list[str], float, list[dict[str, Any]], list[str]]:
    os.environ.setdefault("MEM0_TELEMETRY", "false")
    from mem0 import Memory

    config = {
        "version": "v1.1",
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": f"longmemeval_{case['question_id']}",
                "path": str(work / f"qdrant-{case['question_id']}"),
                "embedding_model_dims": 768,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": model,
                "ollama_base_url": "http://127.0.0.1:11434",
                "embedding_dims": 768,
            },
        },
        # Required by MemoryConfig but unused because every add is infer=False.
        "llm": {
            "provider": "ollama",
            "config": {"model": "qwen3:1.7b", "ollama_base_url": "http://127.0.0.1:11434"},
        },
        "history_db_path": str(work / f"history-{case['question_id']}.db"),
    }
    memory = Memory.from_config(config)
    user_id = "longmemeval-user"
    for index, (session_id, text) in enumerate(entries):
        memory.add(
            text,
            user_id=user_id,
            metadata={"session_id": session_id, "chunk_index": index},
            infer=False,
        )
    started = time.perf_counter()
    found = memory.search(
        str(case["question"]),
        filters={"user_id": user_id},
        limit=max(100, limit * 20),
    )
    latency = (time.perf_counter() - started) * 1000
    rows = []
    for item in found.get("results", found) if isinstance(found, dict) else found:
        metadata = item.get("metadata") or {}
        session_id = metadata.get("session_id") or item.get("session_id")
        if session_id:
            rows.append((str(session_id), float(item.get("score") or 0.0)))
    sessions = _dedupe_sessions(rows, limit)
    return sessions, latency, [], sessions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("atmem", "mem0"), required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--cases-per-type", type=int, default=2)
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="run one exact eligible case; repeat to run an ordered focused set",
    )
    parser.add_argument("--chunk-chars", type=int, default=1600)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--embedding-model", default="nomic-embed-text:latest")
    args = parser.parse_args()

    cases = _load_cases(args.dataset, args.cases_per_type, args.case_id)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    run = _run_atmem if args.backend == "atmem" else _run_mem0
    any_hits = all_hits = 0
    reciprocal_ranks: list[float] = []
    latencies: list[float] = []
    details: list[dict[str, Any]] = []
    for position, case in enumerate(cases, 1):
        entries = _corpus(case, args.chunk_chars)
        print(f"[{position}/{len(cases)}] {args.backend} {case['question_id']} ({len(entries)} chunks)", flush=True)
        retrieved, latency, aggregation, baseline_retrieved = run(
            case, entries, args.work_dir, args.embedding_model, args.limit
        )
        expected = {str(value) for value in case["answer_session_ids"]}
        ranks = [index + 1 for index, value in enumerate(retrieved) if value in expected]
        any_hit = bool(ranks)
        all_hit = expected.issubset(retrieved)
        any_hits += int(any_hit)
        all_hits += int(all_hit)
        reciprocal_ranks.append(1.0 / min(ranks) if ranks else 0.0)
        baseline_ranks = [
            index + 1
            for index, value in enumerate(baseline_retrieved)
            if value in expected
        ]
        latencies.append(latency)
        details.append({
            "case_id": case["question_id"],
            "question_type": case["question_type"],
            "expected_session_ids": sorted(expected),
            "retrieved_session_ids": retrieved,
            "baseline_retrieved_session_ids": baseline_retrieved,
            "any_hit": any_hit,
            "all_hit": all_hit,
            "reciprocal_rank": reciprocal_ranks[-1],
            "baseline_reciprocal_rank": (
                1.0 / min(baseline_ranks) if baseline_ranks else 0.0
            ),
            "latency_ms": latency,
            "chunk_count": len(entries),
            "aggregation": aggregation,
        })

    dataset_bytes = args.dataset.read_bytes()
    dataset = {
        "name": "LongMemEval-S cleaned",
        "upstream_commit": "98d7416c24c778c2fee6e6f3006e7a073259d48f",
        "source_sha256": "sha256:" + sha256(dataset_bytes).hexdigest(),
        "selection": "explicit-case-id-v1" if args.case_id else SELECTION,
        "cases_per_question_type": args.cases_per_type,
        "selection_sha256": _digest([case["question_id"] for case in cases]),
    }
    model_configuration = {
        "task": "evidence-session-retrieval",
        "ingestion": "raw-infer-disabled",
        "embedding_provider": "ollama",
        "embedding_model": args.embedding_model,
        "chunk_chars": args.chunk_chars,
        "session_cutoff": args.limit,
        "retrieved_chunk_limit": max(100, args.limit * 20),
        "scorer": "longmemeval-session-retrieval-v1",
    }
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    report = {
        "format": FORMAT,
        "system": "atmem-local" if args.backend == "atmem" else "mem0-oss-2.0.19",
        "dataset": dataset,
        "case_ids": [case["question_id"] for case in cases],
        "scoring_format": SCORING,
        "model_configuration": model_configuration,
        "metrics": {
            "session_recall_any_at_5": any_hits / len(cases),
            "session_recall_all_at_5": all_hits / len(cases),
            "session_mrr_at_5": statistics.fmean(reciprocal_ranks),
            "latency_p50_ms": statistics.median(latencies),
            "latency_p95_ms": p95,
        },
        "limitations": [
            "This is a fixed stratified retrieval campaign, not the complete 500-case answer-generation evaluation.",
            "Raw ingestion isolates retrieval quality; automatic fact extraction is scored by the deterministic release gate.",
            "Latency includes query embedding and search but excludes corpus ingestion and index construction.",
        ],
        "case_results": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
