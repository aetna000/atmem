"""Fail-closed contracts for evaluator-only benchmark attribution.

This module validates evaluation evidence.  Product formation and retrieval
must never import evaluator manifests or use their gold requirements.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import canonical_digest


REQUIREMENT_MANIFEST_FORMAT = "atmem-evaluator-requirements-v1"
STAGE_LEDGER_FORMAT = "atmem-requirement-stage-ledger-v1"
EQUIVALENCE_RECEIPT_FORMAT = "atmem-five-percent-equivalence-v1"
ACTION_GATE_PAIR_FORMAT = "atmem-dolphin-action-gate-pair-v1"
REVIEW_PROTOCOL_FORMAT = "atmem-attribution-review-protocol-v1"
REVIEWED_OBSERVATIONS_FORMAT = "atmem-reviewed-requirement-observations-v1"

REQUIREMENT_CLASSES = frozenset({
    "exact_fact_value",
    "entity_relation",
    "time_current_state",
    "state_transition",
    "procedure_step_order",
    "applicability_condition",
    "comparison_side",
    "polarity_negative_premise",
    "conflict_correction",
    "action_target",
    "required_action",
    "prohibited_action",
})
PIPELINE_STAGES = (
    "source_exists",
    "represented",
    "nominated",
    "expanded",
    "packed",
    "delivered",
    "used_by_reader",
    "reflected_in_answer_or_action",
)
STAGE_STATES = frozenset({"passed", "failed", "not_reached", "not_applicable"})
TERMINAL_OUTCOMES = frozenset({
    "source_dataset_failure",
    "formation_failure",
    "retrieval_failure",
    "packing_failure",
    "reader_use_noise_failure",
    "reader_capability_prompt_failure",
    "parsing_failure",
    "provider_system_failure",
    "action_attempted",
    "action_succeeded",
    "action_failed",
    "answer_succeeded",
    "blocked_missing_requirement",
})
SYSTEM_FAILURES = frozenset({
    "timeout", "truncated", "malformed_output", "parse_error", "provider_error",
})


def _digest_without(value: Mapping[str, Any], field: str) -> str:
    return canonical_digest({key: item for key, item in value.items() if key != field})


def validate_requirement_manifest(
    value: Mapping[str, Any], *, expected_case_ids: Iterable[str]
) -> dict[str, Any]:
    manifest = dict(value)
    if manifest.get("format") != REQUIREMENT_MANIFEST_FORMAT:
        raise ValueError("unsupported evaluator requirement manifest format")
    if manifest.get("visibility") != "evaluator_only":
        raise ValueError("requirement manifest must be evaluator-only")
    if manifest.get("available_to_product") is not False:
        raise ValueError("requirement manifest cannot be available to the product")
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("requirement manifest cases must be a list")
    expected = {str(item) for item in expected_case_ids}
    actual = {str(row.get("case_id") or "") for row in cases if isinstance(row, dict)}
    if actual != expected or len(cases) != len(expected):
        raise ValueError("requirement manifest case coverage differs from the frozen sample")
    requirement_ids: set[str] = set()
    evaluator_questions: set[str] = set()
    for case in cases:
        case_id = str(case.get("case_id") or "")
        if manifest.get("benchmark") == "longmemeval-v2":
            question_text = str(case.get("question_text") or "").strip()
            if not question_text or question_text in evaluator_questions:
                raise ValueError("LongMem evaluator questions must be non-empty and unique")
            evaluator_questions.add(question_text)
        requirements = case.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError(f"case {case_id} requires evaluator requirements")
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise ValueError(f"case {case_id} has a malformed requirement")
            requirement_id = str(requirement.get("requirement_id") or "")
            if not requirement_id or requirement_id in requirement_ids:
                raise ValueError("requirement IDs must be non-empty and globally unique")
            requirement_ids.add(requirement_id)
            classes = requirement.get("classes")
            if not isinstance(classes, list) or not classes or not set(classes) <= REQUIREMENT_CLASSES:
                raise ValueError(f"requirement {requirement_id} has invalid classes")
            source_refs = requirement.get("source_refs")
            if not isinstance(source_refs, list) or not source_refs:
                raise ValueError(f"requirement {requirement_id} requires source references")
            if not all(str(item).strip() for item in source_refs):
                raise ValueError(f"requirement {requirement_id} has an empty source reference")
            for field in ("expected", "verified_evidence_text", "source_verification"):
                if not str(requirement.get(field) or "").strip():
                    raise ValueError(f"requirement {requirement_id} requires {field}")
            if requirement.get("removal_applicable") is True:
                slots = requirement.get("expected_obligation_slots")
                if not isinstance(slots, list) or not slots or not all(
                    isinstance(item, str) and item.strip() for item in slots
                ):
                    raise ValueError(
                        f"removal requirement {requirement_id} requires obligation slots"
                    )
    if manifest.get("manifest_sha256") != _digest_without(manifest, "manifest_sha256"):
        raise ValueError("requirement manifest digest does not match")
    return manifest


def validate_stage_ledger(
    value: Mapping[str, Any], *, expected_requirement_ids: Iterable[str]
) -> dict[str, Any]:
    ledger = dict(value)
    if ledger.get("format") != STAGE_LEDGER_FORMAT:
        raise ValueError("unsupported requirement stage ledger format")
    terminal = str(ledger.get("terminal_outcome") or "")
    if terminal not in TERMINAL_OUTCOMES:
        raise ValueError("ledger requires exactly one known terminal outcome")
    rows = ledger.get("requirements")
    if not isinstance(rows, list):
        raise ValueError("ledger requirements must be a list")
    expected = {str(item) for item in expected_requirement_ids}
    actual = {str(row.get("requirement_id") or "") for row in rows if isinstance(row, dict)}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("ledger does not cover every expected requirement exactly once")
    for row in rows:
        requirement_id = str(row["requirement_id"])
        observations = row.get("stages")
        if not isinstance(observations, list) or len(observations) != len(PIPELINE_STAGES):
            raise ValueError(f"requirement {requirement_id} must record all pipeline stages")
        names = tuple(str(item.get("stage") or "") for item in observations)
        if names != PIPELINE_STAGES:
            raise ValueError(f"requirement {requirement_id} stages are missing or out of order")
        reached_terminal = False
        for observation in observations:
            state = str(observation.get("state") or "")
            reason = str(observation.get("reason") or "").strip()
            evidence = observation.get("evidence_refs")
            if state not in STAGE_STATES:
                raise ValueError(f"requirement {requirement_id} has an unknown stage state")
            if not isinstance(evidence, list):
                raise ValueError(f"requirement {requirement_id} stage evidence must be a list")
            if state == "passed" and not evidence:
                raise ValueError(f"requirement {requirement_id} passed without evidence")
            if state != "passed" and not reason:
                raise ValueError(f"requirement {requirement_id} non-pass stage needs a reason")
            if reached_terminal and state not in {"not_reached", "not_applicable"}:
                raise ValueError(f"requirement {requirement_id} resumes after a failed stage")
            reached_terminal = reached_terminal or state == "failed"
    if ledger.get("ledger_sha256") != _digest_without(ledger, "ledger_sha256"):
        raise ValueError("requirement ledger digest does not match")
    return ledger


def build_stage_ledger(
    *, case_id: str, terminal_outcome: str,
    requirement_observations: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Build a complete ledger without silently filling missing observations."""
    if terminal_outcome not in TERMINAL_OUTCOMES:
        raise ValueError("cannot build a ledger with an unknown terminal outcome")
    rows = []
    for requirement_id in sorted(requirement_observations):
        supplied = requirement_observations[requirement_id]
        if set(supplied) != set(PIPELINE_STAGES):
            missing = sorted(set(PIPELINE_STAGES) - set(supplied))
            extra = sorted(set(supplied) - set(PIPELINE_STAGES))
            raise ValueError(
                f"requirement {requirement_id} stage observations differ; "
                f"missing={missing} extra={extra}"
            )
        rows.append({
            "requirement_id": requirement_id,
            "stages": [
                {"stage": stage, **dict(supplied[stage])}
                for stage in PIPELINE_STAGES
            ],
        })
    ledger = {
        "format": STAGE_LEDGER_FORMAT,
        "case_id": case_id,
        "terminal_outcome": terminal_outcome,
        "requirements": rows,
    }
    ledger["ledger_sha256"] = canonical_digest(ledger)
    return validate_stage_ledger(
        ledger, expected_requirement_ids=requirement_observations
    )


def validate_review_protocol(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the evaluator procedure used to adjudicate stage evidence."""
    protocol = dict(value)
    if protocol.get("format") != REVIEW_PROTOCOL_FORMAT:
        raise ValueError("unsupported attribution review protocol format")
    if protocol.get("visibility") != "evaluator_only":
        raise ValueError("attribution review protocol must be evaluator-only")
    if protocol.get("available_to_product") is not False:
        raise ValueError("attribution review protocol cannot be available to product")
    stages = protocol.get("stages")
    if not isinstance(stages, list) or tuple(
        str(row.get("stage") or "") for row in stages if isinstance(row, dict)
    ) != PIPELINE_STAGES:
        raise ValueError("review protocol must define every pipeline stage in order")
    for row in stages:
        if not str(row.get("decision_rule") or "").strip():
            raise ValueError("every reviewed stage requires a decision rule")
        refs = row.get("permitted_evidence")
        if not isinstance(refs, list) or not refs or not all(str(item).strip() for item in refs):
            raise ValueError("every reviewed stage requires permitted evidence")
    if protocol.get("missing_observation_policy") != "reject":
        raise ValueError("review protocol must reject missing observations")
    if protocol.get("system_failure_policy") != "terminal_system_failure":
        raise ValueError("review protocol must isolate system failures")
    if protocol.get("review_protocol_sha256") != _digest_without(
        protocol, "review_protocol_sha256"
    ):
        raise ValueError("attribution review protocol digest does not match")
    return protocol


def validate_reviewed_observations(
    value: Mapping[str, Any], *, manifest: Mapping[str, Any],
    review_protocol: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate explicit evaluator decisions without filling absent stages."""
    observations = dict(value)
    protocol = validate_review_protocol(review_protocol)
    if observations.get("format") != REVIEWED_OBSERVATIONS_FORMAT:
        raise ValueError("unsupported reviewed-observations format")
    if observations.get("visibility") != "evaluator_only":
        raise ValueError("reviewed observations must be evaluator-only")
    if observations.get("available_to_product") is not False:
        raise ValueError("reviewed observations cannot be available to product")
    if observations.get("review_status") != "complete":
        raise ValueError("reviewed observations are not complete")
    if observations.get("benchmark") != manifest.get("benchmark"):
        raise ValueError("reviewed observations name the wrong benchmark")
    if observations.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise ValueError("reviewed observations are not bound to the requirement manifest")
    if observations.get("review_protocol_sha256") != protocol.get(
        "review_protocol_sha256"
    ):
        raise ValueError("reviewed observations are not bound to the review protocol")
    if not str(observations.get("reviewer_identity") or "").strip():
        raise ValueError("reviewed observations require an attributable reviewer identity")
    manifest_cases = {
        str(row["case_id"]): row for row in manifest.get("cases") or ()
    }
    observed_rows = observations.get("cases")
    if not isinstance(observed_rows, list):
        raise ValueError("reviewed observation cases must be a list")
    observed_cases = {
        str(row.get("case_id") or ""): row
        for row in observed_rows if isinstance(row, dict)
    }
    if set(observed_cases) != set(manifest_cases) or len(observed_rows) != len(manifest_cases):
        raise ValueError("reviewed observations must cover every manifest case exactly once")
    for case_id, manifest_case in manifest_cases.items():
        terminal = str(observed_cases[case_id].get("terminal_outcome") or "")
        if terminal not in TERMINAL_OUTCOMES:
            raise ValueError(f"reviewed case lacks a known terminal outcome: {case_id}")
        requirements = observed_cases[case_id].get("requirements")
        if not isinstance(requirements, dict):
            raise ValueError(f"reviewed requirements are missing: {case_id}")
        expected_ids = {str(row["requirement_id"]) for row in manifest_case["requirements"]}
        if set(requirements) != expected_ids:
            raise ValueError(f"reviewed requirement coverage differs: {case_id}")
        for requirement_id, supplied in requirements.items():
            if not isinstance(supplied, dict) or set(supplied) != set(PIPELINE_STAGES):
                raise ValueError(f"reviewed stages are incomplete: {requirement_id}")
            # Reuse the canonical ledger validator so pass evidence, failure
            # reasons, ordering and fail-closed continuation rules cannot drift.
            build_stage_ledger(
                case_id=case_id,
                terminal_outcome="answer_succeeded",
                requirement_observations={requirement_id: supplied},
            )
    if observations.get("observations_sha256") != _digest_without(
        observations, "observations_sha256"
    ):
        raise ValueError("reviewed observations digest does not match")
    return observations


def classify_longmem_outcome(
    *,
    stages: Mapping[str, str],
    product_complete: bool,
    product_reader: Mapping[str, Any],
    verified_reader: Mapping[str, Any],
    no_memory_reader: Mapping[str, Any],
) -> str:
    """Apply the frozen LongMem failure decision table."""
    for result in (product_reader, verified_reader, no_memory_reader):
        error = str(result.get("error_type") or "")
        if error in SYSTEM_FAILURES:
            return "parsing_failure" if error in {"parse_error", "malformed_output"} else "provider_system_failure"
    if stages.get("source_exists") != "passed":
        return "source_dataset_failure"
    if stages.get("represented") != "passed":
        return "formation_failure"
    if stages.get("nominated") != "passed" or stages.get("expanded") == "failed":
        return "retrieval_failure"
    if stages.get("packed") != "passed" or stages.get("delivered") != "passed":
        return "packing_failure"
    product_correct = product_reader.get("correct") is True
    verified_correct = verified_reader.get("correct") is True
    if product_correct:
        return "answer_succeeded"
    if not product_complete and verified_correct:
        return "retrieval_failure"
    if product_complete and verified_correct:
        return "reader_use_noise_failure"
    if not verified_correct:
        return "reader_capability_prompt_failure"
    raise ValueError("LongMem outcome is not classifiable from the supplied evidence")


def validate_equivalence_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    receipt = dict(value)
    if receipt.get("format") != EQUIVALENCE_RECEIPT_FORMAT:
        raise ValueError("unsupported five-percent equivalence receipt format")
    differences = receipt.get("differences")
    if differences != ["case_ids"]:
        raise ValueError("five-percent execution may differ only by case IDs")
    if receipt.get("equivalent_after_case_selection") is not True:
        raise ValueError("five-percent configuration is not full-run equivalent")
    full = receipt.get("full_configuration")
    sample = receipt.get("sample_configuration")
    selector_path = str(receipt.get("selector_path") or "")
    if not isinstance(full, dict) or not isinstance(sample, dict) or not selector_path:
        raise ValueError("equivalence receipt requires both configurations and selector path")
    normalized_full = deepcopy(full)
    normalized_sample = deepcopy(sample)
    full_selector = _pop_path(normalized_full, selector_path)
    sample_selector = _pop_path(normalized_sample, selector_path)
    if not isinstance(full_selector, list) or not isinstance(sample_selector, list):
        raise ValueError("equivalence selector must identify case-ID lists")
    if not set(sample_selector) <= set(full_selector) or not sample_selector:
        raise ValueError("five-percent case IDs must be a non-empty subset of the full run")
    computed_full = canonical_digest(normalized_full)
    computed_sample = canonical_digest(normalized_sample)
    if receipt.get("full_effective_sha256") != computed_full:
        raise ValueError("full effective configuration digest does not match")
    if receipt.get("sample_effective_sha256") != computed_sample:
        raise ValueError("sample effective configuration digest does not match")
    if computed_full != computed_sample:
        raise ValueError("effective configurations differ beyond case selection")
    if receipt.get("receipt_sha256") != _digest_without(receipt, "receipt_sha256"):
        raise ValueError("equivalence receipt digest does not match")
    return receipt


def _pop_path(value: dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    current: dict[str, Any] = value
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            raise ValueError(f"equivalence selector path is missing: {path}")
        current = child
    if parts[-1] not in current:
        raise ValueError(f"equivalence selector path is missing: {path}")
    return current.pop(parts[-1])


def validate_dolphin_action_gate_pair(value: Mapping[str, Any]) -> dict[str, Any]:
    pair = dict(value)
    if pair.get("format") != ACTION_GATE_PAIR_FORMAT:
        raise ValueError("unsupported Dolphin action gate pair format")
    requirement_id = str(pair.get("removed_requirement_id") or "")
    if not requirement_id:
        raise ValueError("removal control must name the removed requirement")
    removal = dict(pair.get("removal") or {})
    restored = dict(pair.get("restored") or {})
    if removal.get("outcome") != "blocked_missing_requirement":
        raise ValueError("removal did not produce blocked_missing_requirement")
    if removal.get("missing_requirement_id") != requirement_id:
        raise ValueError("removal receipt did not name the removed requirement")
    if removal.get("model_invoked") is not False or int(removal.get("tool_calls", -1)) != 0:
        raise ValueError("removal was not blocked before model and tool execution")
    if str(removal.get("actual_reason") or "") != "missing_requirement":
        raise ValueError("timeout, parse, provider, abstention and silent no-call are not safety blocks")
    if removal.get("error_type") not in {None, ""}:
        raise ValueError("a removal error cannot count as a safety block")
    if restored.get("gate_open") is not True or restored.get("model_invoked") is not True:
        raise ValueError("positive control did not open the gate and invoke the model")
    if int(restored.get("tool_calls", 0)) < 1:
        raise ValueError("positive control did not reach an expected tool call")
    if restored.get("expected_tool_call_observed") is not True:
        raise ValueError("positive control did not observe the expected tool call")
    return pair


def assess_dolphin_action_gate_pair(value: Mapping[str, Any]) -> dict[str, Any]:
    """Retain a structurally valid failed pair without crediting it as passed."""
    pair = dict(value)
    if pair.get("format") != ACTION_GATE_PAIR_FORMAT:
        raise ValueError("unsupported Dolphin action gate pair format")
    if not str(pair.get("case_id") or "") or not str(
        pair.get("removed_requirement_id") or ""
    ):
        raise ValueError("Dolphin action gate pair lacks case/requirement identity")
    if not isinstance(pair.get("removal"), dict) or not isinstance(pair.get("restored"), dict):
        raise ValueError("Dolphin action gate pair requires both control records")
    try:
        validate_dolphin_action_gate_pair(pair)
    except ValueError as exc:
        return {"passed": False, "failure_reason": str(exc)}
    return {"passed": True, "failure_reason": None}


def validate_attribution_artifacts(
    protocol: Mapping[str, Any], *, protocols_root: str | Path,
    longmem_case_ids: Iterable[str], dolphin_case_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """Load and content-bind every evaluator-only pre-paid-run artifact."""
    root = Path(protocols_root).resolve()
    attribution = dict(protocol.get("attribution_requirements") or {})
    if (
        attribution.get("visibility") != "evaluator_only"
        or attribution.get("available_to_product") is not False
        or attribution.get("require_all_pipeline_stages") is not True
        or attribution.get("unknown_is_success") is not False
        or attribution.get("retain_all_failures_in_denominator") is not True
    ):
        raise ValueError("benchmark attribution policy is incomplete or unsafe")
    equivalence = dict(protocol.get("equivalence_receipts") or {})
    review_pin = dict(attribution.get("review_protocol") or {})
    review_path = _bound_artifact(root, review_pin)
    review_protocol = validate_review_protocol(
        json.loads(review_path.read_text(encoding="utf-8"))
    )
    result: dict[str, dict[str, Any]] = {
        "review_protocol": review_protocol,
    }
    for benchmark, expected_ids in (
        ("longmemeval_v2", longmem_case_ids),
        ("dolphinbench", dolphin_case_ids),
    ):
        manifest_pin = dict(attribution.get(benchmark) or {})
        receipt_pin = dict(equivalence.get(benchmark) or {})
        manifest_path = _bound_artifact(root, manifest_pin)
        receipt_path = _bound_artifact(root, receipt_pin)
        manifest = validate_requirement_manifest(
            json.loads(manifest_path.read_text(encoding="utf-8")),
            expected_case_ids=expected_ids,
        )
        receipt = validate_equivalence_receipt(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )
        result[benchmark] = {"manifest": manifest, "equivalence": receipt}
    return result


def _bound_artifact(root: Path, pin: Mapping[str, Any]) -> Path:
    name = str(pin.get("file") or "")
    digest = str(pin.get("file_sha256") or "")
    path = (root / name).resolve()
    if root != path.parent or not path.is_file():
        raise ValueError("benchmark attribution artifact is missing or escapes its root")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != actual:
        raise ValueError(f"benchmark attribution artifact digest differs: {name}")
    return path


def requirement_class_breakdown(
    cases: Iterable[Mapping[str, Any]], manifests: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    for case in cases:
        case_id = str(case.get("case_id") or "")
        requirement = manifests.get(case_id)
        if requirement is None:
            raise ValueError(f"missing diagnostic requirement annotation for {case_id}")
        classes = set(requirement.get("classes") or ())
        if not classes or not classes <= REQUIREMENT_CLASSES:
            raise ValueError(f"invalid diagnostic requirement classes for {case_id}")
        for name in classes:
            totals[name] += 1
            if case.get("complete_evidence") is not True:
                failures[name] += 1
    return [
        {"requirement_class": name, "total": totals[name], "failed": failures[name]}
        for name in sorted(totals)
    ]
