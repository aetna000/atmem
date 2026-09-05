"""Guards: what AtMem noticed, and the line it does not cross.

Every assertion here is about honesty as much as detection. AtMem can say "you
have done this three times and nothing moved" or "you cannot finish yet". It
cannot say it stopped anything, because the host owns execution.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    GuardType,
    ItemStatus,
    OperationKind,
    TaskConstraint,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskStartRequest,
    TaskState,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock, to_iso
from atmem.store.sqlite import SQLiteStore
from atmem.task_state import GENERAL_V1
from atmem.task_state.guards import (
    action_fingerprint,
    evaluate_all,
    evaluate_completion_guard,
    evaluate_dependencies,
    evaluate_no_progress,
    out_of_scope_signal,
)
from atmem.task_state.service import TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def state(**overrides) -> TaskState:
    base = dict(
        task_id="task-1", scope=SCOPE, revision=3, lifecycle=TaskLifecycle.OPEN,
        phase="execute", goal="Ship it", profile_id="general",
        profile_version="general-v1",
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        ),
    )
    base.update(overrides)
    return TaskState(**base)


@pytest.fixture()
def service(tmp_path: Path) -> TaskStateService:
    store = SQLiteStore(tmp_path / "tasks.db")
    engine = TaskStateService(store, clock=FixedUtcClock(MOMENT))
    try:
        yield engine
    finally:
        store.close()


# --- action identity --------------------------------------------------------


def test_the_same_action_on_the_same_target_has_one_fingerprint() -> None:
    first = action_fingerprint(action="click", target="item-1", arguments={"x": 1})
    second = action_fingerprint(action="click", target="item-1", arguments={"x": 1})

    assert first == second
    assert first.startswith("sha256:")


def test_argument_order_does_not_change_the_fingerprint() -> None:
    assert action_fingerprint(
        action="call", target="t", arguments={"a": 1, "b": 2}
    ) == action_fingerprint(action="call", target="t", arguments={"b": 2, "a": 1})


def test_the_same_action_on_a_different_item_is_a_different_action() -> None:
    """Legitimately repeating work across items is not a stuck loop."""
    assert action_fingerprint(action="click", target="item-1") != action_fingerprint(
        action="click", target="item-2"
    )


def test_different_arguments_are_different_actions() -> None:
    assert action_fingerprint(
        action="search", target="item-1", arguments={"q": "invoices"}
    ) != action_fingerprint(
        action="search", target="item-1", arguments={"q": "receipts"}
    )


# --- no progress ------------------------------------------------------------


def test_repeating_an_action_below_the_threshold_raises_nothing(
    service: TaskStateService,
) -> None:
    _seed(service)
    fingerprint = action_fingerprint(action="click", target="item-1")
    for _ in range(2):
        _record(service, fingerprint)

    assert evaluate_no_progress(
        service.store, state(), GENERAL_V1,
        fingerprint=fingerprint, since_utc=to_iso(MOMENT),
    ) is None


def test_reaching_the_threshold_produces_an_explainable_signal(
    service: TaskStateService,
) -> None:
    _seed(service)
    fingerprint = action_fingerprint(action="click", target="item-1")
    for _ in range(3):
        _record(service, fingerprint)

    guard = evaluate_no_progress(
        service.store, state(), GENERAL_V1,
        fingerprint=fingerprint, since_utc=to_iso(MOMENT),
    )

    assert guard is not None
    assert guard.guard_type is GuardType.NO_PROGRESS
    assert guard.repeated_action_count == 3
    assert "3 times" in guard.message
    assert "Nothing has advanced" in guard.message
    assert guard.enforced is False, "AtMem detects; it does not prevent"


def test_distinct_actions_do_not_accumulate_toward_the_threshold(
    service: TaskStateService,
) -> None:
    _seed(service)
    for index in range(5):
        _record(service, action_fingerprint(action="click", target=f"item-{index}"))

    guard = evaluate_no_progress(
        service.store, state(), GENERAL_V1,
        fingerprint=action_fingerprint(action="click", target="item-0"),
        since_utc=to_iso(MOMENT),
    )
    assert guard is None


def test_accepted_progress_resets_the_repeat_window(
    service: TaskStateService,
) -> None:
    """`since_utc` is the last accepted progress, so the count starts over."""
    clock = FixedUtcClock(MOMENT)
    _seed(service)
    fingerprint = action_fingerprint(action="click", target="item-1")
    for _ in range(3):
        clock.advance(seconds=10)
        _record(service, fingerprint, at=to_iso(clock.now()))

    progressed_at = to_iso(clock.now())
    clock.advance(seconds=10)
    _record(service, fingerprint, at=to_iso(clock.now()))

    before = evaluate_no_progress(
        service.store, state(), GENERAL_V1,
        fingerprint=fingerprint, since_utc=to_iso(MOMENT),
    )
    after = evaluate_no_progress(
        service.store, state(), GENERAL_V1,
        fingerprint=fingerprint, since_utc=progressed_at,
    )

    assert before is not None and before.repeated_action_count == 4
    assert after is None, "only actions since the last progress count"


def test_a_profile_may_set_its_own_repeat_threshold(
    service: TaskStateService,
) -> None:
    from dataclasses import replace

    _seed(service)
    fingerprint = action_fingerprint(action="click", target="item-1")
    for _ in range(2):
        _record(service, fingerprint)

    patient = replace(GENERAL_V1, no_progress_action_threshold=5)
    impatient = replace(GENERAL_V1, no_progress_action_threshold=2)

    assert evaluate_no_progress(
        service.store, state(), patient, fingerprint=fingerprint,
        since_utc=to_iso(MOMENT),
    ) is None
    assert evaluate_no_progress(
        service.store, state(), impatient, fingerprint=fingerprint,
        since_utc=to_iso(MOMENT),
    ) is not None


# --- dependencies -----------------------------------------------------------


def test_work_waiting_on_unfinished_dependencies_is_reported() -> None:
    guard = evaluate_dependencies(state())

    assert guard is not None
    assert guard.guard_type is GuardType.DEPENDENCY_UNSATISFIED
    assert guard.blocking_item_ids == ("item-2",)
    assert guard.enforced is False


def test_no_dependency_signal_once_the_blocker_is_settled() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First",
                     status=ItemStatus.COMPLETED, required=True),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        )
    )
    assert evaluate_dependencies(current) is None


def test_a_skipped_dependency_also_unblocks_its_dependents() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First",
                     status=ItemStatus.SKIPPED, skip_reason="Not needed"),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        )
    )
    assert evaluate_dependencies(current) is None


def test_an_already_blocked_item_is_not_double_reported() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First",
                     status=ItemStatus.BLOCKED, blocker_reason="waiting"),
        )
    )
    assert evaluate_dependencies(current) is None, (
        "a blocked item is its own status, not a dependency problem"
    )


# --- completion -------------------------------------------------------------


def test_premature_completion_is_denied_and_names_what_blocks_it() -> None:
    guard = evaluate_completion_guard(state(), GENERAL_V1)

    assert guard is not None
    assert guard.guard_type is GuardType.COMPLETION_NOT_ALLOWED
    assert guard.blocking_item_ids == ("item-1",)
    assert "not allowed yet" in guard.message
    assert guard.enforced is False


def test_an_unsatisfied_constraint_blocks_completion() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True,
                     status=ItemStatus.COMPLETED),
        ),
        constraints=(TaskConstraint(constraint_id="c-1", text="Sign off"),),
    )
    guard = evaluate_completion_guard(current, GENERAL_V1)

    assert guard is not None
    assert guard.blocking_item_ids == ("constraint:c-1",)


def test_completion_is_allowed_once_everything_required_is_settled() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True,
                     status=ItemStatus.COMPLETED),
            TaskItem(item_id="item-2", kind="step", title="Optional extra"),
        )
    )
    assert evaluate_completion_guard(current, GENERAL_V1) is None


def test_skipping_counts_as_settled_for_completion() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True,
                     status=ItemStatus.SKIPPED, skip_reason="Out of scope"),
        )
    )
    assert evaluate_completion_guard(current, GENERAL_V1) is None


def test_a_failed_item_still_blocks_completion() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True,
                     status=ItemStatus.FAILED),
        )
    )
    guard = evaluate_completion_guard(current, GENERAL_V1)
    assert guard is not None and guard.blocking_item_ids == ("item-1",)


# --- scope ------------------------------------------------------------------


def test_an_out_of_scope_request_produces_a_non_disclosing_signal() -> None:
    guard = out_of_scope_signal("task-1", 3)

    assert guard.guard_type is GuardType.OUT_OF_SCOPE
    assert guard.enforced is False
    assert "outside the requesting authority scope" in guard.message
    assert guard.blocking_item_ids == ()


# --- combined ---------------------------------------------------------------


def test_all_applicable_signals_are_returned_in_a_stable_order(
    service: TaskStateService,
) -> None:
    _seed(service)
    fingerprint = action_fingerprint(action="click", target="item-1")
    for _ in range(3):
        _record(service, fingerprint)

    signals = evaluate_all(
        service.store, state(), GENERAL_V1,
        fingerprint=fingerprint, since_utc=to_iso(MOMENT),
    )

    assert [row.guard_type for row in signals] == [
        GuardType.DEPENDENCY_UNSATISFIED,
        GuardType.COMPLETION_NOT_ALLOWED,
        GuardType.NO_PROGRESS,
    ]
    assert all(row.enforced is False for row in signals)


def test_a_healthy_task_produces_no_signals() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True,
                     status=ItemStatus.COMPLETED),
        )
    )
    assert evaluate_all(None, current, GENERAL_V1) == ()


def test_detection_is_never_reported_as_enforcement() -> None:
    """No code path may set `enforced` without an adapter proving it."""
    import inspect

    from atmem.task_state import guards

    source = inspect.getsource(guards)
    assert "enforced=True" not in source, (
        "only an adapter that reports blocking may claim enforcement"
    )


# --- helpers ----------------------------------------------------------------


def _seed(service: TaskStateService) -> None:
    service.start(
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="general-v1", goal="Ship it", actor="op",
            actor_role=ActorRole.OPERATOR, idempotency_key="start-1",
        ),
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        ),
    )


def _record(service: TaskStateService, fingerprint: str, *, at: str | None = None) -> None:
    service.store.insert_task_step(
        task_id="task-1", step_kind="tool_result", outcome="no_change",
        base_revision=1, actor="agent", recorded_at_utc=at or to_iso(MOMENT),
        action_fingerprint=fingerprint,
    )
