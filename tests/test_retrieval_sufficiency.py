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
