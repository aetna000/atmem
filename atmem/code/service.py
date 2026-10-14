"""Authenticated local intake for opt-in coding-agent observations."""

from __future__ import annotations

from hashlib import sha256
import hmac
import json
from typing import Any

from atmem.code.contracts import CodeObservation, CodeScope
from atmem.core.canonical import canonical_json
from atmem.extract.validation import screen_content
from atmem.store.sqlite import SQLiteStore


class CodeIntakeService:
    """A single enabled host session bound to one authorized scope.

    The adapter receives a per-session secret through its local protected
    configuration. This signature authenticates the local adapter, not a
    remote user or a model-generated assertion. A fresh service must be
    enrolled for each session; no scope is inferred from event contents.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        scope: CodeScope,
        host: str,
        session_id: str,
        secret: bytes,
        enabled: bool = False,
        max_pending: int = 500,
    ) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("intake secret must be at least 32 bytes")
        if not 1 <= max_pending <= 10_000:
            raise ValueError("max_pending must be between 1 and 10000")
        if store.path != ":memory:" and store.policy.state != "encrypted":
            raise RuntimeError("persistent Code intake requires encrypted AtMem storage")
        self.store = store
        self.scope = scope
        self.host = host
        self.session_id = session_id
        self._secret = secret
        self.enabled = enabled
        self.max_pending = max_pending

    def assert_active(self) -> None:
        if not self.enabled:
            raise PermissionError("Code intake is disabled")
        row = self.store.code_installation(
            self.scope.subject_id, self.scope.project_id, self.host,
        )
        if row is None or not row["enabled"]:
            raise PermissionError("automatic Code memory is disabled for this project and host")

    def sign(self, observation: CodeObservation) -> str:
        """Adapter-side signing primitive; never expose it over a host API."""
        return hmac.new(
            self._secret, canonical_json(observation.to_dict()).encode("utf-8"), sha256
        ).hexdigest()

    def submit(self, payload: dict[str, Any], signature: str) -> dict[str, Any]:
        observation = CodeObservation.from_dict(payload)
        if (observation.scope != self.scope or observation.host != self.host
                or observation.session_id != self.session_id):
            raise PermissionError("Code intake scope or session mismatch")
        if not isinstance(signature, str) or not hmac.compare_digest(
            self.sign(observation), signature
        ):
            raise PermissionError("Code intake signature invalid")
        self.assert_active()
        screening = screen_content(
            observation.content, trusted=observation.kind == "user_turn"
        )
        if not screening.admissible:
            # No raw observation is queued or logged on refusal.
            return {"event_id": observation.event_id, "accepted": False,
                    "reason_codes": list(screening.reason_codes)}
        serialized = canonical_json(observation.to_dict())
        digest = sha256(serialized.encode("utf-8")).hexdigest()
        with self.store.transaction():
            self.assert_active()
            inserted = self.store.put_code_observation(
                event_id=observation.event_id,
                subject_id=self.scope.subject_id,
                project_id=self.scope.project_id,
                profile_id=self.scope.profile_id,
                agent_id=self.scope.agent_id,
                session_id=observation.session_id,
                turn_id=observation.turn_id,
                payload_sha256=digest,
                payload_json=serialized,
                max_pending=self.max_pending,
            )
        return {"event_id": observation.event_id, "accepted": True, "queued": inserted}

    def pending(self, limit: int = 100) -> list[CodeObservation]:
        self.assert_active()
        return [
            CodeObservation.from_dict(json.loads(row["payload_json"]))
            for row in self.store.list_code_observations(
                subject_id=self.scope.subject_id,
                project_id=self.scope.project_id,
                profile_id=self.scope.profile_id,
                agent_id=self.scope.agent_id,
                limit=limit,
            )
        ]
