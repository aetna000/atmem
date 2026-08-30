"""Private headless companion protocol for AtMem."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
from urllib.parse import urlparse

from atbot.companion import CompanionRuntime
from atbot.config import AtBotConfig


def make_handler(companion: CompanionRuntime, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AtBotCompanion/0.1"

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def _json(self, status: int, value: object) -> None:
            body = json.dumps(value, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, object]:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 1_000_000:
                raise ValueError("request is too large")
            value = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("request must be a JSON object")
            return value

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/api/companion/health"}:
                self._json(200, {**companion.capabilities(), "csrf_token": token})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not secrets.compare_digest(self.headers.get("X-AtBot-CSRF", ""), token):
                self._json(403, {"error": "companion authentication failed"})
                return
            try:
                value = self._body()
                if self.path == "/api/companion/expand-query":
                    if set(value) - {"query"}:
                        raise ValueError("query expansion accepts query only")
                    self._json(200, companion.expand_query(str(value.get("query") or "")))
                    return
                if self.path == "/api/companion/query":
                    candidates = value.get("candidates") or []
                    if not isinstance(candidates, list):
                        raise ValueError("candidates must be an array")
                    self._json(
                        200,
                        companion.answer_query(
                            query=str(value.get("query") or ""),
                            candidates=[row for row in candidates if isinstance(row, dict)],
                            remote=bool(value.get("remote", False)),
                        ),
                    )
                    return
                if self.path == "/api/companion/propose":
                    if set(value) - {"message", "remote"}:
                        raise ValueError("proposal extraction accepts message and remote only")
                    self._json(
                        200,
                        companion.propose_memories(
                            str(value.get("message") or ""),
                            remote=bool(value.get("remote", False)),
                        ),
                    )
                    return
                self._json(404, {"error": "not found"})
            except (TypeError, ValueError) as exc:
                self._json(400, {"error": str(exc)})

    return Handler


def serve(config: AtBotConfig, *, host: str, port: int, open_browser: bool = False) -> None:
    del open_browser
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("AtBot companion must bind to loopback")
    companion = CompanionRuntime(config)
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((host, port), make_handler(companion, token))
    print(f"AtBot companion: http://{host}:{server.server_port}/", flush=True)
    print("Headless memory intelligence for AtMem; Ctrl-C stops it.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
