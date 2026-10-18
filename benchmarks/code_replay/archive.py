"""Bounded framing around existing AtMem recipient-encrypted exports.

No new crypto primitive: the installed ML-DSA binding caps a signed message at
1 MiB. Each existing signed/encrypted chunk stays below that bound. Authenticated
inner framing binds run, ordinal, count, exact size and whole-event digest.
"""
import base64
from hashlib import sha256
import json

from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import encrypted_export, decrypt_export

FORMAT = "atmem-click-chunked-evidence-archive-v2"
CHUNK = 196608
MAX_BYTES = 48_000_000


def seal(raw, *, run_id, recipient_public_key, signing_public_key, signing_secret_key):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("bounded original event bytes required")
    count = (len(raw) + CHUNK - 1) // CHUNK
    identity = sha256(raw).hexdigest()
    chunks = []
    for ordinal in range(count):
        inner = {"format": FORMAT, "run_id": run_id, "ordinal": ordinal, "count": count,
                 "total_bytes": len(raw), "events_sha256": identity,
                 "data_base64": base64.b64encode(raw[ordinal * CHUNK:(ordinal + 1) * CHUNK]).decode()}
        chunks.append(encrypted_export(canonical_json(inner).encode(), recipient_public_key=recipient_public_key,
            signing_public_key=signing_public_key, signing_secret_key=signing_secret_key))
    return {"format": FORMAT, "run_id": run_id, "chunks": chunks}


def open_archive(bundle, *, run_id, recipient_secret_key, trusted_signing_public_key):
    if type(bundle) is not dict or set(bundle) != {"format", "run_id", "chunks"} or bundle["format"] != FORMAT or bundle["run_id"] != run_id:
        raise ValueError("archive format or expected run mismatch")
    chunks = bundle["chunks"]
    if type(chunks) is not list or not 1 <= len(chunks) <= (MAX_BYTES + CHUNK - 1) // CHUNK:
        raise ValueError("archive chunk bound exceeded")
    expected_key = base64.b64encode(trusted_signing_public_key).decode()
    data, binding = [], None
    for ordinal, chunk in enumerate(chunks):
        if type(chunk) is not dict or chunk.get("signing_public_key") != expected_key or len(canonical_json(chunk).encode()) > 400_000:
            raise ValueError("untrusted signing identity or oversized chunk")
        inner = json.loads(decrypt_export(chunk, recipient_secret_key))
        if set(inner) != {"format", "run_id", "ordinal", "count", "total_bytes", "events_sha256", "data_base64"}:
            raise ValueError("invalid authenticated chunk fields")
        if (inner["format"] != FORMAT or inner["run_id"] != run_id or type(inner["ordinal"]) is not int or inner["ordinal"] != ordinal or
                type(inner["count"]) is not int or inner["count"] != len(chunks) or type(inner["total_bytes"]) is not int or
                not 1 <= inner["total_bytes"] <= MAX_BYTES):
            raise ValueError("authenticated chunk framing mismatch")
        current = (inner["total_bytes"], inner["events_sha256"])
        if binding is not None and current != binding:
            raise ValueError("mixed archive chunks")
        binding = current
        value = base64.b64decode(inner["data_base64"], validate=True)
        if len(value) != (CHUNK if ordinal < len(chunks) - 1 else inner["total_bytes"] - ordinal * CHUNK):
            raise ValueError("chunk length mismatch")
        data.append(value)
    raw = b"".join(data)
    if len(raw) != binding[0] or sha256(raw).hexdigest() != binding[1]:
        raise ValueError("archive integrity mismatch")
    return raw
