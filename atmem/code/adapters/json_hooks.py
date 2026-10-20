"""Preserving JSON hook configuration shared by host-specific adapters."""

from __future__ import annotations

import json
import platform
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from atmem.code.adapters.base import HostProbe


class JsonHookAdapter:
    host = "test"
    relative_path = ".atmem/hooks.json"
    events = ("UserPromptSubmit", "PostToolUse", "Stop", "PreCompact", "SessionEnd")

    def __init__(self, root: str | Path, command: str, *, verifier: Callable[[], HostProbe] | None = None) -> None:
        self.root = Path(root).resolve(strict=True)
        if not isinstance(command, str) or not command.strip() or "\n" in command or "\r" in command:
            raise ValueError("hook command must be one nonempty line")
        self.command = command
        self.verifier = verifier

    def probe(self) -> HostProbe:
        binary = shutil.which(self.host)
        version = "unavailable"
        if binary:
            try:
                result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5, check=False)
                if result.returncode == 0:
                    version = (result.stdout or result.stderr).strip()[:160]
            except (OSError, subprocess.TimeoutExpired):
                pass
        return HostProbe(self.host, version, platform.system(), False, False, "submitted", None)

    def verify_installed(self) -> HostProbe:
        # A valid config and a hook process exit are insufficient. The caller
        # must provide the installed-host capture/context verifier.
        return self.verifier() if self.verifier else self.probe()

    def configuration_path(self) -> Path:
        path = self.root / self.relative_path
        if not path.parent.resolve().is_relative_to(self.root):
            raise ValueError("host configuration escapes the project directory")
        parent = path.parent
        while parent != self.root:
            if parent.is_symlink():
                raise ValueError("host configuration parent cannot be a symlink")
            parent = parent.parent
        return path

    def planned_configuration(self, previous: bytes | None) -> bytes:
        value = json.loads(previous) if previous else {}
        if not isinstance(value, dict):
            raise ValueError("host settings must be an object")
        hooks = value.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("host hooks must be an object")
        for event in self.events:
            groups = hooks.setdefault(event, [])
            if not isinstance(groups, list):
                raise ValueError("hook event handlers must be a list")
            handler = {"type": "command", "command": self.command, "timeout": 10}
            if not any(isinstance(group, dict) and handler in group.get("hooks", []) for group in groups):
                groups.append({"hooks": [handler]})
        return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
