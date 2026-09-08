from __future__ import annotations

from atmem import Memory
from atmem.control import ControlMode, ControlPlaneManager
from atmem.retrieve import SupportClass, decide_retrieval
from jsonschema_mini import as_json_document, load, validate


def _candidate(record_id: str, content: str, **signals):
    return {
        "record_id": record_id,
        "content": content,
        "score": signals.pop("score", 0.8),
        "signals": signals,
    }


def test_preference_paraphrase_is_direct_support() -> None:
    decision = decide_retrieval(
        "what is my favourite lunch?",
        [_candidate("burger", "JT likes burgers.", fact_key="food preferred lunch")],
    )
    assert decision.support_class is SupportClass.DIRECT
    assert decision.ranked_record_ids == ("burger",)


def test_single_edit_typo_is_direct_support_without_nearest_memory_fallback() -> None:
    decision = decide_retrieval(
        "pizzaa",
        [_candidate("pizza", "JT likes pizza.", fact_key="food preference")],
    )

    assert decision.support_class is SupportClass.DIRECT
    assert decision.ranked_record_ids == ("pizza",)
    assert decision.candidates[0].signals["typo_tolerant_support"] == 1.0


def test_two_edit_long_typo_recalls_burger_but_not_unrelated_memory() -> None:
    decision = decide_retrieval(
        "burggger",
        [
            _candidate("burger", "JT likes burgers."),
            _candidate("family", "JT has a 7-year-old daughter."),
        ],
    )

    assert decision.ranked_record_ids == ("burger",)
    assert decision.candidates[0].signals["typo_tolerant_support"] == 1.0


def test_dashboard_candidate_generation_tolerates_a_single_edit_typo(
    tmp_path, monkeypatch
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
        memory.remember(
            "local-user",
            "JT likes pizza.",
            interpreted_fact="JT likes pizza.",
            interpreted_fact_key="food preference",
        )
        memory.remember(
            "local-user",
            "JT has a 7-year-old daughter.",
            interpreted_fact="JT has a 7-year-old daughter.",
            interpreted_fact_key="family",
        )
    finally:
        memory.close()
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.health",
        lambda self: {"available": False, "reason": "test fallback"},
    )

    result = manager.memory_query("pizzaa")

    assert [row["content"] for row in result["used_memories"]] == ["JT likes pizza."]
    assert result["retrieval"]["decision"]["support_class"] == "direct_support"


def test_unrelated_personal_memory_is_withheld() -> None:
    decision = decide_retrieval(
        "what cars are available in Australia?",
        [
            _candidate("burger", "JT likes burgers.", fact_key="food preference"),
            _candidate("appearance", "Javad is bald."),
        ],
    )
    assert decision.support_class is SupportClass.NONE
    assert decision.ranked_record_ids == ()
    assert "no_relevance_signal" in decision.reason_codes


def test_diagnostic_hash_similarity_cannot_create_support() -> None:
    decision = decide_retrieval(
        "what cars are available in Australia?",
        [
            _candidate(
                "burger",
                "JT likes burgers.",
                semantic_similarity=0.99,
                semantic_provider="hashing-diagnostic",
            )
        ],
    )
    assert decision.support_class is SupportClass.NONE
    assert "diagnostic_semantic_ignored" in decision.candidates[0].reason_codes


def test_production_semantic_signal_can_support_a_paraphrase() -> None:
    decision = decide_retrieval(
        "where should we eat?",
        [
            _candidate(
                "burger",
                "JT's favourite lunch is burgers.",
                semantic_similarity=0.82,
                semantic_provider="sentence-transformers",
            )
        ],
    )
    assert decision.support_class is SupportClass.DIRECT
    assert decision.ranked_record_ids == ("burger",)


def test_topical_non_answer_is_background_and_withheld_by_default() -> None:
    decision = decide_retrieval(
        "transport safety innovation efficiency",
        [_candidate("transport", "A transport preference was recorded.")],
    )
    assert decision.support_class is SupportClass.BACKGROUND
    assert decision.ranked_record_ids == ()

    permitted = decide_retrieval(
        "transport safety innovation efficiency",
        [_candidate("transport", "A transport preference was recorded.")],
        allow_background=True,
    )
    assert permitted.support_class is SupportClass.BACKGROUND
    assert permitted.ranked_record_ids == ("transport",)
    assert permitted.reason_codes == ("background_context_permitted",)


def test_retrieval_decision_matches_the_published_contract() -> None:
    decision = decide_retrieval(
        "what is my favourite lunch?",
        [_candidate("burger", "JT likes burgers.", fact_key="food preference")],
    )
    validate(as_json_document(decision.to_dict()), load("retrieval-decision.json"))


def test_dashboard_and_control_withhold_unrelated_personal_memory(
    tmp_path, monkeypatch
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
        memory.remember(
            "local-user",
            "JT likes burgers.",
            interpreted_fact="JT likes burgers.",
            interpreted_fact_key="food preference",
        )
        memory.remember("local-user", "Javad is bald.")
    finally:
        memory.close()
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.health",
        lambda self: {"available": False, "reason": "test fallback"},
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {
            "expanded_queries": [query, "cars vehicles automobiles Australia"],
            "content_received": False,
        },
    )

    dashboard = manager.memory_query("what cars are available in Australia?")
    assert dashboard["used_memories"] == []
    assert dashboard["retrieval"]["decision"]["support_class"] == "no_useful_memory"

    manager.transition(ControlMode.ACTIVE)
    prepared = manager.prepare("what cars are available in Australia?")
    assert prepared["inject"] is False
    assert prepared["candidate_ids"] == []
    assert prepared["retrieval"]["decision"]["support_class"] == "no_useful_memory"


def test_short_unrelated_query_does_not_return_nearest_personal_memory() -> None:
    decision = decide_retrieval(
        "Royal",
        [
            _candidate(
                "family",
                "JT has a wife and a 7-year-old daughter.",
                score=0.512007,
                semantic_similarity=0.478743,
            )
        ],
    )

    assert decision.ranked_record_ids == ()
    assert decision.support_class.value == "no_useful_memory"


def test_session_identifier_routes_to_scoped_evidence_not_memory(
    tmp_path, monkeypatch
) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=tmp_path / "memory.db",
    )
    session_id = "d77c5a86-21dd-452e-bdfd-76116485df7a"
    manager.record_blackbox_event(
        event_type="turn.input",
        run_id="run-one",
        session_id=session_id,
        turn_id="turn-one",
        subject_id="local-user",
        payload={"prompt_sha256": "0" * 64, "prompt_chars": 20},
    )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-one",
        session_id=session_id,
        turn_id="turn-one",
        subject_id="local-user",
        payload={"success": True},
    )
    monkeypatch.setattr(
        manager,
        "_hybrid_memory_candidates",
        lambda *args, **kwargs: pytest.fail("identifier must not enter memory retrieval"),
    )

    result = manager.memory_query(session_id)

    assert result["query_kind"] == "execution_identifier"
    assert result["used_memories"] == []
    assert result["candidate_count"] == 0
    assert result["companion"]["skipped"] is True
    assert result["investigation"]["matches"][0]["run_id"] == "run-one"


def test_unknown_session_identifier_does_not_fall_through_to_nearest_memory(
    tmp_path, monkeypatch
) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=tmp_path / "memory.db",
    )
    monkeypatch.setattr(
        manager,
        "_hybrid_memory_candidates",
        lambda *args, **kwargs: pytest.fail("identifier must not enter memory retrieval"),
    )

    result = manager.memory_query("00000000-0000-4000-8000-000000000000")

    assert result["investigation"]["matches"] == []
    assert "couldn't find scoped agent evidence" in result["answer"]
