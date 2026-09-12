"""Cryptographic primitives for the encrypted evidence container."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import stat
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from atmem.core.canonical import canonical_json


CONTAINER_FORMAT = "atmem-encrypted-evidence-object-v1"
EXPORT_FORMAT = "atmem-encrypted-evidence-export-v1"
EXPORT_SUITE = "ML-KEM-768+AES-256-GCM+ML-DSA-65"
KEY_WRAP_FORMAT = "atmem-evidence-data-key-wrap-v1"


def load_or_create_key(path: str | Path) -> bytes:
    target = Path(path).expanduser().resolve(strict=False)
    if target.is_symlink():
        raise ValueError("evidence key path must not be a symlink")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists():
        if not target.is_file() or stat.S_IMODE(target.stat().st_mode) & 0o077:
            raise RuntimeError("evidence key must be a regular mode-0600 file")
        value = base64.b64decode(target.read_text(encoding="ascii").strip(), validate=True)
        if len(value) != 32:
            raise RuntimeError("evidence key must contain exactly 256 bits")
        return value
    value = os.urandom(32)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(base64.b64encode(value).decode("ascii") + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return value


def load_existing_key(path: str | Path) -> bytes:
    """Load an existing KEK without ever manufacturing a replacement."""

    target = Path(path).expanduser().resolve(strict=False)
    if target.is_symlink():
        raise ValueError("evidence key path must not be a symlink")
    if not target.is_file():
        raise FileNotFoundError("evidence key is unavailable")
    if stat.S_IMODE(target.stat().st_mode) & 0o077:
        raise RuntimeError("evidence key must be a regular mode-0600 file")
    value = base64.b64decode(target.read_text(encoding="ascii").strip(), validate=True)
    if len(value) != 32:
        raise RuntimeError("evidence key must contain exactly 256 bits")
    return value


def write_key(path: str | Path, value: bytes, *, replace: bool = False) -> None:
    if len(value) != 32:
        raise ValueError("evidence key must contain exactly 256 bits")
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(base64.b64encode(value).decode("ascii") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists() and not replace:
            raise FileExistsError(str(target))
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def wrap_data_key(kek: bytes, slot_id: str, data_key: bytes) -> tuple[bytes, bytes]:
    if len(kek) != 32 or len(data_key) != 32:
        raise ValueError("key wrapping requires 256-bit keys")
    nonce = os.urandom(12)
    aad = canonical_json({"format": KEY_WRAP_FORMAT, "slot_id": slot_id}).encode()
    return nonce, AESGCM(kek).encrypt(nonce, data_key, aad)


def unwrap_data_key(kek: bytes, slot_id: str, nonce: bytes, wrapped: bytes) -> bytes:
    aad = canonical_json({"format": KEY_WRAP_FORMAT, "slot_id": slot_id}).encode()
    value = AESGCM(kek).decrypt(nonce, wrapped, aad)
    if len(value) != 32:
        raise ValueError("wrapped evidence data key has invalid length")
    return value


def seal_json(key: bytes, object_id: str, value: dict[str, Any]) -> tuple[bytes, bytes]:
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    nonce = os.urandom(12)
    aad = canonical_json({"format": CONTAINER_FORMAT, "object_id": object_id}).encode()
    ciphertext = AESGCM(key).encrypt(nonce, canonical_json(value).encode(), aad)
    return nonce, ciphertext


def open_json(key: bytes, object_id: str, nonce: bytes, ciphertext: bytes) -> dict[str, Any]:
    aad = canonical_json({"format": CONTAINER_FORMAT, "object_id": object_id}).encode()
    value = json.loads(AESGCM(key).decrypt(nonce, ciphertext, aad))
    if not isinstance(value, dict):
        raise ValueError("encrypted evidence object must contain a JSON object")
    return value


def pq_available() -> bool:
    try:
        from pqcrypto.kem import ml_kem_768  # noqa: F401
        from pqcrypto.sign import ml_dsa_65  # noqa: F401
    except ImportError:
        return False
    return True


def generate_recipient_keypair() -> tuple[bytes, bytes]:
    try:
        from pqcrypto.kem.ml_kem_768 import keygen
    except ImportError as exc:
        raise RuntimeError("ML-KEM support requires the atmem post-quantum extra") from exc
    return keygen()


def generate_signing_keypair() -> tuple[bytes, bytes]:
    try:
        from pqcrypto.sign.ml_dsa_65 import keygen
    except ImportError as exc:
        raise RuntimeError("ML-DSA support requires the atmem post-quantum extra") from exc
    return keygen()


def encrypted_export(
    plaintext: bytes,
    *,
    recipient_public_key: bytes,
    signing_secret_key: bytes,
    signing_public_key: bytes,
) -> dict[str, Any]:
    try:
        from pqcrypto.kem.ml_kem_768 import encaps
        from pqcrypto.sign.ml_dsa_65 import sign
    except ImportError as exc:
        raise RuntimeError("quantum-resistant export requires the atmem post-quantum extra") from exc
    kem_ciphertext, shared_secret = encaps(recipient_public_key)
    key = HKDF(algorithm=hashes.SHA512(), length=32, salt=None, info=b"atmem-export-v1").derive(shared_secret)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, EXPORT_FORMAT.encode())
    unsigned = {
        "format": EXPORT_FORMAT,
        "suite": EXPORT_SUITE,
        "kem_ciphertext": base64.b64encode(kem_ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "signing_public_key": base64.b64encode(signing_public_key).decode(),
    }
    signature = sign(signing_secret_key, canonical_json(unsigned).encode())
    return {**unsigned, "signature": base64.b64encode(signature).decode()}


def decrypt_export(bundle: dict[str, Any], recipient_secret_key: bytes) -> bytes:
    if bundle.get("format") != EXPORT_FORMAT or bundle.get("suite") != EXPORT_SUITE:
        raise ValueError("unsupported evidence export")
    try:
        from pqcrypto.kem.ml_kem_768 import decaps
        from pqcrypto.sign.ml_dsa_65 import verify
    except ImportError as exc:
        raise RuntimeError("quantum-resistant export requires the atmem post-quantum extra") from exc
    unsigned = {key: value for key, value in bundle.items() if key != "signature"}
    verify(
        base64.b64decode(str(bundle["signing_public_key"]), validate=True),
        canonical_json(unsigned).encode(),
        base64.b64decode(str(bundle["signature"]), validate=True),
    )
    shared_secret = decaps(
        recipient_secret_key,
        base64.b64decode(str(bundle["kem_ciphertext"]), validate=True),
    )
    key = HKDF(algorithm=hashes.SHA512(), length=32, salt=None, info=b"atmem-export-v1").derive(shared_secret)
    return AESGCM(key).decrypt(
        base64.b64decode(str(bundle["nonce"]), validate=True),
        base64.b64decode(str(bundle["ciphertext"]), validate=True),
        EXPORT_FORMAT.encode(),
    )
