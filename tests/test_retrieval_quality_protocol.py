from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from atmem.benchmark.contracts import (
    canonical_digest,
    load_json_compatible_yaml,
    validate_dolphin_split,
    validate_dolphin_development_profile,
    validate_longmem_development_profile,
    validate_longmem_pilot,
    validate_provider_route_probe,
    validate_question_split,
    validate_retrieval_quality_protocol,
)
from atmem.benchmark.attribution import (
    validate_attribution_artifacts,
    validate_equivalence_receipt,
    validate_requirement_manifest,
)
from atmem.benchmark.finalization import (
    FORMAT as FINALIZATION_FORMAT,
    finalization_identity,
    probe_artifact_identity,
    validate_finalization_gate,
)


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml"
SPLIT = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-question-split-v1.json"
PILOT = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-pilot-v1.json"
DOLPHIN_SPLIT = ROOT / "benchmarks/retrieval_quality/protocols/dolphinbench-task-split-v1.json"
LONGMEM_FIVE_PERCENT = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-development-5pct-v1.json"
DOLPHIN_FIVE_PERCENT = ROOT / "benchmarks/retrieval_quality/protocols/dolphinbench-development-5pct-v1.json"
ROUTE_PROBE = ROOT / "benchmarks/retrieval_quality/protocols/provider-route-probe-v1.json"
LONGMEM_REQUIREMENTS = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-requirements-5pct-v1.json"
DOLPHIN_REQUIREMENTS = ROOT / "benchmarks/retrieval_quality/protocols/dolphinbench-requirements-5pct-v1.json"
LONGMEM_EQUIVALENCE = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-equivalence-5pct-v1.json"
DOLPHIN_EQUIVALENCE = ROOT / "benchmarks/retrieval_quality/protocols/dolphinbench-equivalence-5pct-v1.json"


def documents():
    return load_json_compatible_yaml(PROTOCOL), json.loads(SPLIT.read_text(encoding="utf-8"))


def synthetic_current_route_probe() -> dict:
    """Content-free unit fixture; never used as paid-run evidence."""
    probe = {
        "format": "atmem-provider-route-probe-v1",
        "routes": {
            "reader": {
                "outcome": "succeeded", "status": 200,
                "model": "Qwen/Qwen3.5-9B", "provider_route": "runpod-vllm",
                "content_retained": False,
            },
            "embedding": {
                "outcome": "succeeded", "status": 200,
                "model": "atmem/hash-bow-768-v1",
                "provider_route": "local-deterministic",
                "transport": "openai-compatible-v1-embeddings",
                "content_retained": False,
            },
            "judge": {
                "outcome": "succeeded", "status": 200,
                "model": "gpt-5.2-2025-12-11",
                "provider_route": "openai-direct", "content_retained": False,
            },
        },
    }
    probe["probe_sha256"] = canonical_digest(probe).removeprefix("sha256:")
    return probe


def test_frozen_protocol_and_split_validate() -> None:
    protocol, split = documents()
    validated = validate_retrieval_quality_protocol(
        protocol,
        split=split,
        repository_root=ROOT,
        external_root=ROOT.parent / "benchmark artifacts",
        paid_configurations=8,
    )
    assert validated["status"] == "development-pilot-ready"
    assert len(split["development_ids"]) + len(split["confirmation_ids"]) == 451
    assert {"07ab3723", "ff311d07"} <= set(split["development_ids"])
    assert validated["evaluation_design"]["confirmation_question_ids"] == 317
    assert validated["datasets"]["locomo"]["role"] == "matched-legacy-candidate-no-regression"
    assert validated["datasets"]["beam"]["accuracy_gate"] is False


def test_split_rejects_overlap_bad_digest_and_incomplete_coverage() -> None:
    _, split = documents()
    overlap = deepcopy(split)
    overlap["confirmation_ids"].append(overlap["development_ids"][0])
    with pytest.raises(ValueError, match="overlap"):
        validate_question_split(overlap)

    bad_digest = deepcopy(split)
    bad_digest["split_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest"):
        validate_question_split(bad_digest)

    expected = set(split["development_ids"]) | set(split["confirmation_ids"]) | {"missing-id"}
    with pytest.raises(ValueError, match="coverage"):
        validate_question_split(split, expected_question_ids=expected)


@pytest.mark.parametrize("missing", ["source_commit", "dataset_revision", "split_file"])
def test_protocol_rejects_missing_longmemeval_pins(missing: str) -> None:
    protocol, split = documents()
    broken = deepcopy(protocol)
    broken["datasets"]["longmemeval_v2"][missing] = None
    with pytest.raises(ValueError, match=missing):
        validate_retrieval_quality_protocol(broken, split=split)


def test_protocol_rejects_incomplete_or_invalid_dataset_content_pins() -> None:
    protocol, split = documents()
    incomplete = deepcopy(protocol)
    incomplete["datasets"]["longmemeval_v2"]["content_sha256"].pop(
        "trajectories.jsonl"
    )
    with pytest.raises(ValueError, match="content_sha256 pins are incomplete"):
        validate_retrieval_quality_protocol(incomplete, split=split)

    invalid = deepcopy(protocol)
    invalid["datasets"]["longmemeval_v2"]["content_sha256"][
        "questions.jsonl"
    ] = "not-a-digest"
    with pytest.raises(ValueError, match="content_sha256 pins are invalid"):
        validate_retrieval_quality_protocol(invalid, split=split)


def test_protocol_rejects_leakage_retry_budget_and_repository_storage() -> None:
    protocol, split = documents()
    leaking = deepcopy(protocol)
    leaking["leakage_controls"]["answers_available_to_product"] = True
    with pytest.raises(ValueError, match="leakage"):
        validate_retrieval_quality_protocol(leaking, split=split)

    with pytest.raises(ValueError, match="retries"):
        validate_retrieval_quality_protocol(protocol, split=split, unregistered_retries=1)
    with pytest.raises(ValueError, match="budget"):
        validate_retrieval_quality_protocol(protocol, split=split, paid_configurations=21)
    with pytest.raises(ValueError, match="outside"):
        validate_retrieval_quality_protocol(
            protocol,
            split=split,
            repository_root=ROOT,
            external_root=ROOT / "runs",
        )
    with pytest.raises(ValueError, match="absolute"):
        validate_retrieval_quality_protocol(protocol, split=split, external_root="relative/runs")


def test_protocol_uses_unknown_not_zero_for_unavailable_measurements() -> None:
    schema = json.loads(
        (ROOT / "atmem/schemas/v1/retrieval-stage-event.json").read_text(encoding="utf-8")
    )
    assert "null" in schema["properties"]["duration_ms"]["type"]
    assert "null" in schema["properties"]["usage"]["properties"]["cost_usd"]["type"]


def test_protocol_rejects_split_count_drift_and_visual_case_dropping() -> None:
    protocol, split = documents()
    bad_count = deepcopy(protocol)
    bad_count["evaluation_design"]["confirmation_question_ids"] = 316
    with pytest.raises(ValueError, match="counts"):
        validate_retrieval_quality_protocol(bad_count, split=split)

    dropped_visuals = deepcopy(protocol)
    dropped_visuals["visual_input_policy"]["drop_media_only_cases"] = True
    with pytest.raises(ValueError, match="media-only"):
        validate_retrieval_quality_protocol(dropped_visuals, split=split)

    no_locomo = deepcopy(protocol)
    no_locomo["datasets"].pop("locomo")
    with pytest.raises(ValueError, match="LoCoMo"):
        validate_retrieval_quality_protocol(no_locomo, split=split)


def test_protocol_refuses_paid_run_until_all_provider_settings_are_pinned() -> None:
    protocol, split = documents()
    with pytest.raises(ValueError, match="paid run protocol"):
        validate_retrieval_quality_protocol(protocol, split=split, for_paid_run=True)


def test_historical_three_percent_manifests_remain_valid_with_current_route() -> None:
    protocol, split = documents()
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    dolphin = json.loads(DOLPHIN_SPLIT.read_text(encoding="utf-8"))
    route_probe = json.loads(ROUTE_PROBE.read_text(encoding="utf-8"))

    assert validate_longmem_pilot(pilot, split=split)["question_count"] == 14
    assert len(validate_dolphin_split(dolphin)["development_ids"]) == 18
    validated = validate_retrieval_quality_protocol(
        protocol,
        split=split,
        pilot=pilot,
        dolphin_split=dolphin,
        route_probe=route_probe,
        for_pilot_run=True,
    )
    assert validated["paid_run_requirements"]["provider_route_probe_sha256"] == (
        route_probe["probe_sha256"]
    )


def test_frozen_five_percent_profiles_are_nested_answer_blind_and_development_only() -> None:
    _, split = documents()
    historical_longmem = json.loads(PILOT.read_text(encoding="utf-8"))
    historical_dolphin = json.loads(DOLPHIN_SPLIT.read_text(encoding="utf-8"))
    longmem = validate_longmem_development_profile(
        json.loads(LONGMEM_FIVE_PERCENT.read_text(encoding="utf-8")), split=split,
    )
    dolphin = validate_dolphin_development_profile(
        json.loads(DOLPHIN_FIVE_PERCENT.read_text(encoding="utf-8")),
    )

    assert longmem["question_count"] == 23
    assert set(historical_longmem["question_ids"]) <= set(longmem["question_ids"])
    assert not set(longmem["question_ids"]) & set(split["confirmation_ids"])
    assert len(dolphin["development_ids"]) == 30
    assert set(historical_dolphin["development_ids"]) <= set(dolphin["development_ids"])
    assert all(row["development"] == 10 for row in dolphin["personas"].values())


def test_five_percent_requirement_manifests_cover_all_53_cases_and_are_evaluator_only() -> None:
    long_profile = json.loads(LONGMEM_FIVE_PERCENT.read_text(encoding="utf-8"))
    dolphin_profile = json.loads(DOLPHIN_FIVE_PERCENT.read_text(encoding="utf-8"))
    longmem = validate_requirement_manifest(
        json.loads(LONGMEM_REQUIREMENTS.read_text(encoding="utf-8")),
        expected_case_ids=long_profile["question_ids"],
    )
    dolphin = validate_requirement_manifest(
        json.loads(DOLPHIN_REQUIREMENTS.read_text(encoding="utf-8")),
        expected_case_ids=dolphin_profile["development_ids"],
    )
    assert len(longmem["cases"]) == 23
    assert len(dolphin["cases"]) == 30
    assert all(case["requirements"] for case in longmem["cases"] + dolphin["cases"])
    runtime_roots = [ROOT / "atmem/context_engine", ROOT / "atmem/retrieve", ROOT / "atmem/memory.py"]
    for runtime_root in runtime_roots:
        paths = [runtime_root] if runtime_root.is_file() else runtime_root.rglob("*.py")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            assert "requirements-5pct-v1" not in text
            assert "verified_evidence_text" not in text


def test_five_percent_equivalence_receipts_prove_case_count_is_the_only_reduction() -> None:
    longmem = validate_equivalence_receipt(
        json.loads(LONGMEM_EQUIVALENCE.read_text(encoding="utf-8"))
    )
    dolphin = validate_equivalence_receipt(
        json.loads(DOLPHIN_EQUIVALENCE.read_text(encoding="utf-8"))
    )
    assert len(longmem["full_configuration"]["selector"]["case_ids"]) == 451
    assert len(longmem["sample_configuration"]["selector"]["case_ids"]) == 23
    assert len(dolphin["full_configuration"]["selector"]["case_ids"]) == 600
    assert len(dolphin["sample_configuration"]["selector"]["case_ids"]) == 30

    protocol = load_json_compatible_yaml(PROTOCOL)
    artifacts = validate_attribution_artifacts(
        protocol,
        protocols_root=PROTOCOL.parent,
        longmem_case_ids=json.loads(LONGMEM_FIVE_PERCENT.read_text())["question_ids"],
        dolphin_case_ids=json.loads(DOLPHIN_FIVE_PERCENT.read_text())["development_ids"],
    )
    assert set(artifacts) == {
        "longmemeval_v2", "dolphinbench", "review_protocol"
    }
    assert artifacts["review_protocol"]["missing_observation_policy"] == "reject"


def test_pilot_validators_reject_confirmation_leakage_and_persona_loss() -> None:
    _, split = documents()
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    leaking = deepcopy(pilot)
    leaking["question_ids"][0] = split["confirmation_ids"][0]
    with pytest.raises(ValueError, match="development question IDs"):
        validate_longmem_pilot(leaking, split=split)

    dolphin = json.loads(DOLPHIN_SPLIT.read_text(encoding="utf-8"))
    dolphin["personas"].pop("riley")
    with pytest.raises(ValueError, match="three official personas"):
        validate_dolphin_split(dolphin)

    protocol, split = documents()
    dolphin = json.loads(DOLPHIN_SPLIT.read_text(encoding="utf-8"))
    protocol["datasets"]["dolphinbench"]["development_split_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="split digests"):
        validate_retrieval_quality_protocol(
            protocol, split=split, dolphin_split=dolphin
        )


def test_pilot_protocol_rejects_under_reserved_provider_cost() -> None:
    protocol, split = documents()
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    dolphin = json.loads(DOLPHIN_SPLIT.read_text(encoding="utf-8"))
    route_probe = synthetic_current_route_probe()
    protocol["paid_run_requirements"]["provider_route_probe_sha256"] = route_probe[
        "probe_sha256"
    ]
    protocol["paid_run_requirements"]["pilot_method_reservations_usd"][
        "typed-local"
    ]["openai"] = 0.01

    with pytest.raises(ValueError, match="cost cap"):
        validate_retrieval_quality_protocol(
            protocol,
            split=split,
            pilot=pilot,
            dolphin_split=dolphin,
            route_probe=route_probe,
            for_pilot_run=True,
        )


def _finalization_gate() -> dict:
    identity = {
        "gate_type": "longmemeval",
        "candidate_commit": "a" * 40,
        "candidate_artifact_sha256": "sha256:" + "9" * 64,
        "checkpoint_sha256": "sha256:" + "b" * 64,
        "provider": "runpod",
        "model": "Qwen/Qwen3.5-9B",
        "model_revision": "c" * 40,
        "processor_sha256": "sha256:" + "d" * 64,
        "prompt_sha256": "sha256:" + "e" * 64,
        "proxy_sha256": "sha256:" + "f" * 64,
        "concurrency": 2,
        "input_budget": 8192,
        "output_budget": 1024,
        "sampling": {"temperature": 0, "top_p": 1},
        "judge_provider": "openai", "judge_model": "gpt-5.2",
        "judge_revision": "2026-09-01",
        "judge_prompt_sha256": "sha256:" + "1" * 64,
        "probe_set_sha256": "sha256:" + "0" * 64,
        "run_config_sha256": "sha256:" + "4" * 64,
        "cost_authorization_id": "pilot-1",
        "runner_sha256": "sha256:" + "5" * 64,
        "agent_driver_target": "fixture:run",
        "agent_driver_sha256": "sha256:" + "7" * 64,
        "grader_runtime": {
            "provider": "openai", "model": "gpt-5.2", "maximum_retries": 0,
        },
    }
    probes = []
    for condition in (
        "short_control", "oracle_evidence", "product_context",
        "worst_budget_multimodal",
    ):
        for _ in range(3):
            probes.append({
                "probe_id": f"reader-{condition}-{len(probes)}",
                "role": "reader", "condition": condition, "status": "completed",
                "finish_reason": "stop", "content_sha256": "sha256:" + "2" * 64,
                "content_bytes": 12, "answer_parse_ok": True,
                "artifact_sha256": "sha256:" + "5" * 64,
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                "cleanup_failed": False, "error": None, "retries": 0,
                "latency_ms": 20, "cost_usd": 0.001,
            })
    probes.extend({
        "probe_id": f"judge-{index}",
        "role": "judge", "condition": "official_judge", "status": "completed",
        "finish_reason": "stop", "content_sha256": "sha256:" + "3" * 64,
        "content_bytes": 1, "answer_parse_ok": True,
        "artifact_sha256": "sha256:" + "6" * 64,
        "usage": {"prompt_tokens": 10, "completion_tokens": 1},
        "cleanup_failed": False, "error": None, "retries": 0,
        "latency_ms": 10, "cost_usd": 0.001,
    } for index in range(3))
    identity["probe_set_sha256"] = canonical_digest([
        {"probe_id": probe["probe_id"], "role": probe["role"], "condition": probe["condition"]}
        for probe in probes
    ])
    for probe in probes:
        probe["artifact_sha256"] = probe_artifact_identity(probe, identity)
    now = datetime.now(timezone.utc)
    return {
        "format": FINALIZATION_FORMAT,
        "gate_type": "longmemeval",
        "identity": identity,
        "identity_sha256": finalization_identity(identity),
        "status": "passed",
        "bypassed": False,
        "created_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "probes": probes,
        "cost_authorization": {
            "authorization_id": "pilot-1", "cap_usd": 10.0,
            "reserved_usd": 2.0, "spent_usd": 1.0,
        },
    }


def test_finalization_gate_rejects_reasoning_only_and_stale_evidence() -> None:
    gate = _finalization_gate()
    assert validate_finalization_gate(
        gate, expected_identity=gate["identity"]
    )["status"] == "passed"
    reasoning_only = deepcopy(gate)
    reasoning_only["probes"][0]["content_bytes"] = 0
    with pytest.raises(ValueError, match="no final answer"):
        validate_finalization_gate(
            reasoning_only, expected_identity=reasoning_only["identity"]
        )
    stale = deepcopy(gate["identity"])
    stale["candidate_commit"] = "9" * 40
    with pytest.raises(ValueError, match="another configuration"):
        validate_finalization_gate(gate, expected_identity=stale)


def test_finalization_gate_binds_optional_diagnostic_profile() -> None:
    gate = _finalization_gate()
    diagnostic = deepcopy(gate)
    diagnostic["identity"]["diagnostic_profile_sha256"] = "sha256:" + "a" * 64
    diagnostic["identity_sha256"] = finalization_identity(diagnostic["identity"])
    for probe in diagnostic["probes"]:
        probe["artifact_sha256"] = probe_artifact_identity(
            probe, diagnostic["identity"]
        )

    validate_finalization_gate(
        diagnostic,
        expected_identity=diagnostic["identity"],
    )
    mismatched = deepcopy(diagnostic["identity"])
    mismatched["diagnostic_profile_sha256"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="another configuration"):
        validate_finalization_gate(diagnostic, expected_identity=mismatched)


def test_finalization_gate_binds_optional_reader_runtime() -> None:
    gate = _finalization_gate()
    runtime_bound = deepcopy(gate)
    runtime_bound["identity"]["reader_runtime_sha256"] = "sha256:" + "a" * 64
    runtime_bound["identity_sha256"] = finalization_identity(
        runtime_bound["identity"]
    )
    for probe in runtime_bound["probes"]:
        probe["artifact_sha256"] = probe_artifact_identity(
            probe, runtime_bound["identity"]
        )

    validate_finalization_gate(
        runtime_bound,
        expected_identity=runtime_bound["identity"],
    )
    mismatched = deepcopy(runtime_bound["identity"])
    mismatched["reader_runtime_sha256"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="another configuration"):
        validate_finalization_gate(runtime_bound, expected_identity=mismatched)


def test_finalization_gate_rejects_sampling_relabel_retry_nan_and_wrong_probe_set() -> None:
    gate = _finalization_gate()
    changed = deepcopy(gate["identity"])
    changed["sampling"] = {"temperature": 0.5, "top_p": 1}
    with pytest.raises(ValueError, match="another configuration"):
        validate_finalization_gate(gate, expected_identity=changed)

    relabeled = deepcopy(gate)
    relabeled["gate_type"] = "dolphinbench"
    with pytest.raises(ValueError, match="gate_type"):
        validate_finalization_gate(relabeled, expected_identity=gate["identity"])

    retried = deepcopy(gate)
    retried["probes"][0]["retries"] = 1
    with pytest.raises(ValueError, match="used retries"):
        validate_finalization_gate(retried, expected_identity=retried["identity"])

    non_finite = deepcopy(gate)
    non_finite["cost_authorization"]["spent_usd"] = float("nan")
    with pytest.raises(ValueError, match="cost authorization"):
        validate_finalization_gate(non_finite, expected_identity=non_finite["identity"])

    wrong_condition = deepcopy(gate)
    wrong_condition["probes"][0]["condition"] = "near_limit"
    wrong_condition["probes"][0]["artifact_sha256"] = probe_artifact_identity(
        wrong_condition["probes"][0], wrong_condition["identity"]
    )
    with pytest.raises(ValueError, match="frozen twelve"):
        validate_finalization_gate(
            wrong_condition, expected_identity=wrong_condition["identity"]
        )


def test_finalization_gate_binds_artifacts_attempts_cost_and_runner_type() -> None:
    gate = _finalization_gate()
    with pytest.raises(ValueError, match="runner"):
        validate_finalization_gate(
            gate, expected_identity=gate["identity"],
            expected_gate_type="dolphinbench",
        )
    missing_attempt = deepcopy(gate)
    missing_attempt["probes"][0].pop("retries")
    with pytest.raises(ValueError, match="attempt evidence"):
        validate_finalization_gate(
            missing_attempt, expected_identity=missing_attempt["identity"]
        )
    missing_artifact = deepcopy(gate)
    missing_artifact["probes"][0].pop("artifact_sha256")
    with pytest.raises(ValueError, match="artifact binding"):
        validate_finalization_gate(
            missing_artifact, expected_identity=missing_artifact["identity"]
        )
    over_cap = deepcopy(gate)
    over_cap["probes"][0]["cost_usd"] = 2.0
    over_cap["probes"][0]["artifact_sha256"] = probe_artifact_identity(
        over_cap["probes"][0], over_cap["identity"]
    )
    with pytest.raises(ValueError, match="probe costs"):
        validate_finalization_gate(over_cap, expected_identity=over_cap["identity"])


def test_finalization_probe_artifacts_cannot_move_between_configurations() -> None:
    gate = _finalization_gate()
    transplanted = deepcopy(gate)
    transplanted["identity"]["model_revision"] = "different-checkpoint"
    transplanted["identity_sha256"] = finalization_identity(transplanted["identity"])
    with pytest.raises(ValueError, match="artifact binding"):
        validate_finalization_gate(
            transplanted, expected_identity=transplanted["identity"]
        )
