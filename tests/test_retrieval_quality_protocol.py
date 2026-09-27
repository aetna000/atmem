from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from atmem.benchmark.contracts import (
    load_json_compatible_yaml,
    validate_question_split,
    validate_retrieval_quality_protocol,
)


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "benchmarks/retrieval_quality/protocols/2.3.8.yaml"
SPLIT = ROOT / "benchmarks/retrieval_quality/protocols/longmemeval-v2-question-split-v1.json"


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
    assert validated["status"] == "question-split-frozen-model-pins-pending"
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
