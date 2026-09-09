"""Versioned lifecycle contracts and transition matrix."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXCLUDED = "excluded"
    ARCHIVED = "archived"
    FORGOTTEN = "forgotten"


ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.ACTIVE: frozenset({LifecycleState.SUPERSEDED, LifecycleState.EXCLUDED, LifecycleState.ARCHIVED, LifecycleState.FORGOTTEN}),
    LifecycleState.QUARANTINED: frozenset({LifecycleState.ACTIVE, LifecycleState.REJECTED, LifecycleState.FORGOTTEN}),
    LifecycleState.REJECTED: frozenset({LifecycleState.QUARANTINED, LifecycleState.FORGOTTEN}),
    LifecycleState.SUPERSEDED: frozenset({LifecycleState.ARCHIVED, LifecycleState.FORGOTTEN}),
    LifecycleState.EXCLUDED: frozenset({LifecycleState.ACTIVE, LifecycleState.ARCHIVED, LifecycleState.FORGOTTEN}),
    LifecycleState.ARCHIVED: frozenset({LifecycleState.ACTIVE, LifecycleState.FORGOTTEN}),
    LifecycleState.FORGOTTEN: frozenset(),
}


@dataclass(frozen=True, slots=True)
class LifecyclePolicy:
    policy_id: str
    scope_id: str
    priority: int = 100
    review_after_days: int | None = None
    expire_after_days: int | None = None
    archive_after_days: int | None = None
    automatic: bool = False
    format: str = "atmem-lifecycle-policy-v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    record_id: str
    subject_id: str
    to_state: LifecycleState
    base_generation: int
    actor: str
    reason: str
    evidence: tuple[str, ...] = ()
    occurred_at: str | None = None


@dataclass(frozen=True, slots=True)
class TransitionReceipt:
    transition_id: str
    record_id: str
    subject_id: str
    from_state: LifecycleState
    to_state: LifecycleState
    base_generation: int
    resulting_generation: int
    actor: str
    reason: str
    occurred_at: str
    invalidations: dict[str, Any]
    format: str = "atmem-lifecycle-transition-receipt-v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["from_state"] = self.from_state.value
        value["to_state"] = self.to_state.value
        return value
