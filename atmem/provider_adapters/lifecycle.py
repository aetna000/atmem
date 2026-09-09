"""Private configuration and lifecycle management for provider adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import time
from typing import Any
from urllib.request import Request, build_opener
from atmem.delegated.client import _NoRedirect
from atmem.delegated.transport import (PROFILE, RequestAuthenticator, configure_keyring,
    load_keyring, load_secret, revoke_key, sign_headers)

from .langgraph import LangGraphContextProvider
from .loading import create_from_factory
from .mem0 import Mem0ContextProvider, create_mem0_provider
from .models import ProviderRuntimeIdentity
from .pydantic_ai import PydanticAIContextProvider
from .runtime import ProviderRuntime
from .signing import generate_keypair, load_private_key


def provider_root() -> Path:
    return Path(os.environ.get("ATMEM_PROVIDER_ROOT", str(Path.home() / ".atmem" / "providers"))).expanduser()


def instance_dir(instance: str) -> Path:
    if not instance or not instance.replace("-", "").replace("_", "").isalnum():
        raise ValueError("instance name may contain only letters, numbers, hyphens, and underscores")
    return provider_root() / instance


def initialize(
    *, instance: str, kind: str, port: int, factory: str | None = None,
    mode: str | None = None, provider_id: str | None = None,
    provider_version: str = "1.0", egress: str = "local",
) -> dict[str, Any]:
    if kind not in {"mem0", "langgraph", "pydantic-ai"}:
        raise ValueError("provider kind must be mem0, langgraph, or pydantic-ai")
    if not 1 <= port <= 65535:
        raise ValueError("provider port is outside policy")
    if kind != "mem0" and not factory:
        raise ValueError(f"{kind} requires --factory module:attribute")
    root = instance_dir(instance)
    if root.exists():
        raise ValueError("provider instance already exists")
    root.mkdir(mode=0o700, parents=True)
    private_path, public_path = root / "private.key", root / "public.key"
    generate_keypair(private_path, public_path)
    config = {
        "format": "atmem-provider-instance-v1",
        "instance": instance,
        "kind": kind,
        "host": "127.0.0.1",
        "port": port,
        "factory": factory,
        "mode": mode or ("oss" if kind == "mem0" else "factory"),
        "egress": egress,
        "provider_id": provider_id or f"{kind}-context-provider",
        "provider_version": provider_version,
        "key_id": "primary",
    }
    ProviderRuntimeIdentity(
        config["provider_id"], config["provider_version"], instance, config["key_id"]
    )
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(config_path, 0o600)
    configure_keyring(root / "request-auth.json", provider_id=config["provider_id"], instance_id=instance)
    result = status(instance)
    result["public_key_file"] = str(public_path)
    result["registration_command"] = registration_command(config, public_path)
    return result


def load_config(instance: str) -> tuple[Path, dict[str, Any]]:
    root = instance_dir(instance)
    path = root / "config.json"
    if root.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("provider configuration was not found or is unsafe")
    if root.stat().st_mode & 0o077:
        raise ValueError("provider instance directory permissions must be 0700")
    if path.stat().st_mode & 0o077:
        raise ValueError("provider configuration permissions must be 0600")
    if hasattr(os, "getuid") and (root.stat().st_uid != os.getuid() or path.stat().st_uid != os.getuid()):
        raise ValueError("provider configuration must be owned by the current user")
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"format", "instance", "kind", "host", "port", "factory", "mode", "egress", "provider_id", "provider_version", "key_id"}
    if not isinstance(value, dict) or set(value) != required or value["format"] != "atmem-provider-instance-v1" or value["instance"] != instance:
        raise ValueError("provider configuration fields do not match the contract")
    return root, value


def build_runtime(instance: str) -> ProviderRuntime:
    root, config = load_config(instance)
    authenticator = RequestAuthenticator(root / "request-auth.json", root / "request-nonces.db")
    kind = config["kind"]
    try:
        created = create_from_factory(config["factory"]) if config["factory"] else None
    except (ImportError, ModuleNotFoundError) as exc:
        extra = {"mem0": "mem0", "langgraph": "langgraph-provider", "pydantic-ai": "pydantic-provider"}[kind]
        raise RuntimeError(
            f"provider factory could not load; install 'atmem[{extra}]' and verify --factory"
        ) from exc
    if kind == "mem0":
        provider = Mem0ContextProvider(created, mode="factory") if created is not None else create_mem0_provider(mode=config["mode"])
    elif kind == "langgraph":
        provider = LangGraphContextProvider(created)
    elif kind == "pydantic-ai":
        provider = PydanticAIContextProvider(created, egress=config["egress"])
    else:
        raise ValueError("unsupported provider kind")
    identity = ProviderRuntimeIdentity(config["provider_id"], config["provider_version"], instance, config["key_id"])
    runtime = ProviderRuntime(provider=provider, identity=identity, private_key=load_private_key(root / "private.key"), adapter_kind=kind)
    runtime.request_authenticator = authenticator
    return runtime


def registration_command(config: dict[str, Any], public_path: Path) -> str:
    quoted = shlex.quote
    try:
        ring = load_keyring(public_path.parent / "request-auth.json")
        active = next(key for key in ring["keys"] if key["key_id"] == ring["active_key_id"])
        authentication = f"--request-key-id {quoted(active['key_id'])} --request-secret-file {quoted(active['secret_file'])} "
    except ValueError:
        authentication = "--request-key-id KEY_ID --request-secret-file PRIVATE_FILE "
    return (
        f"atmem delegated register --provider-id {quoted(config['provider_id'])} "
        f"--provider-version {quoted(config['provider_version'])} --instance-id {quoted(config['instance'])} "
        f"--key-id {quoted(config['key_id'])} --public-key-file {quoted(str(public_path))} "
        f"--endpoint http://127.0.0.1:{config['port']}/v1/delegated-context "
        + authentication +
        "--workspace YOUR_WORKSPACE --agent YOUR_AGENT --user YOUR_USER"
    )


def auth_configure(instance: str, *, rotate: bool = False, overlap_seconds: int = 30) -> dict[str, Any]:
    root, config = load_config(instance)
    result = configure_keyring(root / "request-auth.json", provider_id=config["provider_id"],
        instance_id=instance, rotate=rotate, overlap_seconds=overlap_seconds)
    return {**result, "registration_command": registration_command(config, root / "public.key"),
        "next_action": f"Run atmem delegated set-request-auth {config['provider_id']}:{instance} "
        f"--request-key-id {shlex.quote(result['request_key_id'])} --request-secret-file {shlex.quote(result['request_secret_file'])}; explicitly enable afterward."}


def auth_revoke(instance: str, key_id: str) -> dict[str, Any]:
    root, _ = load_config(instance)
    revoke_key(root / "request-auth.json", key_id)
    return {"revoked": key_id, "instance": instance}


def start(instance: str) -> dict[str, Any]:
    root, config = load_config(instance)
    load_keyring(root / "request-auth.json")
    if _live_pid(root):
        raise ValueError("provider instance is already running")
    log = open(root / "service.log", "ab", buffering=0)
    process = subprocess.Popen(
        [sys.executable, "-m", "atmem.provider_adapters.worker", instance],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
    )
    log.close()
    (root / "service.pid").write_text(str(process.pid) + "\n", encoding="ascii")
    os.chmod(root / "service.pid", 0o600)
    time.sleep(0.1)
    result = status(instance)
    if not result["running"]:
        raise RuntimeError("provider service did not start; inspect service.log")
    return result


def stop(instance: str) -> dict[str, Any]:
    root, _ = load_config(instance)
    pid = _live_pid(root)
    if pid is None:
        return status(instance)
    command = _pid_command(pid)
    if "atmem.provider_adapters.worker" not in command or instance not in command:
        raise ValueError("recorded PID does not belong to this provider instance")
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _pid_exists(pid):
            break
        time.sleep(0.05)
    (root / "service.pid").unlink(missing_ok=True)
    return status(instance)


def status(instance: str) -> dict[str, Any]:
    root, config = load_config(instance)
    pid = _live_pid(root)
    health = _health(config) if pid is not None else None
    try:
        load_keyring(root / "request-auth.json")
        auth_state = "configured"
    except ValueError:
        auth_state = "migration_required"
    return {
        "format": "atmem-provider-status-v1", "instance": instance,
        "kind": config["kind"], "running": pid is not None, "pid": pid,
        "endpoint": f"http://127.0.0.1:{config['port']}/v1/delegated-context",
        "provider_id": config["provider_id"],
        "provider_version": config["provider_version"],
        "key_id": config["key_id"],
        "egress": config["egress"],
        "startup_enabled_authority": False,
        "authority_activation": "separate_atmem_delegated_registration",
        "health": health,
        "request_authentication": auth_state,
        "next_action": f"atmem provider auth-init {instance}" if auth_state == "migration_required" else f"atmem provider doctor {instance}",
    }


def doctor(instance: str) -> dict[str, Any]:
    root, config = load_config(instance)
    checks: list[dict[str, Any]] = []
    for name, path, mode in (("configuration", root / "config.json", 0o600), ("private_key", root / "private.key", 0o600)):
        checks.append({"check": name, "ok": path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o777 == mode})
    try:
        build_runtime(instance)
        runtime_check = {"check": "runtime_configuration", "ok": True}
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        runtime_check = {"check": "runtime_configuration", "ok": False, "action": str(exc)}
    checks.append(runtime_check)
    running = _live_pid(root) is not None
    health = _health(config) if running else None
    reachable = health is not None
    checks.append({"check": "service", "ok": reachable, "running": running})
    return {
        "format": "atmem-provider-doctor-v1", "instance": instance,
        "ok": all(check["ok"] for check in checks), "checks": checks,
        "next": registration_command(config, root / "public.key"),
        "note": "Registration remains disabled until you run atmem delegated enable.",
        "health": health,
    }


def remove(instance: str) -> dict[str, Any]:
    root, _ = load_config(instance)
    if _live_pid(root):
        raise ValueError("stop the provider before removing it")
    # Only generated credential filenames inside this validated instance.
    import re
    for path in root.iterdir():
        if re.fullmatch(r"request-[0-9a-f]{24}\.key", path.name):
            path.unlink()
    for name in ("request-auth.json", "request-auth.json.lock", "request-nonces.db", "request-nonces.db-journal", "request-nonces.db.initialized"):
        (root / name).unlink(missing_ok=True)
    for name in ("service.pid", "service.log", "config.json", "public.key", "private.key"):
        (root / name).unlink(missing_ok=True)
    root.rmdir()
    return {"removed": True, "instance": instance, "atmem_evidence_retained": True}


def _live_pid(root: Path) -> int | None:
    path = root / "service.pid"
    if not path.is_file() or path.is_symlink():
        return None
    try:
        pid = int(path.read_text(encoding="ascii").strip())
    except (ValueError, OSError):
        return None
    return pid if _pid_exists(pid) else None


def _pid_exists(pid: int) -> bool:
    if pid <= 1:
        return False
    try:
        waited, _ = os.waitpid(pid, os.WNOHANG)
        if waited == pid:
            return False
    except ChildProcessError:
        pass
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        if stat_path.is_file() and stat_path.read_text(encoding="utf-8").split()[2] == "Z":
            return False
    except (OSError, IndexError):
        pass
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_command(pid: int) -> str:
    proc_path = Path(f"/proc/{pid}/cmdline")
    try:
        if proc_path.is_file():
            return proc_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace")
    except OSError:
        pass
    return subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True, text=True, check=False,
    ).stdout


def _health(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        ring = load_keyring(instance_dir(config["instance"]) / "request-auth.json")
        active = next(key for key in ring["keys"] if key["key_id"] == ring["active_key_id"])
        authority = f"127.0.0.1:{config['port']}"
        headers = sign_headers(secret=load_secret(active["secret_file"]), provider_id=config["provider_id"],
            instance_id=config["instance"], key_id=active["key_id"], method="GET", authority=authority, target="/health")
        with build_opener(_NoRedirect()).open(Request(f"http://{authority}/health", headers=headers), timeout=0.5) as response:
            raw = response.read(16385)
        if len(raw) > 16384:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) and value.get("status") == "ready" and value.get("transport_profile") == PROFILE and (value.get("provider_id"), value.get("instance_id")) == (config["provider_id"], config["instance"]) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None
