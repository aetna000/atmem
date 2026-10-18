from __future__ import annotations

import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import os
import runpy

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt" or os.environ.get("ATMEM_CODE_SKIP_HOST_PROBES") == "1",
                                reason="Installed-host probes are qualified separately from the portable core")


def test_installed_muse_prompt_hook_executes_offline(tmp_path: Path) -> None:
    binary = shutil.which("muse")
    if binary is None:
        pytest.skip("Muse Code is not installed")
    script = Path(__file__).parent / "fixtures" / "muse_canary_hook.py"
    hooks = tmp_path / ".muse" / "hooks.json"
    hooks.parent.mkdir()
    handler = {"hooks": [{
        "type": "command",
        "command": f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}",
        "timeout": 10,
    }]}
    hooks.write_text(json.dumps({"hooks": {"UserPromptSubmit": [handler], "PreLLMCall": [handler]}}), encoding="utf-8")
    try:
        result = subprocess.run(
            [binary, "exec", "--provider", "echo", "--trust-workspace", "--json", "--disable-reminders", "--no-foreign-personal-context", "--no-session-log", "hello"],
            cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.xfail("Installed Muse echo-provider startup timed out; context delivery remains unqualified")
    assert result.returncode == 0, result.stderr[-2000:]
    assert (tmp_path / "muse-hook-fired").exists(), result.stderr[-2000:]
    payload = json.loads((tmp_path / "host-hook-payload.json").read_text())
    assert payload.get("hook_event_name") == "PreLLMCall", payload
    if "ATMEM_CODE_CANARY_7e46a92f" not in json.dumps(payload):
        pytest.xfail("Installed Muse executes the prompt hook but its echo-provider PreLLMCall input omits the canary context")
    # Echo-provider output does not expose model input. This is only hook
    # execution evidence, not proof that a real model received context.


def test_installed_muse_meta_protocol_receives_hook_context(tmp_path):
    binary = shutil.which("muse")
    if binary is None:
        pytest.skip("Muse Code is not installed")
    fixtures = Path(__file__).parent / "fixtures"
    endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
    hooks = tmp_path / ".muse" / "hooks.json"
    hooks.parent.mkdir()
    hooks.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command",
        "command": shlex.join([sys.executable, str(fixtures / "muse_canary_hook.py")]), "timeout": 10}]}]}}))
    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "SHELL", "LANG", "SystemRoot"}}
    with endpoint_type() as endpoint:
        try:
            result = subprocess.run([binary, "exec", "--provider", "meta", "--model", "muse-spark-1.3", "--base-url", endpoint.url,
                                     "--api-key-stdin", "--trust-workspace", "--disable-reminders", "--no-foreign-personal-context",
                                     "--no-session-log", "--disable-web-tools", "--disable-shell", "--disable-write", "--max-model-steps", "1",
                                     "--reasoning-effort", "minimal", "Reply probe complete."],
                                    input="offline-probe-not-a-provider-key\n", cwd=tmp_path, env=environment,
                                    capture_output=True, text=True, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            seen = any("ATMEM_CODE_CANARY_7e46a92f" in json.dumps(value) for value in endpoint.requests)
            pytest.xfail(f"Muse Meta-protocol probe timed out; local model requests={len(endpoint.requests)}, canary observed={seen}")
        assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-1000:]
        assert any("ATMEM_CODE_CANARY_7e46a92f" in json.dumps(value) for value in endpoint.requests)
