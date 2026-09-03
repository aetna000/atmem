"""Exclusive delegated context orchestration; AtMem still owns host delivery."""

from __future__ import annotations

from typing import Any, Callable
import socket
from urllib.parse import urlparse

from atmem.delegated.client import request_context
from atmem.delegated.config import DelegatedConfigStore
from atmem.delegated.contracts import DelegatedBinding, DelegatedContextDecision
from atmem.delegated.validation import parse_and_verify_envelope


Transport = Callable[..., bytes]


class DelegatedContextService:
    def __init__(
        self,
        config: DelegatedConfigStore | None = None,
        *,
        transport: Transport = request_context,
    ) -> None:
        self.config = config or DelegatedConfigStore()
        self.transport = transport

    def prepare(
        self,
        *,
        query: str,
        binding: DelegatedBinding,
        migration_id: str,
        store: Any,
    ) -> dict[str, Any] | None:
        try:
            registration = self.config.match(
                workspace_id=binding.workspace_id,
                agent_id=binding.agent_id,
                user_id=binding.user_id,
            )
        except Exception as exc:
            reservation = store.reserve_delegated_failure(
                migration_id,
                binding,
                native_fallback=False,
            )
            failure = {
                "format": "atmem-delegated-context-authorization-v1",
                "provider": None,
                "binding": binding.to_dict(),
                "decision": "rejected",
                "result_sha256": None,
                "receipt": None,
                "context_sha256": None,
                "context_byte_length": 0,
                "key_id": None,
                "key_fingerprint": None,
                "acceptance_disposition": "rejected",
                "failure_code": type(exc).__name__,
                "failure_reason": _safe_reason(exc),
                "reservation_id": str(reservation["id"]),
            }
            event = store.append_evidence(
                migration_id,
                kind="delegated_context",
                body=failure,
            )
            return {
                **DelegatedContextDecision(
                    authority="delegated",
                    decision="provider_failure",
                    inject=False,
                    context="",
                    context_sha256=None,
                    context_byte_length=0,
                    native_fallback=False,
                ).to_dict(),
                "authorization_event_id": str(event["id"]),
                "failure_code": type(exc).__name__,
                "failure_reason": _safe_reason(exc),
                "provider": None,
            }
        if registration is None:
            return None
        try:
            raw = self.transport(registration, binding=binding, query=query)
            verified = parse_and_verify_envelope(
                raw,
                expected_binding=binding,
                trust=registration,
                max_context_bytes=registration.max_context_bytes,
            )
            acceptance = store.accept_delegated_context(migration_id, verified)
            evidence = {
                **verified.evidence(),
                "acceptance_id": str(acceptance["id"]),
                "acceptance_disposition": (
                    "idempotent_retry" if acceptance["idempotent"] else "accepted"
                ),
                "key_fingerprint": registration.safe_dict()["key_fingerprint"],
            }
            event = store.append_evidence(
                migration_id,
                kind="delegated_context",
                body=evidence,
            )
            delivery = None
            if verified.decision == "inject":
                delivery = store.request_delegated_delivery(
                    migration_id,
                    str(acceptance["id"]),
                    context_sha256=verified.context_sha256,
                    context_byte_length=verified.context_byte_length,
                )
            return {
                **DelegatedContextDecision(
                    authority="delegated",
                    decision=verified.decision,
                    inject=verified.decision == "inject",
                    context=verified.context_text,
                    context_sha256=verified.context_sha256,
                    context_byte_length=verified.context_byte_length,
                    native_fallback=False,
                ).to_dict(),
                "acceptance_id": str(acceptance["id"]),
                "exposure_id": str(delivery["id"]) if delivery else None,
                "authorization_event_id": str(event["id"]),
                "result_sha256": verified.envelope_sha256,
                "receipt": {
                    "id": verified.receipt_id,
                    "contract_id": verified.receipt_contract_id,
                    "sha256": verified.receipt_sha256,
                },
                "provider": {
                    "id": verified.provider_id,
                    "version": verified.provider_version,
                    "instance_id": verified.provider_instance_id,
                    "key_id": verified.key_id,
                    "key_fingerprint": registration.safe_dict()["key_fingerprint"],
                },
                "withhold_reason": verified.withhold_reason,
                "idempotent": bool(acceptance["idempotent"]),
            }
        except Exception as exc:
            reservation = store.reserve_delegated_failure(
                migration_id,
                binding,
                native_fallback=registration.native_fallback_on_failure,
            )
            failure = {
                "format": "atmem-delegated-context-authorization-v1",
                "provider": {
                    "id": registration.provider_id,
                    "version": registration.provider_version,
                    "instance_id": registration.provider_instance_id,
                },
                "binding": binding.to_dict(),
                "decision": "rejected",
                "result_sha256": None,
                "receipt": None,
                "context_sha256": None,
                "context_byte_length": 0,
                "key_id": registration.key_id,
                "key_fingerprint": registration.safe_dict()["key_fingerprint"],
                "acceptance_disposition": "rejected",
                "failure_code": type(exc).__name__,
                "failure_reason": _safe_reason(exc),
                "reservation_id": str(reservation["id"]),
            }
            event = store.append_evidence(
                migration_id,
                kind="delegated_context",
                body=failure,
            )
            return {
                **DelegatedContextDecision(
                    authority=(
                        "atmem_fallback"
                        if registration.native_fallback_on_failure
                        else "delegated"
                    ),
                    decision="provider_failure",
                    inject=False,
                    context="",
                    context_sha256=None,
                    context_byte_length=0,
                    native_fallback=registration.native_fallback_on_failure,
                ).to_dict(),
                "authorization_event_id": str(event["id"]),
                "failure_code": type(exc).__name__,
                "failure_reason": _safe_reason(exc),
                "provider": failure["provider"],
            }

    def status(self) -> dict[str, Any]:
        return self.config.status()

    def doctor(self) -> dict[str, Any]:
        status = self.status()
        registrations = status["registrations"]
        reachability = []
        for row in registrations:
            parsed = urlparse(str(row["endpoint"]))
            reachable = _tcp_reachable(
                str(parsed.hostname or ""),
                int(parsed.port or 0),
                timeout_ms=min(int(row["timeout_ms"]), 1000),
            )
            reachability.append(
                {
                    "registration_id": row["registration_id"],
                    "enabled": bool(row["enabled"]),
                    "reachable": reachable,
                }
            )
        enabled_health = [row for row in reachability if row["enabled"]]
        checks = {
            "native_default": status["authority_default"] == "atmem",
            "delegation_explicit": status["delegated_mode_default"] is False,
            "configuration_readable": True,
            "trust_registered": bool(registrations),
            "enabled_scope_present": any(row["enabled"] for row in registrations),
            "loopback_only": all(
                urlparse(str(row["endpoint"])).hostname in {"127.0.0.1", "::1"}
                for row in registrations
            ),
            "enabled_providers_reachable": bool(enabled_health)
            and all(row["reachable"] for row in enabled_health),
        }
        state = (
            "unconfigured"
            if not registrations
            else "registered_disabled"
            if not enabled_health
            else "ready"
            if checks["enabled_providers_reachable"]
            else "degraded"
        )
        return {
            "format": "atmem-delegated-context-doctor-v1",
            "healthy": all(
                checks[name]
                for name in ("native_default", "delegation_explicit", "configuration_readable", "loopback_only")
            ),
            "ready": state == "ready",
            "state": state,
            "provider_health": reachability,
            "checks": checks,
            "status": status,
            "next_action": status["next_action"],
        }

    def self_test(self) -> dict[str, Any]:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private = Ed25519PrivateKey.generate()
        sample = b"atmem-delegated-context-self-test"
        signature = private.sign(sample)
        private.public_key().verify(signature, sample)
        return {
            "format": "atmem-delegated-context-self-test-v1",
            "passed": True,
            "checks": {
                "ed25519": True,
                "configuration": self.doctor()["healthy"],
                "native_default": True,
            },
        }


def _safe_reason(exc: Exception) -> str:
    reason = " ".join(str(exc).split())[:300]
    return reason or type(exc).__name__


def _tcp_reachable(host: str, port: int, *, timeout_ms: int) -> bool:
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_ms / 1000):
            return True
    except OSError:
        return False
