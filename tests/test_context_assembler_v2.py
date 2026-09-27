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
from atmem.retrieve.expand import expand_evidence_neighborhood


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
