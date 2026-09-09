"""Governed task state on databases that predate it.

The upgrade fixtures in `tests/fixtures/upgrades/` were written by published
AtMem versions that knew nothing about tasks. Adding a whole authority plane to
someone's existing memory is exactly the change that can go wrong quietly, so
each floor is driven through the complete lifecycle — create, advance, inspect,
complete or cancel, delete — while every pre-existing memory stays intact.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock
from atmem.memory import Memory
from atmem.store.sqlite import SQLiteStore
from atmem.task_state.service import TaskStateService


FIXTURES = Path(__file__).parent / "fixtures" / "upgrades"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())
FLOORS = [row["version"] for row in MANIFEST["floors"]]
MEMORY_SUBJECT = MANIFEST["expected"]["subject_id"]
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)

SCOPE = AuthorityScope(MEMORY_SUBJECT, "agent-1", "workspace-1")

TASK_MIGRATIONS = [
    "0070_governed_task_profiles",
    "0071_governed_tasks",
    "0072_governed_task_revisions",
    "0073_governed_task_provenance",
    "0074_governed_task_proposals",
    "0075_governed_task_steps",
    "0076_governed_task_deliveries",
    "0077_governed_task_sequences",
    # Amendment A. Appended, never renumbered: an upgrade from any published
    # floor must arrive at this exact sequence, and a database that already had
    # 0070-0077 gains only this step.
    "0078_governed_task_session_bindings",
]


@pytest.fixture(params=FLOORS)
def upgraded(request, tmp_path: Path) -> Path:
    source = FIXTURES / f"atmem-{request.param}.db"
    target = tmp_path / f"atmem-{request.param}.db"
    shutil.copyfile(source, target)
    return target


def _service(path: Path) -> tuple[TaskStateService, SQLiteStore]:
    store = SQLiteStore(path)
    return TaskStateService(store, clock=FixedUtcClock(MOMENT)), store


def test_the_task_plane_is_created_on_every_published_floor(
    upgraded: Path,
) -> None:
    store = SQLiteStore(upgraded)
    try:
        applied = store.applied_migrations()
        assert [row for row in applied if row.startswith("007")] == TASK_MIGRATIONS
        assert applied == sorted(applied)
    finally:
        store.close()


def test_upgrading_starts_no_tasks_of_its_own(upgraded: Path) -> None:
    """FR-018: an upgrade must never begin influencing an agent."""
    service, store = _service(upgraded)
    try:
        assert store.list_tasks() == []
        assert service.list()["count"] == 0
    finally:
        store.close()


def test_existing_memory_is_untouched_by_the_task_plane(upgraded: Path) -> None:
    memory = Memory(upgraded, auto_vectors=False)
    try:
        assert len(memory.list(MEMORY_SUBJECT)) == (
            MANIFEST["expected"]["active_records"]
        )
        assert len(memory.list(MEMORY_SUBJECT, include_inactive=True)) == (
            MANIFEST["expected"]["total_records"]
        )
        assert memory.verify(MEMORY_SUBJECT)["valid"] is True
    finally:
        memory.close()


@pytest.mark.parametrize("ending", ["complete", "cancel"])
def test_the_full_task_lifecycle_runs_on_upgraded_state(
    upgraded: Path, ending: str
) -> None:
    """Create, advance, inspect, finish, and delete — on someone's real data."""
    service, store = _service(upgraded)
    try:
        view = service.start(
            TaskStartRequest(
                task_id="upgrade-task", scope=SCOPE, profile_id="general",
                profile_version="general-v1", goal="Verify the upgrade",
                actor="operator", actor_role=ActorRole.OPERATOR,
                idempotency_key="upgrade-start",
            ),
            items=(
                TaskItem(item_id="item-1", kind="step", title="Check memory",
                         required=True),
            ),
        )
        assert view.state.revision == 1

        decision = service.submit(
            TaskStateProposal(
                proposal_id="upgrade-proposal", task_id="upgrade-task",
                scope=SCOPE, base_revision=1, idempotency_key="upgrade-delta",
                actor="agent", actor_role=ActorRole.HOST_AGENT,
                assurance=Assurance.HOST_REPORTED,
                operations=(
                    TaskOperation(
                        kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                        status=ItemStatus.COMPLETED,
                    ),
                ),
            )
        )
        assert decision.outcome is StepOutcome.ACCEPTED

        inspected = service.get(SCOPE, "upgrade-task")
        assert inspected.state.revision == 2
        assert inspected.summary["completion_allowed"] is True

        finished = getattr(service, ending)(
            SCOPE, "upgrade-task", actor="operator",
            actor_role=ActorRole.OPERATOR, reason="upgrade drill",
        )
        assert finished.state.lifecycle is (
            TaskLifecycle.COMPLETED if ending == "complete" else TaskLifecycle.CANCELLED
        )

        receipt = service.forget(
            SCOPE, "upgrade-task", actor="admin",
            actor_role=ActorRole.ADMINISTRATOR,
        )
        assert receipt["deleted"] is True
        assert store.list_tasks() == []
    finally:
        store.close()


def test_memory_still_works_alongside_a_governed_task(upgraded: Path) -> None:
    """The two planes share a database and must not disturb each other."""
    memory = Memory(upgraded, auto_vectors=False)
    try:
        service = TaskStateService(memory.store, clock=FixedUtcClock(MOMENT))
        service.start(
            TaskStartRequest(
                task_id="upgrade-task", scope=SCOPE, profile_id="general",
                profile_version="general-v1", goal="Verify coexistence",
                actor="operator", actor_role=ActorRole.OPERATOR,
                idempotency_key="upgrade-start",
            )
        )
        memory.remember(MEMORY_SUBJECT, "My preferred airport is Perth.")

        assert memory.verify(MEMORY_SUBJECT)["valid"] is True
        assert service.get(SCOPE, "upgrade-task").state.revision == 1
        assert any(
            "Perth" in row["content"] for row in memory.list(MEMORY_SUBJECT)
        )
    finally:
        memory.close()


def test_an_interrupted_task_upgrade_recovers_forward(upgraded: Path) -> None:
    store = SQLiteStore(upgraded)
    store.close()

    connection = sqlite3.connect(upgraded)
    connection.execute("DROP TABLE governed_task_deliveries")
    connection.execute("DROP TABLE governed_task_steps")
    connection.execute("DROP TABLE governed_task_proposals")
    connection.execute("DROP TABLE governed_task_provenance")
    connection.execute("DROP TABLE governed_task_revisions")
    connection.execute("DROP TABLE governed_tasks")
    connection.execute("DROP TABLE governed_task_profiles")
    connection.execute("DROP TABLE schema_migrations")
    connection.commit()
    connection.close()

    recovered = SQLiteStore(upgraded)
    try:
        assert [
            row for row in recovered.applied_migrations() if row.startswith("007")
        ] == TASK_MIGRATIONS
        assert recovered.list_tasks() == []
        # And the memory plane is still intact after the repair.
        assert len(recovered.list_records(MEMORY_SUBJECT)) == (
            MANIFEST["expected"]["active_records"]
        )
    finally:
        recovered.close()


def test_reopening_an_upgraded_database_is_idempotent(upgraded: Path) -> None:
    for _ in range(3):
        store = SQLiteStore(upgraded)
        try:
            assert [
                row for row in store.applied_migrations() if row.startswith("007")
            ] == TASK_MIGRATIONS
        finally:
            store.close()


def test_rollback_keeps_the_previous_version_readable(upgraded: Path) -> None:
    """The task plane is additive: an older build ignores tables it never reads."""
    before = _schema(FIXTURES / upgraded.name)
    store = SQLiteStore(upgraded)
    store.close()
    after = _schema(upgraded)

    for table, columns in before.items():
        assert table in after, f"upgrade removed table {table}"
        for name, spec in columns.items():
            assert after[table][name] == spec, f"upgrade changed {table}.{name}"

    added = set(after) - set(before)
    task_tables = {row for row in added if row.startswith("governed_task")}
    assert task_tables == {
        "governed_task_profiles",
        "governed_tasks",
        "governed_task_revisions",
        "governed_task_provenance",
        "governed_task_proposals",
        "governed_task_steps",
        "governed_task_deliveries",
        "governed_task_session_bindings",
    }
    # The task plane adds tables and touches none of the old ones, so an older
    # build that never reads them is unaffected by rolling back onto this file.
    assert not (task_tables & set(before))


def _schema(path: Path) -> dict[str, dict[str, dict[str, object]]]:
    connection = sqlite3.connect(path)
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return {
            table: {
                str(column[1]): {
                    "type": column[2], "notnull": column[3], "default": column[4]
                }
                for column in connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }
            for table in tables
        }
    finally:
        connection.close()
