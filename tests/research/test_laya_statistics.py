from __future__ import annotations

import pytest

from benchmarks.laya_formation.statistics import paired_cluster_interval


def test_cluster_bootstrap_is_deterministic_and_paired() -> None:
    candidate = {"a": 1.0, "b": 1.0, "c": 1.0}
    comparator = {"a": 0.0, "b": 0.0, "c": 1.0}
    clusters = {"a": "one", "b": "one", "c": "two"}
    first = paired_cluster_interval(candidate, comparator, clusters, repetitions=1000)
    second = paired_cluster_interval(candidate, comparator, clusters, repetitions=1000)
    assert first == second
    assert first["difference"] == pytest.approx(2 / 3)
    assert first["clusters"] == 2


def test_cluster_bootstrap_rejects_unmatched_rows() -> None:
    with pytest.raises(ValueError, match="same non-empty"):
        paired_cluster_interval({"a": 1.0}, {"b": 0.0}, {"a": "one", "b": "two"})
