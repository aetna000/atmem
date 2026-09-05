"""Session-to-task bindings: registration, revocation, and resolution.

Spec 007 Amendment A, FR-042/FR-043/FR-052.

AtMem must never choose which task an agent is working on. A binding is how a
conversation gets a task without AtMem choosing: an authenticated operator says
"this conversation is that task", AtMem records it, and later turns *look it
up*. Resolving a recorded authorization is not inference, discovery, or
selection among open tasks.

Two properties are load-bearing and easy to lose:

* The resolver returns exactly one task id or exactly one refusal. It never
  returns a candidate list. If no layer can produce candidates, selection
  cannot be reintroduced later without deleting this contract outright.
* Every identity part is required together. Hosts declare `sessionId`,
  `sessionKey`, and their owner signal as optional, so absence is ordinary,
  and resolving on whatever survived would be guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3
from typing import Any
import uuid

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    BindingResolution,
    EvidenceRef,
    HostSessionIdentity,
    SessionBinding,
    TaskProfile,
)
from atmem.core.time import TrustedUtcClock


class BindingError(ValueError):
    """A binding request AtMem refuses, with a stable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class ResolvedTask:
    """The single answer: one task, or one reason there is none.

    `task_id` is set exactly when `resolution.delivers` is true. There is no
    third state and no candidate collection, by design.
    """

    resolution: BindingResolution
    task_id: str | None = None
    reason_code: str | None = None
    binding_id: str | None = None

    def __post_init__(self) -> None:
        if self.resolution.delivers and not self.task_id:
            raise ValueError("a delivering resolution must name exactly one task")
        if not self.resolution.delivers and self.task_id:
            raise ValueError("a withholding resolution must name no task")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


class SessionBindingService:
    """Register, revoke, list, and resolve bindings against one store."""

    def __init__(self, store: Any, clock: TrustedUtcClock) -> None:
        self._store = store
        self._clock = clock

    # --- registration ------------------------------------------------------

    def register(
        self,
        scope: AuthorityScope,
        identity: HostSessionIdentity,
        *,
        task_id: str,
        actor: str,
        reason: str,
        source: str = "",
        profile: TaskProfile | None = None,
        evidence: tuple[EvidenceRef, ...] = (),
    ) -> SessionBinding:
        """Bind one conversation to one task.

        The caller is responsible for having authorized `actor` as an operator
        and for having checked the task is eligible; this records the decision
        and enforces the uniqueness key.
        """
        now = self._clock.now()
        expires_at = None
        lifetime = getattr(profile, "binding_lifetime_ms", None) if profile else None
        if lifetime:
            expires_at = (now + timedelta(milliseconds=int(lifetime))).isoformat()

        binding = SessionBinding(
            binding_id=f"binding-{uuid.uuid4().hex}",
            scope=scope,
            identity=identity,
            task_id=task_id,
            actor=actor,
            reason=reason,
            source=source,
            registered_at_utc=now.isoformat(),
            evidence=evidence,
        )
        try:
            self._store.insert_session_binding(
                binding_id=binding.binding_id,
                subject_id=scope.subject_id,
                agent_id=scope.agent_id,
                workspace_id=scope.workspace_id,
                host_type=identity.host_type,
                session_key=identity.session_key,
                session_epoch=identity.session_epoch,
                task_id=task_id,
                actor=actor,
                reason=reason,
                source=source,
                evidence=[item.to_dict() for item in evidence],
                registered_at_utc=binding.registered_at_utc,
                expires_at_utc=expires_at,
            )
        except sqlite3.IntegrityError as exc:
            # Retargeting is deliberately not expressible as an update: the
            # operator must revoke and register, each with its own authority
            # and evidence, so a repoint is never a silent side effect.
            raise BindingError(
                "binding_already_active",
                "this conversation already has an active binding; revoke it "
                "before binding it to a different task",
            ) from exc
        return binding

    def revoke(
        self,
        scope: AuthorityScope,
        *,
        binding_id: str,
        actor: str,
        reason: str,
    ) -> None:
        revoked = self._store.revoke_session_binding(
            binding_id=binding_id,
            subject_id=scope.subject_id,
            agent_id=scope.agent_id,
            workspace_id=scope.workspace_id,
            revoked_at_utc=self._clock.now().isoformat(),
            revoked_by=actor,
            revoked_reason=reason,
        )
        if not revoked:
            # Non-disclosing: a binding in another scope and a binding that
            # never existed produce the same answer.
            raise BindingError(
                "binding_not_found", "no active binding matches that identifier"
            )

    def list(
        self,
        scope: AuthorityScope,
        *,
        task_id: str | None = None,
        include_revoked: bool = False,
    ) -> list[dict[str, Any]]:
        return self._store.list_session_bindings(
            subject_id=scope.subject_id,
            agent_id=scope.agent_id,
            workspace_id=scope.workspace_id,
            task_id=task_id,
            include_revoked=include_revoked,
        )

    # --- resolution --------------------------------------------------------

    def resolve(
        self,
        scope: AuthorityScope,
        *,
        identity: HostSessionIdentity | None,
        explicit_task_id: str | None = None,
    ) -> ResolvedTask:
        """Answer which task this call is for, in one fixed total order.

        Explicit host identity, then an active registered binding, then
        withhold. Nothing else. When the first two disagree we withhold rather
        than pick: preferring the explicit id would silently mask a
        misconfigured binding, and preferring the binding would let stale
        operator state override a host that knows better. Only withholding
        surfaces the contradiction to someone who can fix it.
        """
        explicit = (explicit_task_id or "").strip() or None
        bound = self._active_binding(scope, identity) if identity else None

        if explicit and bound and bound["task_id"] != explicit:
            return ResolvedTask(
                BindingResolution.CONFLICT, reason_code="task_binding_conflict"
            )
        if explicit:
            return ResolvedTask(
                BindingResolution.EXPLICIT,
                task_id=explicit,
                binding_id=bound["binding_id"] if bound else None,
            )
        if bound:
            return ResolvedTask(
                BindingResolution.BOUND,
                task_id=bound["task_id"],
                binding_id=bound["binding_id"],
            )
        if identity and self._stale_generation(scope, identity):
            # This conversation *was* bound, under a generation that is no
            # longer current. Inheriting it is the exact failure FR-052 exists
            # to prevent, so it withholds distinguishably from "never bound"
            # and requires an explicit operator re-confirmation.
            return ResolvedTask(
                BindingResolution.STALE_SESSION,
                reason_code="task_binding_stale_session",
            )
        return ResolvedTask(
            BindingResolution.NONE, reason_code="task_context_selection_required"
        )

    def _active_binding(
        self, scope: AuthorityScope, identity: HostSessionIdentity
    ) -> dict[str, Any] | None:
        row = self._store.find_active_session_binding(
            subject_id=scope.subject_id,
            agent_id=scope.agent_id,
            workspace_id=scope.workspace_id,
            host_type=identity.host_type,
            session_key=identity.session_key,
            session_epoch=identity.session_epoch,
        )
        if row is None:
            return None
        if self._expired(row):
            return None
        return row

    def _expired(self, row: dict[str, Any]) -> bool:
        """Supplemental lifetime only. It never stands in for a reset signal."""
        expires_at = row.get("expires_at_utc")
        if not expires_at:
            return False
        return self._clock.now() >= _parse_utc(str(expires_at))

    def _stale_generation(
        self, scope: AuthorityScope, identity: HostSessionIdentity
    ) -> bool:
        """Was this session key bound under some other, or now-expired, generation?

        Used only to choose which refusal to give. It never returns a binding
        and never influences which task is used.
        """
        rows = self._store.find_active_bindings_for_session_key(
            subject_id=scope.subject_id,
            agent_id=scope.agent_id,
            workspace_id=scope.workspace_id,
            host_type=identity.host_type,
            session_key=identity.session_key,
        )
        return any(
            row["session_epoch"] != identity.session_epoch or self._expired(row)
            for row in rows
        )


__all__ = ["BindingError", "ResolvedTask", "SessionBindingService"]
