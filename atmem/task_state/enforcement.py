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


# --- per-adapter Amendment A capabilities -----------------------------------
#
# Session binding and the agent-facing delta tool are not properties of the
# runtime; they are properties of a *host*. OpenClaw supplies a reset signal and
# registers the tool, another adapter may do neither, and one boolean cannot
# describe both truthfully. So these follow the same shape as guard enforcement
# above: adapter-keyed and derived, not a constant anyone can edit.
#
# An adapter appears in a list only while it can actually do the thing.

_SESSION_BINDING_ADAPTERS: dict[str, str] = {}
_HOST_PROPOSAL_ADAPTERS: dict[str, str] = {}
_AGENT_DELTA_TOOL_ADAPTERS: dict[str, str] = {}


def register_session_binding(adapter: str, *, reset_signal: str) -> None:
    """Declare that this adapter supplies a session generation.

    `reset_signal` names the host value that changes when a conversation is
    reset. Requiring it means the registration states *how* the claim is met
    rather than merely asserting it -- an adapter with nothing to name here
    cannot bind, and must report the capability unavailable instead.
    """
    name = str(adapter or "").strip()
    if not name:
        raise ValueError("a session-binding adapter must be named")
    if not str(reset_signal or "").strip():
        raise ValueError(
            "a session-binding adapter must name the host value that rotates on "
            "reset; without one a recycled conversation would inherit a binding"
        )
    _SESSION_BINDING_ADAPTERS[name] = str(reset_signal)


def register_host_proposal(adapter: str) -> None:
    """Declare that this adapter can submit authenticated session-bound requests."""
    name = str(adapter or "").strip()
    if not name:
        raise ValueError("a host-proposal adapter must be named")
    _HOST_PROPOSAL_ADAPTERS[name] = name


def register_agent_delta_tool(adapter: str, *, tool_name: str) -> None:
    """Declare that this adapter registers the typed-delta tool with its model.

    A control-plane operation the model cannot see is not path (b). Naming the
    tool is what makes the claim checkable at the tool boundary.
    """
    name = str(adapter or "").strip()
    if not name:
        raise ValueError("an agent-tool adapter must be named")
    if not str(tool_name or "").strip():
        raise ValueError(
            "an agent-tool adapter must name the tool it registers; an "
            "unregistered tool is invisible to the model and must not be claimed"
        )
    _AGENT_DELTA_TOOL_ADAPTERS[name] = str(tool_name)


def session_binding_adapters() -> tuple[str, ...]:
    return tuple(sorted(_SESSION_BINDING_ADAPTERS))


def host_proposal_adapters() -> tuple[str, ...]:
    return tuple(sorted(_HOST_PROPOSAL_ADAPTERS))


def agent_delta_tool_adapters() -> tuple[str, ...]:
    return tuple(sorted(_AGENT_DELTA_TOOL_ADAPTERS))


def unregister_amendment_capabilities(adapter: str) -> None:
    """Drop every Amendment A registration for one adapter, for tests."""
    name = str(adapter)
    _SESSION_BINDING_ADAPTERS.pop(name, None)
    _HOST_PROPOSAL_ADAPTERS.pop(name, None)
    _AGENT_DELTA_TOOL_ADAPTERS.pop(name, None)


# OpenClaw earns all three today. Recorded here rather than in the bridge so the
# runtime response and the adapter cannot drift apart: T058 pins that OpenClaw
# declares `sessionId` on every hook AtMem resolves identity in, the bridge
# registers `task_report_progress`, and both are exercised by the journey test.
register_session_binding("openclaw", reset_signal="sessionId")
register_host_proposal("openclaw")
register_agent_delta_tool("openclaw", tool_name="task_report_progress")
