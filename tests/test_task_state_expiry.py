"""Expiry: absolute age, no-progress age, and what pausing does to each.

The two clocks behave differently on purpose. Absolute age runs from creation
and keeps running while paused, so a task cannot be parked indefinitely.
No-progress age measures only active time, so deliberately pausing work is not
itself treated as failing to make progress.

Every test here drives an injected clock. Nothing depends on wall time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ExpiryPolicy,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock
from atmem.store.sqlite import SQLiteStore
from atmem.task_state import GENERAL_V1
from atmem.task_state.profiles import ProfileRegistry
from atmem.task_state.service import TaskStateError, TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
HOUR_MS = 60 * 60 * 1000


def _profile(**expiry) -> TaskProfile:
    from dataclasses import replace

    return replace(
        GENERAL_V1, version="expiry-v1", expiry=ExpiryPolicy(**expiry)
    )


class _Registry(ProfileRegistry):
    """A registry that serves one test profile alongside the built-ins."""

    def __init__(self, store, profile: TaskProfile) -> None:
        super().__init__(store)
        self.profile = profile

    def get(self, version: str):
        if version == self.profile.version:
            return self.profile
        return super().get(version)


def _service(
    tmp_path: Path, clock: FixedUtcClock, profile: TaskProfile
) -> tuple[TaskStateService, SQLiteStore]:
    store = SQLiteStore(tmp_path / "tasks.db")
    return TaskStateService(store, clock=clock, registry=_Registry(store, profile)), store


def _start(service: TaskStateService, profile: TaskProfile, **overrides):
    base = dict(
        task_id="task-1", scope=SCOPE, profile_id=profile.profile_id,
        profile_version=profile.version, goal="Ship the migration",
        actor="operator@example.com", actor_role=ActorRole.OPERATOR,
        idempotency_key="start-1",
    )
    base.update(overrides)
    return service.start(
        TaskStartRequest(**base),
        items=(TaskItem(item_id="item-1", kind="step", title="First"),),
    )


def _progress(service: TaskStateService, revision: int, key: str):
    return service.submit(
        TaskStateProposal(
            proposal_id=f"proposal-{key}", task_id="task-1", scope=SCOPE,
            base_revision=revision, idempotency_key=key, actor="agent",
            actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
            operations=(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            ),
        )
    )


# --- no expiry rule ---------------------------------------------------------


def test_a_task_without_an_expiry_rule_never_expires(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile()
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(days=3650)

        view = service.get(SCOPE, "task-1")
        assert view.state.lifecycle is TaskLifecycle.OPEN
    finally:
        store.close()


# --- absolute age -----------------------------------------------------------


def test_absolute_age_expires_exactly_at_the_threshold(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=2 * HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)

        clock.advance(hours=1, minutes=59, seconds=59)
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.OPEN

        clock.advance(seconds=1)
        view = service.get(SCOPE, "task-1")
        assert view.state.lifecycle is TaskLifecycle.EXPIRED
        assert view.task["terminal_reason"] == "expired_absolute_age"
    finally:
        store.close()


def test_absolute_age_keeps_running_while_paused(tmp_path: Path) -> None:
    """Pausing must not become a way to park a task forever."""
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=2 * HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        service.pause(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
            reason="waiting on approval",
        )
        clock.advance(hours=3)

        view = service.get(SCOPE, "task-1")
        assert view.state.lifecycle is TaskLifecycle.EXPIRED
        assert view.task["terminal_reason"] == "expired_absolute_age"
    finally:
        store.close()


# --- no-progress age --------------------------------------------------------


def test_no_progress_age_expires_when_nothing_advances(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=59)
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.OPEN

        clock.advance(minutes=1)
        view = service.get(SCOPE, "task-1")
        assert view.state.lifecycle is TaskLifecycle.EXPIRED
        assert view.task["terminal_reason"] == "expired_no_progress"
    finally:
        store.close()


def test_accepted_progress_resets_the_no_progress_clock(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=50)
        result = _progress(service, 1, "delta-1")
        assert result.outcome is StepOutcome.ACCEPTED

        clock.advance(minutes=50)
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.OPEN

        clock.advance(minutes=11)
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.EXPIRED
    finally:
        store.close()


def test_a_no_change_step_does_not_reset_the_no_progress_clock(
    tmp_path: Path,
) -> None:
    """Repeating yourself is not progress, and must not postpone expiry."""
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=50)
        repeated = service.submit(
            TaskStateProposal(
                proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
                base_revision=1, idempotency_key="delta-1", actor="agent",
                actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
                operations=(
                    TaskOperation(kind=OperationKind.SET_PHASE, phase="plan"),
                ),
            )
        )
        assert repeated.outcome is StepOutcome.NO_CHANGE

        clock.advance(minutes=11)
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.EXPIRED
    finally:
        store.close()


def test_no_progress_age_excludes_a_completed_pause(tmp_path: Path) -> None:
    """An intentional pause cannot itself cause a no-progress expiry."""
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=30)
        service.pause(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
            reason="waiting on approval",
        )
        clock.advance(hours=5)
        service.resume(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)

        # Five paused hours do not count; only the 30 active minutes do.
        view = service.get(SCOPE, "task-1")
        assert view.state.lifecycle is TaskLifecycle.OPEN
        status = service.expiry_status(view.task)
        assert status["paused_ms"] == 5 * HOUR_MS
        assert status["no_progress_age_ms"] == 30 * 60 * 1000

        clock.advance(minutes=31)
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.EXPIRED
    finally:
        store.close()


def test_no_progress_age_excludes_a_currently_open_pause(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=30)
        service.pause(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
            reason="waiting",
        )
        clock.advance(hours=10)

        view = service.get(SCOPE, "task-1")
        assert view.state.lifecycle is TaskLifecycle.PAUSED, (
            "an open pause is subtracted live, so the task has not aged out"
        )
        status = service.expiry_status(view.task)
        assert status["no_progress_age_ms"] == 30 * 60 * 1000
    finally:
        store.close()


def test_multiple_pause_and_resume_cycles_accumulate(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        for _ in range(3):
            clock.advance(minutes=10)
            service.pause(
                SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
                reason="waiting",
            )
            clock.advance(hours=2)
            service.resume(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)

        view = service.get(SCOPE, "task-1")
        status = service.expiry_status(view.task)

        assert view.state.lifecycle is TaskLifecycle.OPEN
        assert status["paused_ms"] == 6 * HOUR_MS
        assert status["no_progress_age_ms"] == 30 * 60 * 1000
    finally:
        store.close()


def test_pause_accounting_is_identical_after_a_restart(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=30)
        service.pause(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
            reason="waiting",
        )
        clock.advance(hours=5)
        service.resume(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)
        before = service.expiry_status(service.get(SCOPE, "task-1").task)
    finally:
        store.close()

    reopened_store = SQLiteStore(tmp_path / "tasks.db")
    reopened = TaskStateService(
        reopened_store, clock=clock, registry=_Registry(reopened_store, profile)
    )
    try:
        after = reopened.expiry_status(reopened.get(SCOPE, "task-1").task)
        assert after["paused_ms"] == before["paused_ms"]
        assert after["no_progress_age_ms"] == before["no_progress_age_ms"]
    finally:
        reopened_store.close()


def test_pause_accounting_matches_the_immutable_revision_chain(
    tmp_path: Path,
) -> None:
    """The stored accumulator is the fast path; history is the audit."""
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_no_progress_age_ms=100 * HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(minutes=10)
        service.pause(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR, reason="a"
        )
        clock.advance(hours=2)
        service.resume(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)
        clock.advance(minutes=10)
        service.pause(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR, reason="b"
        )
        clock.advance(hours=3)
        service.resume(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)

        stored = service.get(SCOPE, "task-1").task["no_progress_paused_ms"]
        rebuilt = store.rebuild_task_pause_accounting("task-1")

        assert stored == 5 * HOUR_MS
        assert rebuilt == stored, "the accumulator must match derivable history"
    finally:
        store.close()


# --- when expiry is evaluated ----------------------------------------------


@pytest.mark.parametrize("trigger", ["read", "proposal", "lifecycle", "list"])
def test_expiry_is_evaluated_lazily_on_every_entry_point(
    tmp_path: Path, trigger: str
) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(hours=2)

        if trigger == "read":
            service.get(SCOPE, "task-1")
        elif trigger == "list":
            service.list(SCOPE)
        elif trigger == "proposal":
            result = _progress(service, 1, "delta-1")
            assert result.outcome is StepOutcome.REJECTED
            assert result.reason_codes == ("task_is_terminal",)
        else:
            with pytest.raises(TaskStateError) as error:
                service.pause(
                    SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
                    reason="too late",
                )
            assert error.value.reason_code == "task_is_terminal"

        stored = store.get_task(
            subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
            workspace_id=SCOPE.workspace_id, task_id="task-1",
        )
        assert stored["lifecycle"] == "expired"
    finally:
        store.close()


def test_the_maintenance_scan_expires_due_tasks_idempotently(
    tmp_path: Path,
) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        for index in range(3):
            _start(
                service, profile, task_id=f"task-{index}",
                idempotency_key=f"start-{index}",
            )
        clock.advance(hours=2)

        first = service.scan_for_expiry()
        second = service.scan_for_expiry()

        assert sorted(first["expired_task_ids"]) == ["task-0", "task-1", "task-2"]
        assert second["expired_task_ids"] == [], "a terminal task is never re-expired"
    finally:
        store.close()


def test_expiry_produces_exactly_one_terminal_transition(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(hours=2)

        for _ in range(5):
            service.get(SCOPE, "task-1")
            service.scan_for_expiry()

        revisions = store.list_task_revisions("task-1")
        expired = [
            row for row in revisions if row["state"].get("lifecycle") == "expired"
        ]
        assert len(expired) == 1, "exactly one expired head, however many evaluations"
        assert revisions[-1]["revision"] == 2
    finally:
        store.close()


def test_expiry_records_the_rule_the_evaluator_and_the_trusted_time(
    tmp_path: Path,
) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(hours=2)
        service.get(SCOPE, "task-1")

        [provenance] = [
            row
            for row in store.list_task_provenance("task-1", target_kind="lifecycle")
            if row["target_id"] == "expired"
        ]
        assert provenance["actor_role"] == "policy_evaluator"
        assert provenance["actor"] == "atmem-policy-evaluator"
        assert provenance["assurance"] == "rule_extracted"
        assert provenance["evidence"][0]["reference_id"] == "expired_absolute_age"
        assert provenance["observed_at_utc"] == "2026-09-05T14:00:00+00:00"

        task = store.get_task(
            subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
            workspace_id=SCOPE.workspace_id, task_id="task-1",
        )
        assert task["clock_source"] == "fixed-utc-v1"
        assert task["expiry_rule"]["max_absolute_age_ms"] == HOUR_MS
    finally:
        store.close()


def test_an_expired_task_cannot_be_mutated_or_reopened(tmp_path: Path) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(hours=2)
        service.get(SCOPE, "task-1")

        rejected = _progress(service, 1, "delta-1")
        assert rejected.outcome is StepOutcome.REJECTED
        assert rejected.reason_codes == ("task_is_terminal",)

        for operation in ("resume", "complete", "cancel"):
            with pytest.raises(TaskStateError) as error:
                getattr(service, operation)(
                    SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
                    reason="try anyway",
                )
            assert error.value.reason_code == "task_is_terminal", operation
    finally:
        store.close()


def test_the_task_expiry_rule_is_bound_at_start_not_read_later(
    tmp_path: Path,
) -> None:
    """Changing a profile must not retroactively expire work already running."""
    from dataclasses import replace

    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=10 * HOUR_MS)
    store = SQLiteStore(tmp_path / "tasks.db")
    registry = _Registry(store, profile)
    service = TaskStateService(store, clock=clock, registry=registry)
    try:
        _start(service, profile)
        # The profile is later replaced with a much stricter rule.
        registry.profile = replace(
            profile, expiry=ExpiryPolicy(max_absolute_age_ms=1)
        )
        clock.advance(hours=2)

        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.OPEN
    finally:
        store.close()


def test_only_the_policy_evaluator_may_expire_a_task(tmp_path: Path) -> None:
    from atmem.task_state.governance import CapabilityDenied, permits

    assert permits(ActorRole.POLICY_EVALUATOR, "expire_task") is True
    for role in (
        ActorRole.OPERATOR,
        ActorRole.ADMINISTRATOR,
        ActorRole.HOST_AGENT,
        ActorRole.ATBOT_INTELLIGENCE,
    ):
        assert permits(role, "expire_task") is False, role

    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        with pytest.raises(CapabilityDenied):
            service._lifecycle(
                SCOPE, "task-1", TaskLifecycle.EXPIRED, actor="op",
                actor_role=ActorRole.ADMINISTRATOR, reason="force it",
            )
    finally:
        store.close()


def test_an_expired_task_is_never_returned_as_active_context(
    tmp_path: Path,
) -> None:
    clock = FixedUtcClock(MOMENT)
    profile = _profile(max_absolute_age_ms=HOUR_MS)
    service, store = _service(tmp_path, clock, profile)
    try:
        _start(service, profile)
        clock.advance(hours=2)

        listing = service.list(SCOPE, lifecycles=("open", "paused"))
        assert listing["tasks"] == [] or all(
            row["lifecycle"] != "open" for row in listing["tasks"]
        )
        assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.EXPIRED
    finally:
        store.close()
