"""Inactive Hermes directory-plugin installation; never writes host configuration."""
from __future__ import annotations

import ctypes
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

from atmem.adapters.hermes.package import plugin_files
from atmem.evidence.crypto import open_json, seal_json
from atmem.locking import ProcessFileLock

RECEIPT = ".atmem-install.json"
FORMAT = "atmem-hermes-install-v1"
SETUP_FORMAT = "atmem-hermes-setup-v1"
CONFIG_BACKUP_FORMAT = "atmem-hermes-config-backup-v1"


def _safe_directory(path: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o022):
        raise ValueError("Hermes paths must be owned directories without group/world write access")


def _read(path: Path, limit: int = 1_048_576) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o022 or info.st_nlink != 1):
            raise ValueError("Hermes plugin files must be owned, unshared regular files")
        value = os.read(fd, limit + 1)
        if len(value) > limit:
            raise ValueError("Hermes plugin file exceeds size limit")
        return value
    finally:
        os.close(fd)


def _hashes(payload):
    return {name: hashlib.sha256(value).hexdigest() for name, value in payload.items()}


def _home(value: str | Path) -> Path:
    if os.name != "posix" or sys.platform not in {"darwin", "linux"}:
        raise ValueError("Hermes inactive installer is qualified only for macOS/Linux; native Windows is pending")
    path = Path(value).expanduser().absolute()
    if path != path.resolve():
        raise ValueError("Use the resolved Hermes Home path, without symbolic links")
    _safe_directory(path)
    if path == Path(path.anchor) or path == Path.home():
        raise ValueError("Select a dedicated existing Hermes Home, not a filesystem or user root")
    return path


def inspect_install(home: str | Path) -> dict:
    """Read only. No AtMem Home, credentials, RPCs or host config are loaded."""
    home = _home(home)
    parent, target = home / "plugins", home / "plugins" / "atmem"
    payload = plugin_files()
    state = "not_installed"
    if parent.exists() or parent.is_symlink():
        _safe_directory(parent)
    if target.exists() or target.is_symlink():
        _safe_directory(target)
        try:
            receipt = json.loads(_read(target / RECEIPT))
            hashes = receipt["sha256"]
            if receipt.get("format") != FORMAT or set(hashes) != set(payload):
                raise ValueError("invalid receipt")
            entries = {p.name for p in target.iterdir()}
            if entries - set(payload) - {RECEIPT, "__pycache__"}:
                raise ValueError("unexpected payload files")
            cache = target / "__pycache__"
            if cache.exists() or cache.is_symlink():
                _safe_directory(cache)
                for entry in cache.iterdir():
                    if entry.suffix != ".pyc":
                        raise ValueError("unexpected cache file")
                    _read(entry)
            actual = _hashes({name: _read(target / name) for name in payload})
            if actual != hashes:
                raise ValueError("modified payload")
            state = "installed" if actual == _hashes(payload) else "upgrade_required"
        except (OSError, ValueError, KeyError, TypeError):
            state = "conflict"
    connection_state, activation, details = "not_configured", "not_performed", {}
    if state == "installed":
        connection, credential = _read_connection(home)
        if connection and credential:
            try:
                from atmem.adapters.hermes.client import HermesRPCClient
                status = HermesRPCClient(
                    connection["endpoint"], credential,
                    profile_id=connection["profile_id"],
                    user_id=connection.get("user_id"), timeout=2.0,
                ).status()
                connection_state = "connected"
                activation = status.get("mode", "active" if status.get("enabled") else "inactive")
                details = {key: status.get(key) for key in (
                    "profile_id", "agent_id", "workspace_id", "binding_id", "mode"
                )}
            except (OSError, RuntimeError, ValueError, KeyError):
                connection_state = "configured_unreachable"
    next_step = (
        "Hermes is connected to AtMem. Restart Hermes only after changing plugin files or mode."
        if connection_state == "connected" else
        "Run `atmem install hermes --yes` to connect this profile with isolated memory."
        if state == "installed" else
        "Run `atmem install hermes` to preview the complete guided setup."
    )
    return {"hermes_home": str(home), "target": str(target), "state": state,
            "sha256": _hashes(payload), "activation": activation,
            "connection": connection_state, "connection_details": details,
            "runtime_discovery": "verify_in_hermes",
            "next_step": next_step,
            "changes": [str(target)] if state == "not_installed" else [],
            "integrity_scope": "packaged source hashes; generated bytecode is not authenticated",
            "upgrade_supported": False}


def _publish(stage: Path, target: Path) -> None:
    """Atomic no-replace rename, including when an empty target appears in a race."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = getattr(libc, "renamex_np", None)
        if function is None:
            raise RuntimeError("Exclusive rename unavailable; installation refused")
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = function(os.fsencode(stage), os.fsencode(target), 4)  # RENAME_EXCL
    else:
        function = getattr(libc, "renameat2", None)
        if function is None:
            raise RuntimeError("Exclusive rename unavailable; installation refused")
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = function(-100, os.fsencode(stage), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
    if result:
        error = ctypes.get_errno()
        raise OSError(error, "Exclusive Hermes plugin publication refused")


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install(home: str | Path, *, apply: bool = False) -> dict:
    preview = inspect_install(home)
    if not apply or preview["state"] == "installed":
        return {**preview, "applied": False}
    if preview["state"] != "not_installed":
        raise ValueError("Existing Hermes plugin differs: inspect it first; overwrite/upgrade is not supported")
    parent = Path(preview["target"]).parent
    parent.mkdir(mode=0o700, exist_ok=True)
    _safe_directory(parent)

    def validate_lock(fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o077):
            raise ValueError("Unsafe Hermes installer lock")

    with ProcessFileLock(parent / ".atmem-install.lock", validate=validate_lock):
        current = inspect_install(home)
        if current["state"] == "installed":
            return {**current, "applied": False}
        if current["state"] != "not_installed":
            raise ValueError("Hermes installation changed during preview; refusing overwrite")
        # Both native discovery systems skip names starting with double underscores.
        stage = Path(tempfile.mkdtemp(prefix="__atmem_stage_", dir=parent))
        payload = plugin_files()
        receipt = {"format": FORMAT, "sha256": _hashes(payload)}
        payload[RECEIPT] = (json.dumps(receipt, sort_keys=True) + "\n").encode()
        for name, value in payload.items():
            fd = os.open(stage / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
        _sync_directory(stage)
        _safe_directory(parent)
        _publish(stage, Path(current["target"]))
        _sync_directory(parent)
    return {**inspect_install(home), "applied": True}


def _upgrade_managed_plugin(home: Path) -> dict[str, Any]:
    """Replace only a receipt-authenticated older payload, retaining rollback."""
    current = inspect_install(home)
    if current["state"] != "upgrade_required":
        return {**current, "upgraded": False}
    target = Path(current["target"])
    backups = home / ".atmem" / "plugin-backups"
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    backups.chmod(0o700)
    old_receipt = json.loads(_read(target / RECEIPT))
    identity = hashlib.sha256(
        json.dumps(old_receipt.get("sha256") or {}, sort_keys=True).encode()
    ).hexdigest()[:16]
    backup = backups / f"atmem-{identity}"
    if backup.exists():
        raise RuntimeError("A managed Hermes plugin rollback copy already exists; inspect it")
    os.replace(target, backup)
    try:
        result = install(home, apply=True)
    except Exception:
        if not target.exists():
            os.replace(backup, target)
        raise
    return {**result, "upgraded": True, "plugin_backup": str(backup)}


def _atomic_private(path: Path, value: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _dashboard_endpoint(*, start: bool = False) -> str:
    from atmem.dashboard_daemon import manage_dashboard_daemon

    value = manage_dashboard_daemon("status")
    if not value.get("running") and start:
        recorded_port = int(value.get("port") or 8768)
        try:
            value = manage_dashboard_daemon("start", port=recorded_port)
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"AtMem could not start its service on the recorded port {recorded_port}; "
                "inspect the process using that port"
            ) from exc
    if not value.get("running"):
        return "http://127.0.0.1:8768"
    port = int(value["port"])
    if not 1 <= port <= 65535:
        raise RuntimeError("AtMem dashboard reported an invalid port")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    except OSError as exc:
        raise RuntimeError("AtMem dashboard service did not become reachable") from exc
    return f"http://127.0.0.1:{port}"


def _hermes_config(home: Path, action: str, *values: str) -> str:
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI was not found on PATH")
    result = subprocess.run(
        [executable, "config", action, *values],
        cwd=home, env={**os.environ, "HERMES_HOME": str(home)},
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError(f"Hermes configuration {action} failed")
    return result.stdout.strip()


def _read_connection(home: Path) -> tuple[dict[str, Any] | None, str | None]:
    private = home / ".atmem"
    try:
        connection = json.loads(_read(private / "connection.json", 16384).decode("utf-8"))
        credential = _read(private / "credential", 256).decode("utf-8").strip()
        return connection, credential
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None, None


def _setup_receipt(home: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(_read(home / ".atmem" / "setup-receipt.json", 65536))
        return value if value.get("format") == SETUP_FORMAT else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _write_setup_receipt(home: Path, receipt: dict[str, Any]) -> None:
    _atomic_private(
        home / ".atmem" / "setup-receipt.json",
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
    )


def _config_sha256(home: Path) -> str | None:
    path = home / "config.yaml"
    return hashlib.sha256(_read(path, 2_000_000)).hexdigest() if path.is_file() else None


def _backup_config(manager: Any, home: Path) -> dict[str, Any]:
    """Protect the exact pre-switch Hermes config with AtMem's evidence key."""
    path = home / "config.yaml"
    content = _read(path, 2_000_000) if path.is_file() else b""
    payload = {"exists": path.is_file(), "content": base64.b64encode(content).decode()}
    vault = manager.evidence_service()
    vault.storage_key()
    nonce, ciphertext = seal_json(vault.accounts.key, CONFIG_BACKUP_FORMAT, payload)
    backup = home / ".atmem" / "config-before-atmem.enc.json"
    _atomic_private(
        backup,
        (json.dumps({
            "format": CONFIG_BACKUP_FORMAT,
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }, sort_keys=True) + "\n").encode(),
    )
    return {"config_backup": str(backup), "config_before_sha256": (
        hashlib.sha256(content).hexdigest() if payload["exists"] else None
    )}


def _restore_config_backup(manager: Any, home: Path, receipt: dict[str, Any]) -> None:
    expected = receipt.get("config_after_sha256")
    if _config_sha256(home) != expected:
        raise RuntimeError(
            "Hermes configuration changed after AtMem setup; refusing to overwrite the user edit"
        )
    backup = Path(str(receipt.get("config_backup") or ""))
    if not backup.is_file() or backup.parent != home / ".atmem":
        raise RuntimeError("The protected Hermes configuration backup is unavailable")
    wrapper = json.loads(_read(backup, 3_000_000))
    if wrapper.get("format") != CONFIG_BACKUP_FORMAT:
        raise RuntimeError("The protected Hermes configuration backup is invalid")
    vault = manager.evidence_service()
    vault.storage_key()
    value = open_json(
        vault.accounts.key, CONFIG_BACKUP_FORMAT,
        base64.b64decode(wrapper["nonce"], validate=True),
        base64.b64decode(wrapper["ciphertext"], validate=True),
    )
    path = home / "config.yaml"
    if value.get("exists") is True:
        content = base64.b64decode(value["content"], validate=True)
        if hashlib.sha256(content).hexdigest() != receipt.get("config_before_sha256"):
            raise RuntimeError("The protected Hermes configuration backup failed verification")
        _atomic_private(path, content)
    else:
        path.unlink(missing_ok=True)
        _sync_directory(home)


def _native_memory_inventory(home: Path) -> list[dict[str, Any]]:
    """Inventory only the bounded, documented Hermes user-memory files."""
    rows: list[dict[str, Any]] = []
    for relative in ("MEMORY.md", "USER.md", "memories/MEMORY.md", "memories/USER.md"):
        path = home / relative
        cursor = home
        for part in Path(relative).parts[:-1]:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError("Hermes native-memory parent directories cannot be symbolic links")
        if not path.is_file() or path.is_symlink():
            continue
        content = _read(path, 1_048_576)
        rows.append({"path": relative, "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest()})
    return rows


def _import_native_proposals(
    manager: Any, *, home: Path, subject_id: str, agent_id: str,
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy native memory into quarantined AtMem proposals; never admit it."""
    from atmem.memory import Memory

    known = {str(row.get("sha256")) for row in (prior or {}).get("native_imports", [])}
    scope, memory_path = manager._memory_authority_scope(  # governed internal boundary
        manager.state(), subject_id=subject_id, agent_id=agent_id
    )
    memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
    imported: list[dict[str, Any]] = []
    try:
        for row in _native_memory_inventory(home):
            if row["sha256"] in known:
                imported.append({**row, "result": "already_proposed"})
                continue
            content = _read(home / row["path"], 1_048_576).decode("utf-8", errors="replace")
            result = memory.remember(
                scope.subject_id, content,
                session_id=f"hermes_native_{row['sha256'][:24]}",
                turn_id=row["sha256"][:32], source_type="external_content",
                actor="hermes-native-migration",
                raw={"source": "hermes_native_memory", "path": row["path"],
                     "sha256": row["sha256"], "bytes": row["bytes"]},
            )
            chunks = [part.strip() for part in content.split("\n\n") if part.strip()]
            proposals = memory.propose_facts(
                scope.subject_id,
                [{"content": chunk[:2000], "evidence": [result["episode_id"]],
                  "confidence": 0.5,
                  "fact_key": f"hermes-native-{row['sha256'][:16]}-{index}"}
                 for index, chunk in enumerate(chunks[:100])],
                proposer="hermes-native-migration",
                session_id=f"hermes_native_{row['sha256'][:24]}",
            ) if result.get("episode_id") and chunks else {"quarantined": []}
            imported.append({**row, "result": "proposed",
                             "episode_id": result.get("episode_id"),
                             "proposal_count": (
                                 len(result.get("records") or [])
                                 + len(proposals.get("quarantined") or [])
                             )})
    finally:
        memory.close()
    return {"files": len(imported),
            "proposals": sum(int(row.get("proposal_count") or 0) for row in imported),
            "native_imports": imported}


def _verify_provider_boundary(client: Any, *, mode: str) -> dict[str, Any]:
    """Exercise scoped recall without manufacturing a dashboard run."""
    nonce = hashlib.sha256(os.urandom(32)).hexdigest()[:20]
    result = client.recall(
        f"AtMem setup boundary probe {nonce}",
        session_id=f"atmem-setup-{nonce}", turn_id="boundary",
    )
    if result.reason == "unavailable_or_denied":
        raise RuntimeError("Hermes provider-boundary recall could not reach AtMem")
    if mode == "shadow" and (result.context or result.reason != "withheld"):
        raise RuntimeError("Hermes shadow verification returned influencing context")
    if client.status().get("mode") != mode:
        raise RuntimeError("Hermes provider-boundary mode did not match the request")
    return {"mode": mode, "reason": result.reason, "context_chars": len(result.context)}


def _verify_turn(
    manager: Any, *, home: Path, agent_id: str, subject_id: str,
) -> dict[str, Any]:
    """Run a normal host turn that must use a temporary governed memory."""
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes CLI was not found on PATH")
    from atmem.memory import Memory

    _, memory_path = manager._memory_authority_scope(
        manager.state(), subject_id=subject_id, agent_id=agent_id
    )
    code = "ATM" + hashlib.sha256(os.urandom(32)).hexdigest()[:12].upper()
    prompt = "What is my AtMem verification code? Reply with only the code."
    prompt_sha256 = hashlib.sha256(prompt.encode()).hexdigest()
    memory = Memory(memory_path, retain_query_text=False, graph_recall=True)
    inserted: list[str] = []
    try:
        created = memory.remember(
            subject_id,
            f"Remember that my AtMem verification code is {code}.",
            interpreted_fact=f"The user's AtMem verification code is {code}.",
            interpreted_fact_key="atmem setup verification code",
            session_id="atmem-install-verification", turn_id=code,
            source_type="user_message", actor="atmem-install-verification",
            raw={"interpreter": "deterministic setup verifier",
                 "interpretation_assurance": "local deterministic",
                 "source_binding": "explicit --verify-turn"},
        )
        inserted = [str(row["id"]) for row in created.get("records") or []]
        if not inserted:
            raise RuntimeError("AtMem could not create the temporary verification memory")
    finally:
        memory.close()
    before = {
        str((row.get("body") or {}).get("run_id"))
        for row in manager.blackbox_events()
    }
    try:
        result = subprocess.run(
            [executable, "chat", "-Q", "--query", prompt,
             "--source", "atmem-install-verification"],
            cwd=home, env={**os.environ, "HERMES_HOME": str(home)},
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode:
            raise RuntimeError("Hermes verification turn failed; setup remains recoverable")
        if code.lower() not in result.stdout.lower():
            raise RuntimeError("Hermes answered without using the governed verification memory")
        report: dict[str, Any] | None = None
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            events = [row.get("body") or {} for row in manager.blackbox_events()]
            matching = {
                str(row.get("run_id")) for row in events
                if row.get("agent_id") == agent_id and row.get("run_id") not in before
                and row.get("event_type") == "turn.input"
                and (row.get("payload") or {}).get("prompt_sha256") == prompt_sha256
            }
            for run_id in matching:
                try:
                    candidate = manager.verify_blackbox_flight(run_id)
                except ValueError:
                    continue
                coverage = candidate.get("coverage") or {}
                if (candidate.get("verdict") == "completed_successfully"
                        and candidate.get("structurally_complete") is True
                        and (candidate.get("context") or {}).get("disposition") == "injected"
                        and all(coverage.get(key) is True for key in (
                            "turn_input_observed", "context_disposition_observed",
                            "model_input_observed", "model_output_observed",
                            "response_digest_bound", "terminal_event_observed",
                        ))):
                    report = candidate
                    break
            if report is not None:
                break
            time.sleep(0.25)
        if report is None:
            raise RuntimeError(
                "Hermes answered, but the matching injected-memory turn was not complete"
            )
        return {"status": "passed", "run_id": str(report["run_id"]),
                "events": int(report.get("events") or 0),
                "context_disposition": "injected",
                "answer_sha256": hashlib.sha256(result.stdout.encode()).hexdigest()}
    finally:
        cleanup = Memory(memory_path, retain_query_text=False, graph_recall=True)
        try:
            cleanup.forget(
                subject_id, {"contains": code},
                session_id="atmem-install-verification", turn_id=code,
                actor="atmem-install-verification",
            )
        finally:
            cleanup.close()


def guided_setup(
    home: str | Path, *, apply: bool = False, activate: bool = False,
    memory: str = "isolated", endpoint: str | None = None,
    verify_turn: bool = False,
) -> dict[str, Any]:
    """Install and connect Hermes through one secret-safe local transaction.

    A distinct Hermes scope is the default. Sharing is explicit and reuses the
    selected primary workspace subject without collapsing agent identity.
    """
    home = _home(home)
    if memory not in {"shared", "isolated"}:
        raise ValueError("--memory must be shared or isolated")
    if verify_turn and not activate:
        raise ValueError("--verify-turn requires --activate so governed context can reach Hermes")
    from atmem.adapters.hermes.client import HermesRPCClient
    from atmem.adapters.hermes.service import HermesService
    from atmem.control import ControlPlaneManager
    from atmem.service import APIPrincipal

    manager = ControlPlaneManager()
    topology = manager.agent_topology()
    default_agent = str(topology["default_agent_id"])
    primary = next(row for row in topology["agents"] if row["agent_id"] == default_agent)
    agent_id = "hermes-" + hashlib.sha256(str(home).encode()).hexdigest()[:12]
    workspace = (str(primary["workspace"]) if memory == "shared"
                 else str(home / ".atmem" / "isolated-workspace"))
    projected_subject = (str(primary["subject_id"]) if memory == "shared"
                         else f"{manager.state().subject_id}:workspace:pending")
    managed_endpoint = endpoint is None
    selected_endpoint = endpoint or _dashboard_endpoint(start=apply)
    current_provider = _hermes_config(home, "get", "memory.provider") or "(built-in / default)"
    previous_receipt = _setup_receipt(home)
    if (previous_receipt and not previous_receipt.get("restored") and
            previous_receipt.get("memory") in {"isolated", "shared"} and
            previous_receipt.get("memory") != memory):
        raise RuntimeError(
            "Hermes is already connected with "
            f"{previous_receipt['memory']} memory. Run `atmem restore hermes --yes` "
            f"before reconnecting with --memory {memory}."
        )
    prior_provider = (
        str(previous_receipt["previous_provider"])
        if previous_receipt and not previous_receipt.get("restored") and current_provider == "atmem"
        else current_provider
    )
    plugin = inspect_install(home)
    plan = {
        "format": SETUP_FORMAT, "hermes_home": str(home),
        "memory": memory, "subject_id": projected_subject,
        "agent_id": agent_id, "workspace_id": "resolved-on-apply",
        "endpoint": selected_endpoint, "previous_provider": prior_provider,
        "requested_mode": "active" if activate else "shadow",
        "verify_turn": bool(verify_turn),
        "plugin_state": plugin["state"],
        "native_memory": _native_memory_inventory(home),
        "changes": ["plugin", "agent memory scope", "native-memory proposals",
                    "scoped connection", "memory provider", "setup receipt"],
        "applied": False,
    }
    if not apply:
        return plan
    if (previous_receipt and not previous_receipt.get("restored")
            and previous_receipt.get("config_after_sha256") is not None
            and _config_sha256(home) != previous_receipt.get("config_after_sha256")):
        raise RuntimeError(
            "Hermes configuration changed after AtMem setup; restore or reconcile it first"
        )
    receipt = {
        **plan, "phase": "planned", "provider_after": current_provider,
        "mode": "inactive", "credential_stored": False,
    }
    if (previous_receipt and not previous_receipt.get("restored")
            and previous_receipt.get("config_after_sha256") is not None):
        for key in ("config_backup", "config_before_sha256", "native_imports"):
            if key in previous_receipt:
                receipt[key] = previous_receipt[key]
    # The journal exists before the first plugin, topology, daemon, credential,
    # binding, memory or provider mutation.
    _write_setup_receipt(home, receipt)
    if not receipt.get("config_backup"):
        receipt.update(_backup_config(manager, home))
    receipt["phase"] = "config_backed_up"
    _write_setup_receipt(home, receipt)
    if plugin["state"] == "not_installed":
        install(home, apply=True)
    elif plugin["state"] == "upgrade_required":
        plugin_upgrade = _upgrade_managed_plugin(home)
    elif plugin["state"] != "installed":
        raise RuntimeError(
            "The existing AtMem plugin is modified or from another version; restore or "
            "upgrade it before guided setup"
        )
    receipt.update(
        phase="plugin_ready", plugin_upgrade=locals().get("plugin_upgrade")
    )
    _write_setup_receipt(home, receipt)

    topology = manager.register_external_agent(
        agent_id=agent_id, name="Hermes", workspace=workspace
    )
    agent = next(row for row in topology["agents"] if row["agent_id"] == agent_id)
    plan.update(subject_id=agent["subject_id"], workspace_id=agent["workspace_id"])
    receipt.update(subject_id=agent["subject_id"], workspace_id=agent["workspace_id"],
                   phase="scope_ready")
    _write_setup_receipt(home, receipt)
    if managed_endpoint:
        # A separately installed dashboard process may have loaded an older
        # package or cached host topology. Restart the AtMem-owned daemon on
        # its recorded port so the new binding is verified by the same code.
        from atmem.dashboard_daemon import manage_dashboard_daemon
        daemon = manage_dashboard_daemon("restart")
        selected_endpoint = str(daemon["url"]).rstrip("/")
        plan["endpoint"] = selected_endpoint

    service = HermesService(manager)
    principal = APIPrincipal(
        "local-os-owner", "admin", str(agent["subject_id"]),
        workspace_id=str(agent["workspace_id"]), tenant_id="local",
    )
    connection, credential = _read_connection(home)
    binding = None
    if connection and credential:
        try:
            status = service.dispatch(credential, "status", {})
            if (status.get("agent_id") == agent["agent_id"] and
                    status.get("workspace_id") == agent["workspace_id"]):
                binding = status
        except (RuntimeError, ValueError, KeyError, PermissionError):
            binding = None
    if binding is None:
        rows = service.list_bindings(principal)
        row = next((item for item in rows
                    if item["identity"]["agent_id"] == agent["agent_id"] and
                    item["identity"]["workspace_id"] == agent["workspace_id"]), None)
        if row is None:
            profile_id = "hermes-" + hashlib.sha256(str(home).encode()).hexdigest()[:16]
            grant = service.provision(
                principal, profile_id=profile_id, agent_id=str(agent["agent_id"]),
                workspace_id=str(agent["workspace_id"]),
                accept_reduced_capture=True,
            )
        else:
            grant = service.rotate(principal, row["binding_id"])
        binding = grant["binding"]
        credential = grant["credential"]
        connection = {
            "format": "atmem-hermes-connection-v1", "hermes_home": str(home),
            "endpoint": selected_endpoint, "profile_id": binding["profile_id"],
        }
        _atomic_private(
            home / ".atmem" / "connection.json",
            (json.dumps(connection, sort_keys=True) + "\n").encode(),
        )
        _atomic_private(home / ".atmem" / "credential", credential.encode() + b"\n")

    # Every new or resumed setup enters shadow first. Active influence is only
    # enabled after a scoped provider-boundary probe succeeds.
    binding = service.configure_mode(principal, binding["binding_id"], mode="shadow")
    # Publish the current endpoint even when an existing credential remains
    # valid; otherwise an explicit endpoint/daemon-port change is invisible to
    # the Hermes plugin.
    connection = {
        **dict(connection or {}),
        "format": "atmem-hermes-connection-v1", "hermes_home": str(home),
        "endpoint": selected_endpoint, "profile_id": binding["profile_id"],
    }
    _atomic_private(
        home / ".atmem" / "connection.json",
        (json.dumps(connection, sort_keys=True) + "\n").encode(),
    )
    receipt.update(
        phase="binding_ready", binding_id=binding["binding_id"],
        profile_id=binding["profile_id"], mode="shadow", credential_stored=True,
        endpoint=selected_endpoint,
    )
    _write_setup_receipt(home, receipt)
    migration = _import_native_proposals(
        manager, home=home, subject_id=str(agent["subject_id"]),
        agent_id=str(agent["agent_id"]), prior=previous_receipt,
    )
    receipt.update(phase="memory_proposed", **migration)
    _write_setup_receipt(home, receipt)
    client = HermesRPCClient(
        selected_endpoint, credential, profile_id=str(connection["profile_id"]),
        user_id=connection.get("user_id"), timeout=5.0,
    )
    boundary = [_verify_provider_boundary(client, mode="shadow")]
    mode = "active" if activate else "shadow"
    if activate:
        binding = service.configure_mode(principal, binding["binding_id"], mode="active")
        boundary.append(_verify_provider_boundary(client, mode="active"))
    receipt.update(phase="boundary_verified", mode=mode,
                   provider_boundary_verification=boundary)
    _write_setup_receipt(home, receipt)
    if current_provider != "atmem":
        _hermes_config(home, "set", "memory.provider", "atmem")
    receipt.update(
        phase="provider_switched", provider_after="atmem",
        config_after_sha256=_config_sha256(home),
    )
    _write_setup_receipt(home, receipt)
    verified = client.status()
    if verified.get("mode") != mode:
        raise RuntimeError("Hermes binding verification did not match the requested mode")
    verification = None
    if verify_turn:
        try:
            verification = _verify_turn(
                manager, home=home, agent_id=str(agent["agent_id"]),
                subject_id=str(agent["subject_id"]),
            )
        except Exception as verification_error:
            # A failed proof must not leave an unverified provider influencing
            # Hermes. Remove influence first; config restoration is independent
            # so one failed rollback step cannot prevent the other.
            rollback_errors: list[str] = []
            shadowed = False
            restored = False
            try:
                service.configure_mode(
                    principal, binding["binding_id"], mode="shadow"
                )
                shadowed = True
            except Exception:
                rollback_errors.append("binding could not return to shadow")
            try:
                _restore_config_backup(manager, home, receipt)
                restored_provider = (
                    _hermes_config(home, "get", "memory.provider")
                    or "(built-in / default)"
                )
                if restored_provider != prior_provider:
                    _hermes_config(home, "set", "memory.provider", prior_provider)
                restored = True
            except Exception:
                rollback_errors.append("Hermes config could not be restored")
            receipt.update(
                phase=("verification_failed" if not rollback_errors else "rollback_incomplete"),
                provider_after=(prior_provider if restored else "atmem"),
                mode=("shadow" if shadowed else "active_unverified"), applied=False,
            )
            if restored:
                # A retry compares against the now-restored bytes, not the
                # obsolete post-switch digest.
                receipt["config_after_sha256"] = _config_sha256(home)
            if rollback_errors:
                receipt["rollback_errors"] = rollback_errors
            _write_setup_receipt(home, receipt)
            if rollback_errors:
                raise RuntimeError(
                    "Hermes verification failed and rollback is incomplete: "
                    + "; ".join(rollback_errors)
                ) from verification_error
            raise
    receipt.update(
        applied=True, phase="complete", verification=verification,
        restart_required=not bool(verification),
    )
    _write_setup_receipt(home, receipt)
    return receipt


def guided_restore(home: str | Path, *, apply: bool = False) -> dict[str, Any]:
    """Disable the scoped binding and restore the provider saved by setup."""
    home = _home(home)
    receipt = _setup_receipt(home)
    if receipt is None:
        raise RuntimeError("No AtMem Hermes setup receipt was found")
    current = _hermes_config(home, "get", "memory.provider") or "(built-in / default)"
    if (current not in {"atmem", str(receipt.get("previous_provider"))}
            and not receipt.get("restored")):
        raise RuntimeError(
            "Hermes memory provider changed after setup; refusing to overwrite the user edit"
        )
    result = {
        "format": SETUP_FORMAT, "hermes_home": str(home),
        "binding_id": receipt.get("binding_id"), "current_provider": current,
        "restore_provider": receipt["previous_provider"],
        "restored": bool(receipt.get("restored")), "applied": False,
    }
    if not apply or result["restored"]:
        return result
    from atmem.control import ControlPlaneManager

    manager = ControlPlaneManager()
    previous = str(receipt["previous_provider"])
    if current == previous:
        pass
    elif receipt.get("config_backup") and "config_after_sha256" in receipt:
        _restore_config_backup(manager, home, receipt)
        restored_provider = _hermes_config(home, "get", "memory.provider") or "(built-in / default)"
        if restored_provider != previous:
            # Test doubles and older Hermes builds may not reread a replaced
            # config file. Use the supported CLI only after exact bytes have
            # been restored and only for the recorded provider value.
            _hermes_config(home, "set", "memory.provider", previous)
    elif previous == "(built-in / default)":
        executable = shutil.which("hermes")
        if not executable:
            raise RuntimeError("Hermes CLI was not found on PATH")
        command = subprocess.run(
            [executable, "memory", "off"], cwd=home,
            env={**os.environ, "HERMES_HOME": str(home)},
            capture_output=True, text=True, timeout=30,
        )
        if command.returncode:
            raise RuntimeError("Hermes provider restore failed")
    else:
        _hermes_config(home, "set", "memory.provider", previous)
    binding_warning = None
    if receipt.get("binding_id"):
        try:
            from atmem.adapters.hermes.service import HermesService
            from atmem.service import APIPrincipal

            service = HermesService(manager)
            identity = service._load(str(receipt["binding_id"]))["identity"]
            principal = APIPrincipal(
                "local-os-owner", "admin", identity["subject_id"],
                workspace_id=identity["workspace_id"], tenant_id="local",
            )
            service.configure_mode(
                principal, str(receipt["binding_id"]), mode="inactive"
            )
        except Exception:
            # Provider restoration must not be held hostage by an expired,
            # revoked, missing or no-longer-scoped AtMem binding.
            binding_warning = "provider restored; the old AtMem binding could not be disabled"
    receipt["restored"] = True
    receipt["mode"] = "inactive"
    receipt["provider_after"] = previous
    _write_setup_receipt(home, receipt)
    return {**result, "restored": True, "applied": True,
            "binding_warning": binding_warning}
