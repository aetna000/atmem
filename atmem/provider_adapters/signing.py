"""Canonical signing for provider-produced delegated context."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import secrets
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atmem.delegated.canonical import canonical_json_bytes, expected_idempotency_key, signed_payload_sha256, signing_bytes
from atmem.delegated.contracts import RESULT_CONTRACT_ID, SIGNATURE_PROFILE
from .models import ProviderProposal, ProviderRequest, ProviderRuntimeIdentity


RECEIPT_CONTRACT_ID = "atmem.context-provider-receipt.v1"


def generate_keypair(private_path: Path, public_path: Path) -> str:
    if private_path.exists() or private_path.is_symlink() or public_path.exists() or public_path.is_symlink():
        raise ValueError("provider signing key already exists")
    private_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(private_path.parent, 0o700)
    key = Ed25519PrivateKey.generate()
    raw_private = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    raw_public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    private_path.write_bytes(raw_private)
    os.chmod(private_path, 0o600)
    public = base64.b64encode(raw_public).decode("ascii")
    public_path.write_text(public + "\n", encoding="utf-8")
    os.chmod(public_path, 0o600)
    return public


def load_private_key(path: Path) -> Ed25519PrivateKey:
    if path.is_symlink() or not path.is_file():
        raise ValueError("provider private key must be a regular non-symlink file")
    if path.stat().st_mode & 0o077:
        raise ValueError("provider private key permissions must be 0600")
    if hasattr(os, "getuid") and path.stat().st_uid != os.getuid():
        raise ValueError("provider private key must be owned by the current user")
    raw = path.read_bytes()
    if len(raw) != 32:
        raise ValueError("provider private key has an invalid length")
    return Ed25519PrivateKey.from_private_bytes(raw)


def signed_envelope(
    *,
    request: ProviderRequest,
    proposal: ProviderProposal,
    context_bytes: bytes,
    identity: ProviderRuntimeIdentity,
    private_key: Ed25519PrivateKey,
    adapter_kind: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(request.deadline[:-1] + "+00:00")
    expires = min(created + timedelta(seconds=60), deadline)
    if expires <= created:
        raise TimeoutError("delegated request deadline has elapsed")
    context_sha = sha256(context_bytes).hexdigest() if context_bytes else None
    receipt_body = {
        "contract_id": RECEIPT_CONTRACT_ID,
        "provider": {
            "id": identity.provider_id,
            "version": identity.provider_version,
            "instance_id": identity.instance_id,
        },
        "binding": request.binding.to_dict(),
        "query_sha256": request.query_sha256,
        "decision": proposal.decision,
        "context_sha256": context_sha,
        "source_refs": list(proposal.source_refs),
        "adapter_kind": adapter_kind,
        "attribution": dict(sorted(proposal.attribution.items())),
    }
    receipt_sha = sha256(canonical_json_bytes(receipt_body)).hexdigest()
    envelope: dict[str, Any] = {
        "contract_id": RESULT_CONTRACT_ID,
        "provider": {
            "id": identity.provider_id,
            "version": identity.provider_version,
            "instance_id": identity.instance_id,
        },
        "binding": request.binding.to_dict(),
        "decision": proposal.decision,
        "context": None,
        "receipt": {
            "id": "receipt-" + receipt_sha,
            "contract_id": RECEIPT_CONTRACT_ID,
            "sha256": receipt_sha,
        },
        "created_at": created.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "expires_at": expires.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "nonce": secrets.token_urlsafe(18),
        "idempotency_key": "",
        "source_refs": list(proposal.source_refs),
        "withhold_reason": proposal.withhold_reason,
        "signature": {},
    }
    if proposal.decision == "inject":
        envelope["context"] = {
            "encoding": "base64",
            "media_type": "text/plain; charset=utf-8",
            "bytes_base64": base64.b64encode(context_bytes).decode("ascii"),
            "byte_length": len(context_bytes),
            "sha256": context_sha,
        }
    envelope["idempotency_key"] = expected_idempotency_key(envelope)
    payload_sha = signed_payload_sha256(envelope)
    envelope["signature"] = {
        "algorithm": "ed25519",
        "profile": SIGNATURE_PROFILE,
        "key_id": identity.key_id,
        "signed_payload_sha256": payload_sha,
        "value_base64": base64.b64encode(private_key.sign(signing_bytes(envelope))).decode("ascii"),
    }
    return envelope
