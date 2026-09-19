from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib import error, request

from .runner_types import JEV_ENDPOINT, JEV_MODEL


def _request(batch: list[dict[str, Any]], *, api_key: str, model: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    questions: dict[str, Any] = {}
    state_cases = []
    for row in batch:
        options = {str(item["id"]): str(item["text"]) for item in row["candidates"]}
        questions[row["case_id"]] = {
            "type": "choice",
            "instructions": "Which candidate best answers the query? Choose only among the supplied candidate IDs.",
            "criteria": options,
        }
        state_cases.append({"case_id": row["case_id"], "query": row["question"], "candidates": options})
    payload = json.dumps({"state": {"benchmark": "locomo", "cases": state_cases}, "model": model, "questions": questions}, separators=(",", ":")).encode()
    req = request.Request(JEV_ENDPOINT, data=payload, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=90) as response:
            value = json.loads(response.read().decode("utf-8"))
        return value, {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
    except (error.HTTPError, error.URLError, TimeoutError, ValueError) as exc:
        return None, {"status": "error", "error_type": type(exc).__name__, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}


def rerank(rows: list[dict[str, Any]], *, batch_size: int = 20, model: str = JEV_MODEL) -> tuple[dict[str, list[str]], dict[str, Any]]:
    api_key = os.environ.get("JEV_API", "")
    if not api_key:
        raise RuntimeError("JEV_API is required for --jev")
    rankings: dict[str, list[str]] = {}
    errors = 0
    batches = 0
    latencies: list[float] = []
    for start in range(0, len(rows), max(1, batch_size)):
        batch = rows[start : start + max(1, batch_size)]
        response, transport = _request(batch, api_key=api_key, model=model)
        batches += 1
        latencies.append(float(transport["latency_ms"]))
        if response is None:
            errors += 1
            for row in batch:
                rankings[row["case_id"]] = list(row["baseline_ranked_ids"])
            continue
        for row in batch:
            answer = response.get("answers", {}).get(row["case_id"], {})
            probabilities = answer.get("probabilities") or {}
            candidate_ids = {str(item["id"]) for item in row["candidates"]}
            ranked = [item[0] for item in sorted(probabilities.items(), key=lambda item: (-float(item[1]), item[0])) if item[0] in candidate_ids]
            rankings[row["case_id"]] = ranked or list(row["baseline_ranked_ids"])
    return rankings, {"model": model, "batches": batches, "errors": errors, "latency_ms_total": round(sum(latencies), 3), "latency_ms_p50_batch": round(sorted(latencies)[len(latencies) // 2], 3) if latencies else 0.0, "latency_ms_p95_batch": round(sorted(latencies)[min(len(latencies) - 1, int(len(latencies) * 0.95))], 3) if latencies else 0.0}
