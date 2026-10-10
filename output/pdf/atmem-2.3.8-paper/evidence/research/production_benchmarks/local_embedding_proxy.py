"""Deterministic, local OpenAI-compatible embeddings for matched benchmarks.

The benchmark compares memory architectures rather than embedding vendors.
Keeping this route local gives every retrieval arm the same content-blind
embedding function, removes a third paid provider, and makes formation
checkpoints reusable after an ephemeral reader pod is terminated.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import math
from pathlib import Path
import re


MODEL = "atmem/hash-bow-768-v1"
DIMENSIONS = 768


def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for token in re.findall(r"\w+", text.casefold()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") not in {"", "/health", "/v1/models"}:
            self.send_error(404)
            return
        self._json(200, {
            "object": "list",
            "data": [{"id": MODEL, "object": "model", "owned_by": "local"}],
        })

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/v1/embeddings":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8 * 1024 * 1024:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            if payload.get("model") != MODEL:
                raise ValueError("unsupported embedding model")
            inputs = payload.get("input")
            texts = [inputs] if isinstance(inputs, str) else inputs
            if not isinstance(texts, list) or not texts or not all(
                isinstance(value, str) for value in texts
            ):
                raise ValueError("input must be a string or non-empty string array")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": {"message": str(exc)}})
            return
        self._json(200, {
            "object": "list",
            "model": MODEL,
            "data": [
                {"object": "embedding", "index": index, "embedding": embed(text)}
                for index, text in enumerate(texts)
            ],
            "usage": {
                "prompt_tokens": sum(len(text.split()) for text in texts),
                "total_tokens": sum(len(text.split()) for text in texts),
            },
        })

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready-file", required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ready = Path(args.ready_file).expanduser().resolve()
    ready.parent.mkdir(parents=True, exist_ok=True)
    ready.write_text(json.dumps({
        "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        "model": MODEL,
        "dimensions": DIMENSIONS,
    }) + "\n", encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
