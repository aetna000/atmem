from __future__ import annotations

from atmem import Memory
from atmem.code.contracts import CodeContextRequest, CodeObservation, CodeScope
from atmem.code.runtime import CodeRuntime
from atmem.code.service import CodeIntakeService
from atmem.code.context import build_context


def _turn(scope, event_id, content):
    return CodeObservation(
        event_id, "session-1", event_id, scope.agent_id, "user_turn", content,
        "2026-10-14T00:00:00Z", f"host:{event_id}", None, scope,
    )


def test_enabled_turn_retrieves_prior_memory_without_agent_remember_call() -> None:
    memory = Memory(":memory:")
    try:
        scope = CodeScope("user-1", "project-1", "shared", "codex")
        intake = CodeIntakeService(memory.store, scope=scope, host="codex",
                                   session_id="session-1", secret=b"x" * 32, enabled=True)
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
        intake = CodeIntakeService(memory.store, scope=codex, host="codex",
                                   session_id="session-1", secret=b"x" * 32, enabled=True)
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
        intake = CodeIntakeService(memory.store, scope=scope, host="codex",
                                   session_id="session-1", secret=b"x" * 32, enabled=True)
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
