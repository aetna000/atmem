from copy import deepcopy
import json
from pathlib import Path

import pytest

from atmem.feedback.baseline import BaselineError
from atmem.feedback.report import diagnostic_report


@pytest.fixture
def manifest():
    return json.loads((Path(__file__).parent/"fixtures/feedback/baseline-manifest.json").read_text())


def test_fast_synthetic_measurements_cannot_accept_or_replace_missing_quality_and_power(manifest):
    report = diagnostic_report(manifest, rule_latencies_ms=(.01,)*20, elapsed_seconds=1)
    assert report["decision"] == "inconclusive" and not report["qualification_issued"]
    assert report["gates"]["pure_rule_p95"]["status"] == "pass"
    for key in ("paired_quality_improvement", "power_and_held_out_provenance", "retrieval_p95_overhead", "false_denial_rate"):
        assert report["gates"][key]["status"] == "insufficient_evidence"
    assert report["resources"]["model_calls"] == 0


def test_observed_latency_and_time_failures_reject_diagnostics(manifest):
    assert diagnostic_report(manifest, rule_latencies_ms=(11,)*20, elapsed_seconds=1)["decision"] == "reject"
    report = diagnostic_report(manifest, rule_latencies_ms=(1,)*20, elapsed_seconds=manifest["budget"]["seconds"]+1)
    assert report["gates"]["diagnostic_time_budget"]["status"] == "fail"


@pytest.mark.parametrize("mutate", [lambda m:m.pop("baselines"), lambda m:m["budget"].update(usd=1),
    lambda m:m["gates"].update(rule_p95_ms_max=100), lambda m:m["corpus"].update(kind="held_out")])
def test_report_rejects_missing_baselines_relaxed_gates_paid_or_inspected_held_out(manifest, mutate):
    changed = deepcopy(manifest)
    mutate(changed)
    with pytest.raises(BaselineError):
        diagnostic_report(changed, rule_latencies_ms=(1,)*20, elapsed_seconds=1)


def test_unbounded_or_nonfinite_measurements_are_not_resource_evidence(manifest):
    for values in ((), (float("nan"),)*20, (True,)*20, (-1,)*20, (1,)*101):
        with pytest.raises(ValueError):
            diagnostic_report(manifest, rule_latencies_ms=values, elapsed_seconds=1)


@pytest.mark.parametrize("mutate", [lambda m:m["tasks"][0].update(id="a"*200),
    lambda m:m["tasks"][0].update(episode="not representable"),
    lambda m:m["tasks"][0]["actions"][0].update(tool="arbitrary/tool"),
    lambda m:m["tasks"][0]["actions"][0].update(checks=["invalid check"])])
def test_freeze_requires_identities_the_actual_ledger_can_represent(manifest, mutate):
    mutate(manifest)
    with pytest.raises(BaselineError):
        diagnostic_report(manifest, rule_latencies_ms=(1,)*20, elapsed_seconds=1)
