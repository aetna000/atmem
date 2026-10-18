"""Opt-in lossless worker-result framing; never alters controller/grade limits."""
import base64
from hashlib import sha256
import json
import lzma
import math
import re
import sys
import zlib


FORMAT = "atmem-benchmark-result-zlib-v1"
LZMA_FORMAT = "atmem-benchmark-result-lzma-v2"
MAX_WIRE_BYTES = 8_000_000
MAX_RESULT_BYTES = 128_000_000
FIELDS = {"format", "result_bytes", "sha256", "payload_base64"}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON constant")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number")
    return result


def _parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=_constant,
                          parse_float=_float)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid result JSON") from exc


def encode_result(result, *, compression="zlib-v1"):
    """Return one complete envelope, or fail without truncating any field."""
    if type(result) is not dict:
        raise ValueError("worker result object required")
    raw = json.dumps(result, ensure_ascii=True, allow_nan=False,
                     sort_keys=True, separators=(",", ":")).encode("ascii")
    if not 1 <= len(raw) <= MAX_RESULT_BYTES:
        raise ValueError("decoded result budget exceeded")
    if compression not in {"zlib-v1", "lzma-v2"}:
        raise ValueError("explicit supported result compression required")
    compressed = (zlib.compress(raw) if compression == "zlib-v1"
                  else lzma.compress(raw, format=lzma.FORMAT_XZ, preset=7))
    envelope = {
        "format": FORMAT if compression == "zlib-v1" else LZMA_FORMAT,
        "result_bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
        "payload_base64": base64.b64encode(compressed).decode("ascii"),
    }
    wire = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")
    # Reserve the worker printer's terminal newline inside the controller cap.
    if len(wire) + 1 > MAX_WIRE_BYTES:
        raise ValueError("encoded result budget exceeded")
    return wire


def decode_result(wire):
    """Verify framing, bounded expansion and exact content before JSON parsing."""
    if type(wire) is not bytes or not 1 <= len(wire) <= MAX_WIRE_BYTES:
        raise ValueError("bounded encoded result bytes required")
    envelope = _parse(wire)
    if (type(envelope) is not dict or set(envelope) != FIELDS
        or envelope["format"] not in {FORMAT, LZMA_FORMAT}
        or type(envelope["result_bytes"]) is not int
        or not 1 <= envelope["result_bytes"] <= MAX_RESULT_BYTES
        or type(envelope["sha256"]) is not str
        or re.fullmatch("[0-9a-f]{64}", envelope["sha256"]) is None
        or type(envelope["payload_base64"]) is not str):
        raise ValueError("unsupported result envelope")
    try:
        compressed = base64.b64decode(envelope["payload_base64"], validate=True)
        if envelope["format"] == FORMAT:
            decoder = zlib.decompressobj()
        else:
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128_000_000)
        raw = decoder.decompress(compressed, envelope["result_bytes"] + 1)
    except (ValueError, zlib.error, lzma.LZMAError) as exc:
        raise ValueError("invalid compressed result") from exc
    if (len(raw) != envelope["result_bytes"] or not decoder.eof
        or getattr(decoder, "unconsumed_tail", b"") or decoder.unused_data
        or sha256(raw).hexdigest() != envelope["sha256"]):
        raise ValueError("result length, stream or digest differs")
    result = _parse(raw)
    if type(result) is not dict:
        raise ValueError("worker result object required")
    return result


def result_printer(*, compression="zlib-v1"):
    """Operator-injected single JSON print sink for a trusted worker main."""
    emitted = False

    def emit(value, *, flush=False):
        nonlocal emitted
        if emitted or type(value) is not str or type(flush) is not bool:
            raise ValueError("exactly one worker JSON result required")
        result = _parse(value)
        encoded = encode_result(result, compression=compression)
        emitted = True
        sys.stdout.buffer.write(encoded + b"\n")
        if flush:
            sys.stdout.buffer.flush()

    return emit
