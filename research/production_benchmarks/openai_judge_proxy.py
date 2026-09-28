"""Single-egress, content-free usage proxy for the pinned OpenAI judge."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import urllib.error
import urllib.request


MODEL = "gpt-5.2-2025-12-11"
UPSTREAM = "https://api.openai.com/v1/chat/completions"
MAX_REQUEST_BYTES = 131_072
MAX_COMPLETION_TOKENS = 4_096
INPUT_USD_PER_MILLION = 1.75
OUTPUT_USD_PER_MILLION = 14.0
RESERVED_MAXIMUM_USD = 0.29


class State:
    def __init__(self, usage_file: Path, upstream_api_key: str) -> None:
        self.usage_file = usage_file
        self.upstream_api_key = upstream_api_key
        self.lock = threading.Lock()
        self.egress_started = False


def _write_json_durable(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    if os.name == "posix":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _completed_usage(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not isinstance(value.get("usage"), dict):
        raise ValueError("provider response is missing usage")
    usage = value["usage"]
    if "prompt_tokens" not in usage or "completion_tokens" not in usage:
        raise ValueError("provider response has incomplete usage")
    prompt_tokens = int(usage["prompt_tokens"])
    completion_tokens = int(usage["completion_tokens"])
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError("provider returned invalid usage")
    cost = (
        prompt_tokens * INPUT_USD_PER_MILLION
        + completion_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    return {
        "format": "atmem-openai-judge-usage-v1",
        "model": MODEL,
        "state": "completed",
        "requests": 1,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 9),
        "content_retained": False,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AtMemOpenAIJudgeProxy/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        authorization = self.headers.get("Authorization", "")
        if authorization != "Bearer local-proxy":
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self.send_error(413)
            return
        body = self.rfile.read(length)
        try:
            request_body = json.loads(body)
            if request_body.get("model") != MODEL:
                raise ValueError("unexpected judge model")
            maximum = int(request_body.get("max_completion_tokens", 0))
            if maximum <= 0 or maximum > MAX_COMPLETION_TOKENS:
                raise ValueError("judge completion limit exceeds the reviewed cap")
            if request_body.get("stream") not in {None, False}:
                raise ValueError("streaming judge responses are not allowed")
            if int(request_body.get("n", 1)) != 1:
                raise ValueError("the judge proxy permits exactly one completion")
        except (TypeError, ValueError, json.JSONDecodeError):
            self.send_error(400)
            return
        state: State = self.server.state  # type: ignore[attr-defined]
        with state.lock:
            if state.egress_started:
                self.send_error(429, "judge egress already consumed")
                return
            state.egress_started = True
            _write_json_durable(
                state.usage_file,
                {
                    "format": "atmem-openai-judge-usage-v1",
                    "model": MODEL,
                    "state": "egress_started",
                    "requests": 1,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "cost_usd": RESERVED_MAXIMUM_USD,
                    "content_retained": False,
                },
            )
        upstream = urllib.request.Request(
            UPSTREAM,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {state.upstream_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(upstream, timeout=43_200) as response:
                response_body = response.read()
                status = response.status
            parsed = json.loads(response_body)
            _write_json_durable(state.usage_file, _completed_usage(parsed))
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status = exc.code
        except Exception:
            response_body = json.dumps(
                {"error": {"message": "judge proxy request failed"}}
            ).encode()
            status = 502
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--usage-file", required=True)
    args = parser.parse_args()
    ready = Path(args.ready_file).expanduser().resolve()
    usage = Path(args.usage_file).expanduser().resolve()
    upstream_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not upstream_api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.state = State(usage, upstream_api_key)  # type: ignore[attr-defined]
    _write_json_durable(
        ready,
        {"base_url": f"http://127.0.0.1:{server.server_port}/v1"},
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
