from dataclasses import replace
import ast
import inspect
import json
import math

import pytest

from research.memory_fabric import protocol
from research.memory_fabric.protocol import Observation, Provenance, Request, arrival_schedule, percentile, summarize


def completed(request_id="r1", **overrides):
    fields = dict(request_id=request_id, outcome="completed", reason="finished",
                  admitted_s=1, started_s=2, terminal_s=3, completed_bytes=100,
                  authorized_at_release=True, evidence_complete=True,
                  output_parity_verified=True)
    fields.update(overrides)
    return Observation(**fields)


def test_schedule_is_open_loop_seeded_and_does_not_change_global_random():
    import random
    state = random.getstate()
    assert arrival_schedule(4, 2) == (0, .5, 1, 1.5)
    first = arrival_schedule(100, 2, seed=9, distribution="poisson")
    assert first == arrival_schedule(100, 2, seed=9, distribution="poisson")
    assert first != arrival_schedule(100, 2, seed=10, distribution="poisson")
    assert list(first) == sorted(first)
    assert random.getstate() == state
    assert arrival_schedule(0, 1) == ()


@pytest.mark.parametrize("kwargs", [
    {"count": -1}, {"count": True}, {"rate_per_s": 0}, {"rate_per_s": math.nan},
    {"rate_per_s": math.inf}, {"rate_per_s": True}, {"seed": -1}, {"distribution": "bogus"},
])
def test_schedule_rejects_invalid_values(kwargs):
    params = {"count": 3, "rate_per_s": 1, **kwargs}
    with pytest.raises(ValueError):
        arrival_schedule(**params)


def test_complete_accounting_and_non_survivor_bound():
    requests = [Request(f"r{i}", 0, "bulk" if i == 6 else "fast", 4) for i in range(1, 7)]
    observations = [
        completed(),
        Observation("r2", "refused", "overload", terminal_s=1),
        Observation("r3", "expired", "deadline", terminal_s=4),
        Observation("r4", "cancelled", "revoked", terminal_s=2),
        Observation("r5", "error", "worker_error", terminal_s=2),
        Observation("r6", "censored", "observation_ended"),
    ]
    report = summarize(requests, observations, horizon_s=5)
    total = report["all"]
    assert total["outcome_counts"] == dict.fromkeys(protocol.OUTCOMES, 1)
    assert total["offered"] == 6
    assert total["authorized_ontime_goodput_per_s"] == .2
    assert total["completed_bytes_per_s"] == 20
    assert total["completed_latency"]["p99_s"] == 3
    assert total["admitted_completed_latency"]["p99_s"] == 2
    assert total["generator_lag"]["p99_s"] == 1
    assert total["queue_wait"]["p99_s"] == 1
    assert total["interactive_deadline_success_lower_bound"] == .2
    assert total["all_offered_verified_completion_bound"]["p99"] == {"status": "unattainable", "seconds": None}
    assert report["observations"][-1]["censored_deadline_missed"] is True
    assert report["lanes"]["bulk"]["outcome_counts"]["expired"] == 0
    assert report["comparative_performance_valid"] is False
    assert report["measurement_kind"] == "synthetic_protocol_observations"
    json.dumps(report, allow_nan=False)


def test_unknown_verification_is_unavailable_not_true_and_is_lane_local():
    report = summarize([Request("r1", 0), Request("r2", 0, "bulk")],
                       [completed(), completed("r2", evidence_complete=None)], horizon_s=5)
    assert report["all"]["authorized_ontime_goodput_per_s"] is None
    assert report["all"]["unknown_verification_count"] == 1
    assert report["all"]["known_goodput_lower_bound_per_s"] == .2
    assert report["lanes"]["fast"]["authorized_ontime_goodput_per_s"] == .2
    assert report["lanes"]["bulk"]["authorized_ontime_goodput_per_s"] is None
    assert report["all"]["all_offered_verified_completion_bound"]["p99"]["status"] == "unknown_verification"


@pytest.mark.parametrize("field", ["authorized_at_release", "evidence_complete", "output_parity_verified"])
def test_failed_verification_is_recorded_but_not_counted_as_goodput(field):
    total = summarize([Request("r1", 0)], [completed(**{field: False})], horizon_s=5)["all"]
    assert total["completed_per_s"] == .2
    assert total["authorized_ontime_goodput_per_s"] == 0
    assert total["failed_verification_count"] == 1


def test_deadline_is_strict_and_late_completion_is_not_hidden():
    total = summarize([Request("r1", 0, deadline_s=3)], [completed()], horizon_s=5)["all"]
    assert total["late_completion_count"] == 1
    assert total["authorized_ontime_goodput_per_s"] == 0
    assert total["outcome_counts"]["completed"] == 1


def test_empty_is_distinct_from_unattainable_and_percentiles_use_nearest_rank():
    total = summarize([], [], horizon_s=1)["all"]
    assert total["completed_latency"] == dict(n=0, max_s=None, p50_s=None, p95_s=None, p99_s=None)
    assert total["all_offered_verified_completion_bound"]["p99"]["status"] == "empty"
    assert percentile([4, 1, 3, 2], .5) == 2
    assert percentile([2, 2], 1) == 2
    assert percentile([], .99) is None
    for p in (0, -1, 1.1, math.nan):
        with pytest.raises(ValueError):
            percentile([1], p)


@pytest.mark.parametrize("requests,observations", [
    ([Request("r1", 0)], []),
    ([], [completed()]),
    ([Request("r1", 0)] * 2, [completed()]),
    ([Request("r1", 0)], [completed()] * 2),
    ([Request("r1", 5)], [completed()]),
    ([Request("r1", 0)], [completed(admitted_s=2.5)]),
    ([Request("r1", 0)], [completed(terminal_s=6)]),
    ([Request("r1", 0)], [completed(revocation_ack_s=6)]),
    ([Request("r1", 0)], [Observation("r1", "expired", "deadline", terminal_s=2)]),
    ([Request("r1", 0, deadline_s=3)], [Observation("r1", "expired", "deadline", terminal_s=2)]),
])
def test_invalid_or_missing_observations_fail_loudly(requests, observations):
    with pytest.raises(ValueError):
        summarize(requests, observations, horizon_s=5)


@pytest.mark.parametrize("override", [
    {"started_s": None}, {"admitted_s": None}, {"terminal_s": None},
    {"completed_bytes": -1}, {"completed_bytes": True}, {"evidence_complete": 1},
    {"authority_generation": -1}, {"started_s": math.inf}, {"reason": "user secret"},
])
def test_closed_observation_invariants(override):
    with pytest.raises(ValueError):
        completed(**override)


def test_censored_and_noncompletion_records_are_strict():
    with pytest.raises(ValueError):
        Observation("r1", "censored", "observation_ended", terminal_s=2)
    with pytest.raises(ValueError):
        Observation("r1", "refused", "policy", terminal_s=2, completed_bytes=1)
    with pytest.raises(ValueError):
        Observation("r1", "refused", "policy", terminal_s=2, evidence_complete=True)
    with pytest.raises(ValueError):
        Request("actual user content", 0)
    with pytest.raises(TypeError):
        Observation("r1", "censored", "observation_ended", prompt="secret")


def test_provenance_is_explicit_and_validated():
    provenance = Provenance("a" * 40, True, "b" * 64, 8)
    report = summarize([], [], horizon_s=1, provenance=provenance)
    assert report["provenance"]["source_revision"] == "a" * 40
    assert summarize([], [], horizon_s=1)["provenance"]["source_revision"] is None
    with pytest.raises(ValueError):
        Provenance(source_revision="not a revision")
    with pytest.raises(ValueError):
        summarize([], [], horizon_s=1, provenance={"secret": "no"})


def test_workload_digest_and_report_are_order_independent():
    requests = [Request("r1", 0), Request("r2", 0)]
    observations = [completed(), completed("r2")]
    assert summarize(requests, observations, horizon_s=5) == summarize(requests[::-1], observations[::-1], horizon_s=5)
    changed = [replace(requests[0], deadline_s=4), requests[1]]
    assert summarize(changed, observations, horizon_s=5)["workload_sha256"] != summarize(requests, observations, horizon_s=5)["workload_sha256"]


def test_verification_buckets_partition_and_known_failure_dominates_unknown():
    requests = [Request(f"r{i}", 0, deadline_s=3 if i == 4 else 4) for i in range(1, 5)]
    observations = [completed(), completed("r2", evidence_complete=False, authorized_at_release=None),
                    completed("r3", evidence_complete=None), completed("r4")]
    total = summarize(requests, observations, horizon_s=5)["all"]
    assert total["verification_counts"] == dict(failed=1, unknown=1, verified_late=1, verified_ontime=1)
    assert sum(total["verification_counts"].values()) == total["outcome_counts"]["completed"]
    failed_only = summarize([requests[1]], [observations[1]], horizon_s=5)["all"]
    assert failed_only["authorized_ontime_goodput_per_s"] == 0


def test_record_digest_binds_outcomes_and_window_but_workload_digest_does_not():
    requests = [Request("r1", 0)]
    first = summarize(requests, [completed()], horizon_s=5)
    for other in (summarize(requests, [completed(terminal_s=4)], horizon_s=5),
                  summarize(requests, [completed()], horizon_s=6)):
        assert other["workload_sha256"] == first["workload_sha256"]
        assert other["record_sha256"] != first["record_sha256"]


def test_elapsed_censored_deadline_is_aggregated_without_inventing_expiry():
    total = summarize([Request("r1", 0, deadline_s=3)],
                      [Observation("r1", "censored", "observation_ended")], horizon_s=5)["all"]
    assert total["known_deadline_miss_count"] == 1
    assert total["outcome_counts"]["expired"] == 0
    assert total["outcome_counts"]["censored"] == 1


def test_revocation_metadata_can_predate_arrival_and_is_retained_not_verified():
    report = summarize([Request("r1", 1)], [Observation("r1", "refused", "revoked",
                       terminal_s=2, revocation_ack_s=.5, authority_generation=7)], horizon_s=5)
    assert report["observations"][0]["observation"]["revocation_ack_s"] == .5
    assert report["observations"][0]["observation"]["authority_generation"] == 7


def test_protocol_has_only_pure_stdlib_imports_and_no_io(monkeypatch):
    tree = ast.parse(inspect.getsource(protocol))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module)
    assert modules == {"__future__", "dataclasses", "fractions", "hashlib", "json", "math", "random", "re"}
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected file I/O")
    monkeypatch.setattr("builtins.open", forbidden)
    offsets = arrival_schedule(3, 2)
    assert len(offsets) == 3
    assert summarize([], [], horizon_s=1)["all"]["offered"] == 0


def test_decimal_nearest_rank_does_not_round_up_at_integer_boundary():
    assert percentile(list(range(100)), .07) == 6
    assert percentile(list(range(100)), .95) == 94
    assert percentile(list(range(100)), .99) == 98


def test_oversized_numeric_fields_fail_with_value_error():
    with pytest.raises(ValueError):
        completed(completed_bytes=10**400)
    with pytest.raises(ValueError):
        Request("r1", 10**400)
