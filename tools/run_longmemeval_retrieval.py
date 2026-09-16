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
from importlib.metadata import version
from importlib.util import find_spec
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


def _load_manifest_cases(
    dataset_path: Path, manifest_path: Path, partition: str
) -> tuple[list[dict[str, Any]], str]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("format") != "atmem-mem0-head-to-head-manifest-v1":
        raise ValueError("benchmark manifest format is unsupported")
    actual = sha256(dataset_path.read_bytes()).hexdigest()
    if actual != str((manifest.get("dataset") or {}).get("source_sha256")):
        raise ValueError("benchmark dataset digest does not match frozen manifest")
    ids = (manifest.get("selection") or {}).get(f"{partition}_case_ids")
    if not isinstance(ids, list) or not ids:
        raise ValueError("benchmark manifest partition is empty or invalid")
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark manifest contains duplicate case IDs")
    cases = _load_cases(dataset_path, 0, ids)
    if [case["question_id"] for case in cases] != ids:
        raise ValueError("benchmark selection does not match frozen manifest")
    return cases, "sha256:" + sha256(manifest_bytes).hexdigest()


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


def _canonical_chunk(text: str) -> str:
    """Match the trusted interpreted-fact normalization used by AtMem."""
    value = " ".join(text.strip().split())
    if not value:
        return "User asked to remember an empty note."
    if value[0].islower():
        value = value[0].upper() + value[1:]
    if value[-1] not in ".?!":
        value += "."
    return value


def _corpus(
    case: dict[str, Any], chunk_chars: int, *, matched_inputs: bool = False
) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    session_ids = case["haystack_session_ids"]
    sessions = case["haystack_sessions"]
    if len(session_ids) != len(sessions):
        raise ValueError(f"session ID mismatch in {case['question_id']}")
    for session_id, session in zip(session_ids, sessions):
        for chunk in _chunks(_session_text(session), chunk_chars):
            if matched_inputs:
                # AtMem deduplicates exact canonical facts. Give both stores
                # the same first-source corpus instead of indexing extra
                # duplicate points in Mem0.
                canonical = _canonical_chunk(chunk)
                if canonical in seen:
                    continue
                seen.add(canonical)
                entries.append((str(session_id), canonical))
            else:
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
    reuse_existing: bool,
    warm_repeats: int,
    matched_inputs: bool,
) -> tuple[list[str], float, list[float], float | None, list[dict[str, Any]], list[str]]:
    from atmem import Memory
    from atmem.semantic import OllamaEmbedder, SemanticIndex, default_index_path

    subject = "longmemeval-user"
    database = work / f"{case['question_id']}.db"
    memory = Memory(database, auto_vectors=False)
    record_sessions: dict[str, str] = {}
    try:
        indexing_started = time.perf_counter()
        if reuse_existing:
            expected_sessions = {session_id for session_id, _ in entries}
            keyed_indices: set[int] = set()
            for record in memory.store.list_records(subject, statuses=("active",)):
                if record.get("source_session_id"):
                    record_sessions[str(record["id"])] = str(record["source_session_id"])
                prefix = f"benchmark.{case['question_id']}."
                key = str(record.get("fact_key") or "")
                if not key.startswith(prefix) or not key[len(prefix):].isdigit():
                    raise ValueError("reused AtMem index has a foreign fact key")
                keyed_indices.add(int(key[len(prefix):]))
                if str(record.get("source_session_id") or "") not in expected_sessions:
                    raise ValueError("reused AtMem index has a foreign session")
            # Canonical exact deduplication can remove repeated raw chunks.
            # This is a guarded convenience profile, not a cryptographic
            # corpus proof; the fresh-build profile binds the dataset digest.
            if not keyed_indices or len(keyed_indices) < len(set(entries)) * 0.9 or max(keyed_indices) >= len(entries):
                raise ValueError("reused AtMem index does not match frozen corpus keys")
        else:
            for index, (session_id, text) in enumerate(entries):
                result = memory.remember(
                    subject,
                    text,
                    source_type="user_message",
                    session_id=session_id,
                    turn_id=index,
                    interpreted_fact=(text if matched_inputs else text.removeprefix("Explicit note: ")),
                    interpreted_fact_key=f"benchmark.{case['question_id']}.{index}",
                    raw={"interpreter": "longmemeval-raw-corpus-v1"},
                )
                for record in result["records"]:
                    record_sessions[str(record["id"])] = session_id
        embedder = OllamaEmbedder(model)
        index = SemanticIndex(default_index_path(database), policy=memory.policy)
        try:
            if reuse_existing:
                if not index.verify(memory, subject)["valid"]:
                    raise ValueError("reused AtMem index failed canonical verification")
                indexing_ms = None
            else:
                index.build(memory, subject, embedder, batch_size=64)
                indexing_ms = (time.perf_counter() - indexing_started) * 1000
            started = time.perf_counter()
            found = index.search(memory, subject, str(case["question"]), embedder, limit=max(100, limit * 20), min_similarity=0.0 if matched_inputs else -1.0)
            latency = (time.perf_counter() - started) * 1000
            warm_latencies = []
            for _ in range(warm_repeats):
                started = time.perf_counter()
                warm_found = index.search(memory, subject, str(case["question"]), embedder, limit=max(100, limit * 20), min_similarity=0.0 if matched_inputs else -1.0)
                warm_latencies.append((time.perf_counter() - started) * 1000)
                if [item["record_id"] for item in warm_found] != [item["record_id"] for item in found]:
                    raise RuntimeError("AtMem cold/warm retrieval changed candidate order")
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
        return sessions, latency, warm_latencies, indexing_ms, evidence, baseline
    finally:
        memory.close()


def _mem0_search(memory: Any, query: str, user_id: str, limit: int, *, matched_inputs: bool) -> Any:
    """Use Mem0's documented `top_k`, never the ignored `limit` keyword."""
    return memory.search(
        query,
        filters={"user_id": user_id},
        top_k=max(100, limit * 20),
        threshold=0.0 if matched_inputs else 0.1,
    )


def _run_mem0(
    case: dict[str, Any],
    entries: list[tuple[str, str]],
    work: Path,
    model: str,
    limit: int,
    reuse_existing: bool,
    warm_repeats: int,
    matched_inputs: bool,
) -> tuple[list[str], float, list[float], float | None, list[dict[str, Any]], list[str]]:
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
    if matched_inputs:
        if model != "nomic-embed-text:latest":
            raise ValueError("matched-inputs profile currently requires nomic-embed-text:latest")
        # Mem0's stock Ollama embedder sends raw text. Bind the exact same
        # Nomic role-prefix contract as AtMem for this controlled comparison.
        original_embed = memory.embedding_model.embed
        original_batch = memory.embedding_model.embed_batch

        def matched_embed(text, memory_action=None):
            prefix = "search_query: " if memory_action == "search" else "search_document: "
            return original_embed(prefix + str(text).strip(), memory_action)

        def matched_batch(texts, memory_action="add"):
            prefix = "search_query: " if memory_action == "search" else "search_document: "
            return original_batch([prefix + str(text).strip() for text in texts], memory_action)

        memory.embedding_model.embed = matched_embed
        memory.embedding_model.embed_batch = matched_batch
    user_id = "longmemeval-user"
    indexing_started = time.perf_counter()
    if not reuse_existing:
        for index, (session_id, text) in enumerate(entries):
            memory.add(
                text,
                user_id=user_id,
                metadata={"session_id": session_id, "chunk_index": index},
                infer=False,
            )
    indexing_ms = None if reuse_existing else (time.perf_counter() - indexing_started) * 1000
    started = time.perf_counter()
    found = _mem0_search(memory, str(case["question"]), user_id, limit, matched_inputs=matched_inputs)
    latency = (time.perf_counter() - started) * 1000
    rows = []
    for item in found.get("results", found) if isinstance(found, dict) else found:
        metadata = item.get("metadata") or {}
        session_id = metadata.get("session_id") or item.get("session_id")
        if session_id:
            rows.append((str(session_id), float(item.get("score") or 0.0)))
    sessions = _dedupe_sessions(rows, limit)
    warm_latencies = []
    for _ in range(warm_repeats):
        started = time.perf_counter()
        warm_found = _mem0_search(memory, str(case["question"]), user_id, limit, matched_inputs=matched_inputs)
        warm_latencies.append((time.perf_counter() - started) * 1000)
        warm_rows = warm_found.get("results", warm_found) if isinstance(warm_found, dict) else warm_found
        warm_sessions = _dedupe_sessions(
            (
                (str((item.get("metadata") or {}).get("session_id") or item.get("session_id")), float(item.get("score") or 0.0))
                for item in warm_rows
                if (item.get("metadata") or {}).get("session_id") or item.get("session_id")
            ),
            limit,
        )
        if warm_sessions != sessions:
            raise RuntimeError("Mem0 cold/warm retrieval changed session order")
    return sessions, latency, warm_latencies, indexing_ms, [], sessions


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
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--partition", choices=("calibration", "heldout"))
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--warm-repeats", type=int, default=1)
    parser.add_argument(
        "--matched-inputs", action="store_true",
        help="canonical-deduplicate both corpora and apply the same Nomic query/document prefixes",
    )
    args = parser.parse_args()
    if args.warm_repeats < 1 or args.warm_repeats > 100:
        parser.error("--warm-repeats must be between 1 and 100")

    if args.partition:
        if args.manifest is None or args.case_id:
            parser.error("--partition requires --manifest and cannot combine with --case-id")
        cases, manifest_sha256 = _load_manifest_cases(
            args.dataset, args.manifest, args.partition
        )
    else:
        cases = _load_cases(args.dataset, args.cases_per_type, args.case_id)
        manifest_sha256 = None
    args.work_dir.mkdir(parents=True, exist_ok=True)
    run = _run_atmem if args.backend == "atmem" else _run_mem0
    any_hits = all_hits = 0
    reciprocal_ranks: list[float] = []
    latencies: list[float] = []
    warm_latencies: list[float] = []
    indexing_durations: list[float] = []
    details: list[dict[str, Any]] = []
    for position, case in enumerate(cases, 1):
        entries = _corpus(case, args.chunk_chars, matched_inputs=args.matched_inputs)
        print(f"[{position}/{len(cases)}] {args.backend} {case['question_id']} ({len(entries)} chunks)", flush=True)
        retrieved, latency, warm_samples, indexing_ms, aggregation, baseline_retrieved = run(
            case, entries, args.work_dir, args.embedding_model, args.limit,
            args.reuse_existing, args.warm_repeats, args.matched_inputs,
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
        warm_latencies.extend(warm_samples)
        if indexing_ms is not None:
            indexing_durations.append(indexing_ms)
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
            "warm_latency_ms": statistics.median(warm_samples),
            "warm_latency_samples_ms": warm_samples,
            "corpus_admission_and_index_ms": indexing_ms,
            "chunk_count": len(entries),
            "aggregation": aggregation,
        })

    dataset_bytes = args.dataset.read_bytes()
    dataset = {
        "name": "LongMemEval-S cleaned",
        "upstream_commit": "98d7416c24c778c2fee6e6f3006e7a073259d48f",
        "source_sha256": "sha256:" + sha256(dataset_bytes).hexdigest(),
        "selection": (
            f"frozen-{args.partition}-v1" if args.partition
            else "explicit-case-id-v1" if args.case_id else SELECTION
        ),
        "manifest_sha256": manifest_sha256,
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
        "index_state": "prebuilt" if args.reuse_existing else "built_for_case",
        "warm_repeats": args.warm_repeats,
        "input_profile": "canonical-deduplicated-nomic-prefixed-v2" if args.matched_inputs else "legacy-product-default-v1",
        "effective_mem0_top_k": max(100, args.limit * 20),
    }
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    ordered_warm = sorted(warm_latencies)
    warm_p95 = ordered_warm[min(len(ordered_warm) - 1, int(len(ordered_warm) * 0.95))]
    report = {
        "format": FORMAT,
        "system": "atmem-local" if args.backend == "atmem" else f"mem0-oss-{version('mem0ai')}",
        "dataset": dataset,
        "case_ids": [case["question_id"] for case in cases],
        "scoring_format": SCORING,
        "model_configuration": model_configuration,
        "backend_capabilities": (
            {
                "numpy_available": find_spec("numpy") is not None,
                "ollama_query_vector_cache": "process-only-128-entries-60s-expiry-on-access",
            }
            if args.backend == "atmem"
            else {
                "spacy_available": find_spec("spacy") is not None,
                "fastembed_available": find_spec("fastembed") is not None,
            }
        ),
        "metrics": {
            "session_recall_any_at_5": any_hits / len(cases),
            "session_recall_all_at_5": all_hits / len(cases),
            "session_mrr_at_5": statistics.fmean(reciprocal_ranks),
            "latency_p50_ms": statistics.median(latencies),
            "latency_p95_ms": p95,
            "warm_latency_p50_ms": statistics.median(warm_latencies),
            "warm_latency_p95_ms": warm_p95,
            "corpus_admission_and_index_p50_ms": (
                statistics.median(indexing_durations) if indexing_durations else None
            ),
        },
        "limitations": [
            "This is a fixed stratified retrieval campaign, not the complete 500-case answer-generation evaluation.",
            "Raw ingestion isolates retrieval quality; automatic fact extraction is scored by the deterministic release gate.",
            "Cold and warm search latency include query embedding and search but exclude corpus ingestion and index construction; warm is the exact repeated query.",
            "Corpus admission and index duration is reported separately and includes different backend-specific persistence work; do not conflate it with query latency.",
            "In a prebuilt-index profile, corpus admission and indexing were not measured; null means not measured, not zero.",
        ],
        "case_results": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
