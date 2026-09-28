"""Loopback facade that converts long Runpod SSE responses to JSON responses."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import urllib.request


class Handler(BaseHTTPRequestHandler):
    server_version = "AtMemRunpodReaderProxy/1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        request = urllib.request.Request(
            os.environ["ATMEM_RUNPOD_UPSTREAM_URL"].rstrip("/")
            + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + os.environ["RUNPOD_READER_API_KEY"],
                "Content-Type": "application/json",
                "User-Agent": "OpenAI/Python 3.19.2",
            },
        )
        content: list[str] = []
        reasoning: list[str] = []
        response_id = ""
        model = str(payload.get("model") or "")
        finish_reason = None
        usage: dict[str, int] = {}
        with urllib.request.urlopen(request, timeout=43_200) as upstream:
            for raw_line in upstream:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                response_id = str(chunk.get("id") or response_id)
                model = str(chunk.get("model") or model)
                if chunk.get("usage"):
                    usage = {
                        key: int(value)
                        for key, value in dict(chunk["usage"]).items()
                        if isinstance(value, (int, float))
                    }
                for choice in chunk.get("choices") or []:
                    delta = dict(choice.get("delta") or {})
                    if isinstance(delta.get("content"), str):
                        content.append(delta["content"])
                    if isinstance(delta.get("reasoning_content"), str):
                        reasoning.append(delta["reasoning_content"])
                    finish_reason = choice.get("finish_reason") or finish_reason
        result = {
            "id": response_id,
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "".join(content),
                    "reasoning_content": "".join(reasoning),
                },
                "finish_reason": finish_reason,
            }],
            "usage": usage,
        }
        encoded = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready-file", required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ready = Path(args.ready_file)
    ready.write_text(
        json.dumps({"base_url": f"http://127.0.0.1:{server.server_port}/v1"}),
        encoding="utf-8",
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
