from __future__ import annotations

import subprocess

import pytest

from atmem.code.identity import CodeIdentity
from atmem.store.sqlite import SQLiteStore


def _repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_clone_does_not_auto_share_and_explicit_rebind_is_scoped(tmp_path) -> None:
    first = _repo(tmp_path / "first")
    clone = _repo(tmp_path / "clone")
    store = SQLiteStore()
    try:
        identity = CodeIdentity(store)
        shared = identity.resolve(first, subject_id="user-1", profile_id="shared", agent_id="codex")
        same = identity.resolve(first, subject_id="user-1", profile_id="shared", agent_id="claude")
        assert shared.project_id == same.project_id
        assert shared.agent_id != same.agent_id
        distinct = identity.resolve(clone, subject_id="user-1", profile_id="private", agent_id="codex")
        assert distinct.project_id != shared.project_id
        with pytest.raises(ValueError, match="already bound"):
            identity.resolve(clone, subject_id="user-1", profile_id="shared", agent_id="codex",
                             rebind_project_id=shared.project_id)
        with pytest.raises(PermissionError, match="not owned"):
            identity.resolve(tmp_path, subject_id="user-2", profile_id="shared", agent_id="codex",
                             rebind_project_id=shared.project_id)
    finally:
        store.close()


def test_unbound_clone_can_rebind_only_when_explicit(tmp_path) -> None:
    first = _repo(tmp_path / "first")
    clone = _repo(tmp_path / "clone")
    store = SQLiteStore()
    try:
        identity = CodeIdentity(store)
        original = identity.resolve(first, subject_id="user-1", profile_id="shared", agent_id="codex")
        bound = identity.resolve(clone, subject_id="user-1", profile_id="shared", agent_id="claude",
                                 rebind_project_id=original.project_id)
        assert bound.project_id == original.project_id
    finally:
        store.close()


def test_remote_change_requires_explicit_confirmation(tmp_path) -> None:
    repo = _repo(tmp_path / "repo")
    store = SQLiteStore()
    try:
        identity = CodeIdentity(store)
        original = identity.resolve(repo, subject_id="user-1", profile_id="shared", agent_id="codex")
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "https://example.invalid/new.git"], check=True)
        with pytest.raises(ValueError, match="remote changed"):
            identity.resolve(repo, subject_id="user-1", profile_id="shared", agent_id="codex")
        confirmed = identity.resolve(repo, subject_id="user-1", profile_id="shared", agent_id="codex",
                                     confirm_remote_change=True)
        assert confirmed.project_id == original.project_id
    finally:
        store.close()
