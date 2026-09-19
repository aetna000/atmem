"""Run the Jev-Lab experiment without changing AtMem production behavior."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .dataset import build_dataset, dataset_digest

DEFAULT_MODEL = "jev-1.13.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"


def _tokens(value: str) -> set[str]:
    return {word.lower().strip(".,!?;:'\"()") for word in value.split() if len(word) > 2}


def _state_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def baseline_rank(case: dict[str, Any]) -> list[str]:
    query = _tokens(case["query"])
    scored = []
    for position, candidate in enumerate(case["candidates"]):
        overlap = len(query & _tokens(candidate["text"]))
        scored.append((overlap, -position, str(candidate["id"])))
    return [item[2] for item in sorted(scored, reverse=True)]


def authority_gate(case: dict[str, Any], nominated: list[str]) -> list[str]:
    by_id = {str(candidate["id"]): candidate for candidate in case["candidates"]}
    return [candidate_id for candidate_id in nominated if by_id.get(candidate_id, {}).get("eligible") and by_id.get(candidate_id, {}).get("status") == "active"]


def _offline_answer(case: dict[str, Any]) -> dict[str, Any]:
    ranking = baseline_rank(case)
    eligible = authority_gate(case, ranking)
    choice = eligible[0] if eligible else None
    probabilities = {candidate_id: (0.85 if candidate_id == choice else 0.05) for candidate_id in ranking}
    return {"type": "choice", "choice": choice, "probabilities": probabilities, "confidence": 0.85 if choice else 0.0}


def _jev_request(dataset: dict[str, Any], model: str) -> dict[str, Any]:
    questions = {}
    for case in dataset["cases"]:
        options = {str(candidate["id"]): candidate["label"] for candidate in case["candidates"]}
        questions[case["id"]] = {
            "type": "choice",
            "instructions": "Which candidate is most relevant to the query? Treat expired or out-of-scope candidates as ineligible; choose the best eligible candidate.",
            "criteria": options,
        }
    state = {"dataset": dataset["format"], "cases": [{"id": c["id"], "query": c["query"], "candidates": c["candidates"]} for c in dataset["cases"]]}
    return {"state": state, "model": model, "questions": questions}


def call_jev(dataset: dict[str, Any], api_key: str, model: str, timeout: float = 30.0) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    body = json.dumps(_jev_request(dataset, model), separators=(",", ":")).encode()
    req = request.Request(ENDPOINT, data=body, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        return parsed, {"status": "ok", "http_status": 200, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except (error.HTTPError, error.URLError, TimeoutError, ValueError) as exc:
        return None, {"status": "unavailable", "error_type": type(exc).__name__, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def _answer_for_live(response: dict[str, Any], case_id: str) -> dict[str, Any]:
    answer = response.get("answers", {}).get(case_id, {})
    return {"type": answer.get("type", "choice"), "choice": answer.get("choice"), "probabilities": answer.get("probabilities", {}), "confidence": answer.get("confidence")}


def _rank_from_answer(case: dict[str, Any], answer: dict[str, Any]) -> list[str]:
    probabilities = answer.get("probabilities") or {}
    return [item[0] for item in sorted(probabilities.items(), key=lambda item: (-float(item[1]), item[0]))]


def _rank_metrics(cases: list[dict[str, Any]], rankings: dict[str, list[str]]) -> dict[str, Any]:
    rr = []
    top1 = 0
    for case in cases:
        ranked = rankings.get(case["id"], [])
        expected = case["expected_id"]
        rank = next((i for i, value in enumerate(ranked, 1) if value == expected), None)
        rr.append(0.0 if rank is None else 1.0 / rank)
        top1 += rank == 1
    return {"mrr_at_5": round(sum(rr) / len(rr), 4), "top1_accuracy": round(top1 / len(cases), 4), "cases": len(cases)}


def _agreement(cases: list[dict[str, Any]], left: dict[str, list[str]], right: dict[str, list[str]]) -> float:
    if not cases:
        return 1.0
    return round(sum(bool(left.get(case["id"]) and right.get(case["id"]) and left[case["id"]][0] == right[case["id"]][0]) for case in cases) / len(cases), 4)


def run(*, seed: int = 34, case_count: int = 8, offline: bool = False, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    dataset = build_dataset(seed, case_count)
    baseline = {case["id"]: baseline_rank(case) for case in dataset["cases"]}
    api_key = os.environ.get("JEV_API", "")
    live_response = None
    transport = {"status": "offline", "latency_ms": 0.0}
    mode = "offline"
    if not offline and api_key:
        live_response, transport = call_jev(dataset, api_key, model)
        if live_response is not None:
            mode = "live"
        else:
            # Do not disguise an API outage as a successful offline result.
            # The local judge is useful for continuity, but the report must
            # make the unavailable live dependency visible.
            mode = "unavailable"
    jev_answers = {}
    jev_rankings = {}
    records = []
    for case in dataset["cases"]:
        answer = _answer_for_live(live_response, case["id"]) if live_response is not None else _offline_answer(case)
        ranked = _rank_from_answer(case, answer) if live_response is not None else baseline[case["id"]]
        gated = authority_gate(case, ranked)
        jev_answers[case["id"]] = answer
        jev_rankings[case["id"]] = ranked
        records.append({"case_id": case["id"], "query": case["query"], "expected_id": case["expected_id"], "baseline_rank": baseline[case["id"]], "jev_rank": ranked, "authority_rank": gated, "jev_answer": answer, "state_sha256": _state_digest(case), "authority_decision": gated[0] if gated else None, "authority_overrode_jev": bool(ranked and ranked[0] not in gated)})
    result = {"format": "atmem-jev-lab-report-v1", "dataset": dataset["format"], "dataset_sha256": dataset_digest(dataset), "seed": seed, "mode": mode, "model": (live_response or {}).get("model", model) if mode == "live" else "offline-deterministic-judge", "transport": transport, "metrics": {"baseline": _rank_metrics(dataset["cases"], baseline), "jev": _rank_metrics(dataset["cases"], jev_rankings), "agreement_rate": _agreement(dataset["cases"], baseline, jev_rankings), "authority_overrides": sum(row["authority_overrode_jev"] for row in records)}, "records": records, "synthetic_only": True, "api_key_recorded": False, "limitations": ["Jev is advisory; AtMem authority gates every returned candidate.", "Synthetic text only; no user or production memory was sent.", "Offline mode demonstrates the contract, not Jev model quality."]}
    return result
