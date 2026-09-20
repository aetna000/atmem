"""Start the optional AtFlows companion with AtMem-owned local sign-in.

AtFlows remains a separate process and data store. This module owns only the
launcher record for processes started by ``atmem init``; it never adopts or
stops an independently started AtFlows instance.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlparse

from atmem.home.layout import compatible_home_path


def _paths() -> tuple[Path, Path]:
    state = compatible_home_path("runtime/atflows-service.json", "atflows-service.json")
    return state, state.with_name("atflows-service.log")


def _running() -> list[dict[str, Any]]:
    try:
        from atflows.status import running_servers

        return running_servers()
    except (ImportError, OSError, ValueError):
        return []


def status() -> dict[str, Any]:
    try:
        installed_version = version("atflows")
    except PackageNotFoundError:
        installed_version = None
    state_path, log_path = _paths()
    try:
        record = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    if not isinstance(record, dict):
        record = {}
    servers = _running() if installed_version else []
    owned = next(
        (row for row in servers if row.get("instance_id") == record.get("instance_id")),
        None,
    ) if record.get("instance_id") else None
    selected = owned or (servers[0] if len(servers) == 1 else None)
    result: dict[str, Any] = {
        "installed_version": installed_version,
        "bun_available": bool(shutil.which("bun")),
        "running": bool(servers),
        "managed_by_atmem": bool(owned),
        "pid": selected.get("pid") if selected else None,
        "running_version": record.get("atflows_version") if owned else None,
        "auth_mode": "atmem" if owned else ("unknown" if selected else None),
        "dashboard_url": (
            f"http://127.0.0.1:{selected['dashboard_port']}/"
            if selected and selected.get("dashboard_online") else None
        ),
        "proxy_url": (
            f"http://127.0.0.1:{selected['proxy_port']}/"
            if selected and selected.get("proxy_online") else None
        ),
        "restart_required": bool(
            owned and record.get("atflows_version") != installed_version
        ),
        "log_path": str(log_path) if owned else None,
    }
    if len(servers) > 1:
        result["warning"] = (
            f"{len(servers)} AtFlows servers are running; AtMem links only to its managed instance."
            if owned else
            f"{len(servers)} independent AtFlows servers are running; AtMem cannot choose one safely."
        )
    elif selected and not owned:
        result["warning"] = "An independently started AtFlows server is running; its sign-in mode is unknown. Stop that server, then run `atmem init` to enable shared sign-in."
    elif selected and (not result["dashboard_url"] or not result["proxy_url"]):
        result["warning"] = "AtFlows is only partially healthy; inspect its log or restart it."
    elif result["restart_required"]:
        result["warning"] = "AtFlows is running an older version than the installed package."
    elif installed_version and not result["running"] and not result["bun_available"]:
        result["warning"] = "Bun 1.1+ is missing. Install it from https://bun.sh, then run `atmem init`."
    return result


def validated_dashboard_url(candidate: object) -> str | None:
    """Return a local navigation target, never an arbitrary companion URL."""
    if not isinstance(candidate, str):
        return None
    try:
        parsed = urlparse(candidate)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or not 1 <= port <= 65535
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    return f"http://127.0.0.1:{port}/"


def _stop_managed_instance() -> None:
    """Stop only the live instance whose random ID matches our private record."""
    state_path, _ = _paths()
    record = json.loads(state_path.read_text(encoding="utf-8"))
    instance_id = record["instance_id"]
    instance = next((row for row in _running() if row.get("instance_id") == instance_id), None)
    if instance is None:
        return
    pid = int(instance["pid"])
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not any(row.get("instance_id") == instance_id for row in _running()):
            return
        time.sleep(0.2)
    raise RuntimeError("The AtMem-managed AtFlows process did not stop; inspect its PID before retrying.")


def ensure_started(atmem_url: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """Start one detached companion, without taking over an existing server."""
    current = status()
    if not current["installed_version"]:
        raise RuntimeError("AtFlows is not installed; run `python -m pip install --upgrade atmem`.")
    if current["running"] and current["managed_by_atmem"]:
        state_path, _ = _paths()
        record = json.loads(state_path.read_text(encoding="utf-8"))
        if current["restart_required"] or record.get("atmem_auth_url") != atmem_url.rstrip("/"):
            _stop_managed_instance()
            current = status()
    if current["running"]:
        return current
    bun = shutil.which("bun")
    if not bun:
        raise RuntimeError("Bun is required to start AtFlows. Install Bun 1.1+ from https://bun.sh, then run `atmem init` again.")
    try:
        bun_version = subprocess.run([bun, "--version"], capture_output=True, text=True, timeout=5, check=False)
        pieces = [int(part) for part in bun_version.stdout.strip().split(".")[:2]]
        if bun_version.returncode != 0 or pieces < [1, 1]:
            raise ValueError("Bun 1.1+ is required")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise RuntimeError("Bun 1.1+ is required to start AtFlows; upgrade Bun, then run `atmem init` again.") from None
    from atmem.cli import _atflows_executable

    executable = _atflows_executable(current["installed_version"])
    if executable is None:
        raise RuntimeError("The AtFlows launcher does not match this Python installation; reinstall AtMem in this environment.")
    state_path, log_path = _paths()
    state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path.parent.chmod(0o700)
    log_path.touch(mode=0o600, exist_ok=True)
    log_path.chmod(0o600)
    previous_ids = {row.get("instance_id") for row in _running()}
    environment = os.environ.copy()
    environment["ATFLOWS_ATMEM_AUTH_URL"] = atmem_url.rstrip("/")
    environment["DASHBOARD_HOST"] = "127.0.0.1"
    environment["PROXY_HOST"] = "127.0.0.1"
    environment.pop("ATFLOWS_ADMIN_PASSWORD", None)
    environment.pop("ATFLOWS_SETUP_TOKEN", None)
    environment.pop("ATFLOWS_SETUP_PREFILL_PASSWORD", None)
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(executable), "start"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=environment,
            start_new_session=True,
            close_fds=True,
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        added = [row for row in _running() if row.get("instance_id") not in previous_ids]
        healthy = next((row for row in added if row.get("dashboard_online") and row.get("proxy_online")), None)
        if healthy:
            record_text = json.dumps({
                "instance_id": healthy["instance_id"],
                "launcher_pid": process.pid,
                "atflows_version": current["installed_version"],
                "atmem_auth_url": atmem_url.rstrip("/"),
                "python_executable": sys.executable,
            }, sort_keys=True) + "\n"
            descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(record_text)
            return status()
        if process.poll() is not None:
            break
        time.sleep(0.25)
    if process.poll() is None:
        # Only terminate the process group started above, never another server.
        os.killpg(process.pid, signal.SIGTERM)
    raise RuntimeError(
        "AtFlows did not become ready. Check Bun >=1.1, network access for its first runtime preparation, "
        f"and the private startup log at {log_path}. Run `atmem init` to retry."
    )
