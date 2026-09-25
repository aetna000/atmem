"""Separate local destination with a supervisor-only truth channel.

This generic effect service is a smoke fixture, not a tau retail implementation.
No HTTP route exposes the ledger. OS-level hostile-process isolation is not claimed.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import sqlite3
import threading
import time
from typing import Any
import urllib.error
import urllib.request

from .manifest import digest


def request(url: str, token: str, route: str, body: dict, timeout: float = 10) -> dict:
    req = urllib.request.Request(url + route, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        return {"error": f"http_{exc.code}"}
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return {"outcome": "unknown", "reason": "transport_failure"}


def serve(control: Any, events: Any, release: Any, capability: str,
          fault: str | None, token: str, retention: float = 3600,
          visibility: float = 0, drop_request: bool = False) -> None:
    if capability not in {"I", "Q", "N"}:
        raise ValueError("unknown destination capability")
    # Only this process owns the ledger and its SQLite handle.
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE effects (seq INTEGER PRIMARY KEY, operation TEXT, payload TEXT, effect TEXT, committed REAL)")
    lock = threading.Lock()
    event_lock = threading.Lock()
    fired = False
    dropped = False
    request_states: dict[str, str] = {}

    def emit(event: dict) -> None:
        with event_lock:
            events.send(event)

    def barrier(name: str) -> None:
        nonlocal fired
        if fault == name and not fired:
            fired = True
            emit({"barrier": name, "producer": "destination", "time_ns": time.monotonic_ns()})
            if not release.wait(30):
                raise TimeoutError("supervisor did not release destination")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            pass

        def reply(self, value: dict, code: int = 200) -> None:
            data = json.dumps(value).encode()
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected after the supervisor kills a worker.

        def do_POST(self) -> None:
            nonlocal dropped
            if self.headers.get("Authorization") != "Bearer " + token:
                self.reply({"error": "unauthorized"}, 401)
                return
            if self.path not in {"/effects", "/status"}:
                self.reply({"error": "not_found"}, 404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    raise ValueError("body size")
                body = json.loads(self.rfile.read(size))
                operation = body["operation_id"]
                if not isinstance(operation, str) or not operation:
                    raise ValueError("operation_id")
            except (ValueError, KeyError, TypeError):
                self.reply({"error": "invalid_request"}, 400)
                return
            with lock:
                row = db.execute("SELECT payload,effect,committed FROM effects WHERE operation=? ORDER BY seq LIMIT 1", (operation,)).fetchone()
                request_state = request_states.get(operation)
            if self.path == "/status":
                if capability != "Q":
                    self.reply({"outcome": "unknown", "reason": "query_unsupported"})
                elif row is None and request_state == "aborted":
                    self.reply({"outcome": "confirmed_failed", "reason": "fenced_abort_no_inflight_writer"})
                elif row is None or time.monotonic() - row[2] < visibility:
                    self.reply({"outcome": "unknown", "reason": "not_visible_or_in_flight"})
                else:
                    self.reply({"outcome": "confirmed_succeeded", "effect_id": row[1], "payload_digest": row[0]})
                return
            if "payload" not in body:
                self.reply({"error": "payload_required"}, 400)
                return
            payload_hash = digest(body["payload"])
            # Serialize check + commit: concurrent same-key calls cannot both insert.
            with lock:
                row = db.execute("SELECT payload,effect,committed FROM effects WHERE operation=? ORDER BY seq LIMIT 1", (operation,)).fetchone()
                if capability == "I" and row:
                    if row[0] != payload_hash:
                        self.reply({"error": "idempotency_payload_conflict"}, 409)
                    elif time.monotonic() - row[2] > retention:
                        self.reply({"outcome": "unknown", "reason": "key_retention_expired"})
                    else:
                        self.reply({"outcome": "confirmed_succeeded", "effect_id": row[1], "payload_digest": row[0], "replayed": True})
                    return
                request_states[operation] = "pending"
                barrier("in_flight")
                if drop_request and not dropped:
                    dropped = True
                    request_states[operation] = "aborted"
                    self.reply({"outcome": "confirmed_failed", "reason": "fenced_abort_no_inflight_writer"})
                    emit({"destination_settled": True, "aborted": True, "producer": "destination"})
                    return
                effect_id = secrets.token_hex(12)
                db.execute("INSERT INTO effects(operation,payload,effect,committed) VALUES(?,?,?,?)",
                           (operation, payload_hash, effect_id, time.monotonic()))
                db.commit()
                request_states[operation] = "committed"
                barrier("after_commit")
            self.reply({"outcome": "confirmed_succeeded", "effect_id": effect_id, "payload_digest": payload_hash})
            emit({"destination_settled": True, "producer": "destination"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    control.send({"url": f"http://127.0.0.1:{server.server_port}"})
    try:
        while True:
            command = control.recv()
            if command == "stop":
                break
            if command == "request_states":
                with lock:
                    control.send(dict(request_states))
                continue
            if command != "snapshot":
                control.send({"error": "unknown_control"})
                continue
            with lock:
                rows = db.execute("SELECT seq,operation,payload,effect FROM effects ORDER BY seq").fetchall()
            control.send([dict(zip(("sequence", "operation_id", "payload_digest", "effect_id"), row)) for row in rows])
    finally:
        server.shutdown()
        server.server_close()
        db.close()
