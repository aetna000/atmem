from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path

import pytest

from atmem.benchmark.attribution import (
    ACTION_GATE_PAIR_FORMAT,
    EQUIVALENCE_RECEIPT_FORMAT,
    PIPELINE_STAGES,
    REQUIREMENT_MANIFEST_FORMAT,
    REVIEWED_OBSERVATIONS_FORMAT,
    REVIEW_PROTOCOL_FORMAT,
    STAGE_LEDGER_FORMAT,
    assess_dolphin_action_gate_pair,
    build_stage_ledger,
    classify_longmem_outcome,
    validate_dolphin_action_gate_pair,
    validate_equivalence_receipt,
    validate_requirement_manifest,
    validate_review_protocol,
    validate_reviewed_observations,
    validate_stage_ledger,
)
from atmem.benchmark.contracts import canonical_digest


def _signed(value: dict, field: str) -> dict:
    value[field] = canonical_digest(value)
    return value


def test_evaluator_manifest_is_complete_hashed_and_product_inaccessible() -> None:
    manifest = _signed({
        "format": REQUIREMENT_MANIFEST_FORMAT,
        "benchmark": "fixture",
        "visibility": "evaluator_only",
        "available_to_product": False,
        "cases": [{
            "case_id": "c1",
            "requirements": [{
                "requirement_id": "c1:r1",
                "classes": ["exact_fact_value", "entity_relation"],
                "expected": "7412",
                "verified_evidence_text": "The port is 7412.",
                "source_refs": ["fixture.json#s1"],
                "source_verification": "fixture",
            }],
        }],
    }, "manifest_sha256")
    assert validate_requirement_manifest(manifest, expected_case_ids={"c1"})
    leaked = deepcopy(manifest)
    leaked["available_to_product"] = True
    leaked["manifest_sha256"] = canonical_digest({
        key: item for key, item in leaked.items() if key != "manifest_sha256"
    })
    with pytest.raises(ValueError, match="cannot be available"):
        validate_requirement_manifest(leaked, expected_case_ids={"c1"})


def _ledger() -> dict:
    return _signed({
        "format": STAGE_LEDGER_FORMAT,
        "case_id": "c1",
        "terminal_outcome": "answer_succeeded",
        "requirements": [{
            "requirement_id": "c1:r1",
            "stages": [
                {"stage": stage, "state": "passed", "evidence_refs": [f"run#{stage}"], "reason": ""}
                for stage in PIPELINE_STAGES
            ],
        }],
    }, "ledger_sha256")


def test_stage_ledger_requires_every_stage_and_evidence() -> None:
    assert validate_stage_ledger(_ledger(), expected_requirement_ids={"c1:r1"})
    missing = _ledger()
    missing["requirements"][0]["stages"].pop()
    missing["ledger_sha256"] = canonical_digest({
        key: item for key, item in missing.items() if key != "ledger_sha256"
    })
    with pytest.raises(ValueError, match="all pipeline stages"):
        validate_stage_ledger(missing, expected_requirement_ids={"c1:r1"})
    false_success = _ledger()
    false_success["requirements"][0]["stages"][0]["evidence_refs"] = []
    false_success["ledger_sha256"] = canonical_digest({
        key: item for key, item in false_success.items() if key != "ledger_sha256"
    })
    with pytest.raises(ValueError, match="passed without evidence"):
        validate_stage_ledger(false_success, expected_requirement_ids={"c1:r1"})

    complete = {
        stage: {"state": "passed", "evidence_refs": [f"run#{stage}"], "reason": ""}
        for stage in PIPELINE_STAGES
    }
    assert build_stage_ledger(
        case_id="c1", terminal_outcome="answer_succeeded",
        requirement_observations={"c1:r1": complete},
    )["ledger_sha256"].startswith("sha256:")
    incomplete = deepcopy(complete)
    incomplete.pop("expanded")
    with pytest.raises(ValueError, match="stage observations differ"):
        build_stage_ledger(
            case_id="c1", terminal_outcome="provider_system_failure",
            requirement_observations={"c1:r1": incomplete},
        )


@pytest.mark.parametrize(
    ("stages", "complete", "product", "verified", "control", "expected"),
    [
        ({"source_exists": "failed"}, False, {}, {}, {}, "source_dataset_failure"),
        ({"source_exists": "passed", "represented": "failed"}, False, {}, {}, {}, "formation_failure"),
        ({"source_exists": "passed", "represented": "passed", "nominated": "failed"}, False, {}, {}, {}, "retrieval_failure"),
        ({"source_exists": "passed", "represented": "passed", "nominated": "passed", "expanded": "passed", "packed": "failed"}, False, {}, {}, {}, "packing_failure"),
        ({"source_exists": "passed", "represented": "passed", "nominated": "passed", "expanded": "passed", "packed": "passed", "delivered": "passed"}, False, {"correct": False}, {"correct": True}, {"correct": False}, "retrieval_failure"),
        ({"source_exists": "passed", "represented": "passed", "nominated": "passed", "expanded": "passed", "packed": "passed", "delivered": "passed"}, True, {"correct": False}, {"correct": True}, {"correct": False}, "reader_use_noise_failure"),
        ({"source_exists": "passed", "represented": "passed", "nominated": "passed", "expanded": "passed", "packed": "passed", "delivered": "passed"}, True, {"correct": False}, {"correct": False}, {"correct": False}, "reader_capability_prompt_failure"),
        ({}, False, {"error_type": "parse_error"}, {}, {}, "parsing_failure"),
        ({}, False, {"error_type": "timeout"}, {}, {}, "provider_system_failure"),
        ({"source_exists": "passed", "represented": "passed", "nominated": "passed", "expanded": "passed", "packed": "passed", "delivered": "passed"}, True, {"correct": True}, {"correct": True}, {"correct": False}, "answer_succeeded"),
    ],
)
def test_longmem_terminal_outcomes_are_unambiguous(
    stages, complete, product, verified, control, expected
) -> None:
    assert classify_longmem_outcome(
        stages=stages,
        product_complete=complete,
        product_reader=product,
        verified_reader=verified,
        no_memory_reader=control,
    ) == expected


def _gate_pair() -> dict:
    return {
        "format": ACTION_GATE_PAIR_FORMAT,
        "case_id": "alex:001",
        "removed_requirement_id": "alex:001:r1",
        "removal": {
            "outcome": "blocked_missing_requirement",
            "missing_requirement_id": "alex:001:r1",
            "model_invoked": False,
            "tool_calls": 0,
            "actual_reason": "missing_requirement",
            "error_type": None,
        },
        "restored": {
            "gate_open": True,
            "model_invoked": True,
            "tool_calls": 1,
            "expected_tool_call_observed": True,
        },
    }


def test_dolphin_removal_and_positive_control_must_both_work() -> None:
    assert validate_dolphin_action_gate_pair(_gate_pair())
    for reason in ("timeout", "parse_error", "provider_error", "silent_no_call"):
        bad = _gate_pair()
        bad["removal"]["actual_reason"] = reason
        with pytest.raises(ValueError, match="not safety blocks"):
            validate_dolphin_action_gate_pair(bad)
    always_blocking = _gate_pair()
    always_blocking["restored"]["gate_open"] = False
    always_blocking["restored"]["model_invoked"] = False
    with pytest.raises(ValueError, match="positive control"):
        validate_dolphin_action_gate_pair(always_blocking)
    assessment = assess_dolphin_action_gate_pair(always_blocking)
    assert assessment["passed"] is False
    assert "positive control" in assessment["failure_reason"]


def test_dolphin_adapter_gate_names_missing_obligation_before_model() -> None:
    from research.production_benchmarks.dolphinbench import AtMemDolphinAdapter

    adapter = object.__new__(AtMemDolphinAdapter)
    request = SimpleNamespace(persona="alex", interaction_id="001")
    package = SimpleNamespace(sufficiency=SimpleNamespace(
        decision_id="decision-1",
        status="partial",
        required_slots=("target", "rule"),
        covered_slots=("target",),
        missing_slots=("rule",),
    ))
    receipt = adapter._pre_action_gate_receipt(request, package)
    assert receipt == {
        "format": "atmem-dolphin-pre-action-gate-v1",
        "case_id": "alex:001",
        "decision_id": "decision-1",
        "outcome": "blocked_missing_requirement",
        "required_requirement_ids": ["target", "rule"],
        "covered_requirement_ids": ["target"],
        "missing_requirement_ids": ["rule"],
        "actual_reason": "missing_requirement",
        "model_invoked": False,
        "tool_calls": 0,
        "error_type": None,
    }


def test_equivalence_receipt_allows_only_case_ids() -> None:
    full = {"selector": {"case_ids": ["c1", "c2"]}, "pipeline": {"budget": 8}}
    sample = {"selector": {"case_ids": ["c1"]}, "pipeline": {"budget": 8}}
    receipt = _signed({
        "format": EQUIVALENCE_RECEIPT_FORMAT,
        "benchmark": "longmemeval-v2",
        "differences": ["case_ids"],
        "equivalent_after_case_selection": True,
        "selector_path": "selector.case_ids",
        "full_configuration": full,
        "sample_configuration": sample,
        "full_effective_sha256": canonical_digest({"selector": {}, "pipeline": {"budget": 8}}),
        "sample_effective_sha256": canonical_digest({"selector": {}, "pipeline": {"budget": 8}}),
    }, "receipt_sha256")
    assert validate_equivalence_receipt(receipt)
    weaker = deepcopy(receipt)
    weaker["differences"] = ["case_ids", "context_budget"]
    weaker["receipt_sha256"] = canonical_digest({
        key: item for key, item in weaker.items() if key != "receipt_sha256"
    })
    with pytest.raises(ValueError, match="only by case IDs"):
        validate_equivalence_receipt(weaker)


def test_longmem_control_prompts_preserve_question_and_use_all_three_inputs() -> None:
    from research.production_benchmarks.longmem_attribution import (
        build_control_messages,
        execute_controlled_inputs,
        validate_controlled_reader_results,
    )

    product = {
        "prompt_messages": [
            {"role": "system", "content": "frozen system"},
            {"role": "user", "content": [
                {"type": "text", "text": "### Memory context:\nproduct evidence"},
                {"type": "text", "text": "\n\n### Question to answer:\nWhat is the port?"},
                {"type": "image_path", "image_path": "/tmp/question.png"},
            ]},
        ]
    }
    case = {"requirements": [{
        "requirement_id": "c1:r1",
        "verified_evidence_text": "The port is 7412.",
    }]}
    product_messages = build_control_messages(product, case, variant="product_context")
    verified = build_control_messages(product, case, variant="verified_minimal_evidence")
    empty = build_control_messages(product, case, variant="no_memory")
    assert "product evidence" in str(product_messages)
    assert "The port is 7412" in str(verified)
    assert "product evidence" not in str(verified)
    assert "(empty)" in str(empty)
    assert "/tmp/question.png" in str(verified) and "/tmp/question.png" in str(empty)

    identity = "sha256:" + "a" * 64
    prompt = "sha256:" + "b" * 64
    results = {
        "product_context": {"correct": False, "reader_identity_sha256": identity, "reader_prompt_sha256": prompt},
        "verified_minimal_evidence": {"correct": True, "reader_identity_sha256": identity, "reader_prompt_sha256": prompt},
        "no_memory": {"correct": False, "reader_identity_sha256": identity, "reader_prompt_sha256": prompt},
    }
    row = validate_controlled_reader_results(
        case_id="c1",
        stages={
            "source_exists": "passed", "represented": "passed", "nominated": "passed",
            "expanded": "passed", "packed": "passed", "delivered": "passed",
        },
        product_complete=True,
        results=results,
    )
    assert row["terminal_outcome"] == "reader_use_noise_failure"

    calls = []
    controlled = execute_controlled_inputs(
        product_row={
            **product,
            "response_raw": "wrong",
            "response_parsed_boxed": "wrong",
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        },
        requirement_case=case,
        reader_identity_sha256=identity,
        reader_prompt_sha256=prompt,
        call_reader=lambda messages, variant: (
            calls.append(variant)
            or {"response_raw": "7412", "response_parsed_boxed": "7412", "usage": {"prompt_tokens": 2, "completion_tokens": 1}}
        ),
        score_reader=lambda response, _variant: response["response_parsed_boxed"] == "7412",
    )
    assert calls == ["verified_minimal_evidence", "no_memory"]
    assert controlled["product_context"]["correct"] is False
    assert controlled["verified_minimal_evidence"]["correct"] is True

    mismatched = deepcopy(results)
    mismatched["no_memory"]["reader_identity_sha256"] = "sha256:" + "c" * 64
    with pytest.raises(ValueError, match="one pinned reader identity"):
        validate_controlled_reader_results(
            case_id="c1", stages={}, product_complete=False, results=mismatched
        )


def _manifest(*, benchmark: str = "fixture") -> dict:
    case = {
        "case_id": "c1",
        "requirements": [{
            "requirement_id": "c1:r1",
            "classes": ["exact_fact_value"],
            "expected": "7412",
            "verified_evidence_text": "The port is 7412.",
            "source_refs": ["fixture.json#s1"],
            "source_verification": "fixture",
        }],
    }
    if benchmark == "longmemeval-v2":
        case["question_text"] = "What is the port?"
    return _signed({
        "format": REQUIREMENT_MANIFEST_FORMAT,
        "benchmark": benchmark,
        "visibility": "evaluator_only",
        "available_to_product": False,
        "cases": [case],
    }, "manifest_sha256")


def _review_protocol() -> dict:
    return _signed({
        "format": REVIEW_PROTOCOL_FORMAT,
        "visibility": "evaluator_only",
        "available_to_product": False,
        "missing_observation_policy": "reject",
        "system_failure_policy": "terminal_system_failure",
        "stages": [{
            "stage": stage,
            "decision_rule": f"Review {stage} explicitly.",
            "permitted_evidence": [f"{stage} artifact"],
        } for stage in PIPELINE_STAGES],
    }, "review_protocol_sha256")


def _reviewed_observations(
    *, manifest: dict, terminal: str = "answer_succeeded"
) -> dict:
    del terminal
    protocol = _review_protocol()
    return _signed({
        "format": REVIEWED_OBSERVATIONS_FORMAT,
        "benchmark": manifest["benchmark"],
        "visibility": "evaluator_only",
        "available_to_product": False,
        "manifest_sha256": manifest["manifest_sha256"],
        "review_protocol_sha256": protocol["review_protocol_sha256"],
        "reviewer_identity": "fixture-reviewer-v1",
        "review_status": "complete",
        "cases": [{
            "case_id": "c1",
            "terminal_outcome": "answer_succeeded",
            "requirements": {"c1:r1": {
                stage: {
                    "state": "passed",
                    "evidence_refs": [f"evidence.json#{stage}"],
                    "reason": "",
                }
                for stage in PIPELINE_STAGES
            }},
        }],
    }, "observations_sha256")


def test_longmem_ledger_builder_requires_explicit_reviewed_stages(tmp_path: Path) -> None:
    from benchmarks.retrieval_quality.build_longmem_attribution_ledgers import build_ledgers

    progress = {"cases": [
        {"question_id": "c1", "method": "typed-local", "score_bool": True},
        {"question_id": "c1", "method": "verified-evidence", "score_bool": True},
        {"question_id": "c1", "method": "no-retrieval", "score_bool": False},
    ]}
    manifest = _manifest(benchmark="longmemeval-v2")
    observations = _reviewed_observations(manifest=manifest)
    ledgers = build_ledgers(
        manifest=manifest, progress=progress, observations=observations,
        review_protocol=_review_protocol(), output_root=tmp_path,
    )
    assert len(ledgers) == 1
    assert ledgers[0]["terminal_outcome"] == "answer_succeeded"
    assert (tmp_path / "c1.json").is_file()

    incomplete = deepcopy(observations)
    incomplete["cases"][0]["requirements"]["c1:r1"].pop("packed")
    incomplete["observations_sha256"] = canonical_digest({
        key: item for key, item in incomplete.items() if key != "observations_sha256"
    })
    with pytest.raises(ValueError, match="stages are incomplete"):
        build_ledgers(
            manifest=manifest, progress=progress, observations=incomplete,
            review_protocol=_review_protocol(), output_root=tmp_path / "bad",
        )


def test_dolphin_ledger_builder_retains_failed_control_pair(tmp_path: Path) -> None:
    from benchmarks.retrieval_quality.build_dolphin_attribution_ledgers import build_ledgers

    failed_pair = _gate_pair()
    failed_pair["case_id"] = "c1"
    failed_pair["removed_requirement_id"] = "c1:r1"
    failed_pair["removal"]["missing_requirement_id"] = "c1:r1"
    failed_pair["removal"]["actual_reason"] = "timeout"
    manifest = _manifest()
    ledgers = build_ledgers(
        manifest=manifest, observations=_reviewed_observations(manifest=manifest),
        review_protocol=_review_protocol(), pair_report={"pairs": [failed_pair]},
        output_root=tmp_path,
    )
    assert len(ledgers) == 1
    assert ledgers[0]["action_gate_control"]["passed"] is False
    assert "not safety blocks" in ledgers[0]["action_gate_control"]["failure_reason"]


def test_attribution_table_renderer_rejects_partial_case_sets() -> None:
    from benchmarks.retrieval_quality.render_attribution_tables import (
        render_dolphin,
        render_longmem,
    )

    manifest = _manifest()
    with pytest.raises(ValueError, match="exactly one ledger"):
        render_longmem(manifest, [])
    with pytest.raises(ValueError, match="exactly one removal/positive pair"):
        render_dolphin(manifest, [])


def test_reviewed_observations_are_bound_to_manifest_and_protocol() -> None:
    manifest = _manifest()
    protocol = _review_protocol()
    observations = _reviewed_observations(manifest=manifest)
    assert validate_review_protocol(protocol)
    assert validate_reviewed_observations(
        observations, manifest=manifest, review_protocol=protocol
    )
    unbound = deepcopy(observations)
    unbound["manifest_sha256"] = "sha256:" + "0" * 64
    unbound["observations_sha256"] = canonical_digest({
        key: item for key, item in unbound.items() if key != "observations_sha256"
    })
    with pytest.raises(ValueError, match="not bound to the requirement manifest"):
        validate_reviewed_observations(
            unbound, manifest=manifest, review_protocol=protocol
        )


def test_review_packet_cannot_finalize_with_unreviewed_defaults() -> None:
    from benchmarks.retrieval_quality.review_attribution_observations import (
        finalize_packet,
        initialize_packet,
    )

    manifest = _manifest()
    protocol = _review_protocol()
    packet = initialize_packet(
        manifest=manifest, review_protocol=protocol,
        reviewer_identity="fixture-reviewer-v1",
    )
    assert packet["review_status"] == "unreviewed"
    assert packet["cases"][0]["requirements"]["c1:r1"]["source_exists"][
        "state"
    ] == "unreviewed"
    with pytest.raises(ValueError, match="known terminal outcome|unknown stage state"):
        finalize_packet(
            packet=packet, manifest=manifest, review_protocol=protocol
        )
