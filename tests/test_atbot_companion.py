from __future__ import annotations

from pathlib import Path
from typing import Sequence

from atmem import Memory
from atmem.control import ControlMode, ControlPlaneManager
from atmem.semantic import SemanticIndex, default_index_path


class _ConceptEmbedder:
    @property
    def identity(self) -> dict[str, str]:
        return {
            "provider": "test",
            "model": "runtime-concepts",
            "version": "1",
            "normalization": "l2",
        }

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.casefold()
        concepts = ("airport", "sydney", "departure", "flight")
        if any(word in lowered for word in concepts):
            return [1.0, 0.0]
        return [0.0, 1.0]


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


def test_dashboard_and_control_prepare_use_authorized_support_order_in_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    memory_path = tmp_path / "memory.db"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=memory_path,
    )
    memory = Memory(memory_path, auto_vectors=False)
    try:
        supported = memory.remember(
            "local-user",
            "Supported evidence one.",
            interpreted_fact="Supported evidence one.",
            interpreted_fact_key="support.one",
            session_id="private-source-session",
        )["records"][0]
        peer = memory.remember(
            "local-user",
            "Supported evidence two.",
            interpreted_fact="Supported evidence two.",
            interpreted_fact_key="support.two",
            session_id="private-source-session",
        )["records"][0]
        decoy = memory.remember(
            "local-user",
            "A close singleton decoy.",
            interpreted_fact="A close singleton decoy.",
            interpreted_fact_key="support.decoy",
            session_id="other-session",
        )["records"][0]
    finally:
        memory.close()

    raw_candidates = [
        {"record_id": supported["id"], "content": supported["content"], "score": 0.80},
        {"record_id": peer["id"], "content": peer["content"], "score": 0.75},
        {"record_id": decoy["id"], "content": decoy["content"], "score": 0.81},
    ]
    monkeypatch.setattr(
        manager,
        "_hybrid_memory_candidates",
        lambda *args, **kwargs: list(raw_candidates),
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {"expanded_queries": [query], "content_received": False},
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.health",
        lambda self: {"available": False, "reason": "test companion unavailable"},
    )

    dashboard = manager.memory_query("Which evidence applies?")
    assert [row["record_id"] for row in dashboard["used_memories"]] == [
        supported["id"]
    ]
    signals = dashboard["used_memories"][0]["signals"]
    assert signals["record_score"] == 0.8
    assert signals["aggregate_score"] > 0.81
    assert "private-source-session" not in str(dashboard)

    manager.transition(ControlMode.SHADOW)
    shadow = manager.prepare("Which evidence applies?")
    assert shadow["inject"] is False
    assert shadow["candidate_ids"] == [supported["id"]]

    manager.transition(ControlMode.ACTIVE)
    active = manager.prepare("Which evidence applies?")
    assert active["inject"] is True
    assert active["candidate_ids"] == [supported["id"]]
    assert "Supported evidence one" in active["context"]
    assert "private-source-session" not in str(active)


def test_automatic_capture_uses_atbot_proposals_and_atmem_admission(
    tmp_path: Path, monkeypatch
) -> None:
    memory_path = tmp_path / "memory.db"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=memory_path,
    )
    manager.activate()

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.propose",
        lambda self, message: {
            "format": "atbot-memory-proposals-v1",
            "proposals": [
                {
                    "fact": "User's preferred lunch is burgers.",
                    "fact_key": "food::preferred-lunch",
                    "confidence": 0.96,
                    "sensitivity": "personal",
                    "entities": [{"type": "food", "name": "burgers"}],
                    "suggested_action": "add",
                    "related_record_ids": ["rec_atbot_must_not_introduce"],
                }
            ],
            "interpreter": {
                "provider": "ollama",
                "model": "qwen3:4b",
                "prompt_version": "atbot-extract-v1",
                "assurance": "model_interpreted",
                "egress_class": "local",
            },
            "companion": {"available": True, "fallback": False},
        },
    )

    result = manager.capture(
        "My favourite lunch is burgers.",
        authenticated_user=True,
        session_id="turn-1",
        agent_id="main",
    )

    assert result["admissions"][0]["decision"] == "active"
    assert result["record_ids"]
    assert result["source"]["source_sha256"].startswith("sha256:")
    assert result["admissions"][0]["related_record_ids"] == ()
    assert Path(f"{memory_path}.vectors.db").is_file()
    memory = Memory(memory_path)
    try:
        record = memory.store.get_record("local-user", result["record_ids"][0])
        assert record["content"] == "User's preferred lunch is burgers."
        assert record["raw"]["interpreter"]["provider"] == "ollama"
        assert memory.store.list_episodes("local-user")[0]["message"] == (
            "My favourite lunch is burgers."
        )
    finally:
        memory.close()


def test_automatic_capture_falls_back_to_rules_without_atbot(
    tmp_path: Path, monkeypatch
) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=tmp_path / "memory.db",
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.propose",
        lambda self, message: {
            "proposals": [],
            "companion": {"available": False, "fallback": True},
        },
    )

    result = manager.capture(
        "I prefer dark mode.", authenticated_user=True, agent_id="main"
    )

    assert result["admissions"][0]["decision"] == "quarantined"
    assert result["canonical_candidate_ids"]
    assert result["atbot"]["fallback"] is True


def test_automatic_capture_falls_back_when_model_returns_no_explicit_fact(
    tmp_path: Path, monkeypatch
) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=tmp_path / "memory.db",
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.propose",
        lambda self, message: {
            "proposals": [],
            "interpreter": {
                "provider": "ollama",
                "model": "qwen3:1.7b",
                "prompt_version": "atbot-extract-v1",
                "assurance": "model_interpreted",
                "egress_class": "local",
            },
            "companion": {"available": True, "fallback": False},
        },
    )

    result = manager.capture(
        "Remember that my preferred editor is Neovim.",
        authenticated_user=True,
        agent_id="main",
    )

    assert result["captured"] == 1
    assert result["admissions"][0]["decision"] == "quarantined"


def test_control_prepare_uses_semantic_candidates_and_revalidates_atbot_ids(
    tmp_path: Path, monkeypatch
) -> None:
    memory_path = tmp_path / "memory.db"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=memory_path,
    )
    memory = Memory(memory_path, auto_vectors=False)
    try:
        airport = memory.remember(
            "local-user", "My preferred airport is Sydney."
        )["records"][0]
        index = SemanticIndex(default_index_path(memory_path), policy=memory.policy)
        try:
            embedder = _ConceptEmbedder()
            index.build(memory, "local-user", embedder)
        finally:
            index.close()
    finally:
        memory.close()

    monkeypatch.setattr("atmem.memory._embedder_for_epoch", lambda epoch: embedder)
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {
            "expanded_queries": [query],
            "content_received": False,
        },
    )

    def rank(self, query, candidates):
        del self, query
        semantic = next(row for row in candidates if row["record_id"] == airport["id"])
        assert semantic["signals"]["semantic_evidence"] is not None
        return {
            "ranked_record_ids": ["rec_not_authorized", semantic["record_id"]],
            "companion": {"available": True, "fallback": False},
        }

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.query", rank
    )
    manager.transition(ControlMode.ACTIVE)

    prepared = manager.prepare("departure location")

    assert prepared["inject"] is True
    assert prepared["candidate_ids"] == [airport["id"]]
    assert "Sydney" in prepared["context"]
    assert prepared["context"].startswith('<atmem-context format="v1">')
    assert prepared["candidate_set_id"].startswith("cset_")
    assert prepared["preparation_id"].startswith("prep_")
    assert "rec_not_authorized" not in prepared["context"]
    assert "semantic" in prepared["retrieval"]["signals"]


def test_dashboard_contains_one_governed_memory_chat() -> None:
    from atmem.control.web import dashboard_html

    html = dashboard_html()
    assert "Ask governed memory" in html
    assert "/api/memory/query" in html
    assert "Searching authorized memory" in html
    assert "Configure AtBot" in html
    assert "/api/companion/profiles" in html
    assert "/api/companion/configure" in html
    assert "/api/companion/action" in html
    assert "Keys are not entered here" in html
    assert '<details class="intelligenceconfig" id="intelligenceConfig">' in html
    assert '<details class="intelligenceconfig" id="intelligenceConfig" open>' not in html
    assert 'placeholder="Ask about stored memory"' in html
    assert '<div class="dockmeta" id="memoryChatDockMeta">' in html
    assert '<div class="chatresult" id="memoryChatResult" hidden>' in html
    assert "Governed memory conversation" in html
    assert 'content:"You"' in html
    assert 'content:"AtMem"' in html
    assert 'id="memoryChatToggle"' in html
    assert 'aria-controls="memoryChatResult memoryChatForm memoryChatDockMeta"' in html
    assert 'dock.classList.toggle("collapsed")' in html
    assert 'collapsed?"Open memory assistant":"Hide memory assistant"' in html
    assert 'resultPanel.hidden=false' in html
    assert 'id="navSettings"' in html
    assert 'function activateSettings()' in html
    assert 'showView("settings")' in html
    assert '$("intelligenceConfig").open=false' in html
    assert 'pair[1]==="settings"' in html
    assert '"activitydate"' in html
    assert '"activityclock"' in html
    assert 'csrf=(await get("/api/session")).csrf_token;return post(path,body,true)' in html
    assert "Dashboard session expired. Refresh this page and try again." in html


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
    assert result["candidate_set_id"].startswith("cset_")
    assert result["preparation_id"].startswith("prep_")
    assert "semantic" in result["retrieval"]["signals"]


def test_control_prepare_rejects_a_candidate_set_invalidated_during_ranking(
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
        record = memory.remember("local-user", "My preferred editor is Neovim.")["records"][0]
    finally:
        memory.close()
    manager.transition(ControlMode.ACTIVE)
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {"expanded_queries": [query], "content_received": False},
    )

    def mutate_after_authorization(self, query, candidates):
        del self, query
        changed = Memory(memory_path)
        try:
            changed.forget_record("local-user", record["id"])
        finally:
            changed.close()
        return {
            "ranked_record_ids": [record["id"]],
            "companion": {"available": True, "fallback": False},
        }

    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.query",
        mutate_after_authorization,
    )
    import pytest

    with pytest.raises(ValueError, match="invalidated by a memory change"):
        manager.prepare("Which editor do I prefer?")


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
