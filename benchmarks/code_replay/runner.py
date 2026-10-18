"""Bounded subscription CLI process primitive; dispatch gates live above it.

Uses an explicit RAM-backed home and existing account authorization. Every run
is labelled harness integration, not normal automatic Codex hook support.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import selectors
import shutil
import signal
import subprocess
import time
from uuid import uuid4

from benchmarks.code_replay.sandbox import permission_arguments


@dataclass(frozen=True)
class Session:
    root: Path
    workspace: Path
    cli_home: Path
    temporary: Path
    executable: Path


def allocate_session(ram_root: Path, auth_file: Path) -> Session:
    root = ram_root.resolve(strict=True)
    if root.parent != Path("/Volumes") or not root.name.startswith("AtMemReplayRAM-20261017"):
        raise ValueError("explicit volatile benchmark root required")
    images = plistlib.loads(subprocess.check_output(["hdiutil", "info", "-plist"]))["images"]
    if not any(str(image.get("image-path", "")).startswith("ram://") and any(
            entity.get("mount-point") == str(root) for entity in image.get("system-entities", [])) for image in images):
        raise ValueError("benchmark volume is not a mounted RAM image")
    if auth_file.is_symlink() or not auth_file.is_file() or auth_file.stat().st_size > 65536:
        raise ValueError("bounded existing CLI authentication required")
    auth = json.loads(auth_file.read_bytes())
    if auth.get("auth_mode") not in (None, "chatgpt") or auth.get("OPENAI_API_KEY") or not isinstance(auth.get("tokens"), dict):
        raise ValueError("subscription-only authorization required")
    runtime = root / "atmem-click-cli-runtime"
    runtime.mkdir(mode=0o700, exist_ok=True)
    original = Path(shutil.which("codex")).resolve(strict=True)
    executable = runtime / "codex"
    if not executable.exists():
        shutil.copy2(original, executable)
    if sha256(original.read_bytes()).digest() != sha256(executable.read_bytes()).digest():
        raise ValueError("CLI binary changed from pinned session runtime")
    companion = original.parent / "codex-code-mode-host"
    companion_target = runtime / companion.name
    if not companion.is_file():
        raise ValueError("pinned CLI command-host companion is missing")
    if not companion_target.exists():
        shutil.copy2(companion, companion_target)
    if sha256(companion.read_bytes()).digest() != sha256(companion_target.read_bytes()).digest():
        raise ValueError("CLI command-host companion changed")
    rg_source = original.parent.parent / "codex-path/rg"
    if not rg_source.is_file():
        raise ValueError("pinned native search executable is missing")
    if not (runtime / "rg").exists():
        shutil.copy2(rg_source, runtime / "rg")
    # macOS /usr/bin/git is an xcrun shim, which tries to write a global
    # developer-tool cache under the denied host TMPDIR. Use the native public
    # tool directly in this read-only runtime, without widening filesystem scope.
    native_git = Path(subprocess.check_output(["/usr/bin/xcrun", "--find", "git"], text=True).strip()).resolve(strict=True)
    if str(native_git) not in ("/Library/Developer/CommandLineTools/usr/bin/git",
                              "/Applications/Xcode.app/Contents/Developer/usr/bin/git"):
        raise ValueError("unqualified native Git runtime location")
    if not (runtime / "git").exists():
        shutil.copy2(native_git, runtime / "git")
    if sha256(native_git.read_bytes()).digest() != sha256((runtime / "git").read_bytes()).digest():
        raise ValueError("native Git executable changed")
    session = root / ("session-" + uuid4().hex)
    home, workspace, temporary = session / "cli-home", session / "atmem-click-workspace", session / "tmp"
    for directory in (home, workspace, temporary):
        directory.mkdir(parents=True, mode=0o700)
    shutil.copyfile(auth_file, home / "auth.json")
    (home / "auth.json").chmod(0o600)
    return Session(session, workspace, home, temporary, executable)


def run_cli(session: Session, prompt: str, *, runtime_roots=(), max_seconds=180, max_tool_calls=24, on_submitted=None, mcp_config=None):
    if not isinstance(prompt, str) or not prompt or len(prompt.encode()) > 65536:
        raise ValueError("bounded task input required")
    if type(max_seconds) is not int or not 1 <= max_seconds <= 600 or type(max_tool_calls) is not int or not 1 <= max_tool_calls <= 100:
        raise ValueError("invalid CLI trial budgets")
    from benchmarks.code_replay.progressive import arguments as mcp_arguments
    command = [str(session.executable), "exec", "--ignore-user-config", "--ignore-rules", "--strict-config",
               "--ephemeral", "--json", "-m", "gpt-6-luna", "-C", str(session.workspace), "--skip-git-repo-check",
               "-c", 'default_permissions="click-replay"', "-c", 'approval_policy="never"',
               "-c", 'web_search="disabled"', "-c", 'model_reasoning_effort="low"',
               "-c", 'shell_environment_policy.set.PATH=' + json.dumps(str(session.executable.parent) + ":/usr/bin:/bin"),
               "-c", 'shell_environment_policy.set.PYTHONPATH=' + json.dumps(str(session.workspace / "src") + ":" + str(session.workspace / ".solver-metadata")),
               "-c", 'shell_environment_policy.set.TMPDIR=' + json.dumps(str(session.workspace / ".solver-tmp")),
               "-c", 'shell_environment_policy.set.GIT_CONFIG_NOSYSTEM="1"',
               "-c", 'shell_environment_policy.set.GIT_CONFIG_GLOBAL="/dev/null"',
               "-c", 'shell_environment_policy.set.GIT_CONFIG_SYSTEM="/dev/null"',
               "-c", 'shell_environment_policy.set.GIT_TERMINAL_PROMPT="0"',
               *permission_arguments((session.executable.parent, *runtime_roots)), *mcp_arguments(mcp_config), "-"]
    environment = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "CODEX_HOME": str(session.cli_home),
                   "LANG": "en_US.UTF-8", "TMPDIR": str(session.temporary),
                   "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.Popen(command, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        process.stdin.write(prompt.encode())
        process.stdin.close()
        if on_submitted is not None:
            on_submitted()
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        raise
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    captured, events, pending = {"stdout": bytearray(), "stderr": bytearray()}, [], b""
    start, tools, stop = time.monotonic(), 0, None
    started_items = set()
    turn_started = False
    killed_at = None
    try:
        while selector.get_map():
            if time.monotonic() - start > max_seconds:
                stop = "wall_budget"
            if tools > max_tool_calls:
                stop = "tool_budget"
            if sum(map(len, captured.values())) > 16_000_000:
                stop = "output_budget"
            if stop and killed_at is None:
                # The CLI parent may already have exited while a descendant
                # still owns a pipe. Bound that drain as well as parent life.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                killed_at = time.monotonic()
            if killed_at is not None and time.monotonic() - killed_at > 2:
                break
            for key, _ in selector.select(0.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                captured[key.data].extend(chunk)
                if key.data == "stdout":
                    pending += chunk
                    while b"\n" in pending:
                        line, pending = pending.split(b"\n", 1)
                        try:
                            event = json.loads(line)
                        except (ValueError, UnicodeDecodeError):
                            stop = "invalid_cli_stream"
                            continue
                        events.append(event)
                        if event.get("type") == "turn.started":
                            turn_started = True
                        item = event.get("item", {})
                        if item.get("type") == "error" and not turn_started:
                            stop = "cli_infrastructure_error"
                        if event.get("type") in {"item.started", "item.completed"} and item.get("type") in {
                                "command_execution", "mcp_tool_call", "file_change", "web_search"} and item.get("id") not in started_items:
                            started_items.add(item.get("id"))
                            tools += 1
        process.wait(timeout=5)
    finally:
        selector.close()
        # Once wait() has reaped the parent its PID/group number may be reused.
        # Never send a group signal after that point (macOS can return EPERM,
        # and a successful signal could target an unrelated reused group).
        # Before wait(), an unreaped child still owns its PID, including the
        # descendant-pipe timeout path above.
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
    return {"exit_code": process.returncode, "elapsed_ms": int((time.monotonic() - start) * 1000),
            "stop_reason": stop, "tool_calls": tools, "events": events,
            "stdout": bytes(captured["stdout"]), "stderr": bytes(captured["stderr"]),
            "command": command, "integration": "benchmark_harness_not_normal_hooks", "model": "gpt-6-luna"}
