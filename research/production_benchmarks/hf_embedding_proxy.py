"""Loopback-only OpenAI embedding facade for a pinned HF provider route."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from huggingface_hub import InferenceClient


MODEL = "Qwen/Qwen3-Embedding-8B"
PROVIDER = "scaleway"


class Handler(BaseHTTPRequestHandler):
    server_version = "AtMemHFEmbeddingProxy/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path != "/v1/embeddings":
            self.send_error(404)
            return
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1_000_000:
            self.send_error(413)
            return
        try:
            request = json.loads(self.rfile.read(length))
            if request.get("model") not in {MODEL, f"{MODEL}:{PROVIDER}"}:
                raise ValueError("unexpected embedding model")
            inputs = request.get("input")
            values = inputs if isinstance(inputs, list) else [inputs]
            if not values or any(not isinstance(value, str) for value in values):
                raise ValueError("embedding input must be text or a non-empty text list")
            client = InferenceClient(
                provider=PROVIDER, api_key=authorization.removeprefix("Bearer ")
            )
            vectors = [client.feature_extraction(value, model=MODEL) for value in values]
            normalized = []
            for vector in vectors:
                materialized = vector.tolist() if hasattr(vector, "tolist") else list(vector)
                if (
                    len(materialized) == 1
                    and isinstance(materialized[0], list)
                ):
                    materialized = materialized[0]
                if not materialized or not all(
                    isinstance(item, (int, float)) for item in materialized
                ):
                    raise ValueError("provider returned a non-vector embedding")
                normalized.append(materialized)
            payload = {
                "object": "list",
                "model": f"{MODEL}:{PROVIDER}",
                "data": [
                    {
                        "object": "embedding", "index": index,
                        "embedding": vector,
                    }
                    for index, vector in enumerate(normalized)
                ],
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            }
            body = json.dumps(payload, separators=(",", ":")).encode()
        except Exception as exc:
            body = json.dumps({
                "error": {"type": type(exc).__name__, "message": "embedding request failed"}
            }).encode()
            self.send_response(502)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready-file", required=True)
    args = parser.parse_args()
    ready = Path(args.ready_file).expanduser().resolve()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ready.write_text(
        json.dumps({"base_url": f"http://127.0.0.1:{server.server_port}/v1"}) + "\n",
        encoding="utf-8",
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
