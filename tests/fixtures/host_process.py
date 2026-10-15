"""Resolve installed CLIs and isolate credentials for offline host tests."""

import os
from pathlib import Path
import shutil
import shlex


def cli_argv(host):
    binary = shutil.which(host)
    if not binary:
        raise RuntimeError(host + " is not installed")
    if os.name == "nt" and Path(binary).suffix.lower() in {".cmd", ".ps1", ".bat"}:
        if host == "claude":
            native = Path(binary).parent / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
            if native.is_file():
                return [str(native)]
        script = {"claude": "@anthropic-ai/claude-code/cli.js", "codex": "@openai/codex/bin/codex.js"}[host]
        loader = Path(binary).parent / "node_modules" / script
        node = shutil.which("node")
        if not node or not loader.is_file():
            raise RuntimeError(host + " npm loader is unavailable")
        return [node, str(loader)]
    return [binary]


def offline_environment():
    return {key: value for key, value in os.environ.items()
            if key.upper() in {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SHELL", "LANG",
                               "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATHEXT", "COMSPEC", "USERPROFILE",
                               "HOMEDRIVE", "HOMEPATH", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
                               "ALLUSERSPROFILE", "APPDATA", "LOCALAPPDATA"}}


def hook_command(argv):
    if os.name == "nt":
        script = "& " + " ".join("'" + arg.replace("\\", "/").replace("'", "''") + "'" for arg in argv)
        return 'powershell.exe -NoProfile -NonInteractive -Command "' + script + '"'
    return shlex.join(argv)
