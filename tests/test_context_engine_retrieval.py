from __future__ import annotations

from atmem.context_engine.formation import (
    FormationManager, SourceEpisode, SourcePart, _sentence_ranges,
)
from atmem.context_engine.planner import DeterministicPlanner
from atmem.context_engine.retrieval import DeterministicRetriever, _fts_terms
from atmem.context_engine.sufficiency import decide_sufficiency
from atmem.context_engine.packing import derive_action_constraints, pack_context
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore


SCOPE = AuthorityScope(subject_id="person-1", agent_id="agent-a", workspace_id="work-1")


def test_bounded_clause_ranges_isolate_compound_facts_without_splitting_lists() -> None:
    compound = (
        b"Evergreen follow-up was prepared, and an Acme prompt pointed support "
        b"to the clock-skew docs."
    )
    spans = _sentence_ranges(compound)
    assert [compound[start:end] for start, end in spans] == [
        b"Evergreen follow-up was prepared,",
        b"and an Acme prompt pointed support to the clock-skew docs.",
    ]
    metric = (
        b"OAuth cancellation fell from 41 to 14 and support tickets fell from "
        b"12 to 2, so I am treating that as validated activation work."
    )
    assert len(_sentence_ranges(metric)) == 3
    palette = b"The palette is ultramarine, burnt sienna, and yellow ochre."
    assert _sentence_ranges(palette) == ((0, len(palette)),)


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


def test_planner_splits_explicit_independent_memory_requirements() -> None:
    plan = DeterministicPlanner().plan(
        "Send Kara written notice ending the contractor arrangement on the earliest "
        "permitted date, and include the required external-email copy recipient."
    )
    assert len(plan.obligations) == 2
    assert "earliest permitted date" in plan.obligations[0].relation_or_action
    assert "copy recipient" in plan.obligations[1].relation_or_action
    assert plan.obligations[0].kind == "condition_action"
    assert plan.obligations[1].kind == "condition_action"
    assert plan.pool_queries["raw_state"][1:] == tuple(
        item.relation_or_action for item in plan.obligations
    )


def test_each_planned_requirement_needs_independently_grounded_evidence() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode_id, text in (
            ("notice", "Contract termination notice must be written at least 30 days ahead."),
            ("copy", "Outside email threads must copy Sarah Kim from the start."),
        ):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode_id, scope=SCOPE,
                parts=(SourcePart("text", 0, "text", "text/plain", text.encode()),),
            ))
            manager.form_source(source, generation, range_granularity="sentence")
        query = (
            "Send Kara written notice ending the contractor arrangement on the earliest "
            "permitted date, and include the required outside email copy recipient."
        )
        plan = DeterministicPlanner().plan(query)
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query=query, plan=plan, max_sources=8,
        )
        assert decide_sufficiency(plan, result).status == "sufficient"
        assert {
            obligation_id
            for item in result.candidates
            for obligation_id in item.matched_obligation_ids
        } == {"need-1", "need-2"}

        manager.delete_source(next(
            item.source_id for item in result.candidates
            if "Sarah Kim" in item.text
        ))
        # Rebuild a generation from the remaining immutable source so the
        # lifecycle failure is not confused with a missing requirement.
        replacement = manager.begin_generation(SCOPE, profile_id="context-fast")
        remaining = store._conn.execute(
            "SELECT source_id FROM context_source_episodes"
        ).fetchall()
        for row in remaining:
            manager.form_source(str(row["source_id"]), replacement, range_granularity="sentence")
        partial = DeterministicRetriever(store).retrieve(
            generation_id=replacement, query=query, plan=plan, max_sources=8,
        )
        decision = decide_sufficiency(plan, partial)
        assert decision.status == "partial"
        assert decision.missing_obligation_ids == ("need-2",)
    finally:
        store.close()


def test_withheld_range_in_matched_episode_keeps_obligation_partial() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source = manager.retain_source(SourceEpisode(
            episode_id="closeout", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"The final sample contains 61 requests. "
                b"Send the final intake closeout to Hema.",
            ),),
        ))
        manager.form_source(source, generation, range_granularity="sentence")
        hidden = store._conn.execute(
            """SELECT ur.range_id, u.unit_id
               FROM context_evidence_units u
               JOIN context_unit_ranges ur USING(generation_id, unit_id)
               JOIN context_source_ranges r USING(range_id)
               WHERE u.generation_id=? AND r.start_offset=0""",
            (generation,),
        ).fetchone()
        with store.transaction():
            store._conn.execute(
                "UPDATE context_evidence_units SET lifecycle='deleted' "
                "WHERE generation_id=? AND unit_id=?",
                (generation, hidden["unit_id"]),
            )
            store._conn.execute(
                "UPDATE context_coverage SET disposition='withheld', "
                "reason_code='observation_forgotten' "
                "WHERE generation_id=? AND range_id=?",
                (generation, hidden["range_id"]),
            )
            store.remove_context_range_index(generation, str(hidden["range_id"]))
        query = "What should the final intake closeout sent to Hema contain?"
        plan = DeterministicPlanner().plan(query)
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query=query, plan=plan, max_sources=8,
        )
        decision = decide_sufficiency(plan, result)
        assert result.withheld_obligation_ids == ("need-1",)
        assert decision.status == "partial"
        assert decision.reason_codes == ("source_episode_incomplete",)
    finally:
        store.close()


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
        assert result.scanned_units <= 200
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


def test_rule_evidence_yields_grounded_non_executing_action_constraint() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source = manager.retain_source(SourceEpisode(
            episode_id="rule", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"Release notices must be sent to #eng-releases, never #eng-all.",
            ),),
        ))
        manager.form_source(source, generation)
        query = "Where must release notices be sent?"
        plan = DeterministicPlanner().plan(query)
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query=query, plan=plan, max_sources=2,
        )
        decision = decide_sufficiency(plan, result)
        constraints = derive_action_constraints(query, result, decision)
        assert constraints[0].target == "#eng-releases"
        assert constraints[0].prohibited_action == "use #eng-all"
        assert constraints[0].source_ids == (source,)
    finally:
        store.close()


def test_compact_multi_view_retrieval_emits_each_evidence_id_once() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode_id, text in (
            ("compact-rule", b"Release notices must be sent to eng-releases, never eng-all."),
            ("compact-timezone", b"The release audit timezone is UTC."),
        ):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode_id, scope=SCOPE,
                parts=(SourcePart("text", 0, "text", "text/plain", text),),
            ))
            manager.form_source(source, generation, range_granularity="sentence")
        query = "Where must release notices be sent and which timezone is used?"
        plan = DeterministicPlanner().plan(query)

        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query=query, plan=plan, max_sources=8,
        )

        ids = [item.unit_id for item in result.candidates]
        assert len(ids) == len(set(ids))
        assert len(ids) == 2
        assert any("eng-releases" in item.text for item in result.candidates)
        assert any("UTC" in item.text for item in result.candidates)
    finally:
        store.close()


def test_anchor_date_is_not_treated_as_query_evidence() -> None:
    assert _fts_terms("[2028-01-01] Find the approved release room") == (
        "approved", "release", "room",
    )


def test_retrieval_keeps_source_breadth_and_adjacent_exact_evidence() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        target = manager.retain_source(SourceEpisode(
            episode_id="target", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"The approved tracing vendor is Honeycomb. "
                b"Use it for end-to-end request instrumentation.",
            ),),
        ))
        manager.form_source(target, generation, range_granularity="sentence")
        for index in range(40):
            source = manager.retain_source(SourceEpisode(
                episode_id=f"noise-{index}", scope=SCOPE,
                parts=(SourcePart(
                    "text", 0, "text", "text/plain",
                    f"Request instrumentation review note {index}.".encode(),
                ),),
            ))
            manager.form_source(source, generation, range_granularity="sentence")
        plan = DeterministicPlanner().plan(
            "Which tracing vendor should request instrumentation target?"
        )
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation,
            query="Which tracing vendor should request instrumentation target?",
            plan=plan,
            max_sources=32,
        )
        assert any("Honeycomb" in item.text for item in result.candidates)
        assert any("end-to-end" in item.text for item in result.candidates)
        assert len(result.candidates) <= 32
    finally:
        store.close()


def test_sufficiency_can_report_stale_policy_withheld_and_bounded_not_found() -> None:
    plan = DeterministicPlanner().plan("Where is the release room?")
    from atmem.context_engine.retrieval import RetrievalResult
    empty = RetrievalResult((), ("fact",), 0, False)
    assert decide_sufficiency(plan, empty).status == "not_found_within_budget"
    assert decide_sufficiency(plan, empty, lifecycle_stale=True).status == "stale"
    withheld = decide_sufficiency(plan, empty, policy_withheld=True)
    assert withheld.status == "withheld_by_policy"
    assert withheld.evidence_unit_ids == ()
