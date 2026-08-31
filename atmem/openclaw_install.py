from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Callable
from uuid import uuid4

from atmem.control import ControlPlaneManager, ControlMode
from atmem.control.manager import DEFAULT_STATE_PATH, DEFAULT_CONTROL_ROOT


OPENCLAW_PLUGIN_ID = "memory-atmem"
OPENCLAW_PLUGIN_PACKAGE = "openclaw-memory-atmem"
OPENCLAW_PLUGIN_VERSION = "2.2.1"
_CONFIG_KEY = "plugins.entries.memory-atmem"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str]], CommandResult]
ProgressReporter = Callable[[int, int, str], None]


def install_openclaw(
    *,
    state_path: str | Path = DEFAULT_STATE_PATH,
    control_root: str | Path = DEFAULT_CONTROL_ROOT,
    runner: Runner | None = None,
    engine_executable: str | None = None,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    """Install the matching bridge and enter fail-closed shadow mode.

    The Python package is the authority for this workflow. The npm package is
    a host bridge and is never presented as a standalone installation.
    """

    run = runner or _run
    report = progress or (lambda _step, _total, _label: None)
    total_steps = 8
    report(1, total_steps, "Checking AtMem and OpenClaw")
    engine = _resolve_engine(engine_executable)
    openclaw = shutil.which("openclaw")
    if openclaw is None:
        raise ValueError(
            "OpenClaw was not found on PATH. Install OpenClaw first, then rerun "
            "`atmem openclaw install`."
        )

    engine_version = _verify_engine(engine, run)
    _require_success(run([openclaw, "--version"]), "OpenClaw version check")

    report(2, total_steps, "Reading the current OpenClaw configuration")
    prior_plugin = _inspect_plugin(openclaw, run, optional=True)
    prior_version = _find_plugin_version(prior_plugin)
    prior_entry = _get_optional_json(
        [openclaw, "config", "get", _CONFIG_KEY, "--json"], run
    )
    package_changed = False
    manager: ControlPlaneManager | None = None
    resumed_existing_migration = False
    restore_errors: list[str] = []

    try:
        report(3, total_steps, "Installing the verified OpenClaw bridge")
        if prior_version != OPENCLAW_PLUGIN_VERSION:
            install_command = [
                openclaw,
                "plugins",
                "install",
                f"npm:{OPENCLAW_PLUGIN_PACKAGE}@{OPENCLAW_PLUGIN_VERSION}",
                "--pin",
            ]
            if prior_version is not None:
                install_command.append("--force")
            _require_success(run(install_command), "OpenClaw bridge installation")
            package_changed = True

        report(4, total_steps, "Verifying the installed bridge")
        installed = _inspect_plugin(openclaw, run, optional=False)
        installed_version = _find_plugin_version(installed)
        if installed_version != OPENCLAW_PLUGIN_VERSION:
            raise ValueError(
                "OpenClaw retained bridge version "
                f"{installed_version or 'unknown'}; expected {OPENCLAW_PLUGIN_VERSION}"
            )

        # Record the exact executable before the migration snapshot is taken. This
        # survives service PATH differences and remains the restore baseline.
        _set_json(
            openclaw,
            f"{_CONFIG_KEY}.config.command",
            engine,
            run,
        )
        if prior_plugin is None:
            _set_json(openclaw, f"{_CONFIG_KEY}.enabled", False, run)

        manager, resumed_existing_migration = ControlPlaneManager.start_or_resume_shadow(
            host="openclaw",
            state_path=state_path,
            control_root=control_root,
        )
        report(
            5,
            total_steps,
            (
                "Refreshing the existing OpenClaw memory mirror"
                if resumed_existing_migration
                else "Copying and indexing existing OpenClaw memory"
            ),
        )
        from atmem.control.hosts import configure_host

        # A real manager refreshes and verifies the mirror as part of status;
        # keeping that boundary also makes installer adapters straightforward.
        manager.status()

        configure_kwargs: dict[str, Any] = {"atmem_executable": engine}
        if resumed_existing_migration:
            configure_kwargs["record_snapshot"] = False
        integration = configure_host(manager.state(), state_path, **configure_kwargs)
        report(6, total_steps, "Restarting the OpenClaw gateway")
        _require_success(
            run([openclaw, "gateway", "restart"]),
            "OpenClaw gateway restart",
        )
        report(7, total_steps, "Verifying the gateway and plugin runtime")
        gateway = _get_json(
            [
                openclaw,
                "gateway",
                "status",
                "--require-rpc",
                "--json",
            ],
            run,
        )
        if not _gateway_verified(gateway):
            raise ValueError("OpenClaw gateway RPC verification did not pass")
        runtime_plugin = _inspect_plugin(
            openclaw, run, optional=False, runtime=True
        )
        if not _plugin_runtime_healthy(runtime_plugin):
            raise ValueError("OpenClaw reported that the AtMem bridge is not healthy")
        observed = _get_json(
            [
                openclaw,
                "config",
                "get",
                f"{_CONFIG_KEY}.config",
                "--json",
            ],
            run,
        )
        if not isinstance(observed, dict):
            raise ValueError("OpenClaw did not return the AtMem plugin configuration")
        control_plane = observed.get("controlPlane")
        if not isinstance(control_plane, dict) or control_plane.get("enabled") is not True:
            raise ValueError("OpenClaw did not retain fail-closed memory control plane mode")
        if observed.get("command") != engine:
            raise ValueError("OpenClaw did not retain the exact AtMem executable path")

        report(8, total_steps, "Verifying the memory mirror and audit evidence")
        status = manager.status()
        if status.get("mode") != "shadow":
            raise ValueError("AtMem migration did not enter shadow mode")
        mirror = status.get("mirror")
        mirror = mirror if isinstance(mirror, dict) else {}
        baseline = mirror.get("native_baseline")
        baseline = baseline if isinstance(baseline, dict) else {}
        if not mirror.get("audit_verified") or not baseline.get("snapshot_sha256"):
            raise ValueError(
                "OpenClaw native-memory baseline or searchable mirror did not verify"
            )
        return {
            "format": "atmem-openclaw-install-v1",
            "installed": True,
            "engine_version": engine_version,
            "engine_executable": engine,
            "plugin_version": installed_version,
            "plugin_id": OPENCLAW_PLUGIN_ID,
            "gateway_verified": _gateway_verified(gateway),
            "migration_id": status.get("migration_id"),
            "control_mode": status.get("mode"),
            "changes_model_context": status.get("changes_model_context"),
            "control_dir": status.get("control_dir"),
            "state_path": str(Path(state_path).expanduser().resolve(strict=False)),
            "integration": integration,
            "native_baseline_verified": True,
            "native_baseline_sha256": baseline.get("snapshot_sha256"),
            "native_baseline_files": baseline.get("file_count"),
            "native_baseline_bytes": baseline.get("total_bytes"),
            "mirror_verified": True,
            "mirror_db": mirror.get("mirror_db"),
            "existing_migration_reused": resumed_existing_migration,
        }
    except Exception as exc:
        report(total_steps, total_steps, "Installation failed; restoring prior state")
        if manager is not None and not resumed_existing_migration:
            try:
                manager.transition(ControlMode.OFF, actor="install-restore")
            except Exception as restore_exc:  # pragma: no cover - defensive
                restore_errors.append(f"migration stop: {restore_exc}")
        if package_changed:
            try:
                if prior_version is None:
                    _require_success(
                        run(
                            [
                                openclaw,
                                "plugins",
                                "uninstall",
                                OPENCLAW_PLUGIN_ID,
                                "--force",
                            ]
                        ),
                        "bridge package restore",
                    )
                else:
                    _require_success(
                        run(
                            [
                                openclaw,
                                "plugins",
                                "install",
                                f"npm:{OPENCLAW_PLUGIN_PACKAGE}@{prior_version}",
                                "--pin",
                                "--force",
                            ]
                        ),
                        "bridge package restore",
                    )
            except Exception as restore_exc:
                restore_errors.append(f"bridge package: {restore_exc}")
        try:
            _restore_entry(openclaw, prior_entry, run)
        except Exception as restore_exc:
            restore_errors.append(f"OpenClaw configuration: {restore_exc}")
        try:
            _require_success(
                run([openclaw, "gateway", "restart"]),
                "OpenClaw gateway restart after restore",
            )
        except Exception as restore_exc:
            restore_errors.append(f"gateway restart: {restore_exc}")
        detail = f"AtMem OpenClaw installation failed: {exc}"
        if restore_errors:
            detail += ". Restore also needs attention: " + "; ".join(restore_errors)
        else:
            detail += ". The prior OpenClaw plugin configuration was restored."
        raise ValueError(detail) from exc


def refresh_openclaw_bridge_and_test(
    *,
    state_path: str | Path = DEFAULT_STATE_PATH,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Upgrade only the pinned bridge, restart it, and record one safe test flight."""

    run = runner or _run
    manager = ControlPlaneManager(state_path)
    state = manager.state()
    if state.host != "openclaw":
        raise ValueError("bridge refresh is available only for OpenClaw")
    openclaw = shutil.which("openclaw")
    if openclaw is None:
        raise ValueError("OpenClaw was not found on PATH")
    installed_before = _inspect_plugin(openclaw, run, optional=False)
    prior_version = _find_plugin_version(installed_before)
    runtime_before = _inspect_plugin(openclaw, run, optional=True, runtime=True)
    runtime_version = _find_plugin_version(runtime_before)
    if (
        prior_version == OPENCLAW_PLUGIN_VERSION
        and runtime_version == OPENCLAW_PLUGIN_VERSION
    ):
        raise ValueError(
            f"bridge {OPENCLAW_PLUGIN_VERSION} is already loaded; the installed "
            "AtMem package does not yet pin a newer bridge"
        )

    package_changed = prior_version != OPENCLAW_PLUGIN_VERSION
    try:
        if package_changed:
            _require_success(
                run(
                    [
                        openclaw,
                        "plugins",
                        "install",
                        f"npm:{OPENCLAW_PLUGIN_PACKAGE}@{OPENCLAW_PLUGIN_VERSION}",
                        "--pin",
                        "--force",
                    ]
                ),
                "OpenClaw bridge upgrade",
            )
        installed = _inspect_plugin(openclaw, run, optional=False)
        installed_version = _find_plugin_version(installed)
        if installed_version != OPENCLAW_PLUGIN_VERSION:
            raise ValueError(
                f"OpenClaw retained bridge {installed_version or 'unknown'}; "
                f"expected {OPENCLAW_PLUGIN_VERSION}"
            )
        _require_success(
            run([openclaw, "gateway", "restart"]),
            "OpenClaw gateway restart",
        )
        gateway = _get_json(
            [openclaw, "gateway", "status", "--require-rpc", "--json"], run
        )
        if not _gateway_verified(gateway):
            raise ValueError("OpenClaw gateway RPC verification did not pass")
        runtime = _inspect_plugin(openclaw, run, optional=False, runtime=True)
        if not _plugin_runtime_healthy(runtime):
            raise ValueError("OpenClaw reported that the refreshed bridge is unhealthy")
    except Exception as exc:
        restore_errors: list[str] = []
        if package_changed and prior_version:
            try:
                _require_success(
                    run(
                        [
                            openclaw,
                            "plugins",
                            "install",
                            f"npm:{OPENCLAW_PLUGIN_PACKAGE}@{prior_version}",
                            "--pin",
                            "--force",
                        ]
                    ),
                    "prior bridge restore",
                )
                _require_success(
                    run([openclaw, "gateway", "restart"]),
                    "gateway restart after bridge restore",
                )
            except Exception as restore_exc:  # pragma: no cover - defensive
                restore_errors.append(str(restore_exc))
        detail = f"bridge refresh failed: {exc}"
        if restore_errors:
            detail += ". Restore also needs attention: " + "; ".join(restore_errors)
        raise ValueError(detail) from exc

    before = {
        str(row["run_id"]) for row in manager.blackbox_runs(limit=500).get("runs", [])
    }
    test_session = f"agent:main:atmem-bridge-self-test-{uuid4().hex}"
    test_command = [
        openclaw,
        "agent",
        "--session-key",
        test_session,
        "--message",
        "AtMem bridge self-test. Do not call tools. Reply exactly ATMEM_BRIDGE_OK.",
        "--timeout",
        "90",
        "--json",
    ]
    _require_success(run(test_command), "OpenClaw bridge self-test flight")
    new_rows: list[dict[str, Any]] = []
    for _attempt in range(12):
        rows = manager.blackbox_runs(limit=500).get("runs", [])
        new_rows = [row for row in rows if str(row.get("run_id")) not in before]
        if new_rows:
            break
        time.sleep(0.25)
    if not new_rows:
        raise ValueError(
            "the gateway completed the self-test but no new Black Box flight appeared"
        )
    selected = next(
        (row for row in new_rows if row.get("session_id") == test_session),
        new_rows[0],
    )
    report: dict[str, Any] = {}
    for _attempt in range(40):
        report = manager.verify_blackbox_flight(str(selected["run_id"]))
        if report.get("verdict") != "incomplete_evidence":
            break
        time.sleep(0.25)
    return {
        "format": "atmem-openclaw-bridge-refresh-v1",
        "refreshed": True,
        "previous_bridge_version": prior_version,
        "bridge_version": OPENCLAW_PLUGIN_VERSION,
        "mode": state.mode.value,
        "gateway_verified": True,
        "test_flight": {
            "run_id": report.get("run_id"),
            "verdict": report.get("verdict"),
            "coverage_status": (report.get("coverage_matrix") or {}).get(
                "overall_status"
            ),
            "attention_points": report.get("attention_points") or [],
            "valid": report.get("verdict") == "completed_successfully",
        },
    }


def openclaw_bridge_refresh_status(
    *, runner: Runner | None = None
) -> dict[str, Any]:
    """Report whether the installed Python package pins a bridge refresh."""

    run = runner or _run
    openclaw = shutil.which("openclaw")
    if openclaw is None:
        return {
            "available": False,
            "pinned_version": OPENCLAW_PLUGIN_VERSION,
            "reason": "OpenClaw was not found on PATH",
        }
    installed = _inspect_plugin(openclaw, run, optional=True)
    runtime = _inspect_plugin(openclaw, run, optional=True, runtime=True)
    installed_version = _find_plugin_version(installed)
    runtime_version = _find_plugin_version(runtime)
    available = (
        installed_version != OPENCLAW_PLUGIN_VERSION
        or runtime_version != OPENCLAW_PLUGIN_VERSION
    )
    return {
        "available": available,
        "pinned_version": OPENCLAW_PLUGIN_VERSION,
        "installed_version": installed_version,
        "runtime_version": runtime_version,
        "reason": (
            "A newer pinned bridge can be installed and tested."
            if available
            else "Install a newer AtMem Python release to make a bridge upgrade available."
        ),
    }


def _resolve_engine(explicit: str | None) -> str:
    candidate = explicit or shutil.which("atmem")
    if not candidate:
        raise ValueError(
            "The `atmem` executable is not on PATH. Install the engine first "
            "with `python -m pip install atmem`, confirm `atmem --version`, "
            "then rerun `atmem openclaw install`."
        )
    path = Path(candidate).expanduser().resolve(strict=False)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"AtMem executable is missing or not executable: {path}")
    return str(path)


def _verify_engine(engine: str, run: Runner) -> str:
    result = run([engine, "--version"])
    _require_success(result, "AtMem engine version check")
    output = result.stdout.strip()
    if not output.startswith("atmem "):
        raise ValueError(f"unexpected AtMem version response: {output or 'empty'}")
    return output.removeprefix("atmem ").strip()


def _inspect_plugin(
    openclaw: str, run: Runner, *, optional: bool, runtime: bool = False
) -> Any | None:
    arguments = [openclaw, "plugins", "inspect", OPENCLAW_PLUGIN_ID]
    if runtime:
        arguments.append("--runtime")
    arguments.append("--json")
    result = run(arguments)
    if result.returncode != 0 and optional:
        normalized = f"{result.stderr}\n{result.stdout}".casefold()
        if any(text in normalized for text in ("not found", "not installed", "unknown")):
            return None
    _require_success(result, "OpenClaw bridge inspection")
    return _parse_json(result.stdout, "OpenClaw bridge inspection")


def _find_plugin_version(value: Any) -> str | None:
    if isinstance(value, dict):
        plugin = value.get("plugin")
        if isinstance(plugin, dict) and isinstance(plugin.get("version"), str):
            return str(plugin["version"])
        if isinstance(value.get("version"), str):
            return str(value["version"])
        for nested in value.values():
            found = _find_plugin_version(nested)
            if found is not None:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_plugin_version(nested)
            if found is not None:
                return found
    return None


def _gateway_verified(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    rpc = value.get("rpc")
    if isinstance(rpc, dict) and rpc.get("ok") is True:
        return True
    gateway = value.get("gateway")
    if not isinstance(gateway, dict):
        return False
    probe = gateway.get("probe")
    if isinstance(probe, dict):
        return probe.get("ok") is True
    return gateway.get("reachable") is True or gateway.get("status") in {
        "running",
        "ready",
    }


def _plugin_runtime_healthy(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    plugin = value.get("plugin")
    if not isinstance(plugin, dict) or plugin.get("status") not in {
        "loaded",
        "active",
        "ready",
    }:
        return False
    diagnostics = value.get("diagnostics")
    if isinstance(diagnostics, list):
        for item in diagnostics:
            if isinstance(item, dict) and str(item.get("level", "")).casefold() in {
                "error",
                "fatal",
            }:
                return False
    typed_hooks = {
        str(row.get("name"))
        for row in value.get("typedHooks", [])
        if isinstance(row, dict)
    }
    required_hooks = {
        "before_model_resolve",
        "before_prompt_build",
        "llm_input",
        "llm_output",
        "agent_end",
        "before_message_write",
        "before_tool_call",
        "after_tool_call",
    }
    return required_hooks.issubset(typed_hooks)


def _set_json(openclaw: str, key: str, value: Any, run: Runner) -> None:
    _require_success(
        run(
            [
                openclaw,
                "config",
                "set",
                key,
                json.dumps(value, separators=(",", ":")),
                "--strict-json",
            ]
        ),
        f"OpenClaw configuration write for {key}",
    )


def _restore_entry(openclaw: str, prior_entry: Any | None, run: Runner) -> None:
    if prior_entry is None:
        result = run([openclaw, "config", "unset", _CONFIG_KEY])
        if result.returncode != 0:
            normalized = f"{result.stderr}\n{result.stdout}".casefold()
            if not any(
                text in normalized
                for text in ("not found", "no value", "missing", "unknown config path")
            ):
                _require_success(result, "OpenClaw configuration restore")
        return
    _set_json(openclaw, _CONFIG_KEY, prior_entry, run)


def _get_json(arguments: list[str], run: Runner) -> Any:
    result = run(arguments)
    _require_success(result, " ".join(arguments[1:3]))
    return _parse_json(result.stdout, " ".join(arguments[1:3]))


def _get_optional_json(arguments: list[str], run: Runner) -> Any | None:
    result = run(arguments)
    if result.returncode != 0:
        normalized = f"{result.stderr}\n{result.stdout}".casefold()
        if any(
            text in normalized
            for text in ("not found", "missing", "no value", "unknown config path")
        ):
            return None
        _require_success(result, " ".join(arguments[1:3]))
    return _parse_json(result.stdout, " ".join(arguments[1:3]))


def _parse_json(text: str, operation: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} did not return JSON") from exc


def _require_success(result: CommandResult, operation: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout).strip() or "no diagnostic output"
    raise ValueError(f"{operation} failed: {detail}")


def _run(arguments: list[str]) -> CommandResult:
    try:
        result = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"could not run {' '.join(arguments[:3])}: {exc}") from exc
    return CommandResult(result.returncode, result.stdout, result.stderr)
