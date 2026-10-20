"""Offline installed-Claude delivery probe with a local protocol endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from threading import Thread

from atmem.code.adapters.base import HostProbe
from atmem.core.canonical import canonical_json


def claude_probe(*, store, subject: str, project: str, root: Path, credential: bytes, initial: HostProbe, command: str,
                 prompt_override: str | None = None, expected_context: str | None = None, canary_mode: bool = True) -> HostProbe:
    token = expected_context or "ATMEM_CANARY_" + secrets.token_hex(16)
    prompt = prompt_override or "Reply with probe complete. Probe reference " + secrets.token_hex(16)
    probe_id = sha256(credential).hexdigest()
    challenge = {"prompt": prompt, "canary": token, "hook_seen": False,
                 "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()}
    if canary_mode:
        store.put_code_document(subject, project, "probe", probe_id, challenge)
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                self.send_error(400)
                return
            value = json.loads(self.rfile.read(size))
            if "count_tokens" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"input_tokens":100}')
                return
            if token in json.dumps(value):
                observed.append(sha256(canonical_json(value).encode()).hexdigest())
            message = {"id": "msg-atmem-probe", "type": "message", "role": "assistant", "model": value.get("model", "claude"),
                       "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens":100,"output_tokens":1}}
            events = [("message_start", {"type":"message_start","message":message}),
                      ("content_block_start", {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}),
                      ("content_block_delta", {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Probe complete."}}),
                      ("content_block_stop", {"type":"content_block_stop","index":0}),
                      ("message_delta", {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":None},"usage":{"output_tokens":3}}),
                      ("message_stop", {"type":"message_stop"})]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for event, data in events:
                self.wfile.write(("event: " + event + "\ndata: " + json.dumps(data) + "\n\n").encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="atmem-claude-probe-") as config:
            settings = Path(config) / "probe-settings.json"
            settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [
                {"type": "command", "command": command, "timeout": 10}]}]}}), encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "SHELL", "LANG", "SystemRoot"}}
            environment.update(ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_port}",
                               ANTHROPIC_API_KEY="offline-probe-not-a-provider-key", CLAUDE_CONFIG_DIR=config,
                               CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
            run = subprocess.run(["claude", "-p", prompt, "--max-turns", "1", "--tools", "", "--setting-sources", "", "--settings", str(settings)],
                                 cwd=root, env=environment, text=True, capture_output=True, timeout=40, check=False)
        receipt = store.code_document(subject, project, "probe", probe_id) or {}
        okay = run.returncode == 0 and bool(observed) and (receipt.get("hook_seen") is True if canary_mode else True)
        evidence = sha256(canonical_json({"host": initial.host, "version": initial.version, "platform": initial.platform,
                                          "model_request_sha256": observed, "hook_seen": receipt.get("hook_seen"),
                                          "returncode": run.returncode}).encode()).hexdigest()
        return HostProbe(initial.host, initial.version, initial.platform, okay, okay, "model_input_observed", evidence if okay else None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if canary_mode:
            store.delete_code_documents(subject, project, "probe", probe_id)
