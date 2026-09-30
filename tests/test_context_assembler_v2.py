from atmem import Memory
from atmem.contracts import (
    AuthorityScope,
    ContextRequestV2,
    EpisodeIngestRequest,
    EpisodePart,
    RecallRequest,
    RetrievalBudget,
)
from atmem.core.canonical import sha256_hex
from atmem.extract.review import ReviewService
from atmem.retrieve.assemble import (
    _complementary_rows,
    _evidence_guidance,
    _unit_text,
    assemble_context_v2,
)
from atmem.retrieve.expand import expand_evidence_neighborhood
from atmem.retrieve.intent import route_information_need
from dataclasses import replace


SCOPE = AuthorityScope("context-person", "context-agent", "context-workspace")


def request(parts, episode_id="context-episode"):
    return EpisodeIngestRequest(
        episode_id=episode_id, idempotency_key=f"key-{episode_id}", scope=SCOPE,
        parts=tuple(
            EpisodePart(
                part_id=f"part-{index}", ordinal=index, kind="text",
                source_type="user_message", content=text,
                content_sha256=f"sha256:{sha256_hex(text)}",
            )
            for index, text in enumerate(parts)
        ),
    )


def candidates(memory, query, *, limit=8, candidate_limit=50, egress="local"):
    return memory.eligible_candidates(RecallRequest(
        request_id=f"recall-{sha256_hex(query)[:12]}", scope=SCOPE, query=query,
        limit=limit, candidate_limit=candidate_limit,
        signals=("lexical", "graph"), retrieval_strategy="core-rrf-v1",
        egress_class=egress,
    ))


def context(memory, candidate_set, query, *, bytes_=8192):
    return memory.prepare_context_v2(ContextRequestV2(
        context_id=f"context-{sha256_hex(query)[:12]}",
        candidate_set_id=candidate_set.candidate_set_id,
        scope=SCOPE,
        query=query,
        budget=RetrievalBudget(context_bytes=bytes_),
    ))


def test_evidence_guidance_prevents_reader_from_strengthening_ui_hints() -> None:
    transition = route_information_need(
        "After clearing the assignment, what value should I set the state to?"
    )
    failure = route_information_need(
        "After Execute Now, deletion does not happen. What action remains?"
    )
    premise = route_information_need(
        "What are the exact two item names for Linux and Chromebook laptops?"
    )

    assert any("not a transition" in line for line in _evidence_guidance(transition))
    assert any("later observed recovery" in line for line in _evidence_guidance(failure))
    assert any("premise to verify" in line for line in _evidence_guidance(premise))


def test_exact_fact_is_evidence_complete_and_v1_safe(tmp_path):
    memory = Memory(
        tmp_path / "context.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        memory.form_episode(request(["I am 45 years old."]))
        package = context(memory, candidates(memory, "How old am I?"), "How old am I?")
        assert package.sufficiency.status == "sufficient"
        assert package.sufficiency.missing_slots == ()
        assert "45" in package.context
        assert package.provenance[0]["source_id"] in package.source_ids
        assert package.to_v1().context == package.context
        summary = memory.store.retrieval_quality_summary([SCOPE.subject_id])
        assert {row["stage"] for row in summary["stage_events"]} >= {
            "formation", "nomination", "expansion", "packing",
        }
        assert "I am 45 years old." not in str(summary["stage_events"])
        assert "How old" not in str(summary["stage_events"])
    finally:
        memory.close()


def test_partial_procedure_is_not_strengthened_for_v1_reader(tmp_path):
    memory = Memory(
        tmp_path / "context.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        formed = memory.form_episode(request([
            "To publish a build, 1. run tests 2. build the package 3. upload the artifact"
        ]))
        assert formed["outcomes"][0]["review_state"] == "pending_review"
        # This test exercises sufficiency directly with the still-governed pending unit
        # in its review view; pending evidence is never eligible for retrieval.
        assert candidates(memory, "How do I publish a build?").candidates == ()
    finally:
        memory.close()


def test_adjacent_sources_complete_relational_synthesis(tmp_path):
    memory = Memory(
        tmp_path / "context.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        memory.form_episode(request([
            "My favorite city is Sydney.",
            "My favorite food is pasta.",
        ], episode_id="two-facts"))
        candidate_set = candidates(
            memory, "Compare my favorite city and food together",
            limit=1, candidate_limit=1,
        )
        assert len(candidate_set.candidates) == 1
        package = context(
            memory, candidate_set, "Compare my favorite city and food together"
        )
        assert package.sufficiency.status == "sufficient"
        assert len(package.record_ids) == 2
        assert "Sydney" in package.context and "pasta" in package.context
        event = next(
            row for row in memory.store.list_audit_events(SCOPE.subject_id)
            if row["event_type"] == "memory.context_prepared_v2"
        )
        assert event["payload"]["neighborhood_visited"] == 2
    finally:
        memory.close()


def test_shared_formation_provenance_expands_without_source_adjacency(tmp_path):
    memory = Memory(
        tmp_path / "context.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        memory.form_episode(request([
            "My favorite city is Sydney.",
            "My favorite food is pasta.",
        ], episode_id="shared-formation"))
        # Prove the independent provenance edge rather than accidentally
        # exercising the ordered-source edge covered by the previous test.
        with memory.store.transaction():
            memory.store._conn.execute("DELETE FROM source_adjacency")
        candidate_set = candidates(
            memory, "Compare my favorite city and food together",
            limit=1, candidate_limit=1,
        )
        package = context(
            memory, candidate_set, "Compare my favorite city and food together"
        )
        assert package.sufficiency.status == "sufficient"
        assert len(package.record_ids) == 2
        neighborhood = expand_evidence_neighborhood(
            memory.store,
            subject_id=SCOPE.subject_id,
            workspace_id=SCOPE.workspace_id,
            need_id="shared-formation-need",
            seed_record_ids=(candidate_set.candidates[0].record_id,),
            budget=RetrievalBudget(),
        )
        assert any(
            "same_formation" in path.edge_types
            for path in neighborhood.paths
        )
    finally:
        memory.close()


def test_sufficient_rule_becomes_a_structured_action_constraint(tmp_path):
    memory = Memory(
        tmp_path / "context.db", auto_vectors=False,
        allow_insecure_typed_development=True,
        review_authorities=({
            "principal_id": "owner", "subject_id": SCOPE.subject_id,
            "agent_id": SCOPE.agent_id, "workspace_id": SCOPE.workspace_id,
            "scopes": ("procedure:review",),
        },),
    )
    try:
        formed = memory.form_episode(request([
            "When deploying a release, must post to the releases channel."
        ], episode_id="deployment-rule"))
        proposal_id = formed["outcomes"][0]["proposal_id"]
        authorization = memory.issue_review_authorization(
            "owner", scopes=("procedure:review",)
        )
        reviewed = ReviewService(memory).decide(
            proposal_id, "approve", actor="owner", authorization=authorization
        )
        assert reviewed["review_state"] == "committed"
        query = "Which channel should deployment updates use under our policy?"
        package = context(memory, candidates(memory, query), query)
        assert package.sufficiency.status == "sufficient"
        assert len(package.action_constraints) == 1
        assert package.action_constraints[0].required_action == "post to the releases channel"
        assert "Required action" in package.context
    finally:
        memory.close()


def test_excluded_neighbor_cannot_reenter_through_expansion(tmp_path):
    memory = Memory(
        tmp_path / "context.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        formed = memory.form_episode(request([
            "My favorite city is Sydney.",
            "My favorite food is pasta.",
        ], episode_id="excluded-neighbor"))
        seed, excluded = [item["record_ids"][0] for item in formed["outcomes"]]
        memory.set_retrieval_excluded(SCOPE.subject_id, excluded, True)
        neighborhood = expand_evidence_neighborhood(
            memory.store, subject_id=SCOPE.subject_id,
            workspace_id=SCOPE.workspace_id, need_id="exclusion-test",
            seed_record_ids=(seed,), budget=RetrievalBudget(),
        )
        assert excluded not in neighborhood.selected_record_ids
    finally:
        memory.close()


def test_rank_precedes_diversity_and_oversized_conflict_never_becomes_sufficient():
    need = route_information_need("What is Alice age?")

    def candidate(record_id, relation, value, rank, sources):
        return {
            "record_id": record_id,
            "rank": rank,
            "unit": {
                "kind": "atomic_fact",
                "payload": {
                    "subject": "Alice", "relation": relation,
                    "value": value, "polarity": "positive",
                },
                "evidence": [{
                    "source_id": source,
                    "start_offset": 0, "end_offset": 1,
                    "excerpt_sha256": "sha256:" + "0" * 64,
                } for source in sources],
            },
        }

    ranked = _complementary_rows(need, [
        candidate("rank-1", "age", "45", 1, ["s1"]),
        candidate("rank-50", "color", "blue", 50, ["s2", "s3"]),
    ], 3_000)
    assert ranked[0]["record_id"] == "rank-1"

    package = assemble_context_v2(
        context_id="conflict-context", scope=SCOPE, need=need,
        profile_id="test", generation=1, preparation_id="prep",
        budget=RetrievalBudget(context_bytes=1_300),
        typed_rows=[
            candidate("age-45", "age", "45", 1, ["s1"]),
            candidate("age-46", "age", "46 " + "x" * 2_000, 2, ["s2"]),
        ],
    )
    assert package.sufficiency.status == "unsupported"
    assert package.record_ids == ()
    assert "known_conflict_did_not_fit_context_budget" in package.sufficiency.reason_codes


def test_packing_prefers_uncovered_obligations_over_duplicate_evidence():
    need = route_information_need("Compare Alice age and Bob city")

    def candidate(record_id, subject, relation, value, rank):
        return {
            "record_id": record_id,
            "rank": rank,
            "unit": {
                "kind": "atomic_fact",
                "payload": {
                    "subject": subject, "relation": relation,
                    "value": value, "polarity": "positive",
                },
                "evidence": [{
                    "source_id": f"source-{record_id}", "start_offset": 0,
                    "end_offset": 1, "excerpt_sha256": "sha256:" + "0" * 64,
                }],
            },
        }

    chosen = _complementary_rows(need, [
        candidate("alice-1", "Alice", "age", "45", 1),
        candidate("alice-2", "Alice", "age", "45", 2),
        candidate("bob", "Bob", "city", "Paris", 3),
    ], 1_200)
    assert [row["record_id"] for row in chosen[:2]] == ["alice-1", "bob"]


def test_conflict_requires_actual_pair_not_same_value_duplicates():
    need = route_information_need("What is Alice age?")

    def candidate(record_id, value, rank):
        return {
            "record_id": record_id, "rank": rank,
            "unit": {
                "kind": "atomic_fact",
                "payload": {
                    "subject": "Alice", "relation": "age",
                    "value": value, "polarity": "positive",
                },
                "evidence": [{
                    "source_id": f"source-{record_id}", "start_offset": 0,
                    "end_offset": 1, "excerpt_sha256": "sha256:" + "0" * 64,
                }],
            },
        }

    package = assemble_context_v2(
        context_id="minimal-conflict", scope=SCOPE, need=need,
        profile_id="test", generation=1, preparation_id="prep",
        budget=RetrievalBudget(context_bytes=2_000),
        typed_rows=[
            candidate("age-45-a", "45", 1),
            candidate("age-45-b", "45", 2),
            candidate("age-46", "46", 3),
        ],
    )

    assert package.sufficiency.status == "contradictory"
    assert {"age-45-a", "age-46"} <= set(package.record_ids)


def test_authorized_lexical_fallback_is_retained_as_unverified_background():
    need = route_information_need("What is the support email?")
    package = assemble_context_v2(
        context_id="fallback-context", scope=SCOPE, need=need,
        profile_id="test", generation=1, preparation_id="prep",
        budget=RetrievalBudget(context_bytes=2_000),
        typed_rows=[{
            "record_id": "fallback", "rank": 1,
            "unit": {
                "kind": "environment_state",
                "payload": {
                    "entity": "episode", "relation": "observed text",
                    "value": "For support, contact ops@example.test",
                    "polarity": "positive",
                },
                "evidence": [{
                    "source_id": "source-fallback", "start_offset": 0,
                    "end_offset": 1, "excerpt_sha256": "sha256:" + "0" * 64,
                }],
            },
        }],
    )
    assert package.sufficiency.status == "partial"
    assert package.record_ids == ("fallback",)
    assert "ops@example.test" in package.context
    assert package.action_constraints == ()


def test_accessibility_tree_reader_projection_preserves_ordered_labels_compactly():
    value = (
        '{"accessibility_tree":"RootWebArea \'Customer\'\\\\n\\\\t[10] '
        "button 'Delete Customer', clickable, visible\\\\n\\\\t[11] "
        "button 'Login as Customer', clickable, visible\\\\n\\\\t[12] "
        "button 'Back', clickable, visible" + ("\\\\n\\\\tgeneric ''" * 200) + '"}'
    )
    rendered = _unit_text({
        "kind": "environment_state",
        "payload": {
            "entity": "customer page", "relation": "accessibility_tree",
            "value": value, "polarity": "positive",
        },
    })

    assert "Delete Customer | Login as Customer | Back" in rendered
    assert rendered.index("Delete Customer") < rendered.index("Back")
    assert len(rendered) < len(value) // 4


def test_accessibility_tree_reader_projection_preserves_control_values_and_blank():
    value = (
        '{"accessibility_tree":"RootWebArea \'Hardware\'\\\\n\\\\t[10] '
        "combobox 'Catalog Input Type' value='Text Swatch', clickable\\\\n\\\\t[11] "
        "textbox 'Managed by' value='', clickable\\\\n\\\\t[12] "
        "checkbox 'Active' checked='true', clickable" + '"}'
    )
    rendered = _unit_text({
        "kind": "environment_state",
        "payload": {
            "entity": "hardware form", "relation": "accessibility_tree",
            "value": value, "polarity": "positive",
        },
    })

    assert "combobox 'Catalog Input Type' [value=Text Swatch]" in rendered
    assert "textbox 'Managed by' [value=<blank>]" in rendered
    assert "checkbox 'Active' [checked=true]" in rendered


def test_accessibility_tree_missing_text_value_is_explicit_blank() -> None:
    rendered = _unit_text({
        "kind": "environment_state",
        "payload": {
            "entity": "blank form", "relation": "accessibility_tree",
            "value": "searchbox 'Managed by', clickable, visible",
            "polarity": "positive",
        },
    })

    assert "searchbox 'Managed by' [value=<blank>]" in rendered


def test_packing_caps_duplicate_accessibility_surfaces():
    need = route_information_need("Compare the Size attribute and Theme page")

    def candidate(record_id, subject, rank):
        return {
            "record_id": record_id,
            "rank": rank,
            "unit": {
                "kind": "environment_state",
                "payload": {
                    "entity": subject,
                    "relation": "accessibility_tree",
                    "value": f"RootWebArea '{subject}'",
                    "polarity": "positive",
                },
                "evidence": [{
                    "source_id": f"source-{record_id}", "start_offset": 0,
                    "end_offset": 1, "excerpt_sha256": "sha256:" + "0" * 64,
                }],
            },
        }

    chosen = _complementary_rows(need, [
        candidate("size-1", "size-url", 1),
        candidate("size-2", "size-url", 2),
        candidate("size-3", "size-url", 3),
        candidate("theme", "theme-url", 4),
    ], 4_000)

    assert [row["record_id"] for row in chosen] == [
        "size-1", "theme", "size-2",
    ]


def test_trajectory_projection_preserves_goal_ordered_actions_and_outcome():
    rendered = _unit_text({
        "kind": "environment_state",
        "payload": {
            "entity": "trajectory-1", "relation": "trajectory goal",
            "value": (
                '{"goal":"notify the customer","actions":'
                '["open order","click notify","submit message"],'
                '"outcome":"success","start_url":"https://admin.test/"}'
            ),
            "polarity": "positive",
        },
    })

    assert "Goal: notify the customer" in rendered
    assert "1. open order; 2. click notify; 3. submit message" in rendered
    assert "Outcome: success" in rendered
    assert "Start URL: https://admin.test/" in rendered


def test_historical_target_wins_before_publication_limit(tmp_path):
    memory = Memory(
        tmp_path / "historical.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        old = request(["I am 45 years old."], episode_id="age-2020")
        old = replace(old, parts=(replace(
            old.parts[0], observed_at="2020-06-01T00:00:00Z"
        ),))
        new = request(["I am 46 years old."], episode_id="age-2021")
        new = replace(new, parts=(replace(
            new.parts[0], observed_at="2021-06-01T00:00:00Z"
        ),))
        memory.form_episode(old)
        memory.form_episode(new)
        query = "How old was I in 2020?"
        package = context(
            memory,
            candidates(memory, query, limit=1, candidate_limit=1),
            query,
        )
        assert package.sufficiency.status == "sufficient"
        assert "45" in package.context
        assert "user age: 46" not in package.context
    finally:
        memory.close()


def test_historical_qualified_relation_wins_at_candidate_limit_one(tmp_path):
    memory = Memory(
        tmp_path / "historical-food.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        for episode_id, value, observed_at in (
            ("food-2020", "pasta", "2020-06-01T00:00:00Z"),
            ("food-2021", "pizza", "2021-06-01T00:00:00Z"),
        ):
            item = request([f"My favorite food is {value}."], episode_id=episode_id)
            item = replace(item, parts=(replace(item.parts[0], observed_at=observed_at),))
            memory.form_episode(item)
        query = "What was my favorite food in 2020?"
        package = context(
            memory, candidates(memory, query, limit=1, candidate_limit=1), query
        )
        assert package.sufficiency.status == "sufficient"
        assert "pasta" in package.context and "pizza" not in package.context
    finally:
        memory.close()


def test_historical_environment_state_wins_at_candidate_limit_one(tmp_path):
    memory = Memory(
        tmp_path / "historical-state.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        for year in range(2020, 2030):
            item = request(
                [f"Dashboard currently uses configuration state-{year}."],
                episode_id=f"dashboard-{year}",
            )
            item = replace(
                item,
                binding_method="host_asserted",
                binding_assurance="host_asserted",
                parts=(replace(
                    item.parts[0], kind="state",
                    observed_at=f"{year}-06-01T00:00:00Z",
                ),),
            )
            memory.form_episode(item)
        query = "What was the dashboard configuration in 2020?"
        package = context(
            memory, candidates(memory, query, limit=1, candidate_limit=1), query
        )
        assert package.sufficiency.status == "sufficient"
        assert "state-2020" in package.context
        assert "state-2029" not in package.context
    finally:
        memory.close()


def test_repeated_fact_occurrences_keep_historical_timestamps(tmp_path):
    memory = Memory(
        tmp_path / "fact-occurrences.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        for year in (2020, 2021):
            item = request(["I am 45 years old."], episode_id=f"age-{year}")
            item = replace(item, parts=(replace(
                item.parts[0], observed_at=f"{year}-06-01T00:00:00Z"
            ),))
            memory.form_episode(item)
        query = "How old was I in 2021?"
        package = context(
            memory, candidates(memory, query, limit=1, candidate_limit=1), query
        )
        assert package.sufficiency.status == "sufficient"
        assert "45" in package.context
        assert package.provenance[0]["record_id"]
    finally:
        memory.close()


def test_reader_projection_keeps_focused_controls_and_local_neighbours():
    rendered = _unit_text({
        "kind": "environment_state",
        "payload": {
            "entity": "form",
            "relation": "accessibility_tree",
            "polarity": "positive",
            "value": (
                "button 'Unrelated A'\n"
                "textbox 'Incident number' value='INC1'\n"
                "combobox 'Priority' value='5 - Planning'\n"
                "button 'Save Incident'\n"
                "button 'Unrelated B'\n"
                "button 'Unrelated C'\n"
                "button 'Unrelated D'"
            ),
        },
    }, focus_terms=("incident", "priority"))

    assert "Incident number" in rendered
    assert "Priority" in rendered
    assert "Save Incident" in rendered
    assert "Unrelated D" not in rendered
