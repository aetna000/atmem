"""Guided, non-influencing Code onboarding and host readiness inventory."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from atmem.code.identity import CodeIdentity
from atmem.store.sqlite import SQLiteStore


HOST_BINARIES = {
    "muse": "muse", "claude": "claude", "grok": "grok",
    "copilot": "copilot", "codex": "codex",
}


class CodeInstall:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.identity = CodeIdentity(store)

    def doctor(self, host: str) -> dict:
        if host not in HOST_BINARIES:
            raise ValueError("unsupported coding host")
        executable = shutil.which(HOST_BINARIES[host])
        version = None
        if executable:
            try:
                result = subprocess.run(
                    [executable, "--version"], capture_output=True, text=True,
                    check=False, timeout=5,
                )
                if result.returncode == 0:
                    version = (result.stdout or result.stderr).strip()[:120]
            except (OSError, subprocess.TimeoutExpired):
                pass
        return {"host": host, "detected": executable is not None,
                "version": version, "automatic_verified": False,
                "mode": "manual_only", "reason": "host hook and context-boundary probe pending"}

    def setup(
        self, project: str | Path, *, subject_id: str, profile_id: str,
        agent_id: str, host: str, apply: bool = False,
    ) -> dict:
        readiness = self.doctor(host)
        if self.store.path != ":memory:" and self.store.policy.state != "encrypted":
            return {"applied": False, "ready": False, "reason": "encrypted AtMem household required",
                    "next_action": f"atmem household init {self.store.path} --encrypted",
                    "host": readiness}
        if not apply:
            return {"applied": False, "ready": True, "host": readiness,
                    "project": str(Path(project).resolve()), "enabled": False}
        scope = self.identity.resolve(
            project, subject_id=subject_id, profile_id=profile_id,
            agent_id=agent_id,
        )
        self.store.put_code_installation(
            subject_id=subject_id, project_id=scope.project_id,
            host=host, enabled=False,
        )
        return {"applied": True, "ready": True, "host": readiness,
                "scope": scope.to_dict(), "enabled": False}

    def status(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        from atmem.code.identity import repository_key

        binding = self.store.code_project_binding(subject_id, repository_key(project))
        installation = (
            self.store.code_installation(subject_id, binding["project_id"], host)
            if binding else None
        )
        return {"configured": installation is not None,
                "enabled": bool(installation and installation["enabled"]),
                "project_id": binding["project_id"] if binding else None,
                "host": self.doctor(host)}

    def enable(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        # An installed package or hook file is not evidence of model-visible
        # delivery. Adapters must register a versioned, tested probe first.
        raise RuntimeError(f"{host} automatic adapter is not yet verified; Code remains disabled")

    def disable(self, *, project: str | Path, subject_id: str, host: str) -> dict:
        from atmem.code.identity import repository_key

        binding = self.store.code_project_binding(subject_id, repository_key(project))
        if binding is None:
            raise ValueError("project is not configured")
        self.store.put_code_installation(
            subject_id=subject_id, project_id=binding["project_id"],
            host=host, enabled=False,
        )
        return self.status(project=project, subject_id=subject_id, host=host)
