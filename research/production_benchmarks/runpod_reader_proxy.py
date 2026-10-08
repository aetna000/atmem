"""Loopback facade that converts long Runpod SSE responses to JSON responses."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import urllib.request


def encoded_upstream_body(
    payload: dict,
    maximum: int,
    *,
    seed: int | None = None,
    stop_sequences: list[str] | None = None,
    include_stop_str_in_output: bool = False,
) -> bytes:
    value = dict(payload)
    value["stream"] = True
    value["stream_options"] = {"include_usage": True}
    if seed is not None:
        value["seed"] = seed
    if stop_sequences:
        value["stop"] = stop_sequences
        value["include_stop_str_in_output"] = include_stop_str_in_output
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if maximum <= 0 or len(encoded) > maximum:
        raise ValueError("serialized reader request exceeds the frozen byte budget")
    return encoded


class Handler(BaseHTTPRequestHandler):
    server_version = "AtMemRunpodReaderProxy/1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        maximum = int(os.environ.get("ATMEM_READER_REQUEST_MAX_BYTES", "0"))
        if maximum <= 0 or length <= 0 or length > maximum:
            self.send_error(413, "reader request exceeds the frozen byte budget")
            return
        payload = json.loads(self.rfile.read(length))
        try:
            upstream_body = encoded_upstream_body(
                payload,
                maximum,
                seed=int(os.environ["ATMEM_READER_SEED"]),
                stop_sequences=json.loads(
                    os.environ["ATMEM_READER_STOP_SEQUENCES"]
                ),
                include_stop_str_in_output=(
                    os.environ["ATMEM_READER_INCLUDE_STOP_STR"] == "1"
                ),
            )
        except ValueError:
            self.send_error(413, "serialized reader request exceeds the frozen byte budget")
            return
        request = urllib.request.Request(
            os.environ["ATMEM_RUNPOD_UPSTREAM_URL"].rstrip("/")
            + "/chat/completions",
            data=upstream_body,
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
        if finish_reason != "stop" or not "".join(content).strip():
            self.send_error(502, "reader did not produce a complete final answer")
            return
        if int(usage.get("prompt_tokens") or 0) <= 0 or int(
            usage.get("completion_tokens") or 0
        ) <= 0:
            self.send_error(502, "reader response lacks complete token usage")
            return
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
