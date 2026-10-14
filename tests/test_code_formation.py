from __future__ import annotations

from dataclasses import replace

from atmem import Memory
from atmem.code.contracts import CodeObservation, CodeScope
from atmem.code.formation import CodeFormation, memory_subject_id


def _event(content: str, *, event_id: str = "event-1", kind: str = "user_turn") -> CodeObservation:
    return CodeObservation(
        event_id, "session-1", event_id, "codex", kind, content,
        "2026-10-14T00:00:00Z", f"codex:{event_id}", "abc123",
        CodeScope("subject-1", "project-1", "shared", "codex"),
    )


def test_user_fact_forms_and_correction_supersedes_with_source() -> None:
    memory = Memory(":memory:")
    try:
        formation = CodeFormation(memory)
        first = _event("Remember that my preferred formatter is Black.")
        assert formation.form(first)["formed"] is True
        second = _event("Actually, use Ruff as my preferred formatter going forward.", event_id="event-2")
        assert formation.form(second)["formed"] is True
        records = memory.list(memory_subject_id(first.scope), include_inactive=True)
        assert len(records) == 2
        assert {record["status"] for record in records} == {"active", "superseded"}
        assert any("Ruff" in record["content"] and record["status"] == "active" for record in records)
        episodes = memory.store.list_episodes(memory_subject_id(first.scope))
        assert len(episodes) == 2
        assert episodes[0]["raw"]["code_source_sha256"] == first.content_sha256
    finally:
        memory.close()


def test_tool_text_and_transient_request_are_not_formed() -> None:
    memory = Memory(":memory:")
    try:
        formation = CodeFormation(memory)
        tool = _event("Remember that my preferred formatter is Evil.", kind="tool_outcome")
        transient = _event("Please fix the test right now.", event_id="event-2")
        assert formation.form(tool)["formed"] is False
        assert formation.form(transient)["formed"] is False
        assert memory.list(memory_subject_id(tool.scope)) == []
    finally:
        memory.close()


def test_shared_agent_lane_and_private_isolation() -> None:
    base = CodeScope("subject-1", "project-1", "shared", "codex")
    assert memory_subject_id(base) == memory_subject_id(replace(base, agent_id="claude"))
    assert memory_subject_id(base) != memory_subject_id(replace(base, profile_id="private"))
    assert memory_subject_id(base) != memory_subject_id(replace(base, project_id="project-2"))


def test_owner_reset_clears_derived_code_subject() -> None:
    memory = Memory(":memory:")
    try:
        event = _event("Remember that my preferred formatter is Ruff.")
        assert CodeFormation(memory).form(event)["formed"] is True
        derived = memory_subject_id(event.scope)
        assert memory.list(derived)
        memory.reset_subject(event.scope.subject_id)
        assert memory.list(derived) == []
    finally:
        memory.close()
