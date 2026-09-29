from atmem.retrieve.intent import route_information_need
from atmem.retrieve.sufficiency import decide_sufficiency


def row(
    record_id: str, kind: str, payload: dict, *, fact_key: str = "",
    **unit_fields,
) -> dict:
    return {
        "record_id": record_id,
        "fact_key": fact_key,
        "unit": {
            "kind": kind,
            "payload": payload,
            "evidence": [{
                "source_id": f"source-{record_id}",
                "start_offset": 0,
                "end_offset": 1,
                "excerpt_sha256": "sha256:" + "0" * 64,
            }],
            **unit_fields,
        },
    }


def test_exact_fact_requires_subject_relation_and_value():
    need = route_information_need("How old am I?")
    decision = decide_sufficiency(need, [
        row("age", "atomic_fact", {
            "subject": "user", "relation": "age", "value": "45",
            "polarity": "positive",
        })
    ])
    assert decision.status == "sufficient"
    assert decision.missing_slots == ()


def test_exact_fact_must_match_the_query_obligation_not_only_its_shape():
    need = route_information_need("How old am I?")
    decision = decide_sufficiency(need, [
        row("food", "atomic_fact", {
            "subject": "user", "relation": "favorite food", "value": "pasta",
            "polarity": "positive",
        })
    ])
    assert decision.status == "unsupported"
    assert decision.evidence_ids == ()


def test_exact_fact_requires_entity_and_relation_not_either_one():
    need = route_information_need("What is Alice age?")
    for candidate in (
        row("wrong-relation", "atomic_fact", {
            "subject": "Alice", "relation": "food", "value": "pasta",
            "polarity": "positive",
        }),
        row("wrong-entity", "atomic_fact", {
            "subject": "Bob", "relation": "age", "value": "45",
            "polarity": "positive",
        }),
    ):
        decision = decide_sufficiency(need, [candidate])
        assert decision.status == "unsupported"


def test_unknown_relation_is_preserved_and_cannot_match_another_fact():
    need = route_information_need("What is Alice salary?")
    assert need.obligations == ({"entity": "alice", "relation": "salary"},)
    decision = decide_sufficiency(need, [
        row("alice-age", "atomic_fact", {
            "subject": "Alice", "relation": "age", "value": "45",
            "polarity": "positive",
        })
    ])
    assert decision.status == "unsupported"


def test_multiword_relation_requires_its_distinguishing_terms():
    need = route_information_need("What is my favorite food?")
    decision = decide_sufficiency(need, [
        row("favorite-color", "atomic_fact", {
            "subject": "user", "relation": "favorite color", "value": "teal",
            "polarity": "positive",
        })
    ])
    assert decision.status == "unsupported"


def test_billing_email_does_not_match_work_email():
    need = route_information_need("What is my billing email?")
    assert need.obligations == ({"entity": "user", "relation": "billing email"},)
    decision = decide_sufficiency(need, [
        row("work-email", "atomic_fact", {
            "subject": "user", "relation": "work email", "value": "work@example.test",
            "polarity": "positive",
        })
    ])
    assert decision.status == "unsupported"


def test_relation_qualifiers_are_not_discarded_or_collapsed():
    preferred = route_information_need("What is my preferred email?")
    assert decide_sufficiency(preferred, [row("billing", "atomic_fact", {
        "subject": "user", "relation": "billing email",
        "value": "billing@example.test", "polarity": "positive",
    })]).status == "unsupported"

    primary_billing = route_information_need("What is my primary billing email?")
    assert primary_billing.obligations[0]["relation"] == "primary billing email"
    assert decide_sufficiency(primary_billing, [row("secondary", "atomic_fact", {
        "subject": "user", "relation": "secondary billing email",
        "value": "secondary@example.test", "polarity": "positive",
    })]).status == "unsupported"


def test_year_temporal_target_accepts_a_date_within_that_year():
    need = route_information_need("What was Alice age in 2020?")
    decision = decide_sufficiency(need, [
        row("alice-age-2020", "atomic_fact", {
            "subject": "Alice", "relation": "age", "value": "45",
            "polarity": "positive",
        }, observed_at="2020-06-01T00:00:00Z")
    ])
    assert decision.status == "sufficient"


def test_compound_polarity_and_time_obligations_fail_closed():
    compound = route_information_need("What is Alice age and Bob city?")
    decision = decide_sufficiency(compound, [
        row("alice-age", "atomic_fact", {
            "subject": "Alice", "relation": "age", "value": "45",
            "polarity": "positive",
        })
    ])
    assert decision.status in {"partial", "unsupported"}
    assert decision.status != "sufficient"

    from dataclasses import replace
    historical_negative = replace(
        route_information_need("What is Alice age?"),
        polarity="negative", temporal_target="2020-01-01T00:00:00Z",
    )
    decision = decide_sufficiency(historical_negative, [
        row("current-positive", "atomic_fact", {
            "subject": "Alice", "relation": "age", "value": "45",
            "polarity": "positive",
        }, observed_at="2026-01-01T00:00:00Z")
    ])
    assert decision.status == "unsupported"


def test_compound_temporal_targets_remain_bound_to_their_clauses():
    need = route_information_need("Compare Alice age in 2020 and Bob city in 2021")
    assert [item["temporal_target"] for item in need.obligations] == ["2020", "2021"]
    decision = decide_sufficiency(need, [
        row("alice", "atomic_fact", {
            "subject": "Alice", "relation": "age", "value": "45",
            "polarity": "positive",
        }, observed_at="2020-06-01T00:00:00Z"),
        row("bob-wrong-year", "atomic_fact", {
            "subject": "Bob", "relation": "city", "value": "Paris",
            "polarity": "positive",
        }, observed_at="2020-07-01T00:00:00Z"),
    ])
    assert decision.status in {"partial", "unsupported"}
    assert decision.status != "sufficient"

    correct = decide_sufficiency(need, [
        row("alice-correct", "atomic_fact", {
            "subject": "Alice", "relation": "age", "value": "45",
            "polarity": "positive",
        }, observed_at="2020-06-01T00:00:00Z"),
        row("bob-correct", "atomic_fact", {
            "subject": "Bob", "relation": "city", "value": "Paris",
            "polarity": "positive",
        }, observed_at="2021-07-01T00:00:00Z"),
    ])
    assert correct.status == "sufficient"


def test_procedure_with_missing_conditions_and_completion_is_partial():
    need = route_information_need("How should I publish the package?")
    decision = decide_sufficiency(need, [
        row("procedure", "procedure", {
            "goal": "publish the package",
            "steps": [{"ordinal": 1, "instruction": "run tests"}],
            "prerequisites": [],
            "completion_evidence": [],
        })
    ])
    assert decision.status == "partial"
    assert decision.missing_slots == ("conditions", "completion")


def test_conflicting_current_values_are_not_reported_sufficient():
    need = route_information_need("How old am I?")
    decision = decide_sufficiency(need, [
        row("age-45", "atomic_fact", {
            "subject": "user", "relation": "age", "value": "45",
            "polarity": "positive",
        }),
        row("age-46", "atomic_fact", {
            "subject": "user", "relation": "age", "value": "46",
            "polarity": "positive",
        }),
    ])
    assert decision.status == "contradictory"
    assert decision.evidence_ids == ("age-45",)
    assert decision.contradiction_ids == ("age-46",)


def test_expired_evidence_is_stale_and_unrelated_evidence_is_unsupported():
    current_need = route_information_need("What is the current selected model?")
    stale = decide_sufficiency(current_need, [
        row("model-old", "environment_state", {
            "entity": "runtime", "relation": "selected model", "value": "qwen",
            "polarity": "positive",
        }, valid_until="2020-01-01T00:00:00+00:00")
    ])
    assert stale.status == "stale"

    unsupported = decide_sufficiency(
        route_information_need("How old am I?"),
        [row("rule", "durable_rule", {
            "condition": "when deploying", "required_action": "run tests",
            "exceptions": [],
        })],
    )
    assert unsupported.status == "unsupported"
    assert unsupported.evidence_ids == ()


def test_irrelevant_conflicts_do_not_create_evidence_free_contradiction():
    need = route_information_need("How should I publish the package?")
    decision = decide_sufficiency(need, [
        row("one", "environment_state", {
            "entity": "service", "relation": "status", "value": "ready",
            "polarity": "positive",
        }),
        row("two", "environment_state", {
            "entity": "service", "relation": "status", "value": "stopped",
            "polarity": "positive",
        }),
    ])
    assert decision.status == "unsupported"
    assert decision.evidence_ids == ()
    assert decision.contradiction_ids == ()


def test_structured_state_partitions_are_complementary_not_contradictory():
    need = route_information_need("What is the current selected model?")
    decision = decide_sufficiency(need, [
        row("one", "environment_state", {
            "entity": "runtime", "relation": "selected model", "value": "qwen ",
            "polarity": "positive",
        }, fact_key="runtime_selected_model_chunk_0000"),
        row("two", "environment_state", {
            "entity": "runtime", "relation": "selected model", "value": "3.5",
            "polarity": "positive",
        }, fact_key="runtime_selected_model_chunk_0001"),
    ])
    assert decision.status == "sufficient"
    assert decision.contradiction_ids == ()
