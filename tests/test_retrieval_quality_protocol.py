from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from atmem.benchmark.contracts import (
    load_json_compatible_yaml,
    validate_dolphin_split,
    validate_longmem_pilot,
    validate_provider_route_probe,
    validate_question_split,
    validate_retrieval_quality_protocol,
)


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml"
SPLIT = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-question-split-v1.json"
PILOT = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-pilot-v1.json"
DOLPHIN_SPLIT = ROOT / "benchmarks/retrieval_quality/protocols/dolphinbench-task-split-v1.json"
ROUTE_PROBE = ROOT / "benchmarks/retrieval_quality/protocols/provider-route-probe-v1.json"


def documents():
    return load_json_compatible_yaml(PROTOCOL), json.loads(SPLIT.read_text(encoding="utf-8"))


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


def test_frozen_three_percent_pilots_validate_and_are_development_only() -> None:
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
        "b7c7222534bac83f957c4cfca7c5b68362999694f3d66730733bd6910b27dc07"
    )
    assert validate_provider_route_probe(route_probe)["routes"]["judge"]["model"] == (
        "gpt-5.2-2025-12-11"
    )


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
    route_probe = json.loads(ROUTE_PROBE.read_text(encoding="utf-8"))
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
