"""Only isolated, explicitly vetted hooks may use the per-invocation trust flag."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import runpy

helpers = runpy.run_path(str(Path(__file__).with_name("host_process.py")))


def run_codex(root, command, prompt, endpoint, *, trust_bypass=True):
    root = Path(root).resolve()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    hooks = root / ".codex"
    hooks.mkdir(exist_ok=True)
    (hooks / "config.toml").write_text("# Isolated project hook layer\n")
    (hooks / "hooks.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{
        "type": "command", "command": command, "timeout": 10}]}]}}))
    environment = helpers["offline_environment"]()
    home_parent = None
    if os.name == "nt":
        # Codex refuses creating its helper binaries under the Windows Temp
        # tree. Use a fresh test-only application-data directory instead.
        home_parent = Path(os.environ["LOCALAPPDATA"]) / "AtMemHostTests"
        home_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="atmem-codex-probe-", dir=home_parent) as home:
        (Path(home) / "config.toml").write_text('[projects.' + json.dumps(str(root)) + ']\ntrust_level="trusted"\n')
        environment["CODEX_HOME"] = home
        return helpers['run_owned_cli']([*helpers["cli_argv"]("codex"), "exec", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", *(["--dangerously-bypass-hook-trust"] if trust_bypass else []), "-c", 'model="atmem-probe"',
            "-c", 'model_provider="atmem_probe"', "-c", 'model_providers.atmem_probe.name="AtMem local probe"',
            "-c", 'model_providers.atmem_probe.wire_api="responses"', "-c", 'model_providers.atmem_probe.requires_openai_auth=false',
            "-c", 'model_providers.atmem_probe.base_url="' + endpoint.url + '"', prompt],
            cwd=root, env=environment, timeout=40)
