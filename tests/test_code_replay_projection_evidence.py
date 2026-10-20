import base64
from hashlib import sha256

import pytest

from atmem.core.canonical import canonical_json
from benchmarks.code_replay.projection_evidence import recover_projection_stream


def fixture():
    raw = b"fixture complete bytes"
    payload = {"offset": 0, "bytes_base64": base64.b64encode(raw).decode()}
    event = {"object_id": "fixture", "envelope": {"run_id": "fixture-run",
             "event_type": "external.runtime_projection_chunk", "payload": payload}}
    descriptor = {"bytes": len(raw), "sha256": sha256(raw).hexdigest(), "receipts": [{
        "object_id": "fixture", "run_id": "fixture-run",
        "payload_sha256": sha256(canonical_json(payload).encode()).hexdigest()}]}
    return {"fixture": event}, descriptor, raw


def test_projection_recovery_follows_exact_receipts_and_full_identity():
    events, descriptor, raw = fixture()
    assert recover_projection_stream(events, descriptor) == raw


@pytest.mark.parametrize("change", ["bytes", "digest", "offset", "receipt", "role", "run"])
def test_tampered_projection_stream_is_never_recovered(change):
    events, descriptor, _ = fixture()
    if change == "bytes":
        descriptor["bytes"] -= 1
    elif change == "digest":
        descriptor["sha256"] = "0" * 64
    elif change == "offset":
        events["fixture"]["envelope"]["payload"]["offset"] = 1
    elif change == "receipt":
        descriptor["receipts"][0]["payload_sha256"] = "0" * 64
    elif change == "role":
        events["fixture"]["envelope"]["event_type"] = "different"
    else:
        descriptor["receipts"][0]["run_id"] = "other"
    with pytest.raises(ValueError):
        recover_projection_stream(events, descriptor)
