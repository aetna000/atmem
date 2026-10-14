from __future__ import annotations

from dataclasses import replace

import pytest

from atmem.code.contracts import CodeObservation, CodeScope
from atmem.code.service import CodeIntakeService
from atmem.store.sqlite import SQLiteStore


def _observation(*, event_id: str = "event-1", scope: CodeScope | None = None) -> CodeObservation:
    return CodeObservation(
        event_id, "session-1", "turn-1", "codex", "user_turn",
        "Use Ruff for this project's Python formatting.",
        "2026-10-14T00:00:00Z", "codex:turn-1", None,
        scope or CodeScope("subject-1", "project-1", "shared", "codex"),
    )


def _service(store: SQLiteStore, *, enabled: bool = True, max_pending: int = 500) -> CodeIntakeService:
    store.put_code_installation(
        subject_id="subject-1", project_id="project-1", host="codex", enabled=True,
    )
    return CodeIntakeService(
        store, scope=_observation().scope, host="codex", session_id="session-1",
        secret=b"a" * 32, enabled=enabled, max_pending=max_pending,
    )


def test_intake_is_opt_in_signed_idempotent_and_scope_bound() -> None:
    store = SQLiteStore()
    try:
        service = _service(store, enabled=False)
        event = _observation()
        with pytest.raises(PermissionError, match="disabled"):
            service.submit(event.to_dict(), service.sign(event))
        service.enabled = True
        with pytest.raises(PermissionError, match="signature"):
            service.submit(event.to_dict(), "0" * 64)
        assert service.submit(event.to_dict(), service.sign(event))["queued"] is True
        assert service.submit(event.to_dict(), service.sign(event))["queued"] is False
        assert service.pending() == [event]
        other_scope = replace(event, scope=replace(event.scope, project_id="other"))
        with pytest.raises(PermissionError, match="scope"):
            service.submit(other_scope.to_dict(), service.sign(other_scope))
        other_session = replace(event, session_id="session-2")
        with pytest.raises(PermissionError, match="session"):
            service.submit(other_session.to_dict(), service.sign(other_session))
        changed = replace(event, content="Use Black instead.")
        with pytest.raises(ValueError, match="idempotency conflict"):
            service.submit(changed.to_dict(), service.sign(changed))
    finally:
        store.close()


def test_queue_is_bounded_and_secrets_are_not_written() -> None:
    store = SQLiteStore()
    try:
        service = _service(store, max_pending=1)
        secret = replace(_observation(), content="API key = sk-test-FakeCredential123456")
        assert service.submit(secret.to_dict(), service.sign(secret))["accepted"] is False
        assert service.pending() == []
        event = _observation()
        service.submit(event.to_dict(), service.sign(event))
        with pytest.raises(OverflowError, match="queue is full"):
            next_event = replace(event, event_id="event-2")
            service.submit(next_event.to_dict(), service.sign(next_event))
        assert service.pending() == [event]
    finally:
        store.close()


def test_persistent_plaintext_queue_fails_closed(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "code.db")
    try:
        with pytest.raises(RuntimeError, match="encrypted"):
            _service(store)
    finally:
        store.close()
