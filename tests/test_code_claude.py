"""Installed-host hook probe against an isolated local model protocol server."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt" or os.environ.get("ATMEM_CODE_SKIP_HOST_PROBES") == "1",
                                reason="Installed-host probes are qualified separately from the portable core")


def test_installed_claude_includes_prompt_hook_context_in_model_request(tmp_path):
    binary = shutil.which("claude")
    if not binary:
        pytest.skip("Claude Code is not installed")
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(value)
            if "count_tokens" in self.path:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(b'{"input_tokens":100}')
                return
            message = {"id": "msg-canary", "type": "message", "role": "assistant", "model": value.get("model", "claude"),
                       "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens":100,"output_tokens":1}}
            events = [("message_start", {"type":"message_start","message":message}),
                      ("content_block_start", {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}),
                      ("content_block_delta", {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Canary complete."}}),
                      ("content_block_stop", {"type":"content_block_stop","index":0}),
                      ("message_delta", {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":None},"usage":{"output_tokens":3}}),
                      ("message_stop", {"type":"message_stop"})]
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for event, data in events:
                self.wfile.write(("event: " + event + "\ndata: " + json.dumps(data) + "\n\n").encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        settings = tmp_path / ".claude" / "settings.local.json"
        settings.parent.mkdir()
        script = Path(__file__).parent / "fixtures" / "muse_canary_hook.py"
        command = shlex.join([sys.executable, str(script)])
        settings.write_text(json.dumps({"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":command}]}]}}))
        environment = {key: value for key,value in os.environ.items() if key in {"PATH","HOME","TMPDIR","SHELL","LANG","SystemRoot"}}
        environment.update(ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_port}",
                           ANTHROPIC_API_KEY="offline-probe-not-a-provider-key", CLAUDE_CONFIG_DIR=str(tmp_path / ".claude-home"),
                           CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
        result = subprocess.run([binary, "-p", "Reply with canary complete.", "--max-turns", "1", "--tools", "", "--setting-sources", "project,local"],
                                cwd=tmp_path, env=environment, text=True, capture_output=True, timeout=45, check=False)
        assert result.returncode == 0, result.stderr[-1500:] + result.stdout[-1500:]
        assert (tmp_path / "host-hook-payload.json").exists()
        assert any("ATMEM_CODE_CANARY_7e46a92f" in json.dumps(value) for value in requests)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_installed_claude_enable_pause_resume_and_uninstall(tmp_path):
    if not shutil.which("claude"):
        pytest.skip("Claude Code is not installed")
    pytest.importorskip("sqlcipher3")
    from atmem.code.install import CodeInstall
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    root = tmp_path / "project with spaces"
    root.mkdir()
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    try:
        installer = CodeInstall(memory.store)
        installer.setup(root, subject_id="local", profile_id="shared", agent_id="claude", host="claude", apply=True)
        from atmem.code.application import CodeApplication
        CodeApplication(memory, subject_id='local').settings(installer.status(project=root, subject_id='local', host='claude')['project_id'], {'context_mode': 'content'})
        active = installer.enable(project=root, subject_id="local", host="claude")
        assert active["enabled"] and active["host"]["automatic_verified"]
        path = root / ".claude" / "settings.local.json"
        configured = path.read_bytes()
        from atmem.code.adapters.probe import claude_probe
        from atmem.code.adapters.claude import ClaudeAdapter
        from atmem.evidence.crypto import load_existing_key
        import shlex
        command = json.loads(configured)["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        argv = shlex.split(command)
        credential = load_existing_key(argv[argv.index("--credential-file") + 1])
        initial = ClaudeAdapter(root, command).probe()
        common = dict(store=memory.store, subject="local", project=active["project_id"], root=root,
                      credential=credential, initial=initial, command=command, canary_mode=False)
        claude_probe(**common, prompt_override="Remember that my preferred formatter is Ruff.")
        from atmem.code.application import CodeApplication
        assert "Ruff" in CodeApplication(memory, subject_id="local").records(active["project_id"])[0]["content"]
        delivery = claude_probe(**common, prompt_override="Which formatter should I use?", expected_context="Ruff")
        assert delivery.automatic and delivery.assurance == "model_input_observed"
        installer.disable(project=root, subject_id="local", host="claude")
        assert path.read_bytes() == configured
        assert installer.enable(project=root, subject_id="local", host="claude")["enabled"]
        installer.disable(project=root, subject_id="local", host="claude")
        installer.uninstall(project=root, subject_id="local", host="claude")
        assert not path.exists()
    finally:
        memory.close()
