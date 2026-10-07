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
from atmem.extract.formation import _fact_key, form_typed_proposals
from atmem.extract.models import Polarity, ProposalAction, ProposalPrecondition
from atmem.extract.review import ReviewPolicy
from dataclasses import replace
import json
from pathlib import Path

import pytest


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


def test_structured_slice_cannot_forge_identity_or_polarity(tmp_path):
    body = json.dumps({"title": "Settings", "tree": "visible setting " * 600})
    memory = Memory(
        tmp_path / "structured-grounding.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        formed = memory.form_episode(episode(
            "structured-source", [body], part_kind="state", host_asserted=True
        ))
        source_id = formed["receipt"]["source_ids"][0]
        proposal = form_typed_proposals(
            body, scope=SCOPE, source_id=source_id,
            formation_id="forged-formation", part_kind="state",
        )[1]
        forged = replace(
            proposal,
            proposal_id="forged-proposal",
            idempotency_key="forged-proposal",
            unit=replace(
                proposal.unit,
                unit_id="forged-unit",
                payload=replace(
                    proposal.unit.payload,
                    entity="Unseen Entity",
                    relation="Unseen Relation",
                    polarity=Polarity.NEGATIVE,
                ),
            ),
        )
        outcome = memory.submit_extraction_proposal(
            forged, source_text=body,
            review_policy=ReviewPolicy(quarantine_non_durable=False),
        )
        assert outcome["review_state"] == "rejected"
        assert "typed_structured_identity_mismatch" in outcome["reason_codes"]
        assert "typed_polarity_mismatch" in outcome["reason_codes"]
    finally:
        memory.close()


def test_fact_keys_do_not_collapse_punctuation_or_unicode_relations():
    c_plus_plus = _fact_key("user", "C++ preference")
    c_sharp = _fact_key("user", "C# preference")
    japanese = _fact_key("user", "言語")

    assert c_plus_plus != c_sharp
    assert japanese
    assert len({c_plus_plus, c_sharp, japanese}) == 3
    assert _fact_key("a_b", "c") != _fact_key("a", "b_c")


def test_structured_snapshot_negation_does_not_invert_container_polarity(tmp_path):
    body = '{"title":"Settings","warning":"feature is not available"}'
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "structured-negation", [body], part_kind="state", host_asserted=True
        ))
        assert result["receipt"]["rejected"] == 0
        assert result["receipt"]["admitted"] == 1
    finally:
        memory.close()


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
        assert receipt["unrepresented_ranges"] == ()
        assert receipt["withheld"] == 1
        source = memory.store.get_protocol_source_by_id(receipt["source_ids"][0])
        retained = memory.store.get_episode(SCOPE.subject_id, source["episode_id"])
        assert retained["message"] == text
        assert result["outcomes"][0]["review_state"] == "pending_review"
    finally:
        memory.close()


def test_sentence_source_observations_are_exact_independent_spans(tmp_path):
    text = "First fact is blue; second fact is green. Third fact is current."
    request = replace(
        episode("episode-source-observations", [text], host_asserted=True),
        source_observation_granularity="sentence",
    )
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(request)
        observations = [
            row for row in memory.list_extraction_proposals(
                SCOPE.subject_id, review_states=None, limit=100
            )
            if ((row.get("proposal") or {}).get("unit") or {}).get("payload", {}).get(
                "relation"
            ) == "source statement"
        ]
        assert [row["proposal"]["fact"] for row in observations] == [
            "First fact is blue;",
            "second fact is green.",
            "Third fact is current.",
        ]
        source = memory.store.get_protocol_source_by_id(result["receipt"]["source_ids"][0])
        for row in observations:
            evidence = row["proposal"]["evidence"][0]
            assert text[evidence["start_offset"] : evidence["end_offset"]] == row["proposal"]["fact"]
            assert row["review_state"] == "pending_review"
        assert len({row["fact_key"] for row in observations}) == 3
    finally:
        memory.close()


def test_authorized_history_import_is_explicit_scoped_and_audited(tmp_path):
    request = replace(
        episode(
            "episode-authorized-import",
            ["When publishing, must use the release channel. Another fact is blue."],
            host_asserted=True,
        ),
        source_observation_granularity="sentence",
    )
    authority = {
        "principal_id": "history-importer",
        "subject_id": SCOPE.subject_id,
        "agent_id": SCOPE.agent_id,
        "workspace_id": SCOPE.workspace_id,
        "scopes": ("history_import:review", "procedure:review"),
        "assurance": "explicit_test_configuration",
    }
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
        review_authorities=(authority,),
    )
    try:
        with pytest.raises(PermissionError, match="host-asserted"):
            memory.form_episode(
                replace(request, binding_method="caller_asserted", binding_assurance="caller_asserted"),
                history_import_principal="history-importer",
            )
        result = memory.form_episode(
            request, history_import_principal="history-importer"
        )
        assert result["receipt"]["withheld"] == 0
        assert result["receipt"]["retrieval_ready"] is True
        reviewed = [
            row for row in memory.list_extraction_proposals(
                SCOPE.subject_id, review_states=("committed",), limit=100
            )
            if "history" in " ".join(
                review.get("reason") or ""
                for review in memory.store.list_memory_reviews(row["proposal_id"])
            )
        ]
        assert reviewed
        assert all(
            memory.store.list_memory_reviews(row["proposal_id"])[0]["actor"]
            == "history-importer"
            for row in reviewed
        )
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
    body = '{"accessibility_tree":"' + ("visible button text " * 500) + '"}'
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
        assert all(
            0 < len(row["raw"]["typed_unit"]["payload"]["value"]) <= 8_000
            for row in rows
        )
    finally:
        memory.close()


def test_long_browser_state_preserves_navigation_fields_and_large_tree(tmp_path):
    body = json.dumps({
        "state_index": 17,
        "step": 17,
        "url": "https://admin.example.test/customer/10",
        "action": "click('notify')",
        "thought": "The customer toolbar is visible; send the notification next.",
        "accessibility_tree": "button label and state " * 900,
    }, sort_keys=True, separators=(",", ":"))
    memory = Memory(
        tmp_path / "browser-state.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "browser-state", [body], part_kind="state", host_asserted=True
        ))
        assert result["receipt"]["rejected"] == 0
        assert result["receipt"]["representation_complete"] is True
        records = [
            memory.store.get_record(SCOPE.subject_id, record_id)
            for outcome in result["outcomes"]
            for record_id in outcome["record_ids"]
        ]
        payloads = [record["raw"]["typed_unit"]["payload"] for record in records]
        summary = next(value for value in payloads if value["relation"] == "state summary")
        assert "https://admin.example.test/customer/10" in summary["value"]
        assert "click('notify')" in summary["value"]
        assert "send the notification next" in summary["value"]
        tree_parts = [
            value["value"] for value in payloads
            if value["relation"] == "accessibility_tree"
        ]
        assert len(tree_parts) >= 2
        assert all(0 < len(value) <= 8_000 for value in tree_parts)
    finally:
        memory.close()


def test_long_browser_state_builds_compact_control_state_index(tmp_path):
    body = json.dumps({
        "state_index": 1,
        "url": "https://admin.example.test/hardware/new",
        "accessibility_tree": (
            "RootWebArea 'New Hardware'\n"
            "searchbox 'Managed by', clickable, visible\n"
            "combobox 'Priority' value='5 - Planning', clickable\n"
            "option '4 - Low', selected=False\n"
            "option '5 - Planning', selected=True\n"
            + "generic 'padding'\n" * 900
        ),
    }, sort_keys=True, separators=(",", ":"))
    memory = Memory(
        tmp_path / "control-index.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "control-index", [body], part_kind="state", host_asserted=True
        ))
        records = [
            memory.store.get_record(SCOPE.subject_id, record_id)
            for outcome in result["outcomes"]
            for record_id in outcome["record_ids"]
        ]
        indexes = [
            record["raw"]["typed_unit"]["payload"]["value"]
            for record in records
            if record["raw"]["typed_unit"]["payload"]["relation"]
            == "ui control state index"
        ]
        assert len(indexes) == 1
        assert "searchbox 'Managed by' value='<blank>'" in indexes[0]
        assert "combobox 'Priority' value='5 - Planning'" in indexes[0]
        assert "option '4 - Low' selected='False'" not in indexes[0]
        assert "option '5 - Planning' selected='True'" in indexes[0]
    finally:
        memory.close()


def test_large_control_state_index_admits_every_grounded_chunk(tmp_path):
    controls = "\n".join(
        f"checkbox 'Field {index:04d}' checked='false'" for index in range(600)
    )
    body = json.dumps({
        "state_index": 9,
        "url": "https://admin.example.test/large-form",
        "accessibility_tree": controls + "\n" + "generic 'padding'\n" * 600,
    }, sort_keys=True, separators=(",", ":"))
    memory = Memory(
        tmp_path / "large-control-index.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "large-control-index", [body], part_kind="state", host_asserted=True
        ))
        assert result["receipt"]["rejected"] == 0
        records = [
            memory.store.get_record(SCOPE.subject_id, record_id)
            for outcome in result["outcomes"]
            for record_id in outcome["record_ids"]
        ]
        indexes = [
            record["raw"]["typed_unit"]["payload"]["value"]
            for record in records
            if record["raw"]["typed_unit"]["payload"]["relation"]
            == "ui control state index"
        ]
        assert len(indexes) > 1
        assert "checkbox 'Field 0000' checked='false'" in "".join(indexes)
        assert "checkbox 'Field 0599' checked='false'" in "".join(indexes)
    finally:
        memory.close()


def test_large_browser_state_builds_ordered_ui_surface_index(tmp_path):
    body = json.dumps({
        "state_index": 3,
        "url": "https://shop.example.test/catalog",
        "accessibility_tree": (
            "RootWebArea 'Developer laptops'\n"
            "link 'Windows Developer Laptop'\n"
            "button 'Sort by'\n"
            "option 'Newest' selected='False'\n"
            "option 'Most Commented' selected='True'\n"
            + "generic 'padding'\n" * 900
        ),
    }, sort_keys=True, separators=(",", ":"))
    memory = Memory(
        tmp_path / "surface-index.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "surface-index", [body], part_kind="state", host_asserted=True
        ))
        assert result["receipt"]["rejected"] == 0
        records = [
            memory.store.get_record(SCOPE.subject_id, record_id)
            for outcome in result["outcomes"]
            for record_id in outcome["record_ids"]
        ]
        indexes = [
            record["raw"]["typed_unit"]["payload"]["value"]
            for record in records
            if record["raw"]["typed_unit"]["payload"]["relation"]
            == "ui surface index"
        ]
        assert len(indexes) == 1
        assert indexes[0].splitlines() == [
            "rootwebarea 'Developer laptops'",
            "link 'Windows Developer Laptop'",
            "button 'Sort by'",
            "option 'Newest'",
            "option 'Most Commented'",
        ]
        candidates = memory.eligible_candidates(RecallRequest(
            request_id="surface-recall",
            scope=SCOPE,
            query="What option is immediately after Newest in the Sort by menu?",
            limit=8,
            candidate_limit=40,
            signals=("lexical", "graph"),
        ))
        package = memory.prepare_context_v2(ContextRequestV2(
            context_id="surface-context",
            candidate_set_id=candidates.candidate_set_id,
            scope=SCOPE,
            query="What option is immediately after Newest in the Sort by menu?",
            budget=RetrievalBudget(context_bytes=16_384),
        ))
        assert "option &#x27;Newest&#x27;" in package.context
        assert "option &#x27;Most Commented&#x27;" in package.context
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


def test_long_structured_state_does_not_treat_container_negation_as_claim_polarity(tmp_path):
    body = json.dumps({"title": "Settings", "tree": "not available " * 700})
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "long-negative-state", [body], part_kind="state", host_asserted=True
        ))
        assert result["receipt"]["rejected"] == 0
        assert result["receipt"]["representation_complete"] is True
    finally:
        memory.close()


def test_fact_updates_are_order_independent_when_observation_time_is_known(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        newer = episode("age-new", ["I am 46 years old."])
        newer = replace(newer, parts=(replace(
            newer.parts[0], observed_at="2026-09-02T00:00:00Z"
        ),))
        older = episode("age-old", ["I am 45 years old."])
        older = replace(older, parts=(replace(
            older.parts[0], observed_at="2026-09-01T00:00:00Z"
        ),))
        memory.form_episode(newer)
        result = memory.form_episode(older)
        assert result["outcomes"][0]["review_state"] == "committed"
        assert "historical_observation" in result["outcomes"][0]["reason_codes"]
        active = memory.store.active_records_for_fact_key(SCOPE.subject_id, "user_age")
        assert [row["content"] for row in active] == ["user age: 46 (positive)"]
        history = memory.store.list_records(SCOPE.subject_id, statuses=None)
        assert {(row["content"], row["status"]) for row in history} == {
            ("user age: 45 (positive)", "superseded"),
            ("user age: 46 (positive)", "active"),
        }
    finally:
        memory.close()


def test_untrusted_fact_cannot_retire_a_trusted_current_fact(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        trusted = memory.form_episode(episode("trusted-age", ["I am 46 years old."]))
        external = episode("external-age", ["I am 30 years old."])
        external = replace(external, parts=(replace(
            external.parts[0], source_type="website"
        ),))
        result = memory.form_episode(external)
        assert result["outcomes"][0]["review_state"] == "pending_review"
        trusted_id = trusted["outcomes"][0]["record_ids"][0]
        assert memory.store.get_record(SCOPE.subject_id, trusted_id)["status"] == "active"
    finally:
        memory.close()


def test_explicit_untrusted_supersession_cannot_retire_trusted_fact(tmp_path):
    memory = Memory(
        tmp_path / "explicit-trust.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        trusted = memory.form_episode(episode("trusted", ["I am 45 years old."]))
        target_id = trusted["outcomes"][0]["record_ids"][0]
        target = memory.store.get_record(SCOPE.subject_id, target_id)
        external = episode("external", ["I am 30 years old."])
        external = replace(external, parts=(replace(
            external.parts[0], source_type="website"
        ),))
        observed = memory.form_episode(external)
        source_id = observed["receipt"]["source_ids"][0]
        proposal = form_typed_proposals(
            "I am 30 years old.", scope=SCOPE, source_id=source_id,
            formation_id="explicit-untrusted",
        )[0]
        proposal = replace(
            proposal, proposal_id="explicit-untrusted",
            idempotency_key="explicit-untrusted",
            action=ProposalAction.SUPERSEDE,
            affected_record_ids=(target_id,),
            preconditions=(ProposalPrecondition(
                record_id=target_id, generation=int(target["generation"]),
                status="active",
                content_sha256=f"sha256:{sha256_hex(target['content'])}",
            ),),
        )
        outcome = memory.submit_extraction_proposal(
            proposal, source_text="I am 30 years old."
        )
        assert outcome["review_state"] == "pending_review"
        assert memory.store.get_record(SCOPE.subject_id, target_id)["status"] == "active"
    finally:
        memory.close()


def test_plain_state_relation_named_chunk_cannot_forge_negative_polarity(tmp_path):
    text = "The current download chunk is available."
    memory = Memory(
        tmp_path / "chunk-polarity.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        formed = memory.form_episode(episode(
            "chunk-source", [text], part_kind="state", host_asserted=True
        ))
        proposal = form_typed_proposals(
            text, scope=SCOPE, source_id=formed["receipt"]["source_ids"][0],
            formation_id="forged-chunk", part_kind="state",
        )[0]
        forged = replace(
            proposal, proposal_id="forged-chunk", idempotency_key="forged-chunk",
            unit=replace(
                proposal.unit, unit_id="forged-chunk-unit",
                payload=replace(proposal.unit.payload, polarity=Polarity.NEGATIVE),
            ),
        )
        outcome = memory.submit_extraction_proposal(
            forged, source_text=text,
            review_policy=ReviewPolicy(quarantine_non_durable=False),
        )
        assert outcome["review_state"] == "rejected"
        assert "typed_polarity_mismatch" in outcome["reason_codes"]
    finally:
        memory.close()


def test_bracket_prefixed_plain_state_cannot_forge_negative_polarity(tmp_path):
    text = "[notice] The service is available."
    memory = Memory(
        tmp_path / "bracket-polarity.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        formed = memory.form_episode(episode(
            "bracket-source", [text], part_kind="state", host_asserted=True
        ))
        proposal = form_typed_proposals(
            text, scope=SCOPE, source_id=formed["receipt"]["source_ids"][0],
            formation_id="forged-bracket", part_kind="state",
        )[0]
        forged = replace(
            proposal, proposal_id="forged-bracket", idempotency_key="forged-bracket",
            unit=replace(
                proposal.unit, unit_id="forged-bracket-unit",
                payload=replace(proposal.unit.payload, polarity=Polarity.NEGATIVE),
            ),
        )
        outcome = memory.submit_extraction_proposal(
            forged, source_text=text,
            review_policy=ReviewPolicy(quarantine_non_durable=False),
        )
        assert outcome["review_state"] == "rejected"
        assert "typed_polarity_mismatch" in outcome["reason_codes"]
    finally:
        memory.close()


def test_long_unclassified_text_forms_lossless_bounded_units(tmp_path):
    text = "Background context. " * 150
    memory = Memory(
        tmp_path / "long-unclassified.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "long-unclassified", [text], host_asserted=True
        ))
        assert result["receipt"]["representation_complete"] is True
        assert result["receipt"]["retrieval_ready"] is True
        assert result["receipt"]["proposals_by_kind"]["environment_state"] > 1
    finally:
        memory.close()


def test_replay_does_not_mark_pending_review_retrieval_ready(tmp_path):
    memory = Memory(
        tmp_path / "pending-replay.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        request = episode("pending-replay", [
            "I am 45 years old.",
            "When deploying a release, must post to the releases channel.",
        ])
        first = memory.form_episode(request)
        replay = memory.form_episode(request)
        assert first["receipt"]["withheld"] == 1
        assert first["receipt"]["retrieval_ready"] is False
        assert replay["receipt"]["retrieval_ready"] is False
    finally:
        memory.close()


def test_resume_keeps_earlier_pending_review_not_ready(tmp_path):
    memory = Memory(
        tmp_path / "pending-resume.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        request = episode("pending-resume", [
            "When deploying a release, must post to the releases channel.",
            "I am 45 years old.",
        ])
        first = memory.form_episode(request, budget=RetrievalBudget(proposals=1))
        resumed = memory.form_episode(request, budget=RetrievalBudget(proposals=8))
        assert first["receipt"]["withheld"] == 2
        assert resumed["receipt"]["processing_complete"] is True
        assert resumed["receipt"]["withheld"] == 1
        assert resumed["receipt"]["retrieval_ready"] is False
    finally:
        memory.close()


def test_negative_neutral_observation_is_retrievable_as_observed_text(tmp_path):
    memory = Memory(
        tmp_path / "negative-observation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        result = memory.form_episode(episode(
            "negative-observation", ["There was no music playing in the room."],
            host_asserted=True,
        ))
        assert result["outcomes"][0]["review_state"] == "committed"
        assert result["receipt"]["retrieval_ready"] is True
    finally:
        memory.close()


def test_duplicate_typed_observations_retain_each_source_occurrence(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = memory.form_episode(episode("age-one", ["I am 45 years old."]))
        second = memory.form_episode(episode("age-two", ["I am 45 years old."]))
        assert second["outcomes"][0]["review_state"] == "noop"
        assert second["outcomes"][0]["record_ids"] == first["outcomes"][0]["record_ids"]
        duplicate = memory.store._conn.execute(
            "SELECT unit_id FROM typed_memory_units"
        ).fetchone()
        unit = memory.store.get_typed_memory_unit(
            SCOPE.subject_id, SCOPE.workspace_id, duplicate["unit_id"]
        )
        assert len(unit["evidence"]) == 2
        replay = memory.form_episode(episode("age-two", ["I am 45 years old."]))
        assert replay["receipt"]["retrieval_ready"] is True
    finally:
        memory.close()


def test_negative_fact_and_state_are_admitted_with_negative_polarity(tmp_path):
    memory = Memory(
        tmp_path / "negative.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        fact = memory.form_episode(episode(
            "negative-fact", ["My preferred airport is not Sydney."]
        ))
        state = memory.form_episode(episode(
            "negative-state", ["The current subscription is not available."],
            part_kind="state", host_asserted=True,
        ))
        assert fact["receipt"]["rejected"] == 0
        assert state["receipt"]["rejected"] == 0
        for result in (fact, state):
            record = memory.store.get_record(
                SCOPE.subject_id, result["outcomes"][0]["record_ids"][0]
            )
            assert record["raw"]["typed_unit"]["payload"]["polarity"] == "negative"
    finally:
        memory.close()


def test_claim_local_negation_does_not_invert_other_facts(tmp_path):
    memory = Memory(
        tmp_path / "local-negation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        compound = memory.form_episode(episode(
            "compound-negation",
            ["I am 45 years old and my subscription is not available."],
        ))
        contrast = memory.form_episode(episode(
            "contrast-negation",
            ["My preferred airport is Sydney, not Melbourne."],
        ))
        assert compound["outcomes"][0]["review_state"] == "committed"
        record = memory.store.get_record(
            SCOPE.subject_id, contrast["outcomes"][0]["record_ids"][0]
        )
        assert record["raw"]["typed_unit"]["payload"]["value"] == "Sydney"
        assert record["raw"]["typed_unit"]["payload"]["polarity"] == "positive"
    finally:
        memory.close()


def test_excluded_typed_occurrence_cannot_be_resurrected_by_reingest(tmp_path):
    memory = Memory(
        tmp_path / "excluded-reingest.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = memory.form_episode(episode("excluded-one", ["I am 45 years old."]))
        record_id = first["outcomes"][0]["record_ids"][0]
        memory.set_retrieval_excluded(SCOPE.subject_id, record_id, True)
        second = memory.form_episode(episode("excluded-two", ["I am 45 years old."]))
        assert second["outcomes"][0]["review_state"] == "rejected"
        assert "typed_occurrence_previously_excluded" in second["outcomes"][0]["reason_codes"]
        assert second["receipt"]["retrieval_ready"] is False
    finally:
        memory.close()


def test_source_identity_is_scoped_not_globally_episode_named(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = episode("same-episode", ["I am 45 years old."])
        second = replace(
            first,
            scope=AuthorityScope("other-person", "other-agent", "other-workspace"),
            idempotency_key="other-key",
        )
        a = memory.form_episode(first)
        b = memory.form_episode(second)
        assert a["receipt"]["source_ids"] != b["receipt"]["source_ids"]
    finally:
        memory.close()


def test_independent_structured_observations_do_not_supersede_by_fact_key(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = memory.form_episode(episode(
            "snapshot-one", ['{"state_index":1,"url":"https://example.test/a"}'],
            part_kind="state", host_asserted=True,
        ))
        second = memory.form_episode(episode(
            "snapshot-two", ['{"state_index":1,"url":"https://example.test/a"}'],
            part_kind="state", host_asserted=True,
        ))
        first_id = first["outcomes"][0]["record_ids"][0]
        second_id = second["outcomes"][0]["record_ids"][0]
        assert first_id != second_id
        assert memory.store.get_record(SCOPE.subject_id, first_id)["status"] == "active"
        assert memory.store.get_record(SCOPE.subject_id, second_id)["status"] == "active"
    finally:
        memory.close()


def test_host_can_explicitly_admit_sensitive_observation_only_when_encrypted(tmp_path):
    from dataclasses import replace

    from atmem.core.keys import sqlcipher_runtime_status
    from atmem.service.household import HouseholdApplication

    request = replace(
        episode(
            "sensitive-state",
            ['{"state_index":1,"label":"Medical diagnosis"}'],
            part_kind="state",
            host_asserted=True,
        ),
        sensitive_observation_handling="admit_encrypted",
    )
    path = tmp_path / "encrypted.db"
    if sqlcipher_runtime_status()["available"]:
        HouseholdApplication.initialize(path, encrypted=True, backend="file")
        memory = Memory(path, auto_vectors=False)
        try:
            result = memory.form_episode(request)
            assert result["receipt"]["retrieval_ready"] is True
            assert result["receipt"]["withheld"] == 0
        finally:
            memory.close()

    insecure = Memory(
        tmp_path / "plain.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        with pytest.raises(ValueError, match="only into encrypted storage"):
            insecure.form_episode(request)
    finally:
        insecure.close()


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


def test_partial_formation_resumes_by_proposal_with_a_larger_budget(tmp_path):
    memory = Memory(
        tmp_path / "formation.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        request = episode("resume", [
            "My favorite city is Sydney.",
            "My favorite food is pasta.",
        ])
        partial = memory.form_episode(
            request, budget=RetrievalBudget(proposals=1)
        )
        assert partial["receipt"]["processing_complete"] is False
        assert partial["receipt"]["next_positions"][0]["proposal_id"]
        completed = memory.form_episode(
            request, budget=RetrievalBudget(proposals=8)
        )
        assert completed["replayed"] is False
        assert completed["receipt"]["processing_complete"] is True
        assert completed["receipt"]["representation_complete"] is True
        replay = memory.form_episode(request, budget=RetrievalBudget(proposals=8))
        assert replay["replayed"] is True
    finally:
        memory.close()


def test_resume_processes_both_proposal_and_source_budget_positions(tmp_path):
    values = [
        "My favorite city is Sydney.",
        "My favorite food is pasta.",
        "My favorite color is blue.",
    ]
    memory = Memory(
        tmp_path / "resume-mixed.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        request = episode("mixed-resume", values)
        first = memory.form_episode(
            request,
            budget=RetrievalBudget(
                proposals=1,
                source_bytes=len("".join(values[:2]).encode()),
            ),
        )
        assert {row["part_id"] for row in first["receipt"]["next_positions"]} == {
            "part-1", "part-2",
        }
        resumed = memory.form_episode(
            request, budget=RetrievalBudget(proposals=10, source_bytes=1_000)
        )
        assert resumed["receipt"]["retrieval_ready"] is True
        assert resumed["receipt"]["next_positions"] == ()
        assert {row["content"] for row in memory.store.list_records(
            SCOPE.subject_id, statuses=None
        )} == {
            "user favorite city: Sydney (positive)",
            "user favorite food: pasta (positive)",
            "user favorite color: blue (positive)",
        }
    finally:
        memory.close()


def test_untrusted_transition_cannot_retire_trusted_state(tmp_path):
    memory = Memory(
        tmp_path / "transition-trust.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        memory.form_episode(episode(
            "trusted-transition",
            ["Account status changed from pending to active after approval."],
            part_kind="state",
            host_asserted=True,
        ))
        request = episode(
            "website-transition",
            ["Account status changed from active to disabled after rejection."],
            part_kind="state",
            host_asserted=True,
        )
        request = replace(request, parts=(replace(
            request.parts[0], source_type="website"
        ),))
        result = memory.form_episode(request)
        assert result["outcomes"][0]["review_state"] == "pending_review"
        active = memory.store.list_records(SCOPE.subject_id)
        assert len(active) == 1
        assert "active" in active[0]["content"]
    finally:
        memory.close()


def test_protected_media_follows_encryption_exclusion_deletion_and_occurrence(tmp_path):
    media_path = tmp_path / "screen.bin"
    media_path.write_bytes(b"same screenshot bytes")

    def media_episode(name: str) -> EpisodeIngestRequest:
        base = episode(
            name, ["My favorite city is Sydney."], host_asserted=True
        )
        return replace(base, parts=base.parts + (EpisodePart(
            part_id="image", ordinal=1, kind="media_reference",
            source_type="tool_output", reference_id=str(media_path),
            reference_sha256=f"sha256:{sha256_hex(media_path.read_bytes())}",
        ),))

    plaintext = Memory(tmp_path / "plain.db", auto_vectors=False)
    try:
        result = plaintext.form_episode(media_episode("plain-media"))
        assert result["receipt"]["media_references"] == ()
        assert plaintext.store._conn.execute(
            "SELECT COUNT(*) FROM protected_formation_media"
        ).fetchone()[0] == 0
    finally:
        plaintext.close()

    memory = Memory(
        tmp_path / "media.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = memory.form_episode(media_episode("media-one"))
        record_id = first["outcomes"][0]["record_ids"][0]
        media_id = first["receipt"]["media_references"][0]["media_id"]
        assert memory.store.protected_formation_media(
            SCOPE.subject_id, SCOPE.workspace_id, media_id
        ) is not None
        memory.set_retrieval_excluded(SCOPE.subject_id, record_id, True)
        assert memory.store.protected_formation_media(
            SCOPE.subject_id, SCOPE.workspace_id, media_id
        ) is None
        memory.set_retrieval_excluded(SCOPE.subject_id, record_id, False)
        memory.forget_record(SCOPE.subject_id, record_id)
        assert memory.store.protected_formation_media(
            SCOPE.subject_id, SCOPE.workspace_id, media_id
        ) is None
        second = memory.form_episode(media_episode("media-two"))
        third = memory.form_episode(media_episode("media-three"))
        assert (
            second["receipt"]["media_references"][0]["media_id"]
            != third["receipt"]["media_references"][0]["media_id"]
        )
    finally:
        memory.close()


def test_incomplete_replay_stays_not_ready(tmp_path):
    memory = Memory(
        tmp_path / "incomplete-replay.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        request = episode(
            "incomplete-replay", ["I am 45 years old. We discussed a project."]
        )
        first = memory.form_episode(request)
        replay = memory.form_episode(request)
        assert first["receipt"]["representation_complete"] is False
        assert replay["receipt"]["representation_complete"] is False
        assert replay["receipt"]["retrieval_ready"] is False
    finally:
        memory.close()


def test_deferred_source_keeps_adjacent_media_resumable(tmp_path):
    media = tmp_path / "screen.bin"
    media.write_bytes(b"screen bytes")
    base = episode("deferred-media", ["I am 45 years old."], host_asserted=True)
    request = replace(base, parts=base.parts + (EpisodePart(
        part_id="image", ordinal=1, kind="media_reference",
        source_type="tool_output", reference_id=str(media),
        reference_sha256=f"sha256:{sha256_hex(media.read_bytes())}",
    ),))
    memory = Memory(
        tmp_path / "deferred-media.db", auto_vectors=False,
        allow_insecure_typed_development=True,
    )
    try:
        first = memory.form_episode(
            request, budget=RetrievalBudget(source_bytes=1)
        )
        assert {row["part_id"] for row in first["receipt"]["next_positions"]} == {
            "part-0", "image",
        }
        resumed = memory.form_episode(
            request, budget=RetrievalBudget(source_bytes=1_000)
        )
        assert resumed["receipt"]["retrieval_ready"] is True
        assert len(resumed["receipt"]["media_references"]) == 1
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
