"""Observability that is useful to operate and useless to snoop on.

The two properties under test pull against each other on purpose: the snapshot
must carry enough to run the system, and must carry none of what the tasks
actually say.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import json
import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ExpiryPolicy,
    ItemStatus,
    OperationKind,
    TaskItem,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock, to_iso
from atmem.store.sqlite import SQLiteStore
from atmem.task_state import GENERAL_V1
from atmem.task_state.observability import TaskObservability
from atmem.task_state.profiles import ProfileRegistry
from atmem.task_state.service import TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
OTHER = AuthorityScope("subject-2", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)

SECRET_GOAL = "Migrate the Contoso payroll database using credential hunter2"
SECRET_ITEM = "Rotate the API key sk-live-abcdefghijklmnop"
SECRET_BLOCKER = "Blocked: the vault password is correct-horse-battery-staple"


@pytest.fixture()
def clock() -> FixedUtcClock:
    return FixedUtcClock(MOMENT)


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    engine = SQLiteStore(tmp_path / "tasks.db")
    try:
        yield engine
    finally:
        engine.close()


@pytest.fixture()
def service(store: SQLiteStore, clock: FixedUtcClock) -> TaskStateService:
    return TaskStateService(store, clock=clock)


def seed(
    service: TaskStateService,
    *,
    task_id: str = "task-1",
    scope: AuthorityScope = SCOPE,
    goal: str = SECRET_GOAL,
) -> None:
    service.start(
        TaskStartRequest(
            task_id=task_id, scope=scope, profile_id="general",
            profile_version="general-v1", goal=goal, actor="op",
            actor_role=ActorRole.OPERATOR, idempotency_key=f"start-{task_id}",
        ),
        items=(
            TaskItem(item_id="item-1", kind="step", title=SECRET_ITEM, required=True),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        ),
    )


def propose(service, *operations, task_id="task-1", revision=1, key="delta-1",
            scope=SCOPE, **overrides):
    base = dict(
        proposal_id=f"proposal-{key}", task_id=task_id, scope=scope,
        base_revision=revision, idempotency_key=key, actor="agent",
        actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
    )
    base.update(overrides)
    return service.submit(TaskStateProposal(operations=tuple(operations), **base))


# --- counts and outcomes ----------------------------------------------------


def test_lifecycle_counts_cover_every_value(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service, task_id="task-open")
    seed(service, task_id="task-paused")
    service.pause(SCOPE, "task-paused", actor="op",
                  actor_role=ActorRole.OPERATOR, reason="waiting")
    seed(service, task_id="task-cancelled")
    service.cancel(SCOPE, "task-cancelled", actor="op",
                   actor_role=ActorRole.OPERATOR, reason="not needed")

    counts = TaskObservability(service.store, clock=clock).snapshot(SCOPE)["tasks"]

    assert counts["total"] == 3
    assert counts["by_lifecycle"]["open"] == 1
    assert counts["by_lifecycle"]["paused"] == 1
    assert counts["by_lifecycle"]["cancelled"] == 1
    assert counts["by_lifecycle"]["completed"] == 0
    assert counts["open_or_paused"] == 2


def test_every_transition_outcome_is_counted(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="teatime"),
            revision=2, key="delta-2")
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            revision=2, key="delta-3")
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="execute"),
            revision=1, key="delta-4")

    transitions = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "transitions"
    ]

    assert transitions["by_outcome"]["accepted"] == 2  # start + one transition
    assert transitions["by_outcome"]["rejected"] == 1
    assert transitions["by_outcome"]["no_change"] == 1
    assert transitions["by_outcome"]["conflict"] == 1
    assert transitions["stale_revision_conflicts"] == 1


def test_reason_codes_are_counted_by_name(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="teatime"))

    reasons = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "transitions"
    ]["by_reason_code"]

    assert reasons["illegal_phase_transition"] == 1
    assert list(reasons) == sorted(reasons), "reason counts are stably ordered"


def test_latency_is_reported_as_a_distribution(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))

    latency = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "latency_ms"
    ]

    assert latency["samples"] >= 2
    assert latency["p50"] is not None and latency["p50"] >= 0
    assert latency["p95"] is not None and latency["p95"] >= latency["p50"]


def test_an_empty_scope_reports_zeroes_rather_than_nulls(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    snapshot = TaskObservability(service.store, clock=clock).snapshot(SCOPE)

    assert snapshot["tasks"]["total"] == 0
    assert snapshot["transitions"]["by_outcome"]["accepted"] == 0
    assert snapshot["latency_ms"]["samples"] == 0
    assert snapshot["latency_ms"]["p50"] is None
    assert snapshot["integrity"]["valid"] is True


# --- context disposition ----------------------------------------------------


def test_prepared_exposed_and_withheld_are_counted_separately(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    injected = service.store.insert_task_delivery(
        task_id="task-1", revision=1, subject_id=SCOPE.subject_id,
        agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
        disposition="injected", prepared_at_utc=to_iso(MOMENT),
        context_sha256="sha256:" + "a" * 64,
    )
    service.store.mark_task_delivery_exposed(injected)
    service.store.insert_task_delivery(
        task_id="task-1", revision=1, subject_id=SCOPE.subject_id,
        agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
        disposition="injected", prepared_at_utc=to_iso(MOMENT),
    )
    service.store.insert_task_delivery(
        task_id="task-1", revision=1, subject_id=SCOPE.subject_id,
        agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
        disposition="withheld", prepared_at_utc=to_iso(MOMENT),
        reason_codes=["task_context_budget_exceeded"],
    )

    snapshot = TaskObservability(service.store, clock=clock).snapshot(SCOPE)

    assert snapshot["context"] == {"prepared": 3, "exposed": 1, "withheld": 1}
    assert snapshot["transitions"]["by_reason_code"][
        "task_context_budget_exceeded"
    ] == 1


# --- expiry and freshness ---------------------------------------------------


def test_overdue_tasks_are_surfaced_without_expiring_them(
    store: SQLiteStore, clock: FixedUtcClock
) -> None:
    from dataclasses import replace

    class _Registry(ProfileRegistry):
        def get(self, version: str):
            if version == "expiry-v1":
                return replace(
                    GENERAL_V1, version="expiry-v1",
                    expiry=ExpiryPolicy(max_absolute_age_ms=60_000),
                )
            return super().get(version)

    service = TaskStateService(store, clock=clock, registry=_Registry(store))
    service.start(
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="expiry-v1", goal="Ship it", actor="op",
            actor_role=ActorRole.OPERATOR, idempotency_key="start-1",
        )
    )
    clock.advance(minutes=5)

    snapshot = TaskObservability(store, clock=clock).snapshot(SCOPE)

    assert [row["task_id"] for row in snapshot["overdue_tasks"]] == ["task-1"]
    assert snapshot["overdue_tasks"][0]["reason"] == "expired_absolute_age"
    # Observability observes; it does not mutate.
    assert store.get_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    )["lifecycle"] == "open"


def test_freshness_reports_the_most_recent_progress(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    clock.advance(minutes=10)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    clock.advance(minutes=5)

    freshness = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "freshness"
    ]

    assert freshness["last_progress_at_utc"] == "2026-09-05T12:10:00+00:00"
    assert freshness["no_progress_age_ms"] == 5 * 60 * 1000


# --- integrity --------------------------------------------------------------


def test_integrity_passes_for_a_healthy_chain(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))

    integrity = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "integrity"
    ]
    assert integrity["valid"] is True
    assert integrity["problems"] == []
    assert integrity["checked_tasks"] == 1


def test_integrity_detects_a_head_that_outran_its_revisions(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    service.store._conn.execute(
        "UPDATE governed_tasks SET head_revision = 9 WHERE task_id = 'task-1'"
    )

    integrity = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "integrity"
    ]

    assert integrity["valid"] is False
    assert any("head does not match" in row for row in integrity["problems"])


def test_integrity_detects_a_gap_in_the_revision_chain(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    service.store._conn.execute(
        "DELETE FROM governed_task_revisions WHERE task_id = 'task-1' AND revision = 1"
    )

    integrity = TaskObservability(service.store, clock=clock).snapshot(SCOPE)[
        "integrity"
    ]
    assert integrity["valid"] is False


# --- scope isolation --------------------------------------------------------


def test_metrics_are_scope_filtered(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service, task_id="task-mine")
    seed(service, task_id="task-theirs", scope=OTHER, goal="Another subject's work")

    mine = TaskObservability(service.store, clock=clock).snapshot(SCOPE)
    theirs = TaskObservability(service.store, clock=clock).snapshot(OTHER)

    assert mine["tasks"]["total"] == 1
    assert theirs["tasks"]["total"] == 1
    assert mine["scope"]["subject_id"] == "subject-1"


def test_task_detail_is_not_readable_from_another_scope(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)

    detail = TaskObservability(service.store, clock=clock).task_detail(
        OTHER, "task-1"
    )
    assert detail["found"] is False
    assert "lifecycle" not in detail


# --- content minimization ---------------------------------------------------


def test_no_task_content_appears_anywhere_in_a_snapshot(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(
        service,
        TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
                      status=ItemStatus.BLOCKED, reason=SECRET_BLOCKER),
    )

    snapshot = TaskObservability(service.store, clock=clock).snapshot(SCOPE)
    text = json.dumps(snapshot)

    for secret in (SECRET_GOAL, SECRET_ITEM, SECRET_BLOCKER,
                   "hunter2", "sk-live-abcdefghijklmnop",
                   "correct-horse-battery-staple", "Contoso"):
        assert secret not in text, f"observability leaked {secret!r}"


def test_no_task_content_appears_in_a_task_detail(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(
        service,
        TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
                      status=ItemStatus.BLOCKED, reason=SECRET_BLOCKER),
    )

    detail = TaskObservability(service.store, clock=clock).task_detail(SCOPE, "task-1")
    text = json.dumps(detail)

    for secret in (SECRET_GOAL, SECRET_ITEM, SECRET_BLOCKER, "hunter2"):
        assert secret not in text, f"task detail leaked {secret!r}"


def test_task_detail_still_carries_what_an_operator_needs(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    seed(service)
    propose(service, TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))

    detail = TaskObservability(service.store, clock=clock).task_detail(SCOPE, "task-1")

    assert detail["found"] is True
    assert detail["lifecycle"] == "open"
    assert detail["revision"] == 2
    assert detail["recent_decisions"][-1]["outcome"] == "accepted"
    assert detail["recent_decisions"][-1]["reason_codes"] == ["transition_accepted"]
    assert [row["sequence"] for row in detail["recent_decisions"]] == sorted(
        row["sequence"] for row in detail["recent_decisions"]
    ), "decisions are returned in a stable order"
