"""Stable local project identity, independent of coding host and worktree."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.code.contracts import CodeScope
from atmem.store.sqlite import SQLiteStore


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def repository_key(path: str | Path) -> str:
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project root must be a directory")
    # Linked worktrees share one common Git directory. Clones do not.
    git_dir = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    canonical = Path(git_dir).resolve() if git_dir else root
    return sha256(str(canonical).encode("utf-8")).hexdigest()


class CodeIdentity:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def resolve(
        self, path: str | Path, *, subject_id: str, profile_id: str,
        agent_id: str, rebind_project_id: str | None = None,
        confirm_remote_change: bool = False,
    ) -> CodeScope:
        key = repository_key(path)
        remote = _git(Path(path).resolve(), "remote", "get-url", "origin")
        remote_digest = sha256(remote.encode("utf-8")).hexdigest() if remote else None
        existing = self.store.code_project_binding(subject_id, key)
        if existing is not None:
            if rebind_project_id is not None and existing["project_id"] != rebind_project_id:
                raise ValueError("repository is already bound to another project")
            if existing["remote_sha256"] != remote_digest:
                if not confirm_remote_change:
                    raise ValueError("Git remote changed; explicit confirmation required")
                self.store.confirm_code_remote_change(
                    subject_id=subject_id, repository_key=key,
                    project_id=existing["project_id"], remote_sha256=remote_digest,
                )
            return CodeScope(subject_id, existing["project_id"], profile_id, agent_id)
        if rebind_project_id is not None:
            # Rebinding a clone is an explicit user action, and can only name a
            # project already owned by the same authenticated subject.
            if not self.store.code_project_exists(subject_id, rebind_project_id):
                raise PermissionError("target project is not owned by subject")
            project_id = rebind_project_id
        else:
            project_id = f"project-{uuid4().hex}"
        self.store.bind_code_project(
            subject_id=subject_id, repository_key=key, project_id=project_id,
            remote_sha256=remote_digest,
        )
        return CodeScope(subject_id, project_id, profile_id, agent_id)
