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
LONGMEM_PILOT_FORMAT = "atmem-longmemeval-v2-pilot-v1"
DOLPHIN_SPLIT_FORMAT = "atmem-dolphinbench-task-split-v1"
PROVIDER_ROUTE_PROBE_FORMAT = "atmem-provider-route-probe-v1"
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


def validate_longmem_pilot(
    value: Mapping[str, Any], *, split: Mapping[str, Any]
) -> dict[str, Any]:
    pilot = dict(value)
    if pilot.get("format") != LONGMEM_PILOT_FORMAT:
        raise ValueError(f"pilot format must be {LONGMEM_PILOT_FORMAT}")
    validated_split = validate_question_split(split)
    identifiers = _identifier_set(pilot.get("question_ids"), "pilot question_ids")
    if identifiers - set(validated_split["development_ids"]):
        raise ValueError("pilot may contain development question IDs only")
    if int(pilot.get("question_count", -1)) != len(identifiers):
        raise ValueError("pilot question count does not match its IDs")
    if pilot.get("confirmation_overlap") != 0:
        raise ValueError("pilot must not overlap confirmation")
    if pilot.get("question_split_sha256") != validated_split.get("split_sha256"):
        raise ValueError("pilot names a different frozen question split")
    stable = {key: item for key, item in pilot.items() if key != "pilot_sha256"}
    expected = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()
    if pilot.get("pilot_sha256") != expected:
        raise ValueError("pilot digest does not match its canonical content")
    _reject_secrets(pilot, "longmem_pilot")
    return pilot


def validate_dolphin_split(value: Mapping[str, Any]) -> dict[str, Any]:
    split = dict(value)
    if split.get("format") != DOLPHIN_SPLIT_FORMAT:
        raise ValueError(f"DolphinBench split format must be {DOLPHIN_SPLIT_FORMAT}")
    development = _identifier_set(split.get("development_ids"), "development_ids")
    confirmation = _identifier_set(split.get("confirmation_ids"), "confirmation_ids")
    if development & confirmation:
        raise ValueError("DolphinBench development and confirmation tasks overlap")
    personas = dict(split.get("personas") or {})
    if set(personas) != {"alex", "morgan", "riley"}:
        raise ValueError("DolphinBench split must contain all three official personas")
    combined = development | confirmation
    for persona, counts in personas.items():
        prefix = f"{persona}:"
        dev_count = sum(item.startswith(prefix) for item in development)
        confirmation_count = sum(item.startswith(prefix) for item in confirmation)
        if (
            int(counts.get("development", -1)) != dev_count
            or int(counts.get("confirmation", -1)) != confirmation_count
            or int(counts.get("total", -1)) != dev_count + confirmation_count
        ):
            raise ValueError(f"DolphinBench counts differ for {persona}")
    if len(combined) != 600 or any(counts.get("development") != 6 for counts in personas.values()):
        raise ValueError("DolphinBench split must freeze 6 development tasks per persona and all 600 tasks")
    stable = {key: item for key, item in split.items() if key != "split_sha256"}
    expected = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()
    if split.get("split_sha256") != expected:
        raise ValueError("DolphinBench split digest does not match its canonical content")
    _reject_secrets(split, "dolphin_split")
    return split


def validate_provider_route_probe(value: Mapping[str, Any]) -> dict[str, Any]:
    probe = dict(value)
    if probe.get("format") != PROVIDER_ROUTE_PROBE_FORMAT:
        raise ValueError(f"provider probe format must be {PROVIDER_ROUTE_PROBE_FORMAT}")
    stable = {key: item for key, item in probe.items() if key != "probe_sha256"}
    expected = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()
    if probe.get("probe_sha256") != expected:
        raise ValueError("provider route probe digest does not match its canonical content")
    routes = dict(probe.get("routes") or {})
    expected_routes = {
        "reader": ("Qwen/Qwen3.5-9B", "deepinfra"),
        "embedding": ("Qwen/Qwen3-Embedding-8B", "scaleway"),
        "judge": ("gpt-5.2-2025-12-11", "openai-direct"),
    }
    if set(routes) != set(expected_routes):
        raise ValueError("provider route probe must contain reader, embedding and judge")
    for name, (model, provider_route) in expected_routes.items():
        row = dict(routes[name] or {})
        if (
            row.get("outcome") != "succeeded"
            or row.get("status") != 200
            or row.get("model") != model
            or row.get("provider_route") != provider_route
            or row.get("content_retained") is not False
            or (
                name == "embedding"
                and row.get("transport") != "openai-compatible-v1-embeddings"
            )
        ):
            raise ValueError(f"provider route probe is not valid for {name}")
    _reject_secrets(probe, "provider_route_probe")
    return probe


def validate_retrieval_quality_protocol(
    value: Mapping[str, Any],
    *,
    split: Mapping[str, Any],
    repository_root: str | Path | None = None,
    external_root: str | Path | None = None,
    paid_configurations: int = 0,
    unregistered_retries: int = 0,
    for_paid_run: bool = False,
    for_pilot_run: bool = False,
    pilot: Mapping[str, Any] | None = None,
    dolphin_split: Mapping[str, Any] | None = None,
    route_probe: Mapping[str, Any] | None = None,
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
    dolphin = dict(datasets.get("dolphinbench") or {})
    for key in ("repository", "source_commit", "development_split_file", "grader_provider", "grader_model"):
        if not str(dolphin.get(key) or "").strip():
            raise ValueError(f"DolphinBench protocol is missing {key}")
    if dolphin_split is not None:
        validated_dolphin = validate_dolphin_split(dolphin_split)
        if validated_dolphin["source_commit"] != dolphin["source_commit"]:
            raise ValueError("DolphinBench protocol and split commits differ")
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
    if for_pilot_run:
        if pilot is None or dolphin_split is None or route_probe is None:
            raise ValueError(
                "pilot run requires both frozen pilot manifests and provider evidence"
            )
        validate_longmem_pilot(pilot, split=validated_split)
        validate_dolphin_split(dolphin_split)
        requirements = dict(protocol.get("paid_run_requirements") or {})
        required = (
            "official_harness_sha256", "reader_prompt_sha256",
            "judge_prompt_sha256", "provider_route",
            "provider_route_probe_sha256", "hardware_profile",
            "comparator_config_sha256", "official_code_combined_sha256",
            "embedding_proxy_sha256",
        )
        values = [str(requirements.get(key) or "") for key in required]
        verified_probe = validate_provider_route_probe(route_probe)
        if verified_probe["probe_sha256"] != requirements.get(
            "provider_route_probe_sha256"
        ):
            raise ValueError("provider evidence differs from the frozen protocol")
        code_files = dict(requirements.get("official_code_files") or {})
        combined = hashlib.sha256(canonical_json(code_files).encode("utf-8")).hexdigest()
        if combined != requirements.get("official_code_combined_sha256"):
            raise ValueError("official code file pins do not match their combined digest")
        if requirements.get("reader_prompt_sha256") == requirements.get(
            "official_harness_sha256"
        ):
            raise ValueError("reader prompt and harness pins must identify separate artifacts")
        models = dict(protocol.get("models") or {})
        model_revisions = [
            str(dict(models.get(name) or {}).get("revision") or "")
            for name in ("longmemeval_reader", "official_rag_controller", "official_rag_embedding")
        ]
        expected_models = {
            "longmemeval_reader": (
                "Qwen/Qwen3.5-9B:deepinfra", "deepinfra",
                "https://router.huggingface.co/v1",
            ),
            "official_rag_controller": (
                "Qwen/Qwen3.5-9B:deepinfra", "deepinfra",
                "https://router.huggingface.co/v1",
            ),
            "official_rag_embedding": (
                "Qwen/Qwen3-Embedding-8B:scaleway", "scaleway",
                "https://router.huggingface.co/v1",
            ),
        }
        for name, (model, route, base_url) in expected_models.items():
            row = dict(models.get(name) or {})
            if row.get("model") != model or row.get("provider_route") != route:
                raise ValueError(f"pilot model route is not pinned for {name}")
            if base_url is not None and row.get("base_url") != base_url:
                raise ValueError(f"pilot base URL is not pinned for {name}")
        judge = dict(models.get("longmemeval_judge") or {})
        if (
            judge.get("revision") != "gpt-5.2-2025-12-11"
            or judge.get("model") != judge.get("revision")
        ):
            raise ValueError("pilot judge must use the probed dated model snapshot")
        caps = [
            requirements.get("pilot_hf_cost_cap_usd"),
            requirements.get("pilot_openai_cost_cap_usd"),
            requirements.get("pilot_total_cost_cap_usd"),
        ]
        case_reservations = [
            requirements.get("pilot_hf_case_reservation_usd"),
            requirements.get("pilot_openai_case_reservation_usd"),
        ]
        if (
            protocol.get("status") != "development-pilot-ready"
            or any(not value or "pending" in value for value in values + model_revisions)
            or any(not isinstance(cap, (int, float)) or cap <= 0 for cap in caps)
            or any(
                not isinstance(value, (int, float)) or value <= 0
                for value in case_reservations
            )
            or float(case_reservations[0]) > float(caps[0])
            or float(case_reservations[1]) > float(caps[1])
            or abs(float(caps[0]) + float(caps[1]) - float(caps[2])) > 1e-9
        ):
            raise ValueError("pilot run protocol still has an unverified route, pin or cost cap")
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
