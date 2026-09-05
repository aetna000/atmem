"""Governed task state is off until someone turns it on, for one exact scope.

FR-018 is a promise to existing installations: upgrading AtMem must not start
influencing an agent. So enablement is explicit, per scope, and recorded — and
"enabled" is separate from "active", because shadow mode records and evaluates
proposals without ever injecting task state into a model call.

The setting lives in the ordinary audit log rather than a new table: it is a
decision someone made, and it belongs in the same tamper-evident chain as every
other decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atmem.contracts import AuthorityScope


ENABLED_EVENT = "task_state.scope_enabled"
DISABLED_EVENT = "task_state.scope_disabled"


@dataclass(frozen=True, slots=True)
class ScopeMode:
    """Whether task state runs for a scope, and how far it is allowed to go."""

    enabled: bool
    shadow: bool

    @property
    def records(self) -> bool:
        """Shadow mode still evaluates and records; it just never injects."""
        return self.enabled

    @property
    def influences_agent(self) -> bool:
        return self.enabled and not self.shadow

    @property
    def label(self) -> str:
        if not self.enabled:
            return "disabled"
        return "shadow" if self.shadow else "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-task-state-mode-v1",
            "mode": self.label,
            "enabled": self.enabled,
            "shadow": self.shadow,
            "influences_agent": self.influences_agent,
        }


DISABLED = ScopeMode(enabled=False, shadow=False)


class ScopeEnablement:
    """Reads and writes the per-scope task-state setting."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def mode(self, scope: AuthorityScope) -> ScopeMode:
        """The current setting. Absence means disabled, never "probably fine"."""
        latest: dict[str, Any] | None = None
        for event in self.store.list_audit_events(scope.subject_id):
            if str(event.get("event_type")) not in {ENABLED_EVENT, DISABLED_EVENT}:
                continue
            payload = event.get("payload") or {}
            if (
                payload.get("agent_id") != scope.agent_id
                or payload.get("workspace_id") != scope.workspace_id
            ):
                continue
            latest = event
        if latest is None:
            return DISABLED
        if str(latest["event_type"]) == DISABLED_EVENT:
            return DISABLED
        return ScopeMode(
            enabled=True, shadow=bool((latest.get("payload") or {}).get("shadow"))
        )

    def enable(
        self, scope: AuthorityScope, *, actor: str, shadow: bool = False
    ) -> ScopeMode:
        self.store.append_audit_event(
            subject_id=scope.subject_id,
            event_type=ENABLED_EVENT,
            actor=actor,
            session_id=None,
            turn_id=None,
            payload={
                "agent_id": scope.agent_id,
                "workspace_id": scope.workspace_id,
                "shadow": bool(shadow),
            },
        )
        return ScopeMode(enabled=True, shadow=bool(shadow))

    def disable(self, scope: AuthorityScope, *, actor: str) -> ScopeMode:
        self.store.append_audit_event(
            subject_id=scope.subject_id,
            event_type=DISABLED_EVENT,
            actor=actor,
            session_id=None,
            turn_id=None,
            payload={
                "agent_id": scope.agent_id,
                "workspace_id": scope.workspace_id,
            },
        )
        return DISABLED
