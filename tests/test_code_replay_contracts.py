"""Contract fixtures only: no Click task or agent-performance evidence."""

from copy import deepcopy
import json

import pytest

from benchmarks.code_replay.contracts import (
    ProtocolManifest, RunManifest, SCHEDULE, TaskManifest, TrialResult,
)


DIGEST = "a" * 64


def task_row(order=1):
    return {
        "format": TaskManifest.format, "task_id": f"task-{order}", "order": order,
        "parent_commit": f"{order:040x}", "reference_commit": f"{order + 100:040x}",
        "issue_version_sha256": DIGEST, "requirements_sha256": DIGEST,
        "source_sha256": DIGEST, "environment_sha256": DIGEST, "grader_sha256": DIGEST,
        "baseline_policy_sha256": DIGEST, "license_ref": "review-1",
        "requirements_at": f"2020-01-{order:02d}T00:00:00Z",
        "solution_cutoff": f"2020-02-{order:02d}T00:00:00Z",
        "parent_fails": True, "reference_passes": True,
    }


def protocol_row():
    return {
        "format": ProtocolManifest.format, "protocol_id": "fixture-only",
        "anchor_commit": "f" * 40, "search_horizon": 100,
        "tasks": [task_row(i) for i in range(1, 6)], "arms": list("ABCD"),
        "repetitions": 3, "schedule": [list(r) for r in SCHEDULE],
        "versions": {n: {"artifact_sha256": DIGEST, "configuration_sha256": DIGEST}
                     for n in ("atmem", "agent", "model", "extractor")},
        "configuration_sha256": DIGEST, "hardware_sha256": DIGEST,
        "budgets": {"tokens": 1000, "tool_calls": 20, "wall_seconds": 60,
                    "context_bytes": 2048, "cost_microusd": 100},
        "total_cost_microusd": 1000,
        "inference": {"provider_id": "fixture", "endpoint": "https://example.invalid/inference",
                      "license_review_sha256": DIGEST, "egress_policy_sha256": DIGEST},
        "storage_profile": {"profile_id": "fixture-protected", "qualification_sha256": DIGEST},
        "analysis_sha256": DIGEST,
    }


def run_row(protocol):
    row = protocol.to_dict()
    return {
        "format": RunManifest.format, "run_id": "run-1", "protocol_sha256": protocol.sha256,
        "task_id": "task-1", "task_sha256": TaskManifest.from_dict(row["tasks"][0]).sha256,
        "arm": "B", "repetition": 1, "trajectory_id": "trajectory-b-1", "session_id": "session-1",
        "lane_id": "lane-b-1", "source_sha256": DIGEST, "capability_sha256": DIGEST,
        "effective_configuration_sha256": DIGEST, "started_at": "2026-01-01T00:00:00Z",
        "budgets": row["budgets"],
    }


def result_row(run):
    return {
        "format": TrialResult.format, "run_sha256": run.sha256, "status": "failed",
        "reason_code": "target_failed", "ended_at": "2026-01-01T00:01:00Z",
        "checks_total": 10, "checks_passed": 9, "safety_violations": 0,
        "exposure": "submitted", "evidence_sha256": DIGEST, "context_sha256": DIGEST,
        "memory_ids": ["memory-1"],
        "measurements": {n: None for n in ("input_tokens", "output_tokens", "cached_tokens", "cost_microusd",
                                         "elapsed_ms", "tool_calls", "file_reads", "searches", "context_bytes",
                                         "human_interventions", "peak_rss_bytes")},
        "stage_ms": {"retrieval": 4, "index": None}, "price_source_ref": None,
    }


def test_round_trip_canonical_hash_and_immutable_validated_tree():
    source = protocol_row()
    protocol = ProtocolManifest.from_dict(source)
    source["tasks"][0]["task_id"] = "changed"
    copy = protocol.to_dict()
    copy["tasks"].clear()
    assert len(protocol.to_dict()["tasks"]) == 5
    reordered = dict(reversed(list(protocol.to_dict().items())))
    assert ProtocolManifest.from_dict(reordered).sha256 == protocol.sha256
    assert ProtocolManifest.from_json(protocol.canonical_json) == protocol
    run = RunManifest.from_dict(run_row(protocol))
    run.bind(protocol)
    result = TrialResult.from_dict(result_row(run))
    result.bind(run)
    assert result.to_dict()["measurements"]["cost_microusd"] is None


@pytest.mark.parametrize("field", list(protocol_row()))
def test_protocol_rejects_missing_fields(field):
    row = protocol_row()
    del row[field]
    with pytest.raises(ValueError):
        ProtocolManifest.from_dict(row)


@pytest.mark.parametrize("field,value", [
    ("format", "atmem-click-protocol-v2"), ("search_horizon", True),
    ("search_horizon", 99), ("repetitions", True), ("repetitions", 4),
    ("arms", list("ABDC")), ("anchor_commit", "main"), ("analysis_sha256", "latest"),
    ("schedule", [list("ABCD")] * 3), ("storage_profile", {}), ("versions", {}),
    ("budgets", {}), ("inference", {}), ("total_cost_microusd", 0),
])
def test_protocol_rejects_unfrozen_or_incomplete_design(field, value):
    row = protocol_row()
    row[field] = value
    with pytest.raises(ValueError):
        ProtocolManifest.from_dict(row)


@pytest.mark.parametrize("endpoint", ["http://example.invalid", "https://user:secret@example.invalid",
    "https://example.invalid/?key=secret", "https://example.invalid/#secret", "https://example.invalid:8443", "https://"])
def test_endpoint_cannot_smuggle_credentials_or_unapproved_transport(endpoint):
    row = protocol_row()
    row["inference"]["endpoint"] = endpoint
    with pytest.raises(ValueError):
        ProtocolManifest.from_dict(row)


@pytest.mark.parametrize("field,value", [
    ("requirements_at", "2020-01-01"), ("requirements_at", "2021-01-01T00:00:00Z"),
    ("parent_fails", False), ("reference_passes", "true"), ("order", True),
    ("source_sha256", "main"), ("parent_commit", "abcd"),
])
def test_task_requires_pre_solution_requirements_and_qualified_grader(field, value):
    row = task_row()
    row[field] = value
    with pytest.raises(ValueError):
        TaskManifest.from_dict(row)


def test_protocol_rejects_duplicate_tasks_reordered_chronology_and_unknown_fields():
    for mutate in (
        lambda r: r["tasks"].__setitem__(1, deepcopy(r["tasks"][0])),
        lambda r: r["tasks"].reverse(),
        lambda r: r["tasks"][1].__setitem__("solution_cutoff", "2020-01-10T00:00:00Z"),
        lambda r: r.__setitem__("authorization", True),
    ):
        row = protocol_row()
        mutate(row)
        with pytest.raises(ValueError):
            ProtocolManifest.from_dict(row)


def test_run_cannot_change_source_task_protocol_or_raise_ceiling():
    protocol = ProtocolManifest.from_dict(protocol_row())
    for field in ("source_sha256", "task_sha256", "protocol_sha256"):
        row = run_row(protocol)
        row[field] = "b" * 64
        with pytest.raises(ValueError, match="bind"):
            RunManifest.from_dict(row).bind(protocol)
    row = run_row(protocol)
    row["budgets"]["tokens"] += 1
    with pytest.raises(ValueError, match="budgets"):
        RunManifest.from_dict(row).bind(protocol)


def test_unknown_is_not_zero_and_declared_pass_cannot_hide_failure():
    run = RunManifest.from_dict(run_row(ProtocolManifest.from_dict(protocol_row())))
    row = result_row(run)
    assert TrialResult.from_dict(row).to_dict()["measurements"]["input_tokens"] is None
    row["status"] = "passed"
    with pytest.raises(ValueError, match="all checks"):
        TrialResult.from_dict(row)
    row["checks_passed"] = 10
    TrialResult.from_dict(row)
    row["safety_violations"] = 1
    with pytest.raises(ValueError):
        TrialResult.from_dict(row)


def test_cost_requires_provenance_and_timing_must_bind_run():
    run = RunManifest.from_dict(run_row(ProtocolManifest.from_dict(protocol_row())))
    row = result_row(run)
    row["measurements"]["cost_microusd"] = 0
    with pytest.raises(ValueError, match="provenance"):
        TrialResult.from_dict(row)
    row["price_source_ref"] = "provider-price-1"
    TrialResult.from_dict(row).bind(run)
    row["ended_at"] = "2025-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="predates"):
        TrialResult.from_dict(row).bind(run)


def test_raw_json_rejects_duplicate_keys_nonfinite_and_extra_payloads():
    with pytest.raises(ValueError, match="duplicate"):
        ProtocolManifest.from_json('{"format":"x","format":"y"}')
    with pytest.raises(ValueError, match="non-finite"):
        ProtocolManifest.from_json('{"value":NaN}')
    row = protocol_row()
    row["tasks"][0]["raw_transcript"] = "not allowed in metadata manifest"
    with pytest.raises(ValueError, match="fields"):
        ProtocolManifest.from_dict(row)
    raw = json.dumps(protocol_row()).replace('"total_cost_microusd": 1000', '"total_cost_microusd": Infinity')
    with pytest.raises(ValueError):
        ProtocolManifest.from_json(raw)
