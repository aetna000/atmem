from __future__ import annotations

from atmem.retrieve.intent import (
    comparison_retrieval_queries,
    contextual_retrieval_query,
    evidence_anchor_queries,
    plan_retrieval_queries,
    route_information_need,
    salient_retrieval_query,
)


def test_query_plan_preserves_explicit_ui_anchors() -> None:
    query = (
        'On customer detail pages, what is between "Delete Customer" and '
        '"Back" in the top toolbar?'
    )
    plan = plan_retrieval_queries(query)
    assert plan[0] == query
    assert "Delete Customer Back" in plan
    assert len(plan) <= 4
    assert evidence_anchor_queries(query) == ("Delete Customer", "Back")


def test_query_plan_is_bounded_deterministic_and_answer_free() -> None:
    query = "Which forum has the second-most submissions?"
    need = route_information_need(query)
    first = plan_retrieval_queries(query, need=need, limit=3)
    second = plan_retrieval_queries(query, need=need, limit=3)
    assert first == second
    assert 1 <= len(first) <= 3
    assert all("relationship" not in value for value in first)


def test_query_plan_rejects_invalid_inputs() -> None:
    try:
        plan_retrieval_queries("   ")
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("empty query should fail")


def test_salient_query_removes_action_schema_and_output_formatting() -> None:
    query = (
        "I am using our custom shopping admin website. I would like to notify "
        "a user to reorder a recent pending order. I entered its detail page. "
        "Action Space: scroll(delta_x: float), click(bid: str), fill(bid: str). "
        "Your final answer should be an English number wrapped in \\boxed{}."
    )
    salient = salient_retrieval_query(query)
    assert salient == "notify user reorder recent pending order"
    assert "scroll" not in salient
    assert "boxed" not in salient
    assert salient in plan_retrieval_queries(query)


def test_query_plan_ignores_plural_and_imperative_output_instructions() -> None:
    query = (
        "I am on the page that lists all products. I have selected the target "
        "items. At minimum, how many buttons do I click if the final state is "
        "`Archived`? Say the number in English and then list the button names. "
        "Your final answers should be wrapped in \\boxed{}."
    )
    salient = salient_retrieval_query(query)
    need = route_information_need(query)
    assert salient == "minimum buttons state archived"
    assert "say" not in salient
    assert "boxed" not in salient
    assert need.relation_or_action != "using"


def test_product_preamble_does_not_become_personal_memory_obligation() -> None:
    need = route_information_need(
        'I am working with two forms. In both forms, "Priority" is 5, true or false?'
    )

    assert need.type == "assumption_check"
    assert need.entities == ()
    assert all(item.get("entity") != "user" for item in need.obligations)


def test_direct_personal_fact_still_routes_to_user() -> None:
    need = route_information_need("How old am I?")

    assert need.entities == ("user",)
    assert need.obligations == ({"entity": "user", "relation": "age"},)


def test_contextual_query_keeps_entity_clause_for_absent_requested_state() -> None:
    query = (
        "I am on the page that lists all products. I want to take down a product "
        "from the website display. At minimum, how many buttons do I click if "
        "the final state is `Archived`?"
    )
    salient = salient_retrieval_query(query)

    assert "archived" in salient
    assert contextual_retrieval_query(query, excluding=salient) == (
        "want take down product display"
    )
    assert "want take down product display" in plan_retrieval_queries(query)


def test_multiword_literal_gets_exact_probe_even_when_salient_contains_it() -> None:
    query = "On the blank hardware form, what value is shown in `Managed by`?"

    plan = plan_retrieval_queries(query)
    assert plan[1] == "Managed by"


def test_post_action_value_question_routes_as_current_state() -> None:
    need = route_information_need(
        "After clicking New and loading the blank form, what default value is "
        "shown in `Managed by`?"
    )

    assert need.type == "current_state"
    assert need.required_slots == ("entity", "relation", "current_value", "validity")
    assert need.temporal_target == "current"
    assert need.entities == ()
    assert need.obligations == ({"relation": "Managed by"},)


def test_explicit_change_after_action_remains_state_change() -> None:
    need = route_information_need("What changes after applying the filter?")

    assert need.type == "state_change"
    assert need.required_slots == ("entity", "before", "action", "after", "event_time")


def test_exact_names_for_presupposed_set_routes_to_assumption_check() -> None:
    need = route_information_need(
        "What are the exact two item names for the Linux and Chromebook laptops?"
    )
    assert need.type == "assumption_check"
    assert need.required_slots == ("proposition", "polarity", "applicability")


def test_observed_failure_wins_over_incidental_after_language() -> None:
    need = route_information_need(
        "After I press Execute Now the deletion does not happen. What issue or action remains?"
    )
    assert need.type == "exception_risk"
    assert need.required_slots == ("trigger", "failure", "safe_action")


def test_post_action_assignment_is_a_transition_not_an_observed_default() -> None:
    need = route_information_need(
        "After I clear the `Assigned to` field, what value should I set the "
        "`State` field to before clicking `Update`?"
    )

    assert need.type == "state_change"
    assert need.obligations == ({"relation": "State"},)


def test_multiple_choice_options_do_not_become_memory_obligations() -> None:
    need = route_information_need(
        "In the deployment workflow, which rule is correct?\n\n"
        "A. Keep the old order and ignore risk.\n"
        "B. Schedule by risk and keep a one-day gap."
    )

    assert need.type == "ordered_task"
    assert need.obligations == ({"action": "workflow"},)


def test_contextual_query_prefers_named_entities_over_product_preamble() -> None:
    query = (
        "I am working with a few forms in our portal. Create Incident vs Problem. "
        'In both forms, is the default value for "Priority" 5?'
    )
    salient = salient_retrieval_query(query)

    assert contextual_retrieval_query(query, excluding=salient) == (
        "create incident problem"
    )
    plan = plan_retrieval_queries(query)
    assert "incident new record Priority" in plan
    assert "problem new record Priority" in plan
    need = route_information_need(query)
    assert {"incident", "problem", "priority"} <= set(need.evidence_terms)


def test_comparison_query_probes_each_entity_with_exact_relation() -> None:
    query = (
        'I am working with forms. Create Incident vs Problem. In both forms, '
        'is the default value for "Priority" 5?'
    )
    assert comparison_retrieval_queries(query) == (
        "incident new record Priority",
        "problem new record Priority",
    )
    assert plan_retrieval_queries(query)[:3] == (
        query,
        "incident new record Priority",
        "problem new record Priority",
    )
