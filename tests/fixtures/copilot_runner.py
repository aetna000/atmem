"""Run the installed Copilot CLI against an isolated, offline provider."""

import json
import os
from pathlib import Path
import subprocess


def run_copilot(root, command, prompt, endpoint, *, configure=True, resume=None):
    root = Path(root)
    home = root.parent / (root.name + "-copilot-home")
    home.mkdir(exist_ok=True)
    (home / "config.json").write_text(json.dumps({"trustedFolders": [str(root.resolve())]}))
    if configure:
        hooks = root / ".github/hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "atmem-code.json").write_text(json.dumps({"version": 1, "hooks": {
            event: [{"type": "command", "command": command, "timeoutSec": 10}]
            for event in ("sessionStart", "userPromptSubmitted", "sessionEnd")
        }}))
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("COPILOT_", "GITHUB_", "GH_"))}
    env.update(COPILOT_HOME=str(home), COPILOT_OFFLINE="true",
               COPILOT_PROVIDER_BASE_URL=endpoint.url, COPILOT_PROVIDER_TYPE="openai",
               COPILOT_PROVIDER_WIRE_API="responses", COPILOT_MODEL="gpt-5.4")
    return subprocess.run(["copilot", "-p", prompt, *(["--resume", resume] if resume else []), "--allow-all-tools", "--disable-builtin-mcps",
                           "--no-auto-update", "--no-custom-instructions", "--no-ask-user",
                           "--no-remote", "--no-remote-export", "--silent"],
                          cwd=root, env=env, text=True, capture_output=True, timeout=90)
