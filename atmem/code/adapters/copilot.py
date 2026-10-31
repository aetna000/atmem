"""Copilot CLI hooks with explicit dispatch and per-prompt context delivery."""

import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import re
from atmem.code.adapters.json_hooks import JsonHookAdapter
from atmem.code.adapters.copilot_events import EVENTS


def copilot_cli_argv():
    """Resolve npm's Windows shim without passing prompts through cmd.exe."""
    binary = shutil.which("copilot")
    if not binary:
        raise RuntimeError("Copilot CLI is not installed")
    if os.name == "nt" and Path(binary).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        loader = Path(binary).parent / "node_modules/@github/copilot/npm-loader.js"
        node = shutil.which("node")
        if not loader.is_file() or not node:
            raise RuntimeError("Copilot npm launcher is unavailable; repair the Copilot CLI installation")
        return [node, str(loader)]
    return [binary]


def copilot_offline_remote_flags(version: str) -> list[str]:
    """Keep older CLI safeguards; new CLI removed these in offline mode."""
    match = re.search(r'\b(\d+)\.(\d+)\.(\d+)\b', version)
    if match and tuple(map(int, match.groups())) >= (1, 0, 103):
        return []
    return ['--no-remote', '--no-remote-export']


class CopilotAdapter(JsonHookAdapter):
    host = "copilot"
    relative_path = ".github/hooks/atmem-code.json"
    events = EVENTS

    def probe(self):
        from dataclasses import replace
        initial = super().probe()
        if os.name == "nt":
            try:
                result = subprocess.run([*copilot_cli_argv(), "--version"], capture_output=True, text=True, timeout=5, check=False)
                if result.returncode == 0:
                    return replace(initial, version=(result.stdout or result.stderr).strip()[:160])
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
        return initial

    def __init__(self, root, command, *, argv=None, verifier=None):
        super().__init__(root, command, verifier=verifier)
        if argv is not None and (not argv or any(not isinstance(arg, str) or not arg or "\n" in arg or "\r" in arg for arg in argv)):
            raise ValueError("Copilot executable arguments must be nonempty single-line strings")
        self.argv = tuple(argv) if argv is not None else None

    def planned_configuration(self, previous: bytes | None) -> bytes:
        value = json.loads(previous) if previous else {"version": 1}
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("Copilot hook configuration requires version 1")
        hooks = value.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("Copilot hooks must be an object")
        for event in self.events:
            handlers = hooks.setdefault(event, [])
            if not isinstance(handlers, list):
                raise ValueError("Copilot event handlers must be a list")
            handler = {"type": "command", "command": self.command + " --host-event " + shlex.quote(event), "timeoutSec": 10}
            if self.argv is not None:
                handler = {"type": "command", "exec": self.argv[0],
                           "args": [*self.argv[1:], "--host-event", event], "timeoutSec": 10}
            if handler not in handlers:
                handlers.append(handler)
        return (json.dumps(value, indent=2) + "\n").encode()
