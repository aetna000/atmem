from __future__ import annotations

from atmem import Memory
from atmem.code.contracts import CodeContextRequest, CodeObservation, CodeScope
from atmem.code.runtime import CodeRuntime
from atmem.code.service import CodeIntakeService
from atmem.code.context import build_context
import pytest


def _turn(scope, event_id, content):
    return CodeObservation(
        event_id, "session-1", event_id, scope.agent_id, "user_turn", content,
        "2026-10-14T00:00:00Z", f"host:{event_id}", None, scope,
    )


def _intake(memory, scope):
    memory.store.put_code_installation(
        subject_id=scope.subject_id, project_id=scope.project_id,
        host=scope.agent_id, enabled=True,
    )
    return CodeIntakeService(
        memory.store, scope=scope, host=scope.agent_id,
        session_id="session-1", secret=b"x" * 32, enabled=True,
    )


def test_enabled_turn_retrieves_prior_memory_without_agent_remember_call() -> None:
    memory = Memory(":memory:")
    try:
        scope = CodeScope("user-1", "project-1", "shared", "codex")
        intake = _intake(memory, scope)
        runtime = CodeRuntime(memory, intake)
        first = _turn(scope, "event-1", "Remember that my preferred formatter is Ruff.")
        first_request = CodeContextRequest("request-1", "session-1", "event-1", "Which formatter?", 2048, scope)
        result = runtime.on_user_turn(first_request, first, intake.sign(first))
        assert result["context"].memory_ids == ()
        assert result["formation"][0]["formed"] is True
        second = _turn(scope, "event-2", "Please fix the formatter test.")
        second_request = CodeContextRequest("request-2", "session-1", "event-2", "preferred formatter", 2048, scope)
        result = runtime.on_user_turn(second_request, second, intake.sign(second))
        assert "Ruff" in result["context"].content
        assert result["context"].memory_ids
        assert result["formation"][0]["formed"] is False
    finally:
        memory.close()


def test_cross_agent_shared_context_excludes_private_and_other_projects() -> None:
    memory = Memory(":memory:")
    try:
        codex = CodeScope("user-1", "project-1", "shared", "codex")
        intake = _intake(memory, codex)
        runtime = CodeRuntime(memory, intake)
        event = _turn(codex, "event-1", "Remember that my preferred formatter is Ruff.")
        runtime.on_user_turn(
            CodeContextRequest("request-1", "session-1", "event-1", "formatter", 2048, codex),
            event, intake.sign(event),
        )
        claude = CodeScope("user-1", "project-1", "shared", "claude")
        request = CodeContextRequest("request-2", "session-2", "turn-2", "preferred formatter", 2048, claude)
        assert "Ruff" in build_context(memory, request).content
        private = CodeScope("user-1", "project-1", "private", "claude")
        other = CodeScope("user-1", "project-2", "shared", "claude")
        assert build_context(memory, CodeContextRequest("request-3", "session-2", "turn-2", "formatter", 2048, private)).content == ""
        assert build_context(memory, CodeContextRequest("request-4", "session-2", "turn-2", "formatter", 2048, other)).content == ""
    finally:
        memory.close()


def test_context_budget_never_splits_memory_or_claims_delivery() -> None:
    memory = Memory(":memory:")
    try:
        scope = CodeScope("user-1", "project-1", "shared", "codex")
        intake = _intake(memory, scope)
        event = _turn(scope, "event-1", "Remember that my preferred formatter is Ruff.")
        CodeRuntime(memory, intake).on_user_turn(
            CodeContextRequest("request-1", "session-1", "event-1", "formatter", 2048, scope),
            event, intake.sign(event),
        )
        context = build_context(
            memory, CodeContextRequest("request-2", "session-2", "turn-2", "formatter", 256, scope)
        )
        assert len(context.content.encode("utf-8")) <= 256
        assert "assurance" not in context.to_dict()
    finally:
        memory.close()


def test_disable_stops_automatic_capture_and_context_injection() -> None:
    memory = Memory(":memory:")
    try:
        scope = CodeScope("user-1", "project-1", "shared", "codex")
        intake = _intake(memory, scope)
        runtime = CodeRuntime(memory, intake)
        first = _turn(scope, "event-1", "Remember that my preferred formatter is Ruff.")
        runtime.on_user_turn(
            CodeContextRequest("request-1", "session-1", "event-1", "formatter", 2048, scope),
            first, intake.sign(first),
        )
        memory.store.set_code_installation_enabled(
            subject_id=scope.subject_id, project_id=scope.project_id,
            host="codex", enabled=False,
        )
        second = _turn(scope, "event-2", "Remember that my preferred formatter is Black.")
        paused = runtime.on_user_turn(
            CodeContextRequest("request-2", "session-1", "event-2", "formatter", 2048, scope),
            second, intake.sign(second),
        )
        assert paused["context"].content == ""
        assert paused["capture"] == {"accepted": False, "reason": "disabled"}
        assert paused["formation"] == []
        assert memory.store.list_code_observations(
            subject_id=scope.subject_id, project_id=scope.project_id,
            profile_id="shared", agent_id="codex", state="pending",
        ) == []
        memory.store.set_code_installation_enabled(
            subject_id=scope.subject_id, project_id=scope.project_id,
            host="codex", enabled=True,
        )
        resumed = runtime.on_user_turn(
            CodeContextRequest("request-3", "session-1", "event-2", "formatter", 2048, scope),
            second, intake.sign(second),
        )
        assert "Ruff" in resumed["context"].content
    finally:
        memory.close()


def test_disable_pauses_previously_queued_formation() -> None:
    memory = Memory(":memory:")
    try:
        scope = CodeScope("user-1", "project-1", "shared", "codex")
        intake = _intake(memory, scope)
        runtime = CodeRuntime(memory, intake)
        event = _turn(scope, "event-queued", "Remember that my preferred formatter is Ruff.")
        assert intake.submit(event.to_dict(), intake.sign(event))["queued"] is True
        memory.store.set_code_installation_enabled(
            subject_id=scope.subject_id, project_id=scope.project_id,
            host="codex", enabled=False,
        )
        with pytest.raises(PermissionError, match="disabled"):
            runtime.process_pending()
        assert memory.store.list_code_observations(
            subject_id=scope.subject_id, project_id=scope.project_id,
            profile_id="shared", agent_id="codex", state="pending",
        )
        memory.store.set_code_installation_enabled(
            subject_id=scope.subject_id, project_id=scope.project_id,
            host="codex", enabled=True,
        )
        assert runtime.process_pending()[0]["formed"] is True
    finally:
        memory.close()
