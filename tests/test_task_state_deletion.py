"""Forgetting a task, and proving it is actually gone.

Deletion has to remove more than the row a person can see: revisions, the
content inside them, provenance, proposals, steps, and delivery records all
carry task content or its shape. What survives is a receipt carrying digests
and counts, never the goal text itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ItemStatus,
    OperationKind,
    TaskItem,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock, to_iso
from atmem.memory import Memory
from atmem.store.sqlite import SQLiteStore
from atmem.task_state.governance import CapabilityDenied
from atmem.task_state.service import TaskStateError, TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
OTHER = AuthorityScope("subject-2", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)

SECRET_GOAL = "Migrate the Contoso payroll database"
SECRET_ITEM = "Rotate the vault credential hunter2"
SECRET_BLOCKER = "Waiting on approval from finance-director@contoso.example"

TASK_TABLES = (
    "governed_tasks",
    "governed_task_revisions",
    "governed_task_provenance",
    "governed_task_proposals",
    "governed_task_steps",
    "governed_task_deliveries",
)


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    engine = SQLiteStore(tmp_path / "tasks.db")
    try:
        yield engine
    finally:
        engine.close()


@pytest.fixture()
def service(store: SQLiteStore) -> TaskStateService:
    return TaskStateService(store, clock=FixedUtcClock(MOMENT))


def seed(
    service: TaskStateService, task_id: str = "task-1", *, scope=SCOPE
) -> None:
    """A task with content in every place content can hide."""
    service.start(
        TaskStartRequest(
            task_id=task_id, scope=scope, profile_id="general",
            profile_version="general-v1", goal=SECRET_GOAL, actor="operator",
            actor_role=ActorRole.OPERATOR, idempotency_key=f"start-{task_id}",
        ),
        items=(
            TaskItem(item_id="item-1", kind="step", title=SECRET_ITEM),
            TaskItem(item_id="item-2", kind="step", title="Second step"),
        ),
    )
    service.submit(
        TaskStateProposal(
            proposal_id=f"proposal-{task_id}", task_id=task_id, scope=scope,
            base_revision=1, idempotency_key=f"delta-{task_id}", actor="agent",
            actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
            operations=(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
                    status=ItemStatus.BLOCKED, reason=SECRET_BLOCKER,
                ),
            ),
        )
    )
    service.store.insert_task_delivery(
        task_id=task_id, revision=2, subject_id=scope.subject_id,
        agent_id=scope.agent_id, workspace_id=scope.workspace_id,
        disposition="injected", prepared_at_utc=to_iso(MOMENT),
        context_sha256="sha256:" + "a" * 64,
    )


def _remaining(store: SQLiteStore, task_id: str) -> dict[str, int]:
    return {
        table: int(
            store._conn.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE task_id = ?",
                (task_id,),
            ).fetchone()["total"]
        )
        for table in TASK_TABLES
        if table != "governed_tasks"
    } | {
        "governed_tasks": int(
            store._conn.execute(
                "SELECT COUNT(*) AS total FROM governed_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()["total"]
        )
    }


def _database_text(store: SQLiteStore) -> str:
    """Everything still readable in the task tables, as one blob."""
    parts: list[str] = []
    for table in TASK_TABLES:
        for row in store._conn.execute(f"SELECT * FROM {table}").fetchall():
            parts.append(json.dumps({key: str(row[key]) for key in row.keys()}))
    return "\n".join(parts)


# --- what deletion removes --------------------------------------------------


def test_forgetting_a_task_removes_every_derived_row(
    service: TaskStateService, store: SQLiteStore
) -> None:
    seed(service)
    before = _remaining(store, "task-1")
    assert all(count > 0 for count in before.values()), before

    service.forget(SCOPE, "task-1", actor="admin",
                   actor_role=ActorRole.ADMINISTRATOR)

    after = _remaining(store, "task-1")
    assert after == {table: 0 for table in after}, after


def test_no_task_content_survives_anywhere_in_the_task_tables(
    service: TaskStateService, store: SQLiteStore
) -> None:
    seed(service)
    assert SECRET_GOAL in _database_text(store)

    service.forget(SCOPE, "task-1", actor="admin",
                   actor_role=ActorRole.ADMINISTRATOR)

    remaining = _database_text(store)
    for secret in (SECRET_GOAL, SECRET_ITEM, SECRET_BLOCKER, "hunter2", "Contoso"):
        assert secret not in remaining, f"deletion left {secret!r} behind"


def test_the_head_is_unreachable_after_deletion(
    service: TaskStateService,
) -> None:
    seed(service)
    service.forget(SCOPE, "task-1", actor="admin",
                   actor_role=ActorRole.ADMINISTRATOR)

    with pytest.raises(TaskStateError) as error:
        service.get(SCOPE, "task-1")
    assert error.value.reason_code == "task_not_eligible"


def test_deleting_one_task_leaves_its_neighbours_intact(
    service: TaskStateService, store: SQLiteStore
) -> None:
    seed(service, "task-1")
    seed(service, "task-2")

    service.forget(SCOPE, "task-1", actor="admin",
                   actor_role=ActorRole.ADMINISTRATOR)

    assert service.get(SCOPE, "task-2").state.revision == 2
    assert _remaining(store, "task-2")["governed_task_revisions"] == 2


# --- the receipt ------------------------------------------------------------


def test_the_receipt_records_what_was_removed_without_the_content(
    service: TaskStateService,
) -> None:
    seed(service)

    receipt = service.forget(
        SCOPE, "task-1", actor="admin@example.com",
        actor_role=ActorRole.ADMINISTRATOR,
    )

    assert receipt["format"] == "atmem-task-deletion-receipt-v1"
    assert receipt["deleted"] is True
    assert receipt["task_id"] == "task-1"
    assert receipt["revisions_removed"] == 2
    assert receipt["actor"] == "admin@example.com"
    assert receipt["goal_sha256"].startswith("sha256:")
    assert SECRET_GOAL not in json.dumps(receipt)


def test_the_receipt_digest_verifies_which_task_was_deleted(
    service: TaskStateService,
) -> None:
    from atmem.core.canonical import sha256_hex

    seed(service)
    receipt = service.forget(SCOPE, "task-1", actor="admin",
                             actor_role=ActorRole.ADMINISTRATOR)

    assert receipt["goal_sha256"] == f"sha256:{sha256_hex(SECRET_GOAL)}"


def test_the_receipt_counts_every_table_it_touched(
    service: TaskStateService,
) -> None:
    seed(service)
    receipt = service.forget(SCOPE, "task-1", actor="admin",
                             actor_role=ActorRole.ADMINISTRATOR)

    for table in TASK_TABLES:
        assert table in receipt["removed"], table


# --- authority --------------------------------------------------------------


def test_deletion_requires_the_deletion_capability(
    service: TaskStateService,
) -> None:
    seed(service)

    for role in (ActorRole.OPERATOR, ActorRole.HOST_AGENT,
                 ActorRole.ATBOT_INTELLIGENCE, ActorRole.AUDITOR):
        with pytest.raises(CapabilityDenied):
            service.forget(SCOPE, "task-1", actor="someone", actor_role=role)
    assert service.get(SCOPE, "task-1").state.revision == 2


def test_a_task_cannot_be_deleted_from_another_scope(
    service: TaskStateService, store: SQLiteStore
) -> None:
    seed(service)

    with pytest.raises(TaskStateError) as error:
        service.forget(OTHER, "task-1", actor="admin",
                       actor_role=ActorRole.ADMINISTRATOR)

    assert error.value.reason_code == "task_not_eligible"
    assert _remaining(store, "task-1")["governed_tasks"] == 1


def test_deleting_an_unknown_task_is_refused_non_disclosingly(
    service: TaskStateService,
) -> None:
    seed(service)

    with pytest.raises(TaskStateError) as unknown:
        service.forget(SCOPE, "task-nope", actor="admin",
                       actor_role=ActorRole.ADMINISTRATOR)
    with pytest.raises(TaskStateError) as unauthorized:
        service.forget(OTHER, "task-1", actor="admin",
                       actor_role=ActorRole.ADMINISTRATOR)

    assert str(unknown.value) == str(unauthorized.value)


# --- subject deletion -------------------------------------------------------


def test_forgetting_a_subject_removes_all_of_its_governed_tasks(
    service: TaskStateService, store: SQLiteStore
) -> None:
    seed(service, "task-1")
    seed(service, "task-2")
    seed(service, "task-other", scope=OTHER)

    result = store.delete_subject_tasks(SCOPE.subject_id)

    assert result["deleted"] == 2
    assert sorted(result["task_ids"]) == ["task-1", "task-2"]
    assert _remaining(store, "task-1")["governed_tasks"] == 0
    assert _remaining(store, "task-other")["governed_tasks"] == 1


def test_resetting_a_subject_also_clears_its_task_plane(tmp_path: Path) -> None:
    """Memory deletion must not leave a subject's task state behind."""
    memory = Memory(tmp_path / "memories.db", auto_vectors=False)
    try:
        service = TaskStateService(memory.store, clock=FixedUtcClock(MOMENT))
        seed(service)
        memory.remember(SCOPE.subject_id, "My preferred airport is Melbourne.")

        memory.store.reset_subject(SCOPE.subject_id)

        assert memory.store.list_tasks(subject_id=SCOPE.subject_id) == []
        assert _database_text(memory.store) == ""
        assert memory.list(SCOPE.subject_id, include_inactive=True) == []
    finally:
        memory.close()


def test_deleting_a_subject_leaves_other_subjects_untouched(
    tmp_path: Path,
) -> None:
    memory = Memory(tmp_path / "memories.db", auto_vectors=False)
    try:
        service = TaskStateService(memory.store, clock=FixedUtcClock(MOMENT))
        seed(service, "task-1")
        seed(service, "task-other", scope=OTHER)

        memory.store.reset_subject(SCOPE.subject_id)

        assert memory.store.list_tasks(subject_id=SCOPE.subject_id) == []
        assert len(memory.store.list_tasks(subject_id=OTHER.subject_id)) == 1
    finally:
        memory.close()


# --- deletion is not rewriting ---------------------------------------------


def test_history_may_be_deleted_but_never_rewritten(
    service: TaskStateService, store: SQLiteStore
) -> None:
    import sqlite3

    seed(service)

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store._conn.execute(
            "UPDATE governed_task_revisions SET actor = 'someone-else' "
            "WHERE task_id = 'task-1'"
        )
    # Deletion, on the other hand, is permitted for verified erasure.
    service.forget(SCOPE, "task-1", actor="admin",
                   actor_role=ActorRole.ADMINISTRATOR)
    assert _remaining(store, "task-1")["governed_task_revisions"] == 0
