"""Fresh-recall authorization using the ordinary AtMem control plane.

This is the trusted service-side binding, not an HTTP authentication boundary.
The installer/service supplies identity; model tool arguments cannot change it.
It deliberately makes no claim about replayed Hermes conversation history.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Any

from atmem.adapters.base import AtMemAdapterIdentity
from atmem.core.canonical import canonical_json
from atmem.service import APIError, APIPrincipal, AtMemApplication


PROFILE = "authorized-at-recall-v1"


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ValueError(f"{name} must be a nonempty identifier of at most 512 characters")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{name} contains a control character")
    return value


@dataclass(frozen=True, slots=True)
class RecallResult:
    context: str
    reason: str
    candidate_ids: tuple[str, ...] = ()
    exposure_id: str | None = None
    receipt_id: str | None = None
    profile: str = PROFILE


class HermesMemoryBinding:
    """One immutable administrator-selected identity, checked on each operation.

    Constructed inactive. Enabling the binding does not activate the control
    plane: both this explicit selection and AtMem's own active policy are needed.
    No query/context cache is retained. Background scheduling belongs to the host
    bridge; these methods return only after the product operation has finished.
    """

    def __init__(self, manager: Any, identity: AtMemAdapterIdentity, *,
                 profile_id: str, enabled: bool = False, max_context_chars: int = 4096):
        self.manager = manager
        self.identity = replace(identity, framework="hermes")
        self.profile_id = _identifier(profile_id, "profile_id")
        for name in ("agent_id", "workspace_id", "subject_id"):
            _identifier(getattr(identity, name), name)
        if not identity.authenticated_user:
            raise PermissionError("Hermes binding requires an authenticated operator identity")
        if isinstance(max_context_chars, bool) or not isinstance(max_context_chars, int) or not 1 <= max_context_chars <= 4096:
            raise ValueError("max_context_chars must be between 1 and 4096")
        self.enabled = bool(enabled)
        self.max_context_chars = max_context_chars
        self.application = AtMemApplication(manager)

    def _scope(self) -> None:
        """Topology, not request content, binds agent/subject/workspace."""
        topology = self.manager.agent_topology()
        workspaces = topology.get("workspaces", [])
        match = any(
            row.get("workspace_id") == self.identity.workspace_id
            and row.get("subject_id") == self.identity.subject_id
            and self.identity.agent_id in (row.get("agent_ids") or [])
            for row in workspaces
        )
        subject_rows = [row for row in workspaces if row.get("subject_id") == self.identity.subject_id]
        agent_rows = [row for row in workspaces if self.identity.agent_id in (row.get("agent_ids") or [])]
        if not match or len(subject_rows) != 1 or len(agent_rows) != 1:
            raise PermissionError("Hermes binding no longer matches AtMem topology")

    def _session(self, session_id: str) -> str:
        value = [_identifier(self.profile_id, "profile_id"), _identifier(session_id, "session_id")]
        return "hermes_" + hashlib.sha256(canonical_json(value).encode()).hexdigest()

    def recall(self, query: str, *, session_id: str, turn_id: str) -> RecallResult:
        if not self.enabled:
            return RecallResult("", "inactive")
        if not isinstance(query, str) or not query.strip() or len(query) > 65536:
            return RecallResult("", "invalid_query")
        try:
            self._scope()
            session = self._session(session_id)
            turn = _identifier(turn_id, "turn_id")
            prepared = self.manager.prepare(
                query, allow_delegation=False, session_id=session,
                host_run_id=session, turn_id=turn,
                workspace_id=self.identity.workspace_id,
                subject_id=self.identity.subject_id, agent_id=self.identity.agent_id,
                max_chars=self.max_context_chars,
            )
            if not prepared.get("inject"):
                # Shadow previews must never be returned as active context.
                return RecallResult("", "withheld")
            context = prepared.get("context")
            if not isinstance(context, str) or not context:
                return RecallResult("", "no_context")
            if len(context) > self.max_context_chars:
                return RecallResult("", "context_limit")
            # Only fresh canonical preparation can supply bytes. Do not fall
            # back to a previous successful recall if this operation fails.
            return RecallResult(
                context, "authorized",
                tuple(str(value) for value in prepared.get("candidate_ids", [])),
                prepared.get("exposure_id"), prepared.get("context_receipt_id"),
            )
        except (OSError, RuntimeError, ValueError, TypeError, PermissionError):
            # Never disclose exception details (paths/queries/provider secrets)
            # in a model-facing result. No successful-delivery receipt is made.
            return RecallResult("", "unavailable_or_denied")

    def observe_user(self, text: str, *, session_id: str, observation_id: str) -> dict[str, Any]:
        """Persist an authenticated user's source via ordinary governed capture.

        Assistant summaries and tool output are not authenticated user messages;
        the host bridge must not feed them to this method as such.
        """
        if not self.enabled:
            return {"captured": False, "reason": "inactive"}
        self._scope()
        if not isinstance(text, str) or not text.strip() or len(text) > 65536:
            raise ValueError("user text must contain 1–65536 characters")
        session = self._session(session_id)
        observation = _identifier(observation_id, "observation_id")
        key = hashlib.sha256(canonical_json([session, observation]).encode()).hexdigest()
        principal = APIPrincipal(
            principal_id=self.profile_id, role="agent",
            subject_id=str(self.identity.subject_id), agent_id=self.identity.agent_id,
            workspace_id=self.identity.workspace_id,
        )
        try:
            return self.application.create_memory(
                principal, text, idempotency_key=key, session_id=session,
            )
        except APIError:
            raise
        except Exception:
            raise APIError("observation_uncertain", "inspect the observation receipt before retrying", status=409) from None

    def status(self) -> dict[str, Any]:
        return {
            "profile": PROFILE, "enabled": self.enabled,
            "profile_id": self.profile_id, "agent_id": self.identity.agent_id,
            "workspace_id": self.identity.workspace_id,
            "capture_coverage": "memory_operations_only",
            "per_model_call_revalidation": False,
            "previous_context_retraction": False,
        }
