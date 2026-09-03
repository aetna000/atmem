"""Versioned host-neutral delegated-context contract types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any


REQUEST_CONTRACT_ID = "atmem.delegated-context-request.v1"
RESULT_CONTRACT_ID = "atmem.delegated-context-provider.v1"
SIGNATURE_PROFILE = "ed25519-jcs-subset-v1"
SIGNATURE_DOMAIN = b"ATMEM-DELEGATED-CONTEXT-V1\0"
MAX_CONTEXT_BYTES = 262_144
MAX_RESULT_BYTES = 524_288
MAX_LIFETIME_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30


@dataclass(frozen=True, slots=True)
class DelegatedBinding:
    run_id: str
    turn_id: str
    session_id: str
    agent_id: str
    user_id: str
    workspace_id: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DelegatedBinding":
        fields = ("run_id", "turn_id", "session_id", "agent_id", "user_id", "workspace_id")
        if set(value) != set(fields):
            raise ValueError("delegated binding fields do not match the contract")
        normalized: dict[str, str] = {}
        for field in fields:
            item = str(value.get(field) or "")
            if not item or item != item.strip() or len(item) > 256:
                raise ValueError(f"delegated binding requires a valid {field}")
            normalized[field] = item
        return cls(**normalized)

    def to_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
        }


@dataclass(frozen=True, slots=True)
class DelegatedContextRequest:
    """Closed provider request generated from an authenticated host binding."""

    binding: DelegatedBinding
    query: str
    query_sha256: str
    max_context_bytes: int
    deadline: str

    @classmethod
    def create(
        cls,
        *,
        binding: DelegatedBinding,
        query: str,
        max_context_bytes: int,
        timeout_ms: int,
    ) -> "DelegatedContextRequest":
        query_bytes = query.encode("utf-8")
        if not query_bytes or len(query_bytes) > 100_000:
            raise ValueError("delegated query is empty or exceeds policy")
        deadline = datetime.now(timezone.utc) + timedelta(milliseconds=timeout_ms)
        return cls(
            binding=binding,
            query=query,
            query_sha256=sha256(query_bytes).hexdigest(),
            max_context_bytes=max_context_bytes,
            deadline=deadline.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": REQUEST_CONTRACT_ID,
            "binding": self.binding.to_dict(),
            "query": self.query,
            "query_sha256": self.query_sha256,
            "max_context_bytes": self.max_context_bytes,
            "deadline": self.deadline,
        }


@dataclass(frozen=True, slots=True)
class DelegatedContextDecision:
    """Provider-neutral immediate decision returned to a host adapter."""

    authority: str
    decision: str
    inject: bool
    context: str
    context_sha256: str | None
    context_byte_length: int
    native_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-delegated-context-decision-v1",
            "handled": True,
            "authority": self.authority,
            "decision": self.decision,
            "inject": self.inject,
            "context": self.context,
            "context_sha256": self.context_sha256,
            "context_byte_length": self.context_byte_length,
            "context_location": "prependContext" if self.inject else "none",
            "native_fallback": self.native_fallback,
        }


@dataclass(frozen=True, slots=True)
class VerifiedDelegatedResult:
    envelope: dict[str, Any]
    envelope_sha256: str
    binding: DelegatedBinding
    provider_id: str
    provider_version: str
    provider_instance_id: str
    key_id: str
    decision: str
    context_bytes: bytes
    context_text: str
    context_sha256: str | None
    context_byte_length: int
    receipt_id: str
    receipt_contract_id: str
    receipt_sha256: str
    nonce: str
    idempotency_key: str
    created_at: str
    expires_at: str
    source_refs: tuple[str, ...]
    withhold_reason: dict[str, Any] | None

    def evidence(self) -> dict[str, Any]:
        return {
            "format": "atmem-delegated-context-authorization-v1",
            "provider": {
                "id": self.provider_id,
                "version": self.provider_version,
                "instance_id": self.provider_instance_id,
            },
            "binding": self.binding.to_dict(),
            "decision": self.decision,
            "result_sha256": self.envelope_sha256,
            "receipt": {
                "id": self.receipt_id,
                "contract_id": self.receipt_contract_id,
                "sha256": self.receipt_sha256,
            },
            "context_sha256": self.context_sha256,
            "context_byte_length": self.context_byte_length,
            "key_id": self.key_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "withhold_reason": self.withhold_reason,
        }
