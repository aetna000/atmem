"""Domain helpers over the task-state contracts.

The contracts in `atmem.contracts.task_state` describe shape. This module
describes meaning: how a snapshot changes when an operation is applied, which
items are actually ready to work on, and whether a task may complete.

Applying an operation always returns a *new* snapshot. Revisions are immutable,
so nothing here mutates a state in place.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from atmem.contracts.task_state import (
    Assurance,
    ItemStatus,
    OperationKind,
    TaskConstraint,
    TaskItem,
    TaskOperation,
    TaskProfile,
    TaskState,
)


# An item may move between these statuses. Settled work does not silently
# reopen: returning a completed item to active work is an operator correction,
# not an ordinary agent transition.
LEGAL_STATUS_TRANSITIONS: dict[ItemStatus, frozenset[ItemStatus]] = {
    # Pending work may be picked up and finished directly: an agent that does
    # the work and reports it done should not have to stage a "ready" hop.
    ItemStatus.PENDING: frozenset(
        {
            ItemStatus.READY,
            ItemStatus.RUNNING,
            ItemStatus.BLOCKED,
            ItemStatus.COMPLETED,
            ItemStatus.SKIPPED,
            ItemStatus.FAILED,
        }
    ),
    ItemStatus.READY: frozenset(
        {
            ItemStatus.RUNNING,
            ItemStatus.BLOCKED,
            ItemStatus.COMPLETED,
            ItemStatus.SKIPPED,
            ItemStatus.FAILED,
        }
    ),
    ItemStatus.RUNNING: frozenset(
        {ItemStatus.COMPLETED, ItemStatus.BLOCKED, ItemStatus.FAILED, ItemStatus.READY}
    ),
    ItemStatus.BLOCKED: frozenset(
        {ItemStatus.READY, ItemStatus.SKIPPED, ItemStatus.FAILED, ItemStatus.PENDING}
    ),
    ItemStatus.FAILED: frozenset({ItemStatus.READY, ItemStatus.SKIPPED}),
    ItemStatus.COMPLETED: frozenset(),
    ItemStatus.SKIPPED: frozenset(),
}

# Transitions that represent real forward movement. Only these refresh the
# no-progress clock; re-describing an item is not progress.
PROGRESS_STATUSES = frozenset(
    {ItemStatus.RUNNING, ItemStatus.COMPLETED, ItemStatus.SKIPPED}
)


def allows_status_transition(current: ItemStatus, target: ItemStatus) -> bool:
    if current is target:
        return True
    return target in LEGAL_STATUS_TRANSITIONS[current]


def dependencies_satisfied(state: TaskState, item: TaskItem) -> bool:
    """True when everything this item waits on is settled."""
    for dependency_id in item.depends_on:
        dependency = state.item(dependency_id)
        if dependency is None or not dependency.status.settled:
            return False
    return True


def ready_items(state: TaskState) -> tuple[TaskItem, ...]:
    """Items that could be worked on right now, in stable order."""
    return tuple(
        item
        for item in state.items
        if item.status in {ItemStatus.PENDING, ItemStatus.READY}
        and dependencies_satisfied(state, item)
    )


def blocked_items(state: TaskState) -> tuple[TaskItem, ...]:
    return tuple(
        item
        for item in state.items
        if item.status is ItemStatus.BLOCKED
        or (
            item.status in {ItemStatus.PENDING, ItemStatus.READY}
            and not dependencies_satisfied(state, item)
        )
    )


def remaining_items(state: TaskState) -> tuple[TaskItem, ...]:
    return tuple(item for item in state.items if not item.status.settled)


def completion_blockers(state: TaskState, profile: TaskProfile) -> tuple[str, ...]:
    """Exactly what still stands between this task and completion."""
    blocking: list[str] = []
    for item in state.items:
        if item.required and not item.status.settled:
            blocking.append(item.item_id)
    for kind in profile.required_item_kinds:
        matching = [item for item in state.items if item.kind == kind]
        if not matching or any(not item.status.settled for item in matching):
            blocking.append(f"kind:{kind}")
    for constraint in state.constraints:
        if constraint.required_for_completion and not constraint.satisfied:
            blocking.append(f"constraint:{constraint.constraint_id}")
    return tuple(dict.fromkeys(blocking))


def may_complete(state: TaskState, profile: TaskProfile) -> bool:
    return not completion_blockers(state, profile)


def is_progress(operation: TaskOperation, state: TaskState) -> bool:
    """Whether applying this operation would be semantic forward movement."""
    if operation.kind is OperationKind.SET_ITEM_STATUS:
        item = state.item(str(operation.item_id))
        if item is None or operation.status is None:
            return False
        return operation.status is not item.status and operation.status in PROGRESS_STATUSES
    return operation.kind in {
        OperationKind.SET_PHASE,
        OperationKind.SATISFY_CONSTRAINT,
        OperationKind.MARK_SOURCE_INSPECTED,
    }


def apply_operations(
    state: TaskState,
    operations: Iterable[TaskOperation],
    *,
    revision: int,
    updated_at: str,
    last_progress_at: str | None = None,
) -> TaskState:
    """Return the snapshot that results from applying every operation.

    Callers validate first; this function assumes the operations are already
    known to be legal and simply computes the successor snapshot.
    """
    items = list(state.items)
    constraints = list(state.constraints)
    phase = state.phase
    completed_sources = list(state.completed_sources)
    schema_locked = state.schema_locked

    for operation in operations:
        if operation.kind is OperationKind.SET_PHASE:
            phase = str(operation.phase)
        elif operation.kind is OperationKind.SET_ITEM_STATUS:
            items = _replace_item(
                items,
                str(operation.item_id),
                lambda item: replace(
                    item,
                    status=operation.status or item.status,
                    blocker_reason=(
                        operation.reason
                        if operation.status is ItemStatus.BLOCKED
                        else None
                    ),
                    skip_reason=(
                        operation.reason
                        if operation.status is ItemStatus.SKIPPED
                        else item.skip_reason
                    ),
                    assurance=_stronger(item.assurance, operation.assurance),
                ),
            )
        elif operation.kind is OperationKind.ADD_ITEM:
            items.append(
                TaskItem(
                    item_id=str(operation.item_id),
                    kind=str(operation.kind_label),
                    title=str(operation.text),
                    status=operation.status or ItemStatus.PENDING,
                    content=dict(operation.content or {}),
                    depends_on=tuple(operation.depends_on or ()),
                    required=bool(operation.required),
                    assurance=operation.assurance,
                )
            )
        elif operation.kind is OperationKind.SET_ITEM_CONTENT:
            items = _replace_item(
                items,
                str(operation.item_id),
                lambda item: replace(item, content=dict(operation.content or {})),
            )
        elif operation.kind is OperationKind.SET_ITEM_BLOCKER:
            items = _replace_item(
                items,
                str(operation.item_id),
                lambda item: replace(
                    item,
                    status=ItemStatus.BLOCKED,
                    blocker_reason=str(operation.reason or "blocked"),
                ),
            )
        elif operation.kind is OperationKind.ADD_CONSTRAINT:
            constraints.append(
                TaskConstraint(
                    constraint_id=str(operation.constraint_id),
                    text=str(operation.text),
                    required_for_completion=(
                        True if operation.required is None else bool(operation.required)
                    ),
                )
            )
        elif operation.kind is OperationKind.SATISFY_CONSTRAINT:
            constraints = [
                replace(row, satisfied=True)
                if row.constraint_id == str(operation.constraint_id)
                else row
                for row in constraints
            ]
        elif operation.kind is OperationKind.MARK_SOURCE_INSPECTED:
            if str(operation.source_id) not in completed_sources:
                completed_sources.append(str(operation.source_id))
        elif operation.kind is OperationKind.LOCK_SCHEMA:
            schema_locked = True

    return replace(
        state,
        revision=revision,
        parent_revision=state.revision,
        phase=phase,
        items=tuple(items),
        constraints=tuple(constraints),
        completed_sources=tuple(completed_sources),
        schema_locked=schema_locked,
        updated_at=updated_at,
        last_progress_at=last_progress_at or state.last_progress_at,
    )


def summarize(state: TaskState, profile: TaskProfile) -> dict[str, Any]:
    """The plain-language view a person reads before any identifier."""
    blockers = completion_blockers(state, profile)
    return {
        "goal": state.goal,
        "lifecycle": state.lifecycle.value,
        "phase": state.phase,
        "revision": state.revision,
        "total_items": len(state.items),
        "completed_items": sum(
            1 for item in state.items if item.status is ItemStatus.COMPLETED
        ),
        "skipped_items": sum(
            1 for item in state.items if item.status is ItemStatus.SKIPPED
        ),
        "failed_items": sum(
            1 for item in state.items if item.status is ItemStatus.FAILED
        ),
        "blocked_items": [item.item_id for item in blocked_items(state)],
        "ready_items": [item.item_id for item in ready_items(state)],
        "remaining_items": [item.item_id for item in remaining_items(state)],
        "unsatisfied_constraints": [
            row.constraint_id for row in state.constraints if not row.satisfied
        ],
        "completion_allowed": not blockers,
        "completion_blockers": list(blockers),
        "last_progress_at": state.last_progress_at,
    }


def _replace_item(items: list[TaskItem], item_id: str, change: Any) -> list[TaskItem]:
    return [change(item) if item.item_id == item_id else item for item in items]


def _stronger(current: Assurance, proposed: Assurance) -> Assurance:
    return proposed if proposed.rank > current.rank else current
