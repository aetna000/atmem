"""Strict parsing and verification for delegated context results."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atmem.delegated.canonical import (
    envelope_sha256,
    expected_idempotency_key,
    signed_payload_sha256,
    signing_bytes,
    strict_base64,
)
from atmem.delegated.contracts import (
    DelegatedBinding,
    MAX_CONTEXT_BYTES,
    MAX_FUTURE_SKEW_SECONDS,
    MAX_LIFETIME_SECONDS,
    RESULT_CONTRACT_ID,
    SIGNATURE_PROFILE,
    VerifiedDelegatedResult,
)


_TOP = {
    "binding", "context", "contract_id", "created_at", "decision",
    "expires_at", "idempotency_key", "nonce", "provider", "receipt",
    "signature", "source_refs", "withhold_reason",
}
_PROVIDER = {"id", "version", "instance_id"}
_RECEIPT = {"id", "contract_id", "sha256"}
_CONTEXT = {"encoding", "media_type", "bytes_base64", "byte_length", "sha256"}
_SIGNATURE = {"algorithm", "profile", "key_id", "signed_payload_sha256", "value_base64"}
_WITHHOLD = {"code", "retryable"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{22,128}$")
_WITHHOLD_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def parse_json_strict(raw: bytes | str) -> dict[str, Any]:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("delegated result is not UTF-8") from exc
    else:
        text = raw

    def closed_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(text, object_pairs_hook=closed_pairs)
    except json.JSONDecodeError as exc:
        raise ValueError("delegated result is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("delegated result must be an object")
    return value


def parse_and_verify_envelope(
    raw: bytes | str,
    *,
    expected_binding: DelegatedBinding,
    trust: Any,
    now: datetime | None = None,
    max_context_bytes: int = MAX_CONTEXT_BYTES,
) -> VerifiedDelegatedResult:
    envelope = parse_json_strict(raw)
    _validate_shape(envelope, max_context_bytes=max_context_bytes)
    binding = DelegatedBinding.from_dict(envelope["binding"])
    if binding != expected_binding:
        raise ValueError("delegated result does not match the authenticated turn binding")
    provider = envelope["provider"]
    signature = envelope["signature"]
    _verify_trust(provider, signature, binding, trust)
    _verify_time(envelope, now=now)

    context_bytes = b""
    context_text = ""
    context_sha256: str | None = None
    context_length = 0
    if envelope["decision"] == "inject":
        context = envelope["context"]
        context_bytes = strict_base64(context["bytes_base64"])
        if len(context_bytes) != context["byte_length"]:
            raise ValueError("delegated context byte length mismatch")
        from hashlib import sha256

        if sha256(context_bytes).hexdigest() != context["sha256"]:
            raise ValueError("delegated context digest mismatch")
        try:
            context_text = context_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("delegated context is not valid UTF-8") from exc
        context_sha256 = context["sha256"]
        context_length = len(context_bytes)

    if expected_idempotency_key(envelope) != envelope["idempotency_key"]:
        raise ValueError("delegated idempotency binding mismatch")
    if signed_payload_sha256(envelope) != signature["signed_payload_sha256"]:
        raise ValueError("delegated signed-payload digest mismatch")
    public_key = Ed25519PublicKey.from_public_bytes(
        strict_base64(str(trust.public_key_base64), expected_length=32)
    )
    try:
        public_key.verify(
            strict_base64(signature["value_base64"], expected_length=64),
            signing_bytes(envelope),
        )
    except InvalidSignature as exc:
        raise ValueError("delegated signature verification failed") from exc

    receipt = envelope["receipt"]
    return VerifiedDelegatedResult(
        envelope=envelope,
        envelope_sha256=envelope_sha256(envelope),
        binding=binding,
        provider_id=provider["id"],
        provider_version=provider["version"],
        provider_instance_id=provider["instance_id"],
        key_id=signature["key_id"],
        decision=envelope["decision"],
        context_bytes=context_bytes,
        context_text=context_text,
        context_sha256=context_sha256,
        context_byte_length=context_length,
        receipt_id=receipt["id"],
        receipt_contract_id=receipt["contract_id"],
        receipt_sha256=receipt["sha256"],
        nonce=envelope["nonce"],
        idempotency_key=envelope["idempotency_key"],
        created_at=envelope["created_at"],
        expires_at=envelope["expires_at"],
        source_refs=tuple(envelope["source_refs"]),
        withhold_reason=envelope["withhold_reason"],
    )


def _validate_shape(envelope: dict[str, Any], *, max_context_bytes: int) -> None:
    _exact(envelope, _TOP, "result")
    if envelope.get("contract_id") != RESULT_CONTRACT_ID:
        raise ValueError("unsupported delegated result contract")
    _exact(envelope.get("provider"), _PROVIDER, "provider")
    for value in envelope["provider"].values():
        _identifier(value)
    DelegatedBinding.from_dict(envelope.get("binding"))
    _exact(envelope.get("receipt"), _RECEIPT, "receipt")
    _identifier(envelope["receipt"]["id"], maximum=512)
    _identifier(envelope["receipt"]["contract_id"])
    _digest(envelope["receipt"]["sha256"])
    _timestamp(envelope.get("created_at"))
    _timestamp(envelope.get("expires_at"))
    if not isinstance(envelope.get("nonce"), str) or not _NONCE.fullmatch(envelope["nonce"]):
        raise ValueError("invalid delegated nonce")
    if not isinstance(envelope.get("idempotency_key"), str) or not re.fullmatch(r"dcp-[0-9a-f]{64}", envelope["idempotency_key"]):
        raise ValueError("invalid delegated idempotency key")
    refs = envelope.get("source_refs")
    if not isinstance(refs, list) or len(refs) > 32 or len(set(refs)) != len(refs):
        raise ValueError("invalid delegated source references")
    for value in refs:
        _identifier(value, maximum=512)
    _exact(envelope.get("signature"), _SIGNATURE, "signature")
    signature = envelope["signature"]
    if signature.get("algorithm") != "ed25519" or signature.get("profile") != SIGNATURE_PROFILE:
        raise ValueError("unsupported delegated signature profile")
    _identifier(signature.get("key_id"))
    _digest(signature.get("signed_payload_sha256"))
    strict_base64(signature.get("value_base64"), expected_length=64)

    if envelope.get("decision") == "inject":
        if envelope.get("withhold_reason") is not None:
            raise ValueError("inject result cannot contain a withholding reason")
        _exact(envelope.get("context"), _CONTEXT, "context")
        context = envelope["context"]
        if context.get("encoding") != "base64" or context.get("media_type") != "text/plain; charset=utf-8":
            raise ValueError("unsupported delegated context encoding")
        length = context.get("byte_length")
        if isinstance(length, bool) or not isinstance(length, int) or not 1 <= length <= min(MAX_CONTEXT_BYTES, max_context_bytes):
            raise ValueError("delegated context size is outside policy")
        _digest(context.get("sha256"))
        strict_base64(context.get("bytes_base64"))
    elif envelope.get("decision") == "withhold":
        if envelope.get("context") is not None:
            raise ValueError("withhold result cannot contain context")
        _exact(envelope.get("withhold_reason"), _WITHHOLD, "withhold reason")
        reason = envelope["withhold_reason"]
        if not isinstance(reason.get("code"), str) or not _WITHHOLD_CODE.fullmatch(reason["code"]):
            raise ValueError("invalid delegated withholding code")
        if not isinstance(reason.get("retryable"), bool):
            raise ValueError("invalid delegated withholding retry flag")
    else:
        raise ValueError("invalid delegated decision")


def _verify_trust(provider: dict[str, str], signature: dict[str, str], binding: DelegatedBinding, trust: Any) -> None:
    expected = (
        trust.provider_id,
        trust.provider_version,
        trust.provider_instance_id,
        trust.key_id,
    )
    actual = (provider["id"], provider["version"], provider["instance_id"], signature["key_id"])
    if actual != expected:
        raise ValueError("delegated provider is not locally trusted")
    for value, allowed, label in (
        (binding.workspace_id, trust.workspace_ids, "workspace"),
        (binding.agent_id, trust.agent_ids, "agent"),
        (binding.user_id, trust.user_ids, "user"),
    ):
        if value not in allowed:
            raise ValueError(f"delegated provider is not trusted for this {label}")


def _verify_time(envelope: dict[str, Any], *, now: datetime | None) -> None:
    created = _timestamp(envelope["created_at"])
    expires = _timestamp(envelope["expires_at"])
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if created >= expires:
        raise ValueError("delegated result has an invalid time order")
    if (expires - created).total_seconds() > MAX_LIFETIME_SECONDS:
        raise ValueError("delegated result lifetime exceeds policy")
    if (created - current).total_seconds() > MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("delegated result was created too far in the future")
    if current >= expires:
        raise ValueError("delegated result has expired")


def _exact(value: Any, fields: Iterable[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"delegated {label} fields do not match the contract")


def _identifier(value: Any, *, maximum: int = 256) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise ValueError("invalid delegated identifier")


def _digest(value: Any) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("invalid delegated SHA-256 digest")


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("delegated timestamps must be UTC Z values")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid delegated timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("delegated timestamp requires a timezone")
    return parsed.astimezone(timezone.utc)
