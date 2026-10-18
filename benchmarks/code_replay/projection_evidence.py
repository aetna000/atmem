"""Recover exact retained projection-worker transport, never inline approximations."""
import base64
from hashlib import sha256
import json
import re

from atmem.core.canonical import canonical_json
from benchmarks.code_replay.result_transport import decode_result


def recover_projection_stream(by_object_id, descriptor):
    if (type(descriptor.get("bytes")) is not int or not 0 <= descriptor["bytes"] <= 128_000_000
        or type(descriptor.get("sha256")) is not str
        or re.fullmatch("[0-9a-f]{64}", descriptor["sha256"]) is None
        or type(descriptor.get("receipts")) is not list or len(descriptor["receipts"]) > 128):
        raise ValueError("bounded retained projection stream required")
    chunks, size = [], 0
    for receipt in descriptor["receipts"]:
        event = by_object_id[receipt["object_id"]]
        envelope = event["envelope"]
        payload = envelope["payload"]
        if (envelope["event_type"] not in {"external.runtime_projection_chunk",
                                         "external.runtime_projection_decoded_chunk"}
            or envelope["run_id"] != receipt["run_id"]
            or sha256(canonical_json(payload).encode()).hexdigest() != receipt["payload_sha256"]
            or type(payload["offset"]) is not int or payload["offset"] != size):
            raise ValueError("projection stream receipt, role or sequence differs")
        raw = base64.b64decode(payload["bytes_base64"], validate=True)
        if not raw or len(raw) > 3_000_000:
            raise ValueError("bounded nonempty retained chunk required")
        size += len(raw)
        if size > descriptor["bytes"]:
            raise ValueError("projection stream exceeds declared size")
        chunks.append(raw)
    raw = b"".join(chunks)
    if len(raw) != descriptor["bytes"] or sha256(raw).hexdigest() != descriptor["sha256"]:
        raise ValueError("full projection stream identity differs")
    return raw


def verified_projection_controller(events, row):
    if row.get("transport_exit") != 0 or row.get("transport_failure") or row.get("decode_failure"):
        raise ValueError("complete successful projection transport required")
    by_id = {event["object_id"]: event for event in events}
    stdout = recover_projection_stream(by_id, row["streams"]["stdout"])
    recover_projection_stream(by_id, row["streams"]["stderr"])
    controller = json.loads(stdout)
    if (controller.get("reason") or controller.get("exit_code") != 0
        or controller.get("raw_output_truncated") is not False):
        raise ValueError("complete worker output required")
    raw = base64.b64decode(controller["raw_output_base64"], validate=True)
    if len(raw) != controller["output_bytes"]:
        raise ValueError("controller output length differs")
    worker = decode_result(raw)
    inline = row["controller"]
    if {key: value for key, value in controller.items() if key != "worker"} != {
        key: value for key, value in inline.items() if key != "worker"
    }:
        raise ValueError("inline controller metadata differs from retained transport")
    if "decoded_worker_stream" in row:
        decoded = recover_projection_stream(by_id, row["decoded_worker_stream"])
        if decoded != json.dumps(worker, sort_keys=True, separators=(",", ":")).encode():
            raise ValueError("decoded worker record differs from encoded transport")
        omitted = row["worker_fields_projection"]["omitted_from_inline_only"]
        if (row["worker_fields_projection"]["complete_result_retained"] is not True
            or any(name not in worker for name in omitted)
            or {key: value for key, value in worker.items() if key not in omitted} != inline["worker"]):
            raise ValueError("inline worker projection differs from full record")
    elif worker != inline["worker"]:
        raise ValueError("inline worker differs from retained transport")
    return {**controller, "worker": worker}
