from __future__ import annotations

import pytest

from atmem.code.adapters.base import HostProbe
from atmem.code.install import CodeInstall
from atmem.store.sqlite import SQLiteStore


def test_setup_is_preview_first_and_never_auto_enables(tmp_path) -> None:
    store = SQLiteStore()
    try:
        installer = CodeInstall(store)
        preview = installer.setup(
            tmp_path, subject_id="user-1", profile_id="shared",
            agent_id="codex", host="codex",
        )
        assert preview["applied"] is False
        assert installer.status(project=tmp_path, subject_id="user-1", host="codex")["configured"] is False
        applied = installer.setup(
            tmp_path, subject_id="user-1", profile_id="shared",
            agent_id="codex", host="codex", apply=True,
        )
        assert applied["applied"] is True
        assert applied["enabled"] is False
        assert installer.status(project=tmp_path, subject_id="user-1", host="codex")["configured"] is True
        with pytest.raises(RuntimeError, match="not yet verified"):
            installer.enable(project=tmp_path, subject_id="user-1", host="codex")
        assert installer.status(project=tmp_path, subject_id="user-1", host="codex")["enabled"] is False
    finally:
        store.close()


def test_setup_refuses_unencrypted_persistent_storage(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "code.db")
    try:
        result = CodeInstall(store).setup(
            tmp_path, subject_id="user-1", profile_id="shared",
            agent_id="codex", host="codex", apply=True,
        )
        assert result["applied"] is False
        assert "encrypted" in result["reason"]
        assert store.code_project_binding("user-1", "unused") is None
    finally:
        store.close()


class _VerifiedAdapter:
    host = "codex"

    def __init__(self, path):
        self.path = path

    def probe(self):
        return HostProbe("codex", "test-1", "test-os", False, False, "submitted", None)

    def verify_installed(self):
        return HostProbe("codex", "test-1", "test-os", True, True, "host_acknowledged", "a" * 64)

    def configuration_path(self):
        return self.path

    def planned_configuration(self, previous):
        return (previous or b"") + b"\nAtMem Code test hook\n"


def test_explicit_enable_then_exact_disable_across_installer_instances(tmp_path) -> None:
    host_config = tmp_path / "host.json"
    host_config.write_bytes(b"owner settings\n")
    store = SQLiteStore()
    try:
        factory = lambda: _VerifiedAdapter(host_config)
        first = CodeInstall(store, adapters={"codex": factory})
        first.setup(tmp_path, subject_id="user-1", profile_id="shared",
                    agent_id="codex", host="codex", apply=True)
        active = first.enable(project=tmp_path, subject_id="user-1", host="codex")
        assert active["enabled"] is True
        assert active["host"]["automatic_verified"] is True
        with pytest.raises(RuntimeError, match="already enabled"):
            first.setup(tmp_path, subject_id="user-1", profile_id="shared",
                        agent_id="codex", host="codex", apply=True)
        second = CodeInstall(store, adapters={"codex": factory})
        stopped = second.disable(project=tmp_path, subject_id="user-1", host="codex")
        assert stopped["enabled"] is False
        assert host_config.read_bytes() == b"owner settings\n"
    finally:
        store.close()


def test_disable_refuses_to_overwrite_owner_change(tmp_path) -> None:
    host_config = tmp_path / "host.json"
    host_config.write_bytes(b"owner settings\n")
    store = SQLiteStore()
    try:
        installer = CodeInstall(store, adapters={"codex": lambda: _VerifiedAdapter(host_config)})
        installer.setup(tmp_path, subject_id="user-1", profile_id="shared",
                        agent_id="codex", host="codex", apply=True)
        installer.enable(project=tmp_path, subject_id="user-1", host="codex")
        host_config.write_bytes(b"owner changed this")
        with pytest.raises(RuntimeError, match="changed after activation"):
            installer.disable(project=tmp_path, subject_id="user-1", host="codex")
        assert host_config.read_bytes() == b"owner changed this"
        assert installer.status(project=tmp_path, subject_id="user-1", host="codex")["host"]["mode"] == "degraded"
    finally:
        store.close()
