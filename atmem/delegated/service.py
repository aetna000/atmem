"""Exclusive delegated context orchestration; AtMem still owns host delivery."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import socket
from typing import Any, Callable
from urllib.parse import urlparse

from atmem.delegated.client import request_context, request_health
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

        authorization_event_id: str | None = None
        try:
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
            authorization_event_id = str(event["id"])
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
                "authorization_event_id": authorization_event_id,
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
            # Acceptance is already durable and owns this turn. Never try to
            # reserve it again: that masks the original post-acceptance fault.
            # Record a content-free delivery failure bound to the acceptance.
            failure = {
                "format": "atmem-delegated-context-delivery-failure-v1",
                "provider": {
                    "id": verified.provider_id,
                    "version": verified.provider_version,
                    "instance_id": verified.provider_instance_id,
                },
                "binding": binding.to_dict(),
                "decision": "delivery_failure",
                "acceptance_id": str(acceptance["id"]),
                "authorization_event_id": authorization_event_id,
                "result_sha256": verified.envelope_sha256,
                "context_sha256": verified.context_sha256,
                "context_byte_length": verified.context_byte_length,
                "failure_code": type(exc).__name__,
                "failure_reason": _safe_reason(exc),
            }
            failure_event_id: str | None = None
            try:
                failure_event = store.append_evidence(
                    migration_id,
                    kind="delegated_context_delivery",
                    body=failure,
                )
                failure_event_id = str(failure_event["id"])
            except Exception:
                # The original failure remains the operator-facing cause even
                # if the evidence store itself is unavailable.
                pass
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
                "acceptance_id": str(acceptance["id"]),
                "authorization_event_id": authorization_event_id,
                "delivery_failure_event_id": failure_event_id,
                "result_sha256": verified.envelope_sha256,
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
        for registration in self.config.registrations():
            row = registration.safe_dict()
            reachable = _tcp_reachable(registration.endpoint, registration.timeout_ms)
            try:
                request_health(registration)
                authenticated = True
            except (OSError, ValueError, http.client.HTTPException):
                authenticated = False
            reachability.append(
                {
                    "registration_id": row["registration_id"],
                    "enabled": bool(row["enabled"]),
                    "reachable": reachable,
                    "authenticated": authenticated,
                    "request_authentication": row["request_authentication"],
                }
            )
        enabled_health = [row for row in reachability if row["enabled"]]
        checks = {
            "native_default": status["authority_default"] == "atmem",
            "delegation_explicit": status["delegated_mode_default"] is False,
            "configuration_readable": True,
            "request_credentials_configured": all(row["request_authentication"] == "configured" for row in registrations),
            "trust_registered": bool(registrations),
            "enabled_scope_present": any(row["enabled"] for row in registrations),
            "loopback_only": all(
                urlparse(str(row["endpoint"])).hostname in {"127.0.0.1", "::1"}
                for row in registrations
            ),
            "enabled_providers_reachable": bool(enabled_health)
            and all(row["reachable"] for row in enabled_health),
            "enabled_providers_authenticated": bool(enabled_health)
            and all(row["authenticated"] for row in enabled_health),
        }
        state = (
            "unconfigured"
            if not registrations
            else "migration_required"
            if any(row["request_authentication"] == "migration_required" for row in registrations)
            else "registered_disabled"
            if not enabled_health
            else "ready"
            if checks["enabled_providers_authenticated"]
            else "degraded"
        )
        return {
            "format": "atmem-delegated-context-doctor-v1",
            "healthy": all(
                checks[name]
                for name in ("native_default", "delegation_explicit", "configuration_readable", "loopback_only", "request_credentials_configured")
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
        from atmem.delegated.transport import FIELDS, PREFIX, sign_headers, signing_input

        sample = b"atmem-delegated-context-self-test"
        ed25519_ok = False
        try:
            private = Ed25519PrivateKey.generate()
            signature = private.sign(sample)
            private.public_key().verify(signature, sample)
            ed25519_ok = True
        except Exception:
            pass
        secret = hashlib.sha256(b"atmem-delegated-context-self-test-hmac").digest()
        method, authority, target = "POST", "127.0.0.1:8788", "/v1/delegated-context"
        headers = sign_headers(
            secret=secret,
            provider_id="self-test",
            instance_id="local",
            key_id="self-test-key",
            method=method,
            authority=authority,
            target=target,
            body=sample,
        )
        fields = {name: headers[PREFIX + name] for name in FIELDS}
        expected = hmac.new(
            secret,
            signing_input(method, authority, target, sample, fields),
            hashlib.sha256,
        ).hexdigest()
        hmac_ok = hmac.compare_digest(headers[PREFIX + "Signature"], expected)
        tamper_rejected = not hmac.compare_digest(
            headers[PREFIX + "Signature"],
            hmac.new(
                secret,
                signing_input(method, authority, target, sample + b"!", fields),
                hashlib.sha256,
            ).hexdigest(),
        )
        configuration_ok = self.doctor()["healthy"]
        transport_ok = hmac_ok and tamper_rejected
        return {
            "format": "atmem-delegated-context-self-test-v1",
            "passed": configuration_ok and ed25519_ok and transport_ok,
            "checks": {
                "ed25519": ed25519_ok,
                "hmac_exact_request": transport_ok,
                "configuration": configuration_ok,
                "native_default": True,
            },
        }


def _safe_reason(exc: Exception) -> str:
    reason = " ".join(str(exc).split())[:300]
    return reason or type(exc).__name__


def _tcp_reachable(endpoint: str, timeout_ms: int) -> bool:
    """Distinguish an open socket from authenticated provider health."""

    try:
        parsed = urlparse(endpoint)
        if not parsed.hostname:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection(
            (parsed.hostname, port), timeout=min(timeout_ms / 1000, 1)
        ):
            return True
    except (OSError, ValueError):
        return False
