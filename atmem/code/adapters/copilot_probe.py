"""Isolated, offline Copilot activation probe; never edits owner trust."""

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
from atmem.code.adapters.copilot import CopilotAdapter
from atmem.code.identity import repository_key
from atmem.core.canonical import canonical_json


def copilot_probe(*, store, subject, project, root, credential, initial, command):
    token = "ATMEM_CANARY_" + secrets.token_hex(16)
    prompt = "Reply probe complete. Reference " + secrets.token_hex(16)
    probe_id = sha256(credential).hexdigest()
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"data":[],"object":"list"}')

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                self.send_error(400)
                return
            value = json.loads(self.rfile.read(size))
            if token in json.dumps(value):
                observed.append(sha256(canonical_json(value).encode()).hexdigest())
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in (({"role": "assistant", "content": "Probe complete."}, None), ({}, "stop")):
                chunk = {"id": "chatcmpl-probe", "object": "chat.completion.chunk", "created": 1,
                         "model": value.get("model", "gpt-4.1"), "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="atmem-copilot-probe-") as temporary:
            base = Path(temporary)
            probe_root = base / "project"
            probe_root.mkdir()
            subprocess.run(["git", "init", "-q", str(probe_root)], check=True, capture_output=True, timeout=5)
            home = base / "home"
            home.mkdir(mode=0o700)
            (home / "config.json").write_text(json.dumps({"trustedFolders": [str(probe_root.resolve())]}))
            adapter = CopilotAdapter(probe_root, command)
            path = adapter.configuration_path()
            path.parent.mkdir(parents=True)
            path.write_bytes(adapter.planned_configuration(None))
            store.put_code_document(subject, project, "probe", probe_id, {
                "prompt": prompt, "canary": token, "hook_seen": False,
                "repository_key": repository_key(probe_root),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()})
            environment = {key: value for key, value in os.environ.items()
                           if key in {"PATH", "HOME", "TMPDIR", "SHELL", "LANG", "SystemRoot"}}
            environment.update(COPILOT_HOME=str(home), COPILOT_OFFLINE="true", COPILOT_MODEL="gpt-4.1",
                               COPILOT_PROVIDER_BASE_URL=f"http://127.0.0.1:{server.server_port}/v1",
                               COPILOT_PROVIDER_TYPE="openai", COPILOT_PROVIDER_WIRE_API="completions")
            run = subprocess.run(["copilot", "-p", prompt, "--allow-all-tools", "--disable-builtin-mcps",
                                  "--no-auto-update", "--no-custom-instructions", "--no-ask-user",
                                  "--no-remote", "--no-remote-export", "--silent"],
                                 cwd=probe_root, env=environment, capture_output=True, text=True, timeout=40)
        receipt = store.code_document(subject, project, "probe", probe_id) or {}
        okay = run.returncode == 0 and bool(observed) and receipt.get("hook_seen") is True
        evidence = sha256(canonical_json({"version": initial.version, "platform": initial.platform,
                                          "requests": observed, "hook_seen": receipt.get("hook_seen"),
                                          "returncode": run.returncode}).encode()).hexdigest()
        return HostProbe(initial.host, initial.version, initial.platform, okay, okay,
                         "model_input_observed", evidence if okay else None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        store.delete_code_documents(subject, project, "probe", probe_id)
