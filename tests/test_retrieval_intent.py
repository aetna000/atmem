from atmem.contracts import RetrievalBudget
from atmem import Memory
from atmem.retrieve.intent import decompose_information_need, route_information_need
from atmem.retrieve.profiles import profile_for_need


def test_product_questions_route_to_distinct_evidence_needs():
    cases = {
        "How old am I?": "exact_fact",
        "What is my current account status?": "current_state",
        "What changed before and after the upload?": "state_change",
        "How do I publish a release step by step?": "ordered_task",
        "What failed last time and what workaround should I use?": "exception_risk",
        "Which channel should deployment updates use under our policy?": "rule_application",
        "Is the desktop feature available?": "assumption_check",
        "Compare the customer and invoice records together": "relational_synthesis",
    }
    for query, expected in cases.items():
        need = route_information_need(query)
        assert need.type == expected
        assert need.required_slots
        assert profile_for_need(need.type).context_bytes >= 256


def test_routing_is_deterministic_and_has_no_benchmark_vocabulary():
    first = route_information_need("What is my current local model?")
    second = route_information_need("  What is my current local model?  ")
    assert first == second
    assert first.need_id.startswith("need-")
    assert "benchmark" not in str(first.to_dict()).lower()


def test_answer_presentation_suffix_does_not_change_information_need():
    plain = route_information_need(
        'What is the action between "Delete Customer" and "Back"?'
    )
    formatted = route_information_need(
        'What is the action between "Delete Customer" and "Back"? '
        'Your final answer should be wrapped in \\boxed{}.'
    )
    assert plain.type == "exact_fact"
    assert formatted.type == plain.type
    assert formatted.required_slots == plain.required_slots


def test_compound_decomposition_is_bounded_and_preserves_parent_identity():
    parent, children = decompose_information_need(
        "What is the current status and what changed and how do I recover and what failed?",
        budget=RetrievalBudget(subqueries=2),
    )
    assert len(children) == 2
    assert all(child.parent_need_id == parent.need_id for child in children)
    assert len({child.need_id for child in children}) == 2


def test_negation_is_preserved_as_an_evidence_requirement():
    need = route_information_need("Which food should I never order?")
    assert need.polarity == "negative"
    assert need.type == "rule_application"


def test_memory_exposes_one_host_neutral_analysis_boundary():
    memory = Memory(":memory:", auto_vectors=False)
    try:
        result = memory.analyze_information_need("What is my current account status?")
        assert result["need"]["type"] == "current_state"
        assert result["profile"]["profile_id"] == "fact-and-state-v1"
        assert result["budget"]["format"] == "atmem-retrieval-budget-v1"
    finally:
        memory.close()
