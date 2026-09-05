"""Explainable warnings, never executed actions.

AtMem can see that an agent has tried the same thing three times without
getting anywhere, or that it is about to declare victory with required work
outstanding. What AtMem cannot do is stop it: the host owns execution. So every
signal here is a *detection* that says what it saw and why, and `enforced`
stays false unless an adapter reports that it actually blocked something.

Claiming prevention we do not perform would be the worst kind of safety theatre,
so the contract makes the distinction explicit rather than implied.
"""

from __future__ import annotations

from typing import Any

from atmem.contracts.task_state import (
    GuardSignal,
    GuardType,
    ItemStatus,
    TaskProfile,
    TaskState,
)
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.task_state.models import completion_blockers, dependencies_satisfied


def action_fingerprint(
    *,
    action: str,
    target: str | None = None,
    arguments: dict[str, Any] | None = None,
) -> str:
    """A stable identity for "the agent did this same thing again".

    The target is part of the identity on purpose: legitimately repeating one
    action across different task items is normal work, not a stuck loop.
    """
    identity = {
        "action": str(action),
        "target": target,
        "arguments": arguments or {},
    }
    return f"sha256:{sha256_hex(canonical_json(identity))}"


def evaluate_no_progress(
    store: Any,
    state: TaskState,
    profile: TaskProfile,
    *,
    fingerprint: str,
    since_utc: str,
) -> GuardSignal | None:
    """Warn when equivalent actions keep happening and nothing advances.

    `since_utc` is the last accepted progress, so the count resets the moment
    real movement happens rather than accumulating over the task's whole life.
    """
    threshold = int(profile.no_progress_action_threshold)
    repeats = store.count_recent_equivalent_actions(
        state.task_id, fingerprint, since_utc=since_utc
    )
    if repeats < threshold:
        return None
    return GuardSignal(
        guard_type=GuardType.NO_PROGRESS,
        task_id=state.task_id,
        revision=state.revision,
        message=(
            f"The same action has run {repeats} times since the last accepted "
            f"progress at {since_utc}. Nothing has advanced."
        ),
        repeated_action_count=repeats,
        enforced=False,
    )


def evaluate_dependencies(state: TaskState) -> GuardSignal | None:
    """Warn about work that cannot start because something else is unfinished."""
    waiting = [
        item.item_id
        for item in state.items
        if item.status in {ItemStatus.PENDING, ItemStatus.READY}
        and not dependencies_satisfied(state, item)
    ]
    if not waiting:
        return None
    return GuardSignal(
        guard_type=GuardType.DEPENDENCY_UNSATISFIED,
        task_id=state.task_id,
        revision=state.revision,
        message=(
            f"{len(waiting)} item(s) cannot start until their dependencies are "
            "settled."
        ),
        blocking_item_ids=tuple(waiting),
        enforced=False,
    )


def evaluate_completion_guard(
    state: TaskState, profile: TaskProfile
) -> GuardSignal | None:
    """Deny completion while the profile's gates are unsatisfied."""
    blockers = completion_blockers(state, profile)
    if not blockers:
        return None
    return GuardSignal(
        guard_type=GuardType.COMPLETION_NOT_ALLOWED,
        task_id=state.task_id,
        revision=state.revision,
        message=(
            "Completion is not allowed yet: "
            f"{len(blockers)} requirement(s) are unsatisfied."
        ),
        blocking_item_ids=blockers,
        enforced=False,
    )


def out_of_scope_signal(task_id: str, revision: int) -> GuardSignal:
    """A request touched a task the caller has no authority over."""
    return GuardSignal(
        guard_type=GuardType.OUT_OF_SCOPE,
        task_id=task_id,
        revision=max(1, int(revision)),
        message="This task is outside the requesting authority scope.",
        enforced=False,
    )


def evaluate_all(
    store: Any,
    state: TaskState,
    profile: TaskProfile,
    *,
    fingerprint: str | None = None,
    since_utc: str | None = None,
) -> tuple[GuardSignal, ...]:
    """Every signal that currently applies, in a stable order."""
    signals: list[GuardSignal] = []
    dependency = evaluate_dependencies(state)
    if dependency is not None:
        signals.append(dependency)
    completion = evaluate_completion_guard(state, profile)
    if completion is not None:
        signals.append(completion)
    if fingerprint and since_utc:
        no_progress = evaluate_no_progress(
            store, state, profile, fingerprint=fingerprint, since_utc=since_utc
        )
        if no_progress is not None:
            signals.append(no_progress)
    return tuple(signals)
