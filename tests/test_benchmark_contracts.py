from __future__ import annotations

from importlib import resources
import json

import pytest

from atmem.benchmark.contracts import (
    canonical_digest,
    load_dataset,
    metric,
    validate_report,
)
from atmem.benchmark.runner import data_path


def test_checked_in_dataset_is_versioned_unique_and_packaged() -> None:
    dataset = load_dataset(data_path("deterministic-v1.json"))
    assert dataset["format"] == "atmem-benchmark-cases-v1"
    assert len(dataset["cases"]) == 24
    assert len({row["id"] for row in dataset["cases"]}) == 24
    assert dataset["dataset_sha256"].startswith("sha256:")
    packaged = resources.files("atmem.benchmark").joinpath("data", "thresholds-v1.json")
    assert packaged.is_file()


def test_dataset_rejects_duplicate_ids(tmp_path) -> None:
    value = json.loads(data_path("deterministic-v1.json").read_text())
    value["cases"][1]["id"] = value["cases"][0]["id"]
    target = tmp_path / "duplicate.json"
    target.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(target)


def test_unavailable_metric_requires_reason() -> None:
    with pytest.raises(ValueError, match="requires a reason"):
        metric(None, unit="tokens")
    assert metric(None, unit="tokens", reason="not exposed")["value"] is None


def test_report_rejects_secret_material() -> None:
    report = {
        "format": "atmem-benchmark-report-v1",
        "dataset": {}, "profile": {"api_key": "secret-value"},
        "metrics": {}, "thresholds": {}, "case_results": [], "limitations": [],
    }
    with pytest.raises(ValueError, match="secret material"):
        validate_report(report)


def test_canonical_digest_is_key_order_independent() -> None:
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})
