"""Restricted canonicalization used by delegated-context signatures."""

from __future__ import annotations

import base64
from hashlib import sha256
import json
from typing import Any

from atmem.delegated.contracts import SIGNATURE_DOMAIN


def canonical_json_bytes(value: Any) -> bytes:
    _validate_restricted(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def signing_bytes(envelope: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in envelope.items() if key != "signature"}
    return SIGNATURE_DOMAIN + canonical_json_bytes(unsigned)


def envelope_sha256(envelope: dict[str, Any]) -> str:
    return sha256(canonical_json_bytes(envelope)).hexdigest()


def signed_payload_sha256(envelope: dict[str, Any]) -> str:
    return sha256(signing_bytes(envelope)).hexdigest()


def expected_idempotency_key(envelope: dict[str, Any]) -> str:
    context = envelope.get("context")
    receipt = envelope.get("receipt") or {}
    identity = {
        "contract_id": envelope.get("contract_id"),
        "provider": envelope.get("provider"),
        "binding": envelope.get("binding"),
        "decision": envelope.get("decision"),
        "context_sha256": context.get("sha256") if isinstance(context, dict) else None,
        "receipt_id": receipt.get("id"),
        "receipt_sha256": receipt.get("sha256"),
        "source_refs": envelope.get("source_refs"),
        "withhold_reason": envelope.get("withhold_reason"),
    }
    return "dcp-" + sha256(canonical_json_bytes(identity)).hexdigest()


def public_key_fingerprint(public_key_base64: str) -> str:
    raw = strict_base64(public_key_base64, expected_length=32)
    return "sha256:" + sha256(raw).hexdigest()


def strict_base64(value: str, *, expected_length: int | None = None) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid canonical base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("invalid canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("invalid canonical base64")
    if expected_length is not None and len(decoded) != expected_length:
        raise ValueError("invalid decoded byte length")
    return decoded


def _validate_restricted(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("integer exceeds the delegated canonical profile")
        return
    if isinstance(value, list):
        for item in value:
            _validate_restricted(item)
        return
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("canonical object keys must be strings")
        for item in value.values():
            _validate_restricted(item)
        return
    raise ValueError("unsupported value in delegated canonical profile")
