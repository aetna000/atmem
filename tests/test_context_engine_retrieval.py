from __future__ import annotations

from atmem.context_engine.formation import (
    FormationManager, SourceEpisode, SourcePart, _sentence_ranges, _view_kinds,
)
from atmem.context_engine.planner import DeterministicPlanner
from atmem.context_engine.retrieval import (
    DeterministicRetriever, RetrievedCandidate, RetrievalResult, _fts_terms,
    _option_fields,
)
from atmem.context_engine.sufficiency import decide_sufficiency
from atmem.context_engine.packing import derive_action_constraints, pack_context
from atmem.context_engine.service import AuthorizedManifest, StoredContextEngine
from atmem.context_engine.contracts import ContextRequestV3
from atmem.contracts.models import AuthorityScope, RetrievalBudget
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


def test_structured_json_ranges_are_bounded_at_escaped_line_breaks() -> None:
    content = b'{"tree":"' + (b"Problem field value\\n" * 800) + b'"}'

    spans = _sentence_ranges(content)

    assert len(spans) > 1
    assert max(end - start for start, end in spans) <= 4_096
    assert b"".join(content[start:end] for start, end in spans) == content


def test_trajectory_action_and_state_json_form_procedure_and_transition_views() -> None:
    action_batch = '{"action_offset":0,"actions":[{"name":"click"}]}'
    state = '{"state_index":4,"action":{"name":"click"},"text":"Saved"}'

    assert "procedure" in _view_kinds(action_batch, "text")
    assert "transition" in _view_kinds(state, "text")


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


def test_planner_routes_workflow_action_count_as_ordered_steps() -> None:
    plan = DeterministicPlanner().plan(
        "I am using our shopping admin. I would like to notify a user to reorder "
        "for a pending order. I have entered its detail page. According to our "
        "usual workflow, with the action space below, how many more actions do "
        "I need to perform?\n\n"
        "Action Space: click(bid: str), fill(bid: str, value: str)\n\n"
        "Your final answer should be an English number."
    )

    assert len(plan.obligations) == 1
    assert plan.obligations[0].kind == "ordered_steps"
    assert plan.obligations[0].entity is None
    assert any(
        "notify a user to reorder" in query.casefold()
        for query in plan.pool_queries["procedure"]
    )
    assert plan.pool_queries["procedure"]
    assert all("click(bid" not in query for query in plan.pool_queries["procedure"])


def test_planner_does_not_misroute_a_named_change_request_as_a_transition() -> None:
    plan = DeterministicPlanner().plan(
        "Among these five forms (change request/problem/incident/hardware/user), "
        "which page integrates with Outlook calendar?"
    )

    assert all(item.kind != "before_action_after" for item in plan.obligations)
    queries = {query.casefold() for query in plan.pool_queries["raw_state"]}
    assert queries >= {
        "outlook calendar change request", "outlook calendar problem",
        "outlook calendar incident", "outlook calendar hardware",
        "outlook calendar user",
    }


def test_planner_decomposes_multiple_choice_fields_into_targeted_queries() -> None:
    plan = DeterministicPlanner().plan(
        "Which option contains only fields present on the Problem table?\n"
        "A. Problem Statement, Description, Category\n"
        "B. Subcategory, Assignment Group, State"
    )

    queries = {item.casefold() for item in plan.pool_queries["raw_state"]}
    assert "problem table subcategory" in queries
    assert "problem table assignment group" in queries
    assert "problem table state" in queries


def test_sufficient_decision_requires_only_obligation_grounding_units() -> None:
    plan = DeterministicPlanner().plan("Which port does audit use?")
    grounded = RetrievedCandidate(
        unit_id="grounded", kind="fact", source_id="source-1", part_id="text",
        start=0, end=18, text="Audit uses port 7443.", score=2.0,
        matched_obligation_ids=("need-1",),
    )
    neighbor = RetrievedCandidate(
        unit_id="neighbor", kind="raw_state", source_id="source-1", part_id="text",
        start=19, end=48, text="The service also emits metrics.", score=1.0,
        matched_obligation_ids=(),
    )
    result = RetrievalResult(
        candidates=(grounded, neighbor), searched_pools=("fact", "raw_state"),
        scanned_units=2, exhausted=False,
    )

    decision = decide_sufficiency(plan, result)

    assert decision.status == "sufficient"
    assert decision.evidence_unit_ids == ("grounded",)


def test_stored_engine_selects_only_evidence_that_fits_the_canonical_budget() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode_id, text in (
            ("answer", "Audit uses port 7443."),
            ("noise", "Operators must review unrelated diagnostics " + "x" * 1000),
        ):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode_id, scope=SCOPE,
                parts=(SourcePart("text", 0, "text", "text/plain", text.encode()),),
            ))
            manager.form_source(source, generation, range_granularity="sentence")
        request = ContextRequestV3(
            context_id="context-1", request_id="request-1", scope=SCOPE,
            query="Which port does audit use?", profile_id="context-fast",
            mode="active", generation=0,
            budget=RetrievalBudget(
                candidates_per_channel=2, total_candidates=2, context_bytes=160,
            ),
        )
        unit_ids = tuple(
            str(row["unit_id"])
            for row in store._conn.execute(
                "SELECT unit_id FROM context_evidence_units WHERE generation_id=?",
                (generation,),
            ).fetchall()
        )
        selection = StoredContextEngine(store, generation_id=generation).select(
            request,
            AuthorizedManifest(
                request_id=request.request_id, scope=SCOPE, generation=0,
                authorized_unit_ids=unit_ids, authority_sha256="sha256:test",
                all_generation_units_authorized=True,
            ),
        )

        assert selection.status == "sufficient"
        assert len(selection.selected_unit_ids) == 1
        assert selection.selected_unit_ids == selection.sufficiency.evidence_unit_ids
        assert selection.action_constraints == ()
    finally:
        store.close()


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


def test_withheld_range_can_name_query_need_without_exposing_removed_value() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source = manager.retain_source(SourceEpisode(
            episode_id="vendor-choice", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"Honeycomb was selected for end-to-end request tracing. "
                b"The team moved on to unrelated launch planning.",
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
        query = "Name the tracing vendor selected for end-to-end requests."
        plan = DeterministicPlanner().plan(query)
        result = DeterministicRetriever(store).retrieve(
            generation_id=generation, query=query, plan=plan, max_sources=8,
        )
        decision = decide_sufficiency(plan, result)
        assert result.withheld_obligation_ids == ("need-1",)
        assert decision.status == "partial"
        assert all("Honeycomb" not in item.text for item in result.candidates)
        assert all("Honeycomb" not in item.relation_or_action for item in plan.obligations)
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


def test_fts_terms_normalize_common_workflow_inflections() -> None:
    assert _fts_terms("Creating problems, requests, fields, actions and steps") == (
        "create", "problem", "request", "field", "action", "step",
    )


def test_option_fields_are_extracted_without_answer_labels() -> None:
    assert _option_fields(
        "Which option?\nA. Subcategory, Assignment Group\nB. Impact/Priority/Urgency"
    ) == (
        "Subcategory", "Assignment Group", "Impact", "Priority", "Urgency",
    )


def test_planner_adds_compact_create_workflow_facet() -> None:
    plan = DeterministicPlanner().plan(
        "Which option applies on the Problem table when navigating and "
        "creating problem requests?\n\n"
        "A. State, Assignment Group"
    )
    assert "create problem" in plan.pool_queries["raw_state"]
    assert "State" in plan.pool_queries["raw_state"]
    assert plan.pool_queries["raw_state"].index("State") < plan.pool_queries[
        "raw_state"
    ].index("Problem table State")


def test_planner_keeps_alternative_focus_when_integration_is_misspelled() -> None:
    plan = DeterministicPlanner().plan(
        "Among these forms (change request/problem/incident/hardware/user), "
        "which page intergrates with Outlook calendar?"
    )

    assert "Outlook calendar" in plan.pool_queries["raw_state"]
    assert "Outlook calendar user" in plan.pool_queries["raw_state"]


def test_single_need_packing_keeps_grounding_head_first_and_bounded() -> None:
    plan = DeterministicPlanner().plan("How many actions remain in this workflow?")
    obligation_id = plan.obligations[0].obligation_id
    required = RetrievedCandidate(
        unit_id="required", kind="procedure", source_id="z-source",
        part_id="actions", start=0, end=32,
        text="Fill Comment; check Notify; click Submit.", score=10.0,
        matched_obligation_ids=(obligation_id,),
    )
    noise = RetrievedCandidate(
        unit_id="noise", kind="raw_state", source_id="a-source",
        part_id="state", start=0, end=20_000, text="noise " * 4_000,
        score=1.0, matched_obligation_ids=(),
    )
    result = RetrievalResult(
        candidates=(required, noise), searched_pools=("procedure",),
        scanned_units=2, exhausted=False,
    )
    decision = decide_sufficiency(plan, result)

    packed = pack_context(plan, result, decision, max_bytes=32_768)

    assert packed.context.startswith("[source=z-source")
    assert "Fill Comment" in packed.context
    assert "noise" not in packed.context
    assert len(packed.context.encode()) <= 16_384


def test_option_packing_covers_named_fields_before_redundant_states() -> None:
    plan = DeterministicPlanner().plan(
        "Which option contains fields present on the Problem table?\n\n"
        "A. Description, State\nB. Subcategory, Assignment Group"
    )
    obligation_id = plan.obligations[0].obligation_id
    head = RetrievedCandidate(
        unit_id="head", kind="raw_state", source_id="workflow",
        part_id="metadata", start=0, end=20,
        text="Create a new problem.", score=10.0,
        matched_obligation_ids=(obligation_id,),
    )
    redundant = RetrievedCandidate(
        unit_id="redundant", kind="raw_state", source_id="workflow",
        part_id="state-1", start=0, end=8_000,
        text=("Description State " * 400), score=9.0,
        matched_obligation_ids=(),
    )
    complementary = RetrievedCandidate(
        unit_id="complementary", kind="raw_state", source_id="other",
        part_id="state-2", start=0, end=100,
        text="Problems table: Subcategory Assignment Group State", score=5.0,
        matched_obligation_ids=(),
    )
    wrong_surface = RetrievedCandidate(
        unit_id="incident-fields", kind="raw_state", source_id="incident",
        part_id="state-3", start=0, end=100,
        text="Incident fields: Description State Subcategory Assignment Group",
        score=20.0, matched_obligation_ids=(),
    )
    result = RetrievalResult(
        candidates=(head, wrong_surface, redundant, complementary),
        searched_pools=("raw_state",), scanned_units=4, exhausted=False,
    )
    decision = decide_sufficiency(plan, result)

    packed = pack_context(plan, result, decision, max_bytes=16_384)

    assert packed.included_unit_ids[:2] == ("head", "complementary")


def test_option_packing_prefers_complementary_evidence_per_byte() -> None:
    plan = DeterministicPlanner().plan(
        "Which option contains fields present on the Problem table?\n\n"
        "A. Subcategory, Assignment Group, State"
    )
    obligation_id = plan.obligations[0].obligation_id
    head = RetrievedCandidate(
        unit_id="head", kind="raw_state", source_id="workflow",
        part_id="metadata", start=0, end=20,
        text="Create a new problem.", score=10.0,
        matched_obligation_ids=(obligation_id,),
    )
    large = RetrievedCandidate(
        unit_id="large", kind="raw_state", source_id="workflow",
        part_id="state", start=0, end=12_000,
        text=("Problem table filler " * 500) + " Subcategory Assignment Group State",
        score=9.0, matched_obligation_ids=(),
    )
    exact = [
        RetrievedCandidate(
            unit_id=f"exact-{index}", kind="raw_state", source_id=f"source-{index}",
            part_id="state", start=0, end=80,
            text=f"Problem table: {field}", score=5.0,
            matched_obligation_ids=(),
        )
        for index, field in enumerate(("Subcategory", "Assignment Group", "State"))
    ]
    result = RetrievalResult(
        candidates=(head, large, *exact), searched_pools=("raw_state",),
        scanned_units=5, exhausted=False,
    )
    decision = decide_sufficiency(plan, result)

    packed = pack_context(plan, result, decision, max_bytes=16_384)

    assert packed.included_unit_ids[0] == "head"
    assert set(packed.included_unit_ids[1:4]) == {
        "exact-0", "exact-1", "exact-2",
    }


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
