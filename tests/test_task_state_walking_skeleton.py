"""The narrowest end-to-end proof that governed task state works.

One profile, three operations, a process restart. No AtBot, no semantic
services, no guards, no dashboard, no adapters. If this fails, nothing built on
top of it is trustworthy; if it passes, the authority core is real.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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
from atmem.store.sqlite import SQLiteStore
from atmem.task_state.service import TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _service(path: Path, clock: FixedUtcClock) -> tuple[TaskStateService, SQLiteStore]:
    store = SQLiteStore(path)
    return TaskStateService(store, clock=clock), store


def _proposal(*operations, base_revision: int, key: str) -> TaskStateProposal:
    return TaskStateProposal(
        proposal_id=f"proposal-{key}",
        task_id="task-1",
        scope=SCOPE,
        base_revision=base_revision,
        idempotency_key=key,
        actor="agent",
        actor_role=ActorRole.HOST_AGENT,
        assurance=Assurance.HOST_REPORTED,
        operations=tuple(operations),
    )


def test_start_advance_and_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "tasks.db"
    clock = FixedUtcClock(MOMENT)
    service, store = _service(path, clock)

    try:
        # 1. Start: revision 1 with a stable identity and three items.
        view = service.start(
            TaskStartRequest(
                task_id="task-1",
                scope=SCOPE,
                profile_id="general",
                profile_version="general-v1",
                goal="Ship the billing migration",
                actor="operator@example.com",
                actor_role=ActorRole.OPERATOR,
                idempotency_key="start-1",
                constraints=("Do not touch production data",),
            ),
            items=(
                TaskItem(item_id="item-1", kind="step", title="Snapshot the database"),
                TaskItem(item_id="item-2", kind="step", title="Run the migration",
                         depends_on=("item-1",)),
                TaskItem(item_id="item-3", kind="step", title="Notify the team"),
            ),
        )

        assert view.state.revision == 1
        assert view.state.lifecycle is TaskLifecycle.OPEN
        assert view.state.phase == "plan"
        assert view.summary["ready_items"] == ["item-1", "item-3"]
        assert view.summary["blocked_items"] == ["item-2"], (
            "item-2 waits on item-1, so it is not ready work"
        )

        # 2. Advance one item.
        clock.advance(minutes=5)
        completed = service.submit(
            _proposal(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                    status=ItemStatus.COMPLETED,
                ),
                base_revision=1, key="delta-1",
            )
        )
        assert completed.outcome is StepOutcome.ACCEPTED
        assert completed.resulting_revision == 2

        # 3. Block another, with the reason recorded.
        clock.advance(minutes=5)
        blocked = service.submit(
            _proposal(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS, item_id="item-3",
                    status=ItemStatus.BLOCKED, reason="Waiting on the release window",
                ),
                base_revision=2, key="delta-2",
            )
        )
        assert blocked.outcome is StepOutcome.ACCEPTED
        assert blocked.resulting_revision == 3

        # 4. An unchanged observation is `no_change`, not a new revision.
        clock.advance(minutes=1)
        unchanged = service.submit(
            _proposal(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                    status=ItemStatus.COMPLETED,
                ),
                base_revision=3, key="delta-3",
            )
        )
        assert unchanged.outcome is StepOutcome.NO_CHANGE
        assert unchanged.reason_codes == ("state_already_matches",)
        assert unchanged.resulting_revision == 3, "no_change does not advance the head"
    finally:
        store.close()

    # 5. A fresh process reads exactly the same head.
    reopened_service, reopened_store = _service(path, FixedUtcClock(MOMENT))
    try:
        view = reopened_service.get(SCOPE, "task-1")

        assert view.state.revision == 3
        assert view.state.goal == "Ship the billing migration"
        assert view.summary["completed_items"] == 1
        # item-2 became workable the moment its dependency was completed.
        assert view.summary["ready_items"] == ["item-2"]
        assert view.summary["blocked_items"] == ["item-3"]
        assert view.summary["remaining_items"] == ["item-2", "item-3"]
        assert view.state.item("item-3").blocker_reason == (
            "Waiting on the release window"
        )
        assert view.state.item("item-1").status is ItemStatus.COMPLETED

        # The history is intact and every step was recorded exactly once.
        timeline = reopened_service.timeline(SCOPE, "task-1")
        assert [row["revision"] for row in timeline["revisions"]] == [1, 2, 3]
        assert [row["outcome"] for row in timeline["steps"]] == [
            "accepted", "accepted", "accepted", "no_change",
        ]
    finally:
        reopened_store.close()


def test_the_skeleton_runs_without_any_optional_dependency(tmp_path: Path) -> None:
    """Task state must work with no model, no vectors, and no network."""
    import sys

    before = set(sys.modules)
    service, store = _service(tmp_path / "tasks.db", FixedUtcClock(MOMENT))
    try:
        service.start(
            TaskStartRequest(
                task_id="task-1", scope=SCOPE, profile_id="general",
                profile_version="general-v1", goal="Do the thing",
                actor="op", actor_role=ActorRole.OPERATOR,
                idempotency_key="start-1",
            )
        )
    finally:
        store.close()

    newly_imported = set(sys.modules) - before
    for forbidden in ("atbot", "torch", "sentence_transformers", "openai", "requests"):
        assert not any(name.startswith(forbidden) for name in newly_imported), (
            f"governed task state must not pull in {forbidden}"
        )
