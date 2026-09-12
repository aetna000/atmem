from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import statistics
import time

import pytest

from atmem.control.manager import ControlPlaneManager
from atmem.control.store import ControlStore
from atmem.execution.projection import execution_projection
from atmem.execution.coverage import coverage_manifest
from atmem.execution.status import classify_execution
from atmem.service.application import APIError, APIPrincipal, AtMemApplication
from atmem.service.executions import ExecutionService


def _manager(tmp_path: Path) -> ControlPlaneManager:
    return ControlPlaneManager.start(
        host="openclaw",
        state_path=tmp_path / "control.json",
        control_root=tmp_path / "migrations",
        subject_id="user-1",
    )


def _record(manager: ControlPlaneManager, sequence: int, **overrides: object) -> dict:
    values = {
        "event_type": "model.input",
        "run_id": "run-1",
        "execution_id": "execution-1",
        "event_id": f"event-{sequence}",
        "producer_instance_id": "openclaw-plugin-1",
        "producer_epoch": "epoch-1",
        "producer_sequence": sequence,
        "event_time": f"2026-09-12T00:{sequence:02d}:00.000Z",
        "agent_id": "main",
        "subject_id": "user-1",
        "payload": {"provider": "local", "model": "fixture"},
    }
    values.update(overrides)
    return manager.record_blackbox_event(**values)  # type: ignore[arg-type]


def test_durable_delivery_replay_conflict_and_restart(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    accepted = _record(manager, 1)
    replayed = _record(manager, 1)
    conflict = _record(manager, 1, event_type="model.output")
    assert accepted["decision"] == "accepted"
    assert replayed["decision"] == "replayed"
    assert conflict["decision"] == "conflict"
    assert conflict["durably_accepted"] is False
    assert conflict["durably_classified"] is True
    assert len(manager.blackbox_events(run_id="run-1")) == 1

    restarted = ControlPlaneManager(state_path=tmp_path / "control.json")
    assert _record(restarted, 1)["decision"] == "replayed"
    state = restarted.state()
    store = ControlStore(Path(state.control_dir) / "evidence.db")
    try:
        delivery = store.execution_delivery_state(state.migration_id)
    finally:
        store.close()
    assert len(delivery["deliveries"]) == 1
    assert len(delivery["conflicts"]) == 1


def test_sequenced_delivery_requires_stable_valid_event_time(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    with pytest.raises(ValueError, match="event_time is required"):
        _record(manager, 1, event_time=None)
    for value in (
        "not-a-timestamp",
        "2026-09-12T00:00:00Z",
        "2026-09-12T00:00:00.000+00:00",
        "2026-13-12T00:00:00.000Z",
    ):
        with pytest.raises(ValueError, match="ISO 8601 UTC"):
            _record(manager, 1, event_time=value)


def test_execution_relationship_invariants_are_enforced_at_ingest(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    with pytest.raises(ValueError, match="parent_execution_id requires execution_id"):
        _record(manager, 1, execution_id=None, parent_execution_id="parent")
    with pytest.raises(ValueError, match="retry_of_attempt_id requires attempt_id"):
        _record(manager, 1, attempt_id=None, retry_of_attempt_id="prior")


def test_virtual_40_minute_projection_retains_links_and_planted_gap(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    start = datetime(2026, 9, 12, tzinfo=timezone.utc)
    event_types = ["turn.input", "tool.requested", "tool.completed", "turn.ended"]
    sequences = [1, 2, 4, 5]
    for index, (event_type, sequence) in enumerate(zip(event_types, sequences)):
        payload: dict[str, object] = {}
        if event_type == "tool.requested":
            payload = {"tool_name": "fixture", "params_sha256": "a" * 64, "param_keys": []}
        elif event_type == "tool.completed":
            payload = {"tool_name": "fixture", "outcome": "success", "result_sha256": "b" * 64, "result_present": True}
        elif event_type == "turn.ended":
            payload = {"success": True, "cancelled": False, "duration_ms": 2_400_000, "response_sha256": "c" * 64, "response_chars": 2}
        _record(
            manager,
            sequence,
            event_type=event_type,
            event_id=f"journey-{sequence}",
            event_time=(
                start + timedelta(minutes=index * 13 + (1 if index == 3 else 0))
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            parent_execution_id="parent-explicit",
            attempt_id="attempt-2",
            retry_of_attempt_id="attempt-1",
            tool_call_id="call-1" if event_type.startswith("tool.") else None,
            payload=payload,
        )
    projected = execution_projection(
        manager.blackbox_events(), subject_id="user-1", execution_id="execution-1"
    )
    assert projected["event_count"] == 4
    assert projected["parent_execution_ids"] == ["parent-explicit"]
    assert projected["orphan_parent_ids"] == ["parent-explicit"]
    assert projected["retry_of_attempt_ids"] == ["attempt-1"]
    assert projected["coverage_gaps"][0]["first_sequence"] == 3
    assert projected["cross_producer_ordering"].startswith("incomparable")


def test_execution_service_is_non_disclosing_and_does_not_touch_memory(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager, 1)
    service = ExecutionService(manager)
    owner = APIPrincipal("operator", "admin", "user-1")
    outsider = APIPrincipal("operator-2", "admin", "other-user")
    before = manager.memory_status()
    assert service.get(owner, "execution-1")["event_count"] == 1
    with pytest.raises(APIError) as denied:
        service.get(outsider, "execution-1")
    assert denied.value.status == 404
    after = manager.memory_status()
    assert before["record_count"] == after["record_count"]


def test_application_execution_projection_and_coverage_are_bounded(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager, 1)
    owner = APIPrincipal("operator", "admin", "user-1")
    application = AtMemApplication(manager)
    listing = application.executions(owner)
    assert listing["scope"] == "authorized_subject"
    assert application.execution(owner, "execution-1")["event_count"] == 1
    runtime_manifest = manager.blackbox_runs()["capture_coverage"]
    assert runtime_manifest["adapter"] == "openclaw"
    assert runtime_manifest["observed_boundaries"] == ["model.input"]
    assert runtime_manifest["assurance"] == "declared"
    manifest = coverage_manifest(
        adapter="openclaw",
        version="2026.9.1",
        configuration="control-plane-only",
        supported=("turn.input", "model.input", "model.output", "turn.ended"),
        observed=("turn.input", "model.input", "turn.ended"),
        gaps=("model.output hook unavailable in fixture",),
        verified_at="2026-09-12T00:00:00Z",
    )
    assert manifest["omitted_boundaries"] == ["model.output"]
    assert manifest["assurance"] == "observed"


def test_legacy_run_only_projection_uses_separate_compatibility_lookup(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager, 1, execution_id=None, run_id="legacy-run")
    projection = ExecutionService(manager).get(
        APIPrincipal("operator", "admin", "user-1"), "legacy-run"
    )
    assert projection["execution_id"] == "legacy-run"
    assert projection["event_count"] == 1


def test_modern_execution_paging_never_falls_through_to_legacy_rows(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager, 1, execution_id="shared-id", run_id="modern-run")
    for sequence in (1, 2):
        _record(
            manager,
            sequence,
            execution_id=None,
            run_id="shared-id",
            event_id=f"legacy-{sequence}",
            producer_instance_id="legacy-producer",
        )
    assert manager.execution_events(
        subject_id="user-1", execution_id="shared-id", limit=1, offset=1
    ) == []


def test_closed_tool_call_is_running_not_waiting() -> None:
    events = [
        {"event_type": "tool.requested", "tool_call_id": "call-1"},
        {"event_type": "tool.completed", "tool_call_id": "call-1"},
    ]
    assert classify_execution(events) == "running"
    assert classify_execution(events[:1]) == "waiting"


def test_control_schema_five_upgrades_to_six_additively(tmp_path: Path) -> None:
    path = tmp_path / "control.db"
    store = ControlStore(path)
    store.create_migration("migration", "openclaw", "user-1")
    store.close()
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            DROP TABLE execution_coverage_gaps;
            DROP TABLE execution_delivery_conflicts;
            DROP TABLE execution_deliveries;
            UPDATE schema_meta SET value = '5' WHERE key = 'schema_version';
            """
        )
    upgraded = ControlStore(path)
    try:
        assert upgraded._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()["value"] == "6"
        assert upgraded._conn.execute(
            "SELECT host FROM migrations WHERE migration_id = 'migration'"
        ).fetchone()["host"] == "openclaw"
        assert upgraded._conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'execution_deliveries'"
        ).fetchone() is not None
    finally:
        upgraded.close()


def test_late_success_revises_finding_without_rewriting_error(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(manager, 1, event_type="tool.requested", tool_call_id="call-1", payload={"tool_name": "fixture", "params_sha256": "a" * 64, "param_keys": []})
    _record(manager, 2, event_type="tool.completed", tool_call_id="call-1", payload={"tool_name": "fixture", "outcome": "error", "error_category": "fixture", "result_present": False})
    _record(manager, 3, event_type="turn.ended", payload={"success": False, "cancelled": False, "duration_ms": 1})
    first = manager.verify_blackbox_flight("run-1")
    _record(manager, 4, event_type="tool.completed", tool_call_id="call-1", payload={"tool_name": "fixture", "outcome": "success", "result_sha256": "b" * 64, "result_present": True})
    second = manager.verify_blackbox_flight("run-1")
    assert first["report_sha256"] != second["report_sha256"]
    assert any(item["classification"] == "recovered_error" and item["state"] == "superseded" for item in second["findings"])
    assert len(manager.blackbox_events(run_id="run-1")) == 4


def test_capture_loss_is_visible_and_projection_index_is_deletable(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    _record(
        manager,
        1,
        event_type="capture.gap",
        payload={
            "reason": "spool_capacity_exceeded",
            "dropped_count": 3,
            "first_sequence": 8,
            "last_sequence": 10,
        },
    )
    report = manager.verify_blackbox_flight("run-1")
    assert any(point["code"] == "capture_loss" for point in report["attention_points"])
    state = manager.state()
    store = ControlStore(Path(state.control_dir) / "evidence.db")
    try:
        assert store.execution_delivery_counts(state.migration_id) == {
            "durable_deliveries": 1,
            "conflicts": 0,
            "reported_gaps": 1,
        }
        removed = store.prune_execution_projections(
            state.migration_id, before="9999-01-01T00:00:00Z"
        )
        assert removed["deliveries"] == 1
        assert store.execution_events(
            state.migration_id, subject_id="user-1", execution_id="execution-1"
        ) == []
        # Signed source evidence has its separate audit retention boundary.
        assert len(store.list_evidence(state.migration_id, kind="agent_blackbox")) == 1
    finally:
        store.close()


def test_100k_event_first_page_index_is_within_m0_budget(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    accepted = _record(manager, 1)
    state = manager.state()
    store = ControlStore(Path(state.control_dir) / "evidence.db")
    try:
        evidence_id = accepted["evidence_id"]
        template = manager.blackbox_events(run_id="run-1")[0]["body"]
        write_durations = []
        for index in range(1, 101):
            body = {
                **template,
                "event_id": f"write-event-{index}",
                "producer_instance_id": "write-producer",
                "producer_epoch": "write-epoch",
                "producer_sequence": index,
                "execution_id": "write-overhead",
                "run_id": "write-overhead",
            }
            started = time.perf_counter()
            store.accept_execution_delivery(
                state.migration_id,
                body=body,
                producer_instance_id="write-producer",
                producer_epoch="write-epoch",
                producer_sequence=index,
                event_id=f"write-event-{index}",
            )
            write_durations.append(time.perf_counter() - started)
        rows = (
            (
                f"load-{index}", state.migration_id, "load-producer", "load-epoch",
                index, f"load-event-{index}", "0" * 64, evidence_id,
                f"2026-09-12T01:00:{index % 60:02d}Z", "user-1",
                "execution-1" if index <= 100 else f"other-{index // 100}",
                "run-1" if index <= 100 else f"other-{index // 100}",
            )
            for index in range(2, 99_901)
        )
        with store.transaction():
            store._conn.executemany(
                """INSERT INTO execution_deliveries(
                       id, migration_id, producer_instance_id, producer_epoch,
                       producer_sequence, event_id, body_sha256, evidence_id,
                       received_at, subject_id, execution_id, run_id
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        durations = []
        for _ in range(30):
            started = time.perf_counter()
            page = store.execution_events(
                state.migration_id, subject_id="user-1",
                execution_id="execution-1", limit=100,
            )
            durations.append(time.perf_counter() - started)
        p95 = statistics.quantiles(durations, n=20)[18]
        write_p95 = statistics.quantiles(write_durations, n=20)[18]
        total = store._conn.execute(
            "SELECT COUNT(*) AS count FROM execution_deliveries WHERE migration_id = ?",
            (state.migration_id,),
        ).fetchone()["count"]
        size_bytes = Path(state.control_dir, "evidence.db").stat().st_size
        print(
            f"100k execution index: lookup_p95_ms={p95 * 1000:.3f} "
            f"write_p95_ms={write_p95 * 1000:.3f} storage_bytes={size_bytes}"
        )
        assert total == 100_000
        assert len(page) == 100
        assert p95 <= 0.200, f"100k first-page p95 was {p95 * 1000:.2f} ms"
    finally:
        store.close()
