from __future__ import annotations

from pathlib import Path

from atmem import Memory
from atmem.control import ControlPlaneManager


def test_memory_query_revalidates_companion_ids(
    tmp_path: Path, monkeypatch
) -> None:
    memory_path = tmp_path / "memory.db"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=memory_path,
    )
    memory = Memory(memory_path)
    try:
        stored = memory.remember("local-user", "My preferred car is a blue Volvo.")
        record_id = stored["records"][0]["id"]
    finally:
        memory.close()

    def malicious_query(self, query, candidates):
        del self, query
        return {
            "answer": "The user's preferred car is a blue Volvo.",
            "ranked_record_ids": ["rec_not_authorized", candidates[0]["record_id"]],
            "companion": {"available": True, "fallback": False},
        }

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.query", malicious_query
    )
    result = manager.memory_query("What do you remember about me?")
    assert [row["record_id"] for row in result["used_memories"]] == [record_id]
    assert "rec_not_authorized" not in {
        row["record_id"] for row in result["used_memories"]
    }


def test_dashboard_contains_one_governed_memory_chat() -> None:
    from atmem.control.web import dashboard_html

    html = dashboard_html()
    assert "Ask governed memory" in html
    assert "/api/memory/query" in html
    assert "Searching authorized memory" in html


def test_openclaw_overview_excludes_agent_instruction_files(
    tmp_path: Path, monkeypatch
) -> None:
    from atmem.control.openclaw_native import sync_mirror

    manager = ControlPlaneManager.start(
        host="openclaw",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "MEMORY.md").write_text("# Memory\n\n- User likes blue cars.\n")
    (workspace / "AGENTS.md").write_text("# Instructions\n\nAlways use tools carefully.\n")
    sync_mirror(manager.state(), workspace=workspace)

    captured = {}

    def inspect_candidates(self, query, candidates):
        del self, query
        captured["content"] = [row["content"] for row in candidates]
        return {
            "answer": "User likes blue cars.",
            "ranked_record_ids": [],
            "companion": {"available": True, "fallback": False},
        }

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.query", inspect_candidates
    )
    manager.memory_query("What do you remember about me?")
    assert any("blue cars" in value for value in captured["content"])
    assert not any("use tools carefully" in value for value in captured["content"])


def test_favorite_food_uses_expansion_and_hybrid_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    from atmem.control.openclaw_native import sync_mirror

    manager = ControlPlaneManager.start(
        host="openclaw",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    mirror = sync_mirror(manager.state(), workspace=workspace)
    memory = Memory(mirror["mirror_db"])
    try:
        memory.remember(
            "local-user",
            "JT likes burgers.",
            interpreted_fact="JT likes burgers.",
            interpreted_fact_key="food_preference_burgers",
        )
    finally:
        memory.close()

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {
            "expanded_queries": [query, "food preference", "preferred meal"],
            "content_received": False,
        },
    )

    def rank(self, query, candidates):
        del self, query
        burger = next(row for row in candidates if "burgers" in row["content"])
        assert burger["signals"]["semantic"] is True
        assert "food preference" in burger["matched_queries"]
        return {
            "answer": "Your favorite food is burgers.",
            "ranked_record_ids": [burger["record_id"]],
            "companion": {"available": True, "fallback": False},
        }

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.query", rank
    )
    result = manager.memory_query("what is my fav food")
    assert result["answer"] == "Your favorite food is burgers."
    assert result["used_memories"][0]["content"] == "JT likes burgers."
    assert "semantic" in result["retrieval"]["signals"]


def test_openclaw_refresh_preserves_non_native_active_memory(tmp_path: Path) -> None:
    from atmem.control.openclaw_native import search_mirror, sync_mirror

    manager = ControlPlaneManager.start(
        host="openclaw",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "MEMORY.md"
    source.write_text("# Memory\n", encoding="utf-8")
    first = sync_mirror(manager.state(), workspace=workspace)
    memory = Memory(first["mirror_db"])
    try:
        memory.remember(
            "local-user",
            "JT likes burgers.",
            interpreted_fact="JT likes burgers.",
            interpreted_fact_key="food_preference_burgers",
            session_id="agent:authenticated-turn",
        )
    finally:
        memory.close()

    source.write_text("# Memory\n\n- Native file changed.\n", encoding="utf-8")
    sync_mirror(manager.state(), workspace=workspace)
    result = search_mirror(manager.state(), "burger")
    assert result["records"][0]["content"] == "JT likes burgers."
    assert result["records"][0]["fact_key"] == "food_preference_burgers"
