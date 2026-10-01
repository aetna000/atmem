from __future__ import annotations

from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.context_engine.planner import DeterministicPlanner
from atmem.context_engine.retrieval import DeterministicRetriever
from atmem.context_engine.sufficiency import decide_sufficiency
from atmem.context_engine.packing import pack_context
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore


SCOPE = AuthorityScope(subject_id="person-1", agent_id="agent-a", workspace_id="work-1")


def test_planner_declares_distinct_comparison_heads_and_preserves_query() -> None:
    plan = DeterministicPlanner().plan("Compare North and South export formats")
    assert plan.deterministic_fallback is True
    assert [item.kind for item in plan.obligations] == ["comparison_side", "comparison_side"]
    assert [item.entity for item in plan.obligations] == ["North", "South"]
    assert plan.pool_queries["fact"] == ("Compare North and South export formats",)


def test_planner_routes_procedure_transition_and_premise_needs() -> None:
    planner = DeterministicPlanner()
    assert planner.plan("How should the archive be restored?").obligations[0].kind == "ordered_steps"
    assert planner.plan("What changed when the worker was repaired?").obligations[0].kind == "before_action_after"
    assert planner.plan("Which cable is required for the wireless-only sensor?").obligations[0].kind == "premise_check"


def test_independent_pool_retrieval_reserves_both_comparison_sides() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode_id, text in (
            ("north", "North exports audit records as JSON Lines."),
            ("south", "South exports audit records as Parquet."),
            ("noise", "The cafeteria serves tomato soup on Fridays."),
        ):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode_id, scope=SCOPE,
                parts=(SourcePart("text", 0, "text", "text/plain", text.encode()),),
            ))
            manager.form_source(source, generation)
        plan = DeterministicPlanner().plan("Compare North and South export formats")
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query="Compare North and South export formats",
            plan=plan, max_sources=2,
        )
        assert len(result.candidates) == 2
        assert {item.matched_obligation_ids[0] for item in result.candidates} == {
            plan.obligations[0].obligation_id, plan.obligations[1].obligation_id,
        }
        assert all("cafeteria" not in item.text.casefold() for item in result.candidates)
        assert result.scanned_units <= 24
    finally:
        store.close()


def test_negative_premise_retrieval_uses_premise_pool() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source = manager.retain_source(SourceEpisode(
            episode_id="sensor", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"The sensor has no USB connector and communicates only over LoRaWAN.",
            ),),
        ))
        manager.form_source(source, generation)
        plan = DeterministicPlanner().plan(
            "Which USB cable is required for the wireless-only sensor?"
        )
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation,
            query="Which USB cable is required for the wireless-only sensor?",
            plan=plan,
            max_sources=2,
        )
        assert result.candidates
        assert result.candidates[0].kind == "premise"
        assert "no USB connector" in result.candidates[0].text
        decision = decide_sufficiency(plan, result)
        assert decision.status == "contradicted"
        assert decision.missing_obligation_ids == ()
    finally:
        store.close()


def test_packing_preserves_obligation_order_and_one_total_byte_budget() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode_id, text in (
            ("north", "North exports audit records as JSON Lines."),
            ("south", "South exports audit records as Parquet."),
        ):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode_id, scope=SCOPE,
                parts=(SourcePart("text", 0, "text", "text/plain", text.encode()),),
            ))
            manager.form_source(source, generation)
        plan = DeterministicPlanner().plan("Compare North and South export formats")
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query="Compare North and South export formats",
            plan=plan, max_sources=2,
        )
        decision = decide_sufficiency(plan, result)
        packed = pack_context(plan, result, decision, max_bytes=1024)
        assert decision.status == "sufficient"
        assert packed.context.index("North") < packed.context.index("South")
        assert len(packed.context.encode()) <= 1024
        bounded = pack_context(plan, result, decision, max_bytes=20)
        assert bounded.complete is False
        assert bounded.excluded_unit_ids
    finally:
        store.close()


def test_missing_comparison_side_is_partial_not_false_sufficient() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source = manager.retain_source(SourceEpisode(
            episode_id="north", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"North exports audit records as JSON Lines.",
            ),),
        ))
        manager.form_source(source, generation)
        plan = DeterministicPlanner().plan("Compare North and South export formats")
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query="Compare North and South export formats",
            plan=plan, max_sources=2,
        )
        decision = decide_sufficiency(plan, result)
        assert decision.status == "partial"
        assert decision.missing_obligation_ids == ("comparison-2",)
    finally:
        store.close()


def test_cache_key_binds_generation_authority_plan_and_revision() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source = manager.retain_source(SourceEpisode(
            episode_id="cache", scope=SCOPE,
            parts=(SourcePart("text", 0, "text", "text/plain", b"Audit uses port 7412."),),
        ))
        manager.form_source(source, generation)
        plan = DeterministicPlanner().plan("Which port does audit use?")
        retriever = DeterministicRetriever(store)
        first = retriever.retrieve(
            generation_id=generation, query="Which port does audit use?",
            plan=plan, max_sources=2,
        )
        assert retriever.retrieve(
            generation_id=generation, query="Which port does audit use?",
            plan=plan, max_sources=2,
        ) is first
        assert retriever.cache_hits == 1
        manager.delete_source(source)
        import pytest
        with pytest.raises(RuntimeError, match="unavailable"):
            retriever.retrieve(
                generation_id=generation, query="Which port does audit use?",
                plan=plan, max_sources=2,
            )
    finally:
        store.close()
