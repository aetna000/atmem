"""Dependency-free validation and canonical serialization for benchmark data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


CASES_FORMAT = "atmem-benchmark-cases-v1"
REPORT_FORMAT = "atmem-benchmark-report-v1"
EXTERNAL_FORMAT = "atmem-benchmark-external-results-v1"
SCORING_FORMAT = "atmem-memory-quality-scoring-v1"
_CATEGORIES = {
    "extraction",
    "contradiction",
    "recall",
    "no_answer",
    "incorrect_injection",
    "privacy",
    "poisoning",
    "fallback",
}
_SECRET_KEYS = {"api_key", "apikey", "password", "secret", "access_token"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_dataset(path: str | Path) -> dict[str, Any]:
    value = read_json(path)
    if value.get("format") != CASES_FORMAT:
        raise ValueError(f"dataset format must be {CASES_FORMAT}")
    if not str(value.get("name") or "").strip() or not str(value.get("version") or "").strip():
        raise ValueError("dataset name and version are required")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("dataset cases must be a non-empty list")
    ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each benchmark case must be an object")
        case_id = str(case.get("id") or "").strip()
        if not case_id or case_id in ids:
            raise ValueError(f"duplicate or empty benchmark case id: {case_id!r}")
        ids.add(case_id)
        if case.get("category") not in _CATEGORIES:
            raise ValueError(f"unsupported category for {case_id}")
        if not isinstance(case.get("setup", []), list):
            raise ValueError(f"setup must be a list for {case_id}")
        if not isinstance(case.get("expected"), dict):
            raise ValueError(f"expected outcome is required for {case_id}")
    _reject_secrets(value)
    normalized = dict(value)
    normalized["dataset_sha256"] = canonical_digest(
        {key: item for key, item in value.items() if key != "dataset_sha256"}
    )
    return normalized


def metric(value: int | float | None, *, unit: str, reason: str | None = None) -> dict[str, Any]:
    if value is None and not reason:
        raise ValueError("an unavailable metric requires a reason")
    if value is not None and reason:
        raise ValueError("an available metric cannot have an unavailable reason")
    return {"value": value, "unit": unit, "unavailable_reason": reason}


def validate_report(value: Mapping[str, Any]) -> dict[str, Any]:
    report = dict(value)
    if report.get("format") != REPORT_FORMAT:
        raise ValueError(f"report format must be {REPORT_FORMAT}")
    for key in ("dataset", "profile", "metrics", "thresholds", "case_results", "limitations"):
        if key not in report:
            raise ValueError(f"report is missing {key}")
    case_results = report["case_results"]
    if not isinstance(case_results, list):
        raise ValueError("case_results must be a list")
    ids = [str(row.get("case_id") or "") for row in case_results if isinstance(row, dict)]
    if len(ids) != len(case_results) or len(set(ids)) != len(ids) or any(not item for item in ids):
        raise ValueError("case result IDs must be non-empty and unique")
    for name, item in dict(report["metrics"]).items():
        if not isinstance(item, dict) or "value" not in item or "unavailable_reason" not in item:
            raise ValueError(f"metric {name} is malformed")
        if item["value"] is None and not item["unavailable_reason"]:
            raise ValueError(f"metric {name} needs an unavailable reason")
    _reject_secrets(report)
    return report


def stable_quality_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    stable_cases = [
        {key: value for key, value in dict(row).items() if key != "duration_ms"}
        for row in report["case_results"]
    ]
    stable_metrics = {
        key: value
        for key, value in dict(report["metrics"]).items()
        if not key.startswith("latency_")
    }
    return {
        "format": report["format"],
        "scoring_format": report["scoring_format"],
        "dataset": report["dataset"],
        "profile": report["profile"],
        "metrics": stable_metrics,
        "thresholds": report["thresholds"],
        "passed": report["passed"],
        "failures": report["failures"],
        "case_results": stable_cases,
        "limitations": report["limitations"],
    }


def _reject_secrets(value: Any, path: str = "report") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in _SECRET_KEYS and item not in (None, "", "redacted"):
                raise ValueError(f"secret material is not allowed at {path}.{key}")
            _reject_secrets(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secrets(item, f"{path}[{index}]")
