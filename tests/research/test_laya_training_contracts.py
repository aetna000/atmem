from __future__ import annotations

import math
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from research.laya_formation.training.contracts import (
    CROSS_BACKEND_TOLERANCE,
    FORMAT_MANIFEST,
    SAME_BACKEND_TOLERANCE,
    assert_finite,
    calibration_power,
    canonical_digest,
    class_distribution,
    collapse_report,
    secret_findings,
    truncation_report,
    validate_manifest,
)


def manifest() -> dict:
    return {
        "format": FORMAT_MANIFEST,
        "run_id": "run-1",
        "created_at": "2026-10-11T00:00:00Z",
        "code_revision": "0123456789abcdef",
        "base_model": {"repo_id": "convaiinnovations/laya", "revision": "a"},
        "laya": {"repo_id": "NandhaKishorM/laya", "revision": "b"},
        "dataset": {"repo_id": "atmem/data", "revision": "c"},
        "questions_digest": "0" * 64,
        "environment": {},
        "objective": "soft-ce",
        "hyperparameters": {},
        "seeds": {},
        "split_digests": {},
        "hardware": {},
        "checkpoints": [],
        "metrics": None,
        "calibration": None,
        "export_inventory": [],
        "parent_run": None,
        "reproducibility_tolerances": {
            "same_backend": dict(SAME_BACKEND_TOLERANCE),
            "cross_backend": dict(CROSS_BACKEND_TOLERANCE),
        },
    }


def test_training_schemas_are_valid_draft_2020_12() -> None:
    schema_dir = Path("research/laya_formation/training/schemas")
    schemas = sorted(schema_dir.glob("*.schema.json"))
    assert [path.name for path in schemas] == [
        "calibration-bundle-v1.schema.json",
        "metric-report-v1.schema.json",
        "training-run-manifest-v1.schema.json",
    ]
    for path in schemas:
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_manifest_identity_is_deterministic_and_tolerances_are_frozen() -> None:
    value = manifest()
    validate_manifest(value)
    assert canonical_digest(value) == canonical_digest(dict(reversed(list(value.items()))))
    value["reproducibility_tolerances"]["same_backend"]["minimum_choice_agreement"] = 0.9
    with pytest.raises(ValueError, match="frozen FR-019"):
        validate_manifest(value)


def test_nonfinite_loss_is_rejected() -> None:
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="nonfinite"):
            assert_finite([0.5, bad], label="loss")


def test_truncation_is_explicit_and_bound_to_examples() -> None:
    report = truncation_report([
        {"example_id": "a", "truncated": False},
        {"example_id": "b", "truncated": True},
    ])
    assert report == {"items": 2, "truncated_items": 1, "truncated_example_ids": ["b"], "truncation_rate": 0.5}


def test_collapse_and_class_prior_drift_are_measured() -> None:
    report = collapse_report(["keep", "drop", "keep", "drop"], ["keep"] * 4)
    assert class_distribution(["keep", "drop", "keep", "drop"]) == {"drop": 0.5, "keep": 0.5}
    assert report["collapsed"] is True
    assert report["missing_expected_classes"] == ["drop"]
    assert report["class_prior_l1"] == 1.0


def test_calibration_underpower_is_question_specific() -> None:
    report = calibration_power({"operation": 100, "memory_class": 99})
    assert report["sufficient"] is False
    assert report["underpowered_questions"] == ["memory_class"]


@pytest.mark.parametrize("secret", [
    "hf_abcdefghijklmnopqrstuvwxyz123456",
    "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "password=not-for-artifacts",
])
def test_secret_scan_blocks_training_artifacts(secret: str) -> None:
    assert secret_findings({"field": secret})
    value = manifest()
    value["environment"] = {"bad": secret}
    with pytest.raises(ValueError, match="secret-like"):
        validate_manifest(value)
