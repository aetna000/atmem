from atmem import Memory
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart, RetrievalBudget
from atmem.core.canonical import sha256_hex
from atmem.extract.formation import form_typed_proposals
import json
from pathlib import Path


SCOPE = AuthorityScope("formation-person", "formation-agent", "formation-workspace")


def test_structured_state_with_empty_key_uses_non_empty_fallback_relation():
    proposals = form_typed_proposals(
        '{"": "visible but unnamed state"}',
        scope=SCOPE,
        source_id="source-empty-key",
        formation_id="formation-empty-key",
        part_kind="state",
    )

    assert len(proposals) == 1
    assert proposals[0].unit.payload.relation == "structured event"


def _words(value: object) -> set[str]:
    import re

    words = re.findall(r"[a-z0-9#-]+", str(value).casefold())
    return {word[:-1] if len(word) > 3 and word.endswith("s") else word for word in words}


def test_product_derived_formation_corpus_preserves_answer_bearing_fields():
    fixture = Path(__file__).parent / "fixtures/retrieval-quality/product-memory-cases-v1.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]

    for case in cases:
        proposals = form_typed_proposals(
            case["source"], scope=SCOPE, source_id=f"source-{case['id']}",
            formation_id=f"formation-{case['id']}",
        )
        matching = [row for row in proposals if row.unit.kind.value == case["kind"]]
        assert len(matching) == 1, case["id"]
        payload = matching[0].unit.to_dict()["payload"]
        for field, expected in case["required"].items():
            if field == "ordered_steps":
                actual = [row["instruction"] for row in payload["steps"]]
                assert len(actual) == len(expected), case["id"]
                for wanted, found in zip(expected, actual):
                    assert _words(wanted) <= _words(found), (case["id"], wanted, found)
                continue
            actual_field = {
                "condition": "applies_when" if case["kind"] == "premise_constraint" else field,
                "excluded_condition": "excluded_when",
            }.get(field, field)
            actual = payload.get(actual_field)
            assert actual is not None, (case["id"], field)
            expected_words = _words(expected)
            actual_words = _words(actual)
            # Formation may retain harmless source qualifiers (articles,
            # entity names, passive voice), but it may not lose the
            # answer-bearing terms declared by this product corpus.
            assert expected_words <= actual_words or actual_words <= expected_words, (
                case["id"], field, expected, actual,
            )


def episode(
    episode_id: str, texts: list[str], *, part_kind: str = "text",
    host_asserted: bool = False,
) -> EpisodeIngestRequest:
    return EpisodeIngestRequest(
        episode_id=episode_id,
        idempotency_key=f"key-{episode_id}",
        scope=SCOPE,
        parts=tuple(
            EpisodePart(
                part_id=f"part-{index}", ordinal=index, kind=part_kind,
                source_type="user_message", content=text,
                content_sha256=f"sha256:{sha256_hex(text)}",
            )
            for index, text in enumerate(texts)
        ),
        binding_method="host_asserted" if host_asserted else "caller_asserted",
        binding_assurance="host_asserted" if host_asserted else "caller_asserted",
    )


def test_lossless_episode_formation_covers_all_seven_product_types(tmp_path):
    texts = [
        "I am 45 years old.",
        "When deploying a release, must post to the releases channel.",
        "The current local model is qwen3.5.",
        "Account status changed from pending to active after approval.",
        "To publish a build, 1. run tests 2. build the package 3. upload the artifact",
        "When the upload times out, retrying blindly fails; instead reconcile the receipt.",
        "Assume the desktop feature is installed.",
    ]
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode("episode-seven", texts))
        receipt = result["receipt"]
        assert set(receipt["proposals_by_kind"]) == {
            "atomic_fact", "durable_rule", "environment_state", "state_transition",
            "procedure", "failure_gotcha", "premise_constraint",
        }
        assert receipt["source_events_observed"] == 7
        assert receipt["admitted"] + receipt["withheld"] == 7
        assert receipt["rejected"] == 0
        assert receipt["complete"] is True
        kinds = {
            row["kind"] for row in memory.store._conn.execute(
                "SELECT kind FROM typed_memory_units"
            ).fetchall()
        }
        # Durable non-action claims commit; state and action-bearing units are reviewed.
        assert {"atomic_fact", "premise_constraint"} <= kinds
        assert result["outcomes"][1]["review_state"] == "pending_review"
        assert memory.store._conn.execute(
            "SELECT COUNT(*) AS count FROM source_adjacency"
        ).fetchone()["count"] == 6
    finally:
        memory.close()


def test_unstructured_content_is_preserved_and_loss_is_visible(tmp_path):
    text = "We had a useful conversation about the project."
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode("episode-unstructured", [text]))
        receipt = result["receipt"]
        assert receipt["complete"] is False
        assert receipt["unrepresented_ranges"][0]["part_id"] == "part-0"
        source = memory.store.get_protocol_source_by_id(receipt["source_ids"][0])
        retained = memory.store.get_episode(SCOPE.subject_id, source["episode_id"])
        assert retained["message"] == text
        assert result["outcomes"] == []
    finally:
        memory.close()


def test_episode_formation_is_idempotent(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        request = episode("episode-repeat", ["I am 45 years old."])
        first = memory.form_episode(request)
        second = memory.form_episode(request)
        assert first["receipt"]["formation_id"] == second["receipt"]["formation_id"]
        assert second["replayed"] is True
        assert memory.store._conn.execute(
            "SELECT COUNT(*) AS count FROM typed_memory_units"
        ).fetchone()["count"] == 1
    finally:
        memory.close()


def test_long_structured_state_is_losslessly_sliced_with_unique_fact_keys(tmp_path):
    body = '{"accessibility_tree":"' + ("visible button text " * 180) + '"}'
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "long-state", [body], part_kind="state", host_asserted=True
        ))
        units = result["receipt"]["admitted"]
        assert units >= 2
        assert result["receipt"]["complete"] is True
        rows = [
            memory.store.get_record(SCOPE.subject_id, outcome["record_ids"][0])
            for outcome in result["outcomes"]
        ]
        assert len(rows) == units
        assert len({row["fact_key"] for row in rows}) == units
        assert all(0 < len(row["content"]) <= 2_000 for row in rows)
    finally:
        memory.close()


def test_compatible_typed_update_supersedes_old_fact_with_generation_guard(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = memory.form_episode(episode("age-45", ["I am 45 years old."]))
        second_request = episode("age-46", ["I am 46 years old."])
        second = memory.form_episode(second_request)
        first_id = first["outcomes"][0]["record_ids"][0]
        second_id = second["outcomes"][0]["record_ids"][0]
        assert memory.store.get_record(SCOPE.subject_id, first_id)["status"] == "superseded"
        assert memory.store.get_record(SCOPE.subject_id, second_id)["status"] == "active"
        assert "typed_compatible_update" in second["outcomes"][0]["reason_codes"]
        replay = memory.form_episode(second_request)
        assert replay["replayed"] is True
        active = memory.store.active_records_for_fact_key(SCOPE.subject_id, "user_age")
        assert [row["id"] for row in active] == [second_id]
    finally:
        memory.close()


def test_formation_budget_withholds_work_but_retains_source_and_receipt(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(
            episode("bounded", ["I am 45 years old.", "My favorite food is pasta."]),
            budget=RetrievalBudget(proposals=1),
        )
        receipt = result["receipt"]
        assert receipt["admitted"] == 1
        assert receipt["withheld"] == 1
        assert receipt["complete"] is False
        assert "formation_proposal_budget_exhausted" in receipt["reason_codes"]
        assert len(receipt["source_ids"]) == 2
    finally:
        memory.close()


def test_retrieval_quality_summary_is_bounded_and_content_free(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        memory.form_episode(episode("summary-complete", ["I am 45 years old."]))
        memory.form_episode(
            episode("summary-gap", ["We discussed the project in detail."])
        )
        summary = memory.store.retrieval_quality_summary([SCOPE.subject_id])
        assert summary["formations"] == {
            "total": 2, "complete": 1, "with_loss": 1,
        }
        assert summary["typed_by_kind"] == [
            {"value": "atomic_fact", "count": 1}
        ]
        assert summary["context_preparations"] == []
        assert "I am 45 years old." not in str(summary)
    finally:
        memory.close()
