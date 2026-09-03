"""Bounded loopback HTTP service for delegated context providers."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from typing import Any


PROVIDER_PATH = "/v1/delegated-context"
MAX_REQUEST_BYTES = 150_000


def create_server(runtime: Any, host: str, port: int) -> ThreadingHTTPServer:
    address = ipaddress.ip_address(host)
    if not address.is_loopback or host not in {"127.0.0.1", "::1"}:
        raise ValueError("provider service must bind to a numeric loopback address")

    class Handler(BaseHTTPRequestHandler):
        server_version = "AtMemProvider/1"

        def do_GET(self) -> None:
            if self.path != "/health":
                self._send(404, {"error": "not_found"})
                return
            self._send(200, {"status": "ready", **runtime.status()})

        def do_POST(self) -> None:
            if self.path != PROVIDER_PATH:
                self._send(404, {"error": "not_found"})
                return
            if self.headers.get_content_type() != "application/json":
                self._send(415, {"error": "content_type_must_be_application_json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 1 <= length <= MAX_REQUEST_BYTES:
                self._send(413, {"error": "request_size_outside_policy"})
                return
            raw = self.rfile.read(length)
            try:
                result = runtime.handle(raw)
            except TimeoutError:
                self._send(504, {"error": "provider_deadline_elapsed"})
                return
            except (ValueError, RuntimeError):
                self._send(422, {"error": "provider_request_rejected"})
                return
            except Exception:
                self._send(503, {"error": "provider_unavailable"})
                return
            self._send(200, result)

        def _send(self, status: int, value: dict[str, Any]) -> None:
            body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def serve(runtime: Any, host: str, port: int) -> None:
    server = create_server(runtime, host, port)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
