from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from atmem import Memory

from .manifest import BenchmarkManifest
from .metrics import ranking_metrics
from .jev import rerank


def _evidence_ids(values: list[Any]) -> list[str]:
    """Normalize upstream's occasional semicolon and ``D:11:26`` forms."""
    normalized: list[str] = []
    for value in values:
        for part in str(value).split(";"):
            token = part.strip()
            token = re.sub(r"^D:(\d+:\d+)$", r"D\1", token)
            token = re.sub(r"^D:(\d+:\d+)$", r"D\1", token)
            matches = re.findall(r"D\d+:\d+", token)
            normalized.extend(matches or ([token] if token else []))
    return normalized


def load_locomo(path: str | Path, *, strict: bool = True) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("LoCoMo data must be a non-empty list")
    for conversation in payload:
        if not isinstance(conversation, dict) or not isinstance(conversation.get("qa"), list) or not isinstance(conversation.get("conversation"), dict):
            raise ValueError("LoCoMo record missing qa or conversation")
        dialogue_ids = set()
        for key, turns in conversation["conversation"].items():
            if key.startswith("session_") and isinstance(turns, list):
                for turn in turns:
                    if isinstance(turn, dict) and turn.get("dia_id"):
                        dialogue_ids.add(str(turn["dia_id"]))
        for qa in conversation["qa"]:
            evidence = qa.get("evidence")
            evidence_ids = _evidence_ids(evidence) if isinstance(evidence, list) else []
            if strict and (not evidence_ids or not set(evidence_ids) <= dialogue_ids):
                raise ValueError("LoCoMo QA has missing or unknown evidence IDs")
    return payload


def _turns(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    turns = []
    for key, values in conversation["conversation"].items():
        if key.startswith("session_") and key.rsplit("_", 1)[-1].isdigit() and isinstance(values, list):
            turns.extend(value for value in values if isinstance(value, dict) and value.get("dia_id") and value.get("text"))
    return turns


def run_locomo(data_path: str | Path, *, manifest_path: str | Path, sample: int | None = None, full_corpus: bool = False, allow_anomalies: bool = False, use_jev: bool = False, jev_batch_size: int = 20, jev_model: str = "jev-1.13.0") -> dict[str, Any]:
    manifest = BenchmarkManifest.load(manifest_path)
    digest = manifest.validate_file(data_path)
    conversations = load_locomo(data_path, strict=not allow_anomalies)
    selected = conversations if sample is None else conversations[:sample]
    if not selected:
        raise ValueError("LoCoMo sample is empty")
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    errors = 0
    for conversation in selected:
        subject = f"locomo:{conversation.get('sample_id', len(rows))}"
        memory = Memory(":memory:", auto_vectors=False)
        try:
            turns = _turns(conversation)
            normalized_ids = {str(turn["dia_id"]).lower().replace(":", " "): str(turn["dia_id"]) for turn in turns}
            for turn in turns:
                text = str(turn["text"])
                memory.remember(subject, text, interpreted_fact=text, interpreted_fact_key=str(turn["dia_id"]), source_type="user_message", actor="benchmark:locomo", raw={"benchmark": "locomo", "dialogue_id": str(turn["dia_id"])})
            for qa in conversation["qa"]:
                query_started = time.perf_counter()
                recalled = memory.recall(subject, str(qa["question"]), limit=10, include_scores=True)
                latency_ms = (time.perf_counter() - query_started) * 1000
                ranked_ids = [normalized_ids.get(str(item.get("fact_key") or "").lower(), str(item.get("fact_key") or "")) for item in recalled]
                candidates = [{"id": normalized_ids.get(str(item.get("fact_key") or "").lower(), str(item.get("fact_key") or "")), "text": str(item.get("content") or "")} for item in recalled]
                rows.append({"conversation_id": subject, "case_id": f"{subject}:{len(rows)}", "question": qa["question"], "evidence_ids": _evidence_ids(qa["evidence"]), "ranked_ids": ranked_ids, "baseline_ranked_ids": ranked_ids, "candidates": candidates, "latency_ms": round(latency_ms, 3)})
        except Exception:
            errors += 1
        finally:
            memory.close()
    ended = time.perf_counter()
    validation_issues = 0
    for conversation in selected:
        dialogue_ids = {str(turn["dia_id"]) for turn in _turns(conversation)}
        for qa in conversation["qa"]:
            validation_issues += int(not set(_evidence_ids(qa.get("evidence", []))) <= dialogue_ids)
    metrics = ranking_metrics(rows, full_corpus=full_corpus, manifest=manifest.__dict__, digest=digest, baseline="atmem-deterministic-recall-v1", started_at=started, ended_at=ended, errors=errors)
    metrics["validation_issues"] = validation_issues
    claim_status = manifest.claim_status(full_corpus=full_corpus, baseline=metrics["baseline"], metrics=metrics, digest=digest)
    result: dict[str, Any] = {"format": "atmem-production-benchmark-v1", "benchmark": "locomo", "claim_status": claim_status, "metrics": metrics, "rows": rows, "jev": None}
    if use_jev:
        jev_rankings, jev_transport = rerank(rows, batch_size=jev_batch_size, model=jev_model)
        jev_rows = [dict(row, ranked_ids=jev_rankings.get(row["case_id"], row["ranked_ids"])) for row in rows]
        jev_metrics = ranking_metrics(jev_rows, full_corpus=full_corpus, manifest=manifest.__dict__, digest=digest, baseline="atmem-plus-jev-rerank-v1", started_at=started, ended_at=ended, errors=errors + int(jev_transport["errors"]))
        result["jev"] = {"metrics": jev_metrics, "transport": jev_transport, "model": jev_model}
    return result
