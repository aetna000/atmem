"""Controlled native-argument hook fixture, not product onboarding."""

import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile

helpers = runpy.run_path(str(Path(__file__).with_name("host_process.py")))


def run_claude(root, argv, prompt, endpoint):
    root = Path(root)
    settings = root / ".claude/settings.local.json"
    settings.parent.mkdir(exist_ok=True)
    settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [
        {"type": "command", "command": argv[0], "args": argv[1:], "timeout": 10}]}]}}))
    environment = helpers["offline_environment"]()
    with tempfile.TemporaryDirectory(prefix="atmem-claude-test-") as home:
        environment.update(ANTHROPIC_BASE_URL=endpoint.url, ANTHROPIC_API_KEY="offline-fixture-not-a-provider-key",
                           CLAUDE_CONFIG_DIR=home, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
        if os.name == "nt" and Path("C:/Program Files/Git/bin/bash.exe").is_file():
            environment["CLAUDE_CODE_GIT_BASH_PATH"] = "C:/Program Files/Git/bin/bash.exe"
        return subprocess.run([*helpers["cli_argv"]("claude"), "-p", prompt, "--max-turns", "1", "--tools", "",
                               "--setting-sources", "project,local"], cwd=root, env=environment,
                              capture_output=True, text=True, timeout=60)
