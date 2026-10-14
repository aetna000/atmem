"""Only isolated, explicitly vetted hooks may use the per-invocation trust flag."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run_codex(root, command, prompt, endpoint):
    root = Path(root).resolve()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    hooks = root / ".codex"
    hooks.mkdir(exist_ok=True)
    (hooks / "config.toml").write_text("# Isolated project hook layer\n")
    (hooks / "hooks.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{
        "type": "command", "command": command, "timeout": 10}]}]}}))
    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "SHELL", "LANG", "SystemRoot"}}
    with tempfile.TemporaryDirectory(prefix="atmem-codex-probe-") as home:
        (Path(home) / "config.toml").write_text('[projects.' + json.dumps(str(root)) + ']\ntrust_level="trusted"\n')
        environment["CODEX_HOME"] = home
        return subprocess.run([shutil.which("codex"), "exec", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "--dangerously-bypass-hook-trust", "-c", 'model="atmem-probe"',
            "-c", 'model_provider="atmem_probe"', "-c", 'model_providers.atmem_probe.name="AtMem local probe"',
            "-c", 'model_providers.atmem_probe.wire_api="responses"', "-c", 'model_providers.atmem_probe.requires_openai_auth=false',
            "-c", 'model_providers.atmem_probe.base_url="' + endpoint.url + '"', prompt],
            cwd=root, env=environment, capture_output=True, text=True, timeout=40, check=False)
