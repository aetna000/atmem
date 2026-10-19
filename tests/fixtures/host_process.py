"""Resolve installed CLIs and isolate credentials for offline host tests."""

import os
from pathlib import Path
import shutil
import shlex
import signal
import subprocess


def run_owned_cli(argv, *, cwd, env, timeout):
    """Stop this fixture's POSIX descendants before temporary-home cleanup.

    Some CLIs leave a background marketplace checkout after their main process
    exits. A new session scopes cleanup to this exact test invocation, never
    another running coding session. Windows preserves its existing runner.
    """
    if os.name == 'nt':
        return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


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
