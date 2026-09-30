from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.reference_parity import BaselineResult, compare_candidate


def _result(system: str, passed: int) -> BaselineResult:
    return BaselineResult(
        benchmark="longmemeval-v2",
        system=system,
        sample_id="pilot-v1",
        sample_size=20,
        passed=passed,
        primary_score=passed / 20,
        source_revision="abc",
        configuration_sha256="sha256:def",
        model="reader-v1",
    )


def test_comparison_reports_relative_and_absolute_improvement() -> None:
    result = compare_candidate(_result("atmem", 12), _result("reference", 10))
    assert result["parity"] is True
    assert result["target_met"] is True
    assert result["absolute_point_delta"] == pytest.approx(10.0)
    assert result["relative_delta"] == pytest.approx(0.2)


def test_comparison_rejects_different_samples() -> None:
    reference = _result("reference", 10)
    candidate = BaselineResult(
        benchmark="longmemeval-v2", system="atmem", sample_id="other",
        sample_size=20, passed=12, primary_score=0.6, source_revision="abc",
        configuration_sha256="sha256:def", model="reader-v1",
    )
    with pytest.raises(ValueError, match="same benchmark and frozen sample"):
        compare_candidate(candidate, reference)


def test_pinned_reference_manifest_and_baseline_are_loadable() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = json.loads(
        (root / "research/reference_parity/sources.json").read_text()
    )
    baseline = json.loads(
        (root / "benchmarks/retrieval_quality/baselines/reference-parity-v1.json").read_text()
    )
    assert sources["systems"]["agentrunbook"]["commit"] == (
        "2cc8c540bdb87fe6761629b585e727e1c4704520"
    )
    assert baseline["longmemeval_v2"]["sample_size"] == 14
    assert baseline["dolphinbench"]["sample_size"] == 18
