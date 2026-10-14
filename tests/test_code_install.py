from __future__ import annotations

import pytest

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
