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
RETRIEVAL_PROTOCOL_FORMAT = "atmem-retrieval-quality-protocol-v1"
QUESTION_SPLIT_FORMAT = "atmem-longmemeval-v2-question-split-v1"
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


def validate_question_split(
    value: Mapping[str, Any], *, expected_question_ids: set[str] | None = None
) -> dict[str, Any]:
    """Validate a metadata-only development/confirmation boundary."""
    split = dict(value)
    if split.get("format") != QUESTION_SPLIT_FORMAT:
        raise ValueError(f"question split format must be {QUESTION_SPLIT_FORMAT}")
    if not str(split.get("dataset_revision") or "").strip():
        raise ValueError("question split dataset_revision is required")
    if not str(split.get("questions_sha256") or "").strip():
        raise ValueError("question split questions_sha256 is required")
    if not str(split.get("salt") or "").strip():
        raise ValueError("question split salt is required")
    development = _identifier_set(split.get("development_ids"), "development_ids")
    confirmation = _identifier_set(split.get("confirmation_ids"), "confirmation_ids")
    overlap = development & confirmation
    if overlap:
        raise ValueError(f"question split partitions overlap: {sorted(overlap)[:5]}")
    combined = development | confirmation
    if expected_question_ids is not None and combined != expected_question_ids:
        missing = sorted(expected_question_ids - combined)
        extra = sorted(combined - expected_question_ids)
        raise ValueError(f"question split coverage mismatch; missing={missing[:5]} extra={extra[:5]}")
    stable = {key: item for key, item in split.items() if key != "split_sha256"}
    expected_digest = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()
    if split.get("split_sha256") != expected_digest:
        raise ValueError("question split digest does not match its canonical content")
    _reject_secrets(split, "question_split")
    return split


def validate_retrieval_quality_protocol(
    value: Mapping[str, Any],
    *,
    split: Mapping[str, Any],
    repository_root: str | Path | None = None,
    external_root: str | Path | None = None,
    paid_configurations: int = 0,
    unregistered_retries: int = 0,
    for_paid_run: bool = False,
) -> dict[str, Any]:
    """Fail closed on incomplete or leakage-prone retrieval protocols.

    The protocol file is JSON-compatible YAML so the base package can validate
    it without adding a YAML dependency.
    """
    protocol = dict(value)
    if protocol.get("format") != RETRIEVAL_PROTOCOL_FORMAT:
        raise ValueError(f"protocol format must be {RETRIEVAL_PROTOCOL_FORMAT}")
    for key in (
        "release",
        "status",
        "external_artifact_root_env",
        "datasets",
        "models",
        "evaluation_design",
        "leakage_controls",
        "visual_input_policy",
    ):
        if not protocol.get(key):
            raise ValueError(f"retrieval protocol is missing {key}")
    longmem = dict(protocol["datasets"].get("longmemeval_v2") or {})
    for key in ("repository", "source_commit", "dataset", "dataset_revision", "split_file"):
        if not str(longmem.get(key) or "").strip():
            raise ValueError(f"LongMemEval-V2 protocol is missing {key}")
    validated_split = validate_question_split(split)
    if longmem["dataset_revision"] != validated_split["dataset_revision"]:
        raise ValueError("protocol and question split dataset revisions differ")
    if Path(str(longmem["split_file"])).name != "longmemeval-v2-question-split-v1.json":
        raise ValueError("protocol split_file does not name the frozen split")
    development_ids = set(validated_split["development_ids"])
    forced_ids = _identifier_set(longmem.get("forced_development_ids"), "forced_development_ids")
    if not forced_ids <= development_ids:
        raise ValueError("forced development IDs are missing from development")
    strata = validated_split.get("strata")
    if not isinstance(strata, dict) or not strata:
        raise ValueError("question split strata are required")
    if sum(int(row.get("development", -1)) for row in strata.values()) != len(development_ids):
        raise ValueError("question split development strata counts do not match IDs")
    if sum(int(row.get("confirmation", -1)) for row in strata.values()) != len(validated_split["confirmation_ids"]):
        raise ValueError("question split confirmation strata counts do not match IDs")
    design = dict(protocol["evaluation_design"])
    development_count = len(validated_split["development_ids"])
    confirmation_count = len(validated_split["confirmation_ids"])
    expected_counts = {
        "total_question_ids": development_count + confirmation_count,
        "development_question_ids": development_count,
        "confirmation_question_ids": confirmation_count,
    }
    if any(int(design.get(key, -1)) != count for key, count in expected_counts.items()):
        raise ValueError("evaluation design counts do not match the frozen split")
    if not str(design.get("power_note") or "").strip() or not str(design.get("interval") or "").strip():
        raise ValueError("evaluation design must declare uncertainty and power limitations")
    controls = dict(protocol["leakage_controls"])
    required_false = ("answers_available_to_product", "question_metadata_available_to_adapter", "benchmark_terms_allowed_in_runtime")
    if any(controls.get(key) is not False for key in required_false):
        raise ValueError("retrieval protocol weakens a required leakage control")
    if controls.get("inspection_resets_confirmation") is not True:
        raise ValueError("inspection must reset confirmation status")
    visual = dict(protocol["visual_input_policy"])
    if visual.get("preserve_ordered_media_references") is not True:
        raise ValueError("visual policy must preserve ordered media references")
    if visual.get("drop_media_only_cases") is not False:
        raise ValueError("visual policy may not drop media-only cases")
    if visual.get("official_complete_score_includes_visual_cases") is not True:
        raise ValueError("official complete score must include visual cases")
    datasets = dict(protocol["datasets"])
    locomo = dict(datasets.get("locomo") or {})
    if not all(str(locomo.get(key) or "").strip() for key in ("repository", "source_ref", "manifest", "role")):
        raise ValueError("LoCoMo no-regression protocol is incomplete")
    beam = dict(datasets.get("beam") or {})
    if not str(beam.get("applicability") or "").strip() or not str(beam.get("reason") or "").strip():
        raise ValueError("BEAM applicability decision is required")
    maximum = int(protocol.get("maximum_complete_paid_configurations", -1))
    target = int(protocol.get("target_complete_paid_configurations", -1))
    if maximum < 0 or target < 0 or target > maximum or paid_configurations > maximum:
        raise ValueError("paid configuration budget is invalid or exceeded")
    if unregistered_retries:
        raise ValueError("unregistered benchmark retries are not allowed")
    if for_paid_run:
        requirements = dict(protocol.get("paid_run_requirements") or {})
        required = (
            "reader_prompt_sha256",
            "judge_prompt_sha256",
            "provider_route",
            "hardware_profile",
            "comparator_config_sha256",
        )
        values = [str(requirements.get(key) or "") for key in required]
        reader_revision = str(dict(protocol.get("models") or {}).get("longmemeval_reader", {}).get("revision") or "")
        if (
            protocol.get("status") != "paid-run-ready"
            or any(not value or "pending" in value for value in values)
            or not reader_revision
            or "must-be-pinned" in reader_revision
        ):
            raise ValueError("paid run protocol still has unpinned model, prompt, route, hardware or comparator settings")
    if external_root is not None:
        requested_root = Path(external_root).expanduser()
        if not requested_root.is_absolute():
            raise ValueError("external benchmark root must be absolute")
        root = requested_root.resolve()
        if repository_root is not None:
            repository = Path(repository_root).resolve()
            if root == repository or repository in root.parents:
                raise ValueError("heavy benchmark root must be outside the repository")
    _reject_secrets(protocol, "retrieval_protocol")
    return protocol


def load_json_compatible_yaml(path: str | Path) -> dict[str, Any]:
    """Load the protocol subset without making PyYAML a base dependency."""
    return read_json(path)


def _identifier_set(value: Any, name: str) -> set[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    identifiers = [str(item).strip() for item in value]
    if any(not item for item in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{name} must contain unique non-empty identifiers")
    return set(identifiers)


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
