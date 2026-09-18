"""The local pilot must exercise real memory and protected evidence boundaries."""

from concurrent.futures import Future

from research.memory_fabric.local_baseline import _fabric_pick, run_local_baseline
from research.memory_fabric.protocol import Request
import pytest


def test_disposable_baseline_reconstructs_completed_synthetic_evidence() -> None:
    report = run_local_baseline(count=20, seed_records=8, rate_per_s=50,
                                workers=1, max_outstanding=20, seed=17)
    assert report["measurement_kind"] == "real_local_composed_component_measurement"
    assert report["host_delivery_measured"] is False
    assert report["authority_race_verified"] is False
    assert report["capture"]["encrypted"] is True
    assert report["capture"]["mode"] == "full"
    assert report["capture"]["media_exact"]["image"] is True
    assert report["capture"]["reconstructed_count"] == report["accounting"]["summary"]["outcome_counts"]["completed"]
    assert report["accounting"]["summary"]["offered"] == 20
    assert all(row["observation"]["request_id"].startswith("r") for row in report["observations"])
    counts = report["accounting"]["summary"]["outcome_counts"]
    assert len(report["stage_samples"]) == counts["completed"] + counts["error"]


def test_isolated_writer_lane_runs_with_reconstructable_evidence() -> None:
    report = run_local_baseline(count=20, seed_records=8, rate_per_s=20,
                                workers=2, max_outstanding=20, seed=19,
                                isolate_write_lane=True)
    assert report["scheduling_policy"] == "bounded_isolated_single_writer_lane"
    assert report["accounting"]["summary"]["outcome_counts"]["error"] == 0
    assert report["capture"]["reconstructed_count"] == 20


def test_isolated_writer_lane_requires_distinct_workers() -> None:
    with pytest.raises(ValueError, match="at least two workers"):
        run_local_baseline(count=1, workers=1, isolate_write_lane=True)


def test_fabric_pick_deadline_size_and_reserved_bulk() -> None:
    queue = [(Request("r20", 0, "bulk"), 19, 0, Future()),
             (Request("r1", .1, "fast", .8), 0, .1, Future()),
             (Request("r2", .2, "fast", .7), 1, .2, Future())]
    assert _fabric_pick(queue, 0) == 2
    assert _fabric_pick(queue, 4) == 0


def test_fabric_prototype_matches_baseline_evidence_without_write_errors() -> None:
    report = run_local_baseline(count=20, seed_records=8, rate_per_s=20,
                                workers=1, max_outstanding=20, seed=19,
                                policy="fabric-deadline-size")
    assert report["scheduling_policy"] == "research_fabric_deadline_estimated_size_reserved_bulk"
    assert report["accounting"]["summary"]["outcome_counts"]["completed"] == 20
    assert report["capture"]["reconstructed_count"] == 20
