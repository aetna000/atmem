"""Guided, non-influencing Code onboarding and host readiness inventory."""

from __future__ import annotations

from pathlib import Path
import base64
import json
import shutil
import subprocess
from typing import Callable
from functools import wraps

from atmem.code.adapters.base import ConfigSnapshot, HostAdapter, HostConfigTransaction, restore_configuration, snapshot_configuration
from atmem.code.identity import CodeIdentity
from atmem.store.sqlite import SQLiteStore
from atmem.locking import ProcessFileLock


def _configuration_lock(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        if self.store.path == ":memory:":
            return method(self, *args, **kwargs)
        with ProcessFileLock(Path(str(self.store.path) + ".code-install.lock")):
            return method(self, *args, **kwargs)
    return wrapped


HOST_BINARIES = {
    "muse": "muse", "claude": "claude", "grok": "grok",
    "copilot": "copilot", "codex": "codex",
}


class CodeInstall:
    def __init__(
        self, store: SQLiteStore, *, adapters: dict[str, Callable[[], HostAdapter]] | None = None,
    ) -> None:
        self.store = store
        self.identity = CodeIdentity(store)
        self.adapters = adapters or {}

    def doctor(self, host: str) -> dict:
        if host not in HOST_BINARIES:
            raise ValueError("unsupported coding host")
        executable = shutil.which(HOST_BINARIES[host])
        version = None
        if executable:
            try:
                argv = [executable]
                if host == "copilot":
                    from atmem.code.adapters.copilot import copilot_cli_argv
                    argv = copilot_cli_argv()
                result = subprocess.run(
                    [*argv, "--version"], capture_output=True, text=True,
                    check=False, timeout=5,
                )
                if result.returncode == 0:
                    version = (result.stdout or result.stderr).strip()[:120]
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
        return {"host": host, "detected": executable is not None,
                "version": version, "automatic_verified": False,
                "mode": "manual_only", "reason": "host hook and context-boundary probe pending"}

    def setup(
        self, project: str | Path, *, subject_id: str, profile_id: str,
        agent_id: str, host: str, apply: bool = False,
    ) -> dict:
        readiness = self.doctor(host)
        paths = {"muse": ".muse/hooks.json", "claude": ".claude/settings.local.json",
                 "grok": ".grok/hooks/atmem-code.json", "copilot": ".github/hooks/atmem-code.json",
                 "codex": ".codex/hooks.json"}
        planned = {"configuration_path": str(Path(project).expanduser().resolve() / paths[host]),
                   "database_path": str(self.store.path), "host_configuration_changed_by_setup": False,
                   "activation": "explicit enable with installed-host probe", "first_activation_needs_new_host_session": True,
                   "capture": "user turns and bounded tool outcomes", "capture_coverage": "partial",
                   "reconstruction_status": "not_reconstructable", "model_download": False}
        if self.store.path != ":memory:" and self.store.policy.state != "encrypted":
            return {"applied": False, "ready": False, "reason": "encrypted AtMem household required",
                    "next_action": f"atmem household init {self.store.path} --encrypted",
                    "host": readiness, "planned_changes": planned}
        if not apply:
            return {"applied": False, "ready": True, "host": readiness,
                    "project": str(Path(project).resolve()), "enabled": False, "planned_changes": planned}
        scope = self.identity.resolve(
            project, subject_id=subject_id, profile_id=profile_id,
            agent_id=agent_id,
        )
        existing = self.store.code_installation(subject_id, scope.project_id, host)
        # Additive policy for genuinely fresh Code projects only. Repeating
        # setup or adding another host must not change an existing policy.
        installations = self.store._conn.execute(
            'SELECT 1 FROM code_installations WHERE subject_id=? AND project_id=? LIMIT 1',
            (subject_id, scope.project_id)).fetchone()
        if not installations and self.store.code_document(subject_id, scope.project_id, 'settings', 'effective') is None:
            self.store.put_code_document(subject_id, scope.project_id, 'settings', 'effective',
                {'context_mode': 'index', 'index_limit': 3, 'index_bytes': 1024})
            self.store.append_audit_event(subject_id=subject_id, actor='user', event_type='code.context_mode_initialized',
                payload={'project_id': scope.project_id, 'context_mode': 'index'})
        if existing is not None and existing["enabled"]:
            raise RuntimeError("Code host is already enabled; setup cannot replace its restore record")
        if existing is not None and existing["restore_json"]:
            # A paused adapter already owns an exact restore snapshot. Setup
            # must not erase that snapshot just because the user repeats it.
            return {"applied": False, "ready": True, "host": readiness,
                    "scope": scope.to_dict(), "enabled": False,
                    "reason": "host already configured and paused"}
        self.store.put_code_installation(
            subject_id=subject_id, project_id=scope.project_id,
            host=host, enabled=False,
        )
        self.store.put_code_document(subject_id, scope.project_id, "host-scope", host,
                                      {"profile_id": profile_id, "agent_id": agent_id})
        from atmem.extract.validation import screen_content
        label = Path(project).resolve().name
        self.store.put_code_document(subject_id, scope.project_id, "project-info", "info",
                                      {"name": label if screen_content(label, trusted=True).admissible else "Project"})
        return {"applied": True, "ready": True, "host": readiness,
                "scope": scope.to_dict(), "enabled": False, "planned_changes": planned}

    def status(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        from atmem.code.identity import repository_key

        binding = self.store.code_project_binding(subject_id, repository_key(project))
        installation = (
            self.store.code_installation(subject_id, binding["project_id"], host)
            if binding else None
        )
        readiness = self.doctor(host)
        if installation and installation["restore_json"]:
            try:
                restore = json.loads(installation["restore_json"])
                current = snapshot_configuration(restore["path"])
                intact = current.sha256 == restore["installed_sha256"]
                current_version = self.adapters[host]().probe().version if host in self.adapters else readiness["version"]
                intact = intact and (not restore.get("host_version") or current_version == restore["host_version"])
                readiness.update({
                    "installed": True,
                    "automatic_verified": bool(installation["enabled"] and intact and restore.get("probe_evidence_sha256")),
                    "mode": ("automatic" if installation["enabled"] else "paused") if intact else "degraded",
                    "reason": ("automatic memory active" if installation["enabled"] else "automatic memory paused") if intact else "host configuration changed",
                })
            except (OSError, ValueError, TypeError, KeyError):
                readiness.update({"automatic_verified": False, "mode": "degraded",
                                  "reason": "host restore record cannot be verified"})
        return {"configured": installation is not None,
                "capture_coverage": "partial", "reconstruction_status": "not_reconstructable",
                "enabled": bool(installation and installation["enabled"]),
                "project_id": binding["project_id"] if binding else None,
                "scope": self.store.code_document(subject_id, binding["project_id"], "host-scope", host) if binding else None,
                "host": readiness}

    @_configuration_lock
    def enable(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        from atmem.code.identity import repository_key

        if self.store.path != ":memory:" and self.store.policy.state != "encrypted":
            raise RuntimeError("persistent Code enable requires encrypted AtMem storage")
        binding = self.store.code_project_binding(subject_id, repository_key(project))
        if binding is None:
            raise ValueError("project is not configured")
        row = self.store.code_installation(subject_id, binding["project_id"], host)
        if row is None:
            raise ValueError("host is not configured for this project")
        if row["enabled"]:
            return self.status(project=project, subject_id=subject_id, host=host)
        if row["restore_json"]:
            restore = json.loads(row["restore_json"])
            if restore.get("format") != "atmem-code-host-restore-v1":
                raise ValueError("invalid Code host restore record")
            current = snapshot_configuration(restore["path"])
            if current.sha256 != restore["installed_sha256"]:
                raise RuntimeError("host configuration changed while paused; refusing activation")
            current_version = self.adapters[host]().probe().version if host in self.adapters else self.doctor(host)["version"]
            if restore.get("host_version") and current_version != restore["host_version"]:
                raise RuntimeError("host version changed; reinstall and verify the adapter before activation")
            with self.store.transaction():
                latest = self.store.code_installation(subject_id, binding["project_id"], host)
                if latest is None or latest["updated_at"] != row["updated_at"]:
                    raise RuntimeError("Code activation was cancelled by a concurrent setting change")
                self.store.set_code_installation_enabled(
                    subject_id=subject_id, project_id=binding["project_id"],
                    host=host, enabled=True,
                )
            return self.status(project=project, subject_id=subject_id, host=host)
        if host not in self.adapters:
            if self.store.path == ":memory:":
                raise RuntimeError(f"{host} automatic adapter is not yet verified; Code remains disabled")
            from atmem.code.adapters.registry import verified_adapter
            adapter = verified_adapter(self.store, subject=subject_id, project=binding["project_id"], root=str(project), host=host)
            self.adapters[host] = lambda: adapter
        transaction = HostConfigTransaction(self.adapters[host]())
        result = transaction.apply()
        before = transaction.before
        restore = {
            "format": "atmem-code-host-restore-v1",
            "path": str(before.path), "existed": before.existed,
            "content_base64": base64.b64encode(before.content or b"").decode("ascii"),
            "mode": before.mode, "before_sha256": before.sha256,
            "installed_sha256": transaction.after_digest,
            "probe_evidence_sha256": result["probe_evidence_sha256"],
            "host_version": transaction.initial_probe.version,
            "host_platform": transaction.initial_probe.platform,
        }
        try:
            with self.store.transaction():
                latest = self.store.code_installation(subject_id, binding["project_id"], host)
                if latest is None or latest["updated_at"] != row["updated_at"]:
                    raise RuntimeError("Code activation was cancelled by a concurrent setting change")
                self.store.put_code_installation(
                    subject_id=subject_id, project_id=binding["project_id"],
                    host=host, enabled=True, restore_json=json.dumps(restore, sort_keys=True),
                )
        except BaseException:
            transaction.restore()
            raise
        return self.status(project=project, subject_id=subject_id, host=host)

    def disable(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        from atmem.code.identity import repository_key

        binding = self.store.code_project_binding(subject_id, repository_key(project))
        if binding is None:
            raise ValueError("project is not configured")
        row = self.store.code_installation(subject_id, binding["project_id"], host)
        if row is None:
            raise ValueError("host is not configured for this project")
        # Keep the hook and restore snapshot in place. The hook's intake and
        # context paths read this flag for every turn and become no-ops.
        self.store.set_code_installation_enabled(
            subject_id=subject_id, project_id=binding["project_id"],
            host=host, enabled=False,
        )
        return self.status(project=project, subject_id=subject_id, host=host)

    @_configuration_lock
    def uninstall(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        """Explicitly restore prior host configuration after a pause."""
        from atmem.code.identity import repository_key

        binding = self.store.code_project_binding(subject_id, repository_key(project))
        if binding is None:
            raise ValueError("project is not configured")
        row = self.store.code_installation(subject_id, binding["project_id"], host)
        if row is None:
            raise ValueError("host is not configured for this project")
        if row["enabled"]:
            raise RuntimeError("disable automatic Code memory before uninstall")
        if row["restore_json"]:
            value = json.loads(row["restore_json"])
            if value.get("format") != "atmem-code-host-restore-v1":
                raise ValueError("invalid Code host restore record")
            content = base64.b64decode(value["content_base64"], validate=True)
            before = ConfigSnapshot(
                Path(value["path"]), bool(value["existed"]),
                content if value["existed"] else None,
                value["mode"], value["before_sha256"],
            )
            restore_configuration(before, value["installed_sha256"])
        self.store.delete_code_installation(
            subject_id=subject_id, project_id=binding["project_id"],
            host=host,
        )
        for item in self.store.code_document_items(subject_id, binding["project_id"], "enrollment"):
            if item["value"].get("host") == host:
                self.store.delete_code_documents(subject_id, binding["project_id"], "enrollment", item["document_id"])
        return self.status(project=project, subject_id=subject_id, host=host)
