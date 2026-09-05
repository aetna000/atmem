"""Which adapters actually stop a host action, if any.

AtMem detects that completion is not allowed or that an agent has repeated
itself with nothing to show. It cannot *prevent* the host from calling a tool —
the host owns execution. So the capability response must not claim enforcement
on AtMem's behalf.

But a hardcoded `False` is a weak guarantee: anyone can edit a constant. This
registry makes the claim derived instead. An adapter earns the enforcement flag
by registering a callable that reports which actions it actually blocked, and
the capability response reads the registry. The flag cannot be turned on by
editing a boolean, and it cannot be left stale once a real enforcing adapter
exists.

The registry is empty today, so the runtime honestly reports `False`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class GuardEnforcer(Protocol):
    """An adapter that can genuinely refuse to run a host action."""

    adapter: str

    def blocked_actions(self) -> tuple[str, ...]:
        """The actions this adapter has actually prevented, for evidence."""
        ...


@dataclass(frozen=True, slots=True)
class EnforcementRegistration:
    adapter: str
    enforcer: GuardEnforcer
    evidence: Callable[[], dict[str, Any]] | None = None


_REGISTRY: dict[str, EnforcementRegistration] = {}


def register_enforcer(
    adapter: str,
    enforcer: GuardEnforcer,
    *,
    evidence: Callable[[], dict[str, Any]] | None = None,
) -> None:
    """Declare that one adapter really does block actions AtMem denies.

    Registering is a claim the adapter must be able to back with evidence:
    `blocked_actions()` is what a conformance test reads to confirm the
    boundary is real rather than asserted.
    """
    name = str(adapter or "").strip()
    if not name:
        raise ValueError("an enforcing adapter must be named")
    if not isinstance(enforcer, GuardEnforcer):
        raise TypeError(
            "an enforcer must expose blocked_actions() so its claim is checkable"
        )
    _REGISTRY[name] = EnforcementRegistration(name, enforcer, evidence)


def unregister_enforcer(adapter: str) -> None:
    _REGISTRY.pop(str(adapter), None)


def enforcing_adapters() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def guard_enforcement_available() -> bool:
    """True only while at least one adapter can actually block an action."""
    return bool(_REGISTRY)
