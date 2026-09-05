"""Shared fixtures and seeds for the governed task-state suites."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from atmem.contracts import AuthorityScope
from atmem.core.time import to_iso
from atmem.store.sqlite import SQLiteStore


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    """A real on-disk store, so restart behavior is testable."""
    engine = SQLiteStore(tmp_path / "task-state.db")
    try:
        yield engine
    finally:
        engine.close()


def seed_task(
    store: SQLiteStore,
    *,
    task_id: str = "task-1",
    subject_id: str = SCOPE.subject_id,
    agent_id: str = SCOPE.agent_id,
    workspace_id: str = SCOPE.workspace_id,
    lifecycle: str = "open",
    goal: str = "Ship the migration",
    created_offset_minutes: int = 0,
    expiry_rule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert one task with its revision 1, the way a real start would."""
    created = to_iso(MOMENT + timedelta(minutes=created_offset_minutes))
    task = store.insert_task(
        task_id=task_id,
        subject_id=subject_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        profile_id="general",
        profile_version="general-v1",
        goal=goal,
        lifecycle=lifecycle,
        head_revision=1,
        created_at_utc=created,
        last_progress_at_utc=created,
        expiry_rule=expiry_rule or {},
        clock_source="fixed-utc-v1",
        idempotency_key=f"start:{task_id}",
    )
    store.insert_task_revision(
        task_id=task_id,
        revision=1,
        parent_revision=None,
        state={"task_id": task_id, "revision": 1, "lifecycle": lifecycle},
        state_sha256="sha256:" + "a" * 64,
        semantic_sha256="sha256:" + "0" * 64,
        actor="operator",
        actor_role="operator",
        reason_codes=["lifecycle_change_accepted"],
        evidence=[],
        created_at_utc=created,
    )
    return task
