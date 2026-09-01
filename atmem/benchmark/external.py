"""LongMemEval normalization and fair external-result comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from atmem.benchmark.contracts import EXTERNAL_FORMAT, SCORING_FORMAT, canonical_digest, read_json


_METRIC_DIRECTIONS = {
    "extraction_precision": "higher",
    "extraction_recall": "higher",
    "extraction_f1": "higher",
    "contradiction_accuracy": "higher",
    "answerable_recall": "higher",
    "session_recall_any_at_5": "higher",
    "session_recall_all_at_5": "higher",
    "session_mrr_at_5": "higher",
    "no_answer_correctness": "higher",
    "incorrect_injection_rate": "lower",
    "privacy_leak_count": "lower",
    "poisoning_success_count": "lower",
    "fallback_completion": "higher",
    "latency_p50_ms": "lower",
    "latency_p95_ms": "lower",
    "token_usage": "lower",
    "model_cost_usd": "lower",
}
_QUALITY_METRICS = {
    "extraction_precision", "extraction_recall", "extraction_f1",
    "contradiction_accuracy", "answerable_recall", "no_answer_correctness",
    "session_recall_any_at_5", "session_recall_all_at_5", "session_mrr_at_5",
    "incorrect_injection_rate", "privacy_leak_count",
    "poisoning_success_count", "fallback_completion",
}


def import_longmemeval(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    rows = list(_read_rows(source))
    supported: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    unsupported: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        case_id = str(row.get("question_id") or row.get("id") or f"row-{index + 1}")
        question = row.get("question") or row.get("query")
        answer = row.get("answer") or row.get("expected_answer")
        sessions = row.get("haystack_sessions") or row.get("sessions") or row.get("history")
        if row.get("question_type") in {"abstention", "unsupported"}:
            skipped.append({"id": case_id, "reason": "question type is not mapped by v1"})
        elif not isinstance(question, str) or not question.strip():
            unsupported.append({"id": case_id, "reason": "missing question"})
        elif answer is None:
            skipped.append({"id": case_id, "reason": "missing reference answer"})
        elif sessions is None:
            unsupported.append({"id": case_id, "reason": "missing conversation sessions"})
        else:
            supported.append(
                {
                    "id": case_id,
                    "query": question.strip(),
                    "expected_answer": answer,
                    "source_session_count": len(sessions) if isinstance(sessions, list) else 1,
                    "source_sha256": canonical_digest(sessions),
                }
            )
    return {
        "format": "atmem-longmemeval-import-v1",
        "source_sha256": canonical_digest(rows),
        "counts": {"input": len(rows), "supported": len(supported), "skipped": len(skipped), "unsupported": len(unsupported)},
        "cases": supported,
        "skipped": skipped,
        "unsupported": unsupported,
        "limitations": ["The v1 adapter normalizes data; it does not redistribute or automatically download LongMemEval."],
    }


def validate_external_result(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    if result.get("format") != EXTERNAL_FORMAT:
        raise ValueError(f"external result format must be {EXTERNAL_FORMAT}")
    for key in ("system", "dataset", "case_ids", "scoring_format", "model_configuration", "metrics", "limitations"):
        if key not in result:
            raise ValueError(f"external result is missing {key}")
    if result["scoring_format"] != SCORING_FORMAT:
        raise ValueError("external result uses an incompatible scoring format")
    case_ids = result["case_ids"]
    if not isinstance(case_ids, list) or not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("external case_ids must be a non-empty unique list")
    return result


def compare_results(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    a = validate_external_result(left)
    b = validate_external_result(right)
    mismatches: list[str] = []
    if a["dataset"] != b["dataset"]:
        mismatches.append("dataset identity or digest differs")
    if a["case_ids"] != b["case_ids"]:
        mismatches.append("evaluated case IDs or order differs")
    if a["scoring_format"] != b["scoring_format"]:
        mismatches.append("scoring format differs")
    if a["model_configuration"] != b["model_configuration"]:
        mismatches.append("model configuration differs")
    if mismatches:
        raise ValueError("not a fair comparison: " + "; ".join(mismatches))
    kinds = {_system_kind(str(a["system"])), _system_kind(str(b["system"]))}
    if kinds != {"atmem", "mem0"}:
        raise ValueError("comparison requires one AtMem result and one Mem0 result")
    names = sorted(set(a["metrics"]) | set(b["metrics"]))
    metric_results: dict[str, Any] = {}
    quality_wins = {"atmem": 0, "mem0": 0}
    considered: list[str] = []
    for name in names:
        direction = _METRIC_DIRECTIONS.get(name)
        left_value = _metric_value(a["metrics"].get(name))
        right_value = _metric_value(b["metrics"].get(name))
        winner = "not_comparable"
        if direction and left_value is not None and right_value is not None:
            if left_value == right_value:
                winner = "tie"
            else:
                left_wins = (
                    left_value > right_value if direction == "higher" else left_value < right_value
                )
                winner = str(a["system"] if left_wins else b["system"])
                if name in _QUALITY_METRICS:
                    quality_wins[_system_kind(winner)] += 1
            if name in _QUALITY_METRICS:
                considered.append(name)
        metric_results[name] = {
            "direction": direction or "undeclared",
            "values": {str(a["system"]): a["metrics"].get(name), str(b["system"]): b["metrics"].get(name)},
            "winner": winner,
        }
    if not considered:
        raise ValueError("comparison has no comparable declared memory-quality metrics")
    if quality_wins["atmem"] and quality_wins["mem0"]:
        outcome, winner_kind = "mixed", None
    elif quality_wins["atmem"]:
        outcome, winner_kind = "atmem_better", "atmem"
    elif quality_wins["mem0"]:
        outcome, winner_kind = "mem0_better", "mem0"
    else:
        outcome, winner_kind = "equal", None
    system_by_kind = {
        _system_kind(str(a["system"])): str(a["system"]),
        _system_kind(str(b["system"])): str(b["system"]),
    }
    statements = {
        "atmem_better": "AtMem performed better than Mem0 on this benchmark.",
        "mem0_better": "Mem0 performed better than AtMem on this benchmark.",
        "equal": "AtMem and Mem0 performed equally on this benchmark.",
        "mixed": "The benchmark result is mixed: AtMem and Mem0 each won at least one quality metric.",
    }
    return {
        "format": "atmem-benchmark-comparison-v1",
        "fair_comparison": True,
        "dataset": a["dataset"],
        "case_ids": a["case_ids"],
        "scoring_format": a["scoring_format"],
        "model_configuration": a["model_configuration"],
        "systems": [a["system"], b["system"]],
        "metrics": metric_results,
        "overall": {
            "outcome": outcome,
            "winner": system_by_kind.get(winner_kind) if winner_kind else None,
            "statement": statements[outcome],
            "method": "pareto-no-worse-on-all-comparable-quality-metrics",
            "considered_metrics": considered,
        },
        "limitations": {a["system"]: a["limitations"], b["system"]: b["limitations"]},
    }


def _metric_value(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _system_kind(name: str) -> str:
    normalized = name.casefold().replace("_", "-")
    if normalized.startswith("atmem"):
        return "atmem"
    if normalized.startswith("mem0"):
        return "mem0"
    return "other"


def load_external(path: str | Path) -> dict[str, Any]:
    return validate_external_result(read_json(path))


def _read_rows(path: Path) -> Iterable[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.casefold() == ".jsonl":
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_number} must be an object")
            yield value
        return
    value = json.loads(text)
    rows = value.get("data") if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ValueError("LongMemEval input must be a JSON array, data array, or JSONL")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("LongMemEval rows must be objects")
        yield row
