"""Governed Task State: a separate authority plane for execution state.

Durable memory answers "what do we know about this person?". Task state
answers "what is this agent doing right now, what is left, and is it allowed to
finish?". Keeping them apart is the point: temporary workflow progress must not
become permanent personal memory, and a host's own checkpoints, planner, or
session state stay the host's.

AtBot and hosts may propose typed deltas. AtMem alone validates scope,
transition legality, evidence, and concurrency, and alone commits a revision.

This package imports no optional intelligence or framework SDK.
"""

from __future__ import annotations

from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ContextDisposition,
    EvidenceRef,
    ExpiryPolicy,
    GovernanceCapability,
    GuardSignal,
    GuardType,
    ItemStatus,
    OperationKind,
    Provenance,
    StepOutcome,
    TaskConstraint,
    TaskContextPackage,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskStartRequest,
    TaskState,
    TaskStateProposal,
    TransitionDecision,
)
from atmem.task_state.models import (
    allows_status_transition,
    apply_operations,
    blocked_items,
    completion_blockers,
    dependencies_satisfied,
    is_progress,
    may_complete,
    ready_items,
    remaining_items,
    summarize,
)
from atmem.task_state.profiles import (
    BUILT_IN_PROFILES,
    GENERAL_V1,
    ProfileRegistration,
    ProfileRegistry,
)

__all__ = [
    "ActorRole",
    "Assurance",
    "BUILT_IN_PROFILES",
    "ContextDisposition",
    "EvidenceRef",
    "ExpiryPolicy",
    "GENERAL_V1",
    "GovernanceCapability",
    "GuardSignal",
    "GuardType",
    "ItemStatus",
    "OperationKind",
    "ProfileRegistration",
    "ProfileRegistry",
    "Provenance",
    "StepOutcome",
    "TaskConstraint",
    "TaskContextPackage",
    "TaskItem",
    "TaskLifecycle",
    "TaskOperation",
    "TaskProfile",
    "TaskStartRequest",
    "TaskState",
    "TaskStateProposal",
    "TransitionDecision",
    "allows_status_transition",
    "apply_operations",
    "blocked_items",
    "completion_blockers",
    "dependencies_satisfied",
    "is_progress",
    "may_complete",
    "ready_items",
    "remaining_items",
    "summarize",
]
