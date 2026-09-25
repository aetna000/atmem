import json
import os
from pathlib import Path

import pytest

from benchmarks.agent_continuity.observation import assess, fixtures, run


def test_lost_spans_stay_in_denominator():
    report = assess(fixtures(), {"rows": [], "responses": []})
    assert report["expected_unique_spans"] == 3
    assert report["coverage"] == 0
    assert len(report["missing_span_ids"]) == 3
    assert report["cost_accuracy"] is None


def test_conflicting_fixture_is_not_silently_deduplicated():
    plan = json.loads(json.dumps(fixtures()))
    plan["requests"][1]["payload"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] = "changed"
    with pytest.raises(ValueError, match="conflicting"):
        assess(plan, {"rows": [], "responses": []})


def test_actual_atflows_http_probe(tmp_path):
    root = os.environ.get("CONTINUITY_ATFLOWS_ROOT")
    if not root:
        pytest.skip("set CONTINUITY_ATFLOWS_ROOT to current baseline checkout")
    output = tmp_path / "observations"
    report = run(Path(root), output)
    score = report["assessment"]
    assert score["expected_unique_spans"] == 3
    assert score["retained_expected_spans"] == 2
    assert score["coverage"] == pytest.approx(2 / 3)
    assert score["rejected_spans"] == 1
    assert score["missing_usage_stored_as_zero"] == 2
    assert score["missing_cost_stored_as_zero"] == 2
    assert score["attribute_mismatches"] == []
    assert score["unexpected_span_ids"] == []
    assert not report["production_claims_allowed"]
    assert report["observation"]["guarded_egress_attempts_detected"] == 0
    with pytest.raises(FileExistsError):
        run(Path(root), output)
