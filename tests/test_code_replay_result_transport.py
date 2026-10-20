import base64
from hashlib import sha256
import json
import lzma
from pathlib import Path
import subprocess
import sys
import zlib

import pytest

from benchmarks.code_replay.result_transport import (
    FORMAT, LZMA_FORMAT, MAX_RESULT_BYTES, MAX_WIRE_BYTES, decode_result, encode_result,
)


def envelope(raw):
    return {
        "format": FORMAT, "result_bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
        "payload_base64": base64.b64encode(zlib.compress(raw)).decode(),
    }


def wire(value):
    return json.dumps(value).encode()


def test_lossless_source_response_above_original_raw_controller_limit():
    result = {"original": {"code.py": "source\n" * 700_000},
              "candidate": {"code.py": "source\n" * 700_000},
              "grading": {"expected_p2p": 2434, "p2p_success": 2434}}
    encoded = encode_result(result)
    assert json.loads(encoded)["result_bytes"] > MAX_WIRE_BYTES
    assert len(encoded) < MAX_WIRE_BYTES
    assert decode_result(encoded) == result


@pytest.mark.parametrize("field,value", [
    ("format", "unknown"), ("result_bytes", True), ("result_bytes", 0),
    ("result_bytes", MAX_RESULT_BYTES + 1), ("result_bytes", 1.5),
    ("sha256", "0" * 64), ("sha256", "Z" * 64),
    ("payload_base64", "!"), ("payload_base64", 1),
])
def test_invalid_envelope_rejected(field, value):
    value_envelope = envelope(b'{"ok":true}')
    value_envelope[field] = value
    with pytest.raises(ValueError):
        decode_result(wire(value_envelope))


@pytest.mark.parametrize("raw", [
    b'{"a":1,"a":2}', b'{"value":NaN}', b'{"value":Infinity}',
    b'{"value":1e9999}',
    b'{"nested":{"x":1,"x":2}}', b'[]', b'{"invalid":"\xff"}',
])
def test_noncanonical_or_nonfinite_result_is_rejected(raw):
    with pytest.raises(ValueError):
        decode_result(wire(envelope(raw)))


def test_duplicate_envelope_members_and_extra_fields_rejected():
    encoded = encode_result({"ok": True})
    with pytest.raises(ValueError):
        decode_result(b'{"format":"unused",' + encoded[1:])
    value = json.loads(encoded)
    value["override"] = True
    with pytest.raises(ValueError):
        decode_result(wire(value))


@pytest.mark.parametrize("suffix", [b"junk", zlib.compress(b'{"extra":true}')])
def test_trailing_and_concatenated_streams_rejected(suffix):
    value = envelope(b'{"ok":true}')
    value["payload_base64"] = base64.b64encode(
        base64.b64decode(value["payload_base64"]) + suffix).decode()
    with pytest.raises(ValueError):
        decode_result(wire(value))


def test_incomplete_stream_and_false_length_rejected():
    value = envelope(b'{"ok":true}')
    compressed = base64.b64decode(value["payload_base64"])
    value["payload_base64"] = base64.b64encode(compressed[:-1]).decode()
    with pytest.raises(ValueError):
        decode_result(wire(value))
    value = envelope(b'{"ok":true}')
    value["result_bytes"] -= 1
    with pytest.raises(ValueError):
        decode_result(wire(value))


def test_decoder_refuses_expansion_beyond_declared_length():
    value = envelope(b'{"data":"' + b"x" * 1_000_000 + b'"}')
    value["result_bytes"] = 16
    with pytest.raises(ValueError):
        decode_result(wire(value))


def test_wire_budget_and_required_object():
    with pytest.raises(ValueError):
        decode_result(b"x" * (MAX_WIRE_BYTES + 1))
    with pytest.raises(ValueError):
        encode_result([])
    with pytest.raises(ValueError):
        encode_result({"bad": float("nan")})


def test_trusted_worker_bootstrap_opt_in_and_default_unchanged(monkeypatch):
    from benchmarks.code_replay.external_source_boundary import bootstrap_source

    original = Path.read_text

    def source(path, *args, **kwargs):
        if path.name == "external_candidate_worker.py":
            return 'import json\nprint(json.dumps({"result":"x"*9000000}),flush=True)\n'
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", source)
    legacy = bootstrap_source("")
    compressed = bootstrap_source("", result_transport="zlib-v1")
    assert "result_printer" not in legacy
    import ast
    ast.parse(compressed, feature_version=(3, 9))
    proc = subprocess.run([sys.executable, "-I", "-S", "-c", compressed],
                          capture_output=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout) < MAX_WIRE_BYTES
    assert decode_result(proc.stdout) == {"result": "x" * 9_000_000}
    with pytest.raises(ValueError):
        bootstrap_source("", result_transport="arbitrary")


def test_result_printer_rejects_multiple_results_without_combining(monkeypatch):
    from io import BytesIO
    from types import SimpleNamespace
    from benchmarks.code_replay.result_transport import result_printer
    destination = BytesIO()
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=destination))
    emit = result_printer()
    emit('{"ok":true}', flush=True)
    with pytest.raises(ValueError):
        emit('{"other":true}')
    assert decode_result(destination.getvalue()) == {"ok": True}


def test_lzma_is_explicit_and_retains_full_result_under_unchanged_caps():
    result = {"original": {"file.py": "real source\n" * 100000},
              "candidate": {"file.py": "real source\n" * 100000}, "grading": {"passed": 24}}
    encoded = encode_result(result, compression="lzma-v2")
    assert json.loads(encoded)["format"] == LZMA_FORMAT
    assert decode_result(encoded) == result
    assert json.loads(encode_result(result))["format"] == FORMAT
    with pytest.raises(ValueError):
        encode_result(result, compression="arbitrary")


@pytest.mark.parametrize("suffix", [b"junk", lzma.compress(b'{"extra":true}')])
def test_lzma_rejects_trailing_or_concatenated_streams(suffix):
    value = json.loads(encode_result({"ok": True}, compression="lzma-v2"))
    value["payload_base64"] = base64.b64encode(base64.b64decode(value["payload_base64"]) + suffix).decode()
    with pytest.raises(ValueError):
        decode_result(wire(value))


def test_lzma_expansion_and_memory_limits_are_enforced():
    value = json.loads(encode_result({"content": "x" * 1000000}, compression="lzma-v2"))
    value["result_bytes"] = 16
    with pytest.raises(ValueError):
        decode_result(wire(value))
    # Dictionary request above the fixed decoder budget, even for tiny content.
    raw = b'{"ok":true}'
    compressed = lzma.compress(raw, format=lzma.FORMAT_XZ,
                             filters=[{"id": lzma.FILTER_LZMA2, "dict_size": 256*1024*1024}])
    value = {"format": LZMA_FORMAT, "result_bytes": len(raw), "sha256": sha256(raw).hexdigest(),
             "payload_base64": base64.b64encode(compressed).decode()}
    with pytest.raises(ValueError):
        decode_result(wire(value))
