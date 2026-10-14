from __future__ import annotations

from atmem.laya_formation.formation_v2 import (
    FormationPlanV2, FormationRulingV2, apply_ruling_to_proposals,
    revalidate_ruling,
)
from atmem.laya_formation.runtime import LayaTypedDecisionEngineV2
from atmem.laya_formation.packing import pack_evaluation_request_v2
from atmem.laya_formation.escalation import AtBotFormationEscalator, EscalationPolicy
from atmem.laya_formation.formation_v2 import evaluation_request, operation_question


def _noul(question_id: str, value: float, request_id: str) -> dict:
    return {
        "format": "laya-noul-response-v2", "schema_version": "2.0.0",
        "request_id": request_id, "question_id": question_id,
        "type": "noul", "noul": value,
    }


def _choice(
    question_id: str, choice: str, probabilities: dict[str, float],
    request_id: str, *, confidence: float = 0.9,
) -> dict:
    return {
        "format": "laya-choice-response-v2", "schema_version": "2.0.0",
        "request_id": request_id, "question_id": question_id,
        "type": "choice", "choice": choice,
        "probabilities": probabilities, "confidence": confidence,
    }


def _score(request_id: str) -> dict:
    return {
        "format": "laya-score-response-v2", "schema_version": "2.0.0",
        "request_id": request_id,
        "question_id": "formation.future_utility.v2", "type": "score",
        "score": 3.5,
        "probabilities": {"0": 0.0, "1": 0.0, "2": 0.1, "3": 0.3, "4": 0.6},
        "confidence": 0.81,
        "legend": {
            "0": "No expected future usefulness",
            "1": "Limited future usefulness",
            "2": "Moderate future usefulness",
            "3": "High future usefulness",
            "4": "Very high recurring usefulness",
        },
    }


def test_plan_builds_supersede_ruling_without_generating_memory_text() -> None:
    request_ids = {
        "formation.context_sufficient.v2": "request-context",
        "formation.is_durable.v2": "request-durable",
        "formation.memory_class.v2": "request-class",
        "formation.operation.v2": "request-operation",
        "formation.target.v2": "request-target",
        "formation.future_utility.v2": "request-score",
    }
    responses = {
        "formation.context_sufficient.v2": _noul(
            "formation.context_sufficient.v2", 0.98, "request-context",
        ),
        "formation.is_durable.v2": _noul(
            "formation.is_durable.v2", 0.96, "request-durable",
        ),
        "formation.memory_class.v2": _choice(
            "formation.memory_class.v2", "preference", {
                "preference": 0.91, "durable_fact": 0.02, "procedure": 0.01,
                "commitment": 0.01, "relationship": 0.01, "episode": 0.01,
                "temporary_state": 0.01, "sensitive": 0.01, "non_memory": 0.01,
            }, "request-class",
        ),
        "formation.operation.v2": _choice(
            "formation.operation.v2", "SUPERSEDE_EXISTING", {
                "STORE_NEW": 0.01, "UPDATE_EXISTING": 0.03,
                "SUPERSEDE_EXISTING": 0.9, "DUPLICATE": 0.01,
                "DO_NOT_STORE": 0.04, "FORGET_EXISTING": 0.01,
            }, "request-operation", confidence=0.82,
        ),
        "formation.target.v2": _choice(
            "formation.target.v2", "memory-1",
            {"memory-1": 0.95, "memory-2": 0.05}, "request-target",
        ),
        "formation.future_utility.v2": _score("request-score"),
    }
    ruling = FormationPlanV2().build_ruling(
        responses=responses, request_ids=request_ids,
        authorized_targets=[
            {"id": "memory-1", "content": "Call the user Mona."},
            {"id": "memory-2", "content": "Use concise status updates."},
        ],
    )
    assert ruling.operation == "SUPERSEDE_EXISTING"
    assert ruling.memory_class == "preference"
    assert ruling.target_memory_id == "memory-1"
    assert ruling.future_utility_score == 3.5
    assert "memory_text" not in ruling.to_dict()


def test_plan_returns_review_when_context_is_insufficient() -> None:
    ruling = FormationPlanV2().build_ruling(
        responses={
            "formation.context_sufficient.v2": _noul(
                "formation.context_sufficient.v2", 0.2, "request-context",
            ),
        },
        request_ids={"formation.context_sufficient.v2": "request-context"},
        authorized_targets=[],
    )
    assert ruling.operation == "REVIEW"
    assert ruling.review_reason == "insufficient_context"


def test_plan_derives_do_not_store_from_low_durability_without_operation_call() -> None:
    ruling = FormationPlanV2().build_ruling(
        responses={
            "formation.context_sufficient.v2": _noul(
                "formation.context_sufficient.v2", 0.9, "request-context",
            ),
            "formation.is_durable.v2": _noul(
                "formation.is_durable.v2", 0.1, "request-durable",
            ),
        },
        request_ids={
            "formation.context_sufficient.v2": "request-context",
            "formation.is_durable.v2": "request-durable",
        },
        authorized_targets=[],
    )
    assert ruling.operation == "DO_NOT_STORE"
    assert ruling.review_required is False


def test_single_authorized_target_is_selected_without_fake_choice() -> None:
    request_ids = {
        "formation.context_sufficient.v2": "request-context",
        "formation.is_durable.v2": "request-durable",
        "formation.memory_class.v2": "request-class",
        "formation.operation.v2": "request-operation",
    }
    responses = {
        "formation.context_sufficient.v2": _noul(
            "formation.context_sufficient.v2", 0.9, "request-context",
        ),
        "formation.is_durable.v2": _noul(
            "formation.is_durable.v2", 0.9, "request-durable",
        ),
        "formation.memory_class.v2": _choice(
            "formation.memory_class.v2", "durable_fact", {
                "preference": 0.01, "durable_fact": 0.92, "procedure": 0.01,
                "commitment": 0.01, "relationship": 0.01, "episode": 0.01,
                "temporary_state": 0.01, "sensitive": 0.01, "non_memory": 0.01,
            }, "request-class",
        ),
        "formation.operation.v2": _choice(
            "formation.operation.v2", "DUPLICATE", {
                "STORE_NEW": 0.01, "UPDATE_EXISTING": 0.01,
                "SUPERSEDE_EXISTING": 0.01, "DUPLICATE": 0.94,
                "DO_NOT_STORE": 0.02, "FORGET_EXISTING": 0.01,
            }, "request-operation",
        ),
    }
    ruling = FormationPlanV2().build_ruling(
        responses=responses, request_ids=request_ids,
        authorized_targets=[{"id": "memory-1", "content": "Same meaning."}],
    )
    assert ruling.operation == "DUPLICATE"
    assert ruling.target_memory_id == "memory-1"
    assert ruling.target_probability == 1.0


def _engine_request(question: dict) -> dict:
    digest = "sha256:" + "a" * 64
    return {
        "format": "laya-evaluation-request-v2", "schema_version": "2.0.0",
        "request_id": "engine-request", "formation_plan_version": "memory-formation-plan-v2",
        "scope_id": "scope-1", "canonical_generation": 1,
        "observation": {
            "id": "observation-1", "content": "Remember this.",
            "speaker_role": "user", "source_digest": digest,
        },
        "retrieved_memories": [],
        "retrieval_receipt": {
            "retriever_revision": "retriever-v2", "requested_top_k": 8,
            "returned_count": 0, "complete": True, "truncated": False,
            "result_digest": digest,
        },
        "question": question,
    }


class _Agent:
    def __init__(self, answer: dict, *, truncated: bool = False):
        self.answer = answer
        self.truncated = truncated
        self.questions = None

    def system_one(self, state, questions, **kwargs):
        self.questions = questions
        question_id = next(iter(questions))
        return {
            "answers": {question_id: self.answer},
            "usage": {
                "input_tokens": 12, "output_tokens": 0,
                "truncated": self.truncated,
                "state_tokens_dropped": 1 if self.truncated else 0,
            },
        }


def test_v2_engine_projects_full_laya_noul_to_strict_response() -> None:
    question = {
        "question_id": "formation.is_durable.v2", "type": "noul",
        "instructions": "Is this durable?",
    }
    agent = _Agent({
        "type": "noul", "noul": 0.87, "confidence": 0.87,
        "answer_confidence": 0.87, "action": {"act_probability": 1.0},
    })
    response = LayaTypedDecisionEngineV2(agent)(_engine_request(question))
    assert response == {
        "format": "laya-noul-response-v2", "schema_version": "2.0.0",
        "request_id": "engine-request", "question_id": "formation.is_durable.v2",
        "type": "noul", "noul": 0.87,
    }
    assert agent.questions["formation.is_durable.v2"] == {
        "type": "noul", "instructions": "Is this durable?",
    }


def test_v2_engine_rejects_any_state_truncation() -> None:
    question = {
        "question_id": "formation.is_durable.v2", "type": "noul",
        "instructions": "Is this durable?",
    }
    agent = _Agent({"type": "noul", "noul": 0.87}, truncated=True)
    import pytest
    with pytest.raises(ValueError, match="truncated"):
        LayaTypedDecisionEngineV2(agent)(_engine_request(question))


class _PackingAdapter:
    revision = "tokenizer-revision"

    def head_token_count(self, question, head_max_len):
        del head_max_len
        count = 2 if question["t"] == "noul" else len(question["crit"])
        return 4, count

    def serialize_and_encode_state(self, state):
        import json
        serialized = json.dumps(state, sort_keys=True, ensure_ascii=False)
        return serialized, list(range(len(serialized)))


def test_v2_packer_keeps_complete_state_and_reports_overflow() -> None:
    request = _engine_request({
        "question_id": "formation.is_durable.v2", "type": "noul",
        "instructions": "Is this durable?",
    })
    packed = pack_evaluation_request_v2(
        adapter=_PackingAdapter(), question=request["question"],
        observation=request["observation"],
        retrieved_memories=request["retrieved_memories"], max_len=32,
    )
    assert packed.overflow is True
    assert packed.state_tokens > 0
    assert "Remember this." in packed.state


def test_governance_revalidation_does_not_replace_semantic_ruling() -> None:
    ruling = FormationRulingV2(
        operation="SUPERSEDE_EXISTING", memory_class="preference",
        target_memory_id="memory-1",
        operation_probability=0.9, target_probability=0.95,
        context_sufficient_probability=0.98, durable_probability=0.96,
        future_utility_score=3.5, review_required=False, review_reason=None,
    )
    receipt = revalidate_ruling(
        ruling, request_id="request-1", classifier="laya",
        expected_generation=4, observed_generation=4,
        allowed_target_ids=["memory-1"], policy_allowed=True,
    )
    assert receipt.authority_result == "AUTHORIZED_PROPOSAL"
    assert receipt.proposal["operation"] == "SUPERSEDE_EXISTING"


def test_forget_requires_separate_explicit_deletion_authority() -> None:
    ruling = FormationRulingV2(
        operation="FORGET_EXISTING", memory_class="preference",
        target_memory_id="memory-1",
        operation_probability=0.91, target_probability=0.98,
        context_sufficient_probability=0.99, durable_probability=0.99,
        future_utility_score=None, review_required=False, review_reason=None,
    )
    receipt = revalidate_ruling(
        ruling, request_id="request-forget", classifier="laya",
        expected_generation=2, observed_generation=2,
        allowed_target_ids=["memory-1"], policy_allowed=True,
    )
    assert receipt.authority_result == "REVIEW"
    assert receipt.authority_reason == "forget_requires_explicit_deletion_authority"


def test_receptor_replaces_default_add_with_exact_laya_target() -> None:
    from atmem.contracts import AuthorityScope
    from atmem.extract.formation import form_typed_proposals
    from atmem.extract.models import ProposalAction

    proposals = form_typed_proposals(
        "My preferred colour is blue.",
        scope=AuthorityScope("subject", "agent", "workspace"),
        source_id="source-1", formation_id="formation-1",
    )
    ruling = FormationRulingV2(
        operation="SUPERSEDE_EXISTING", memory_class="preference",
        target_memory_id="memory-1",
        operation_probability=0.88, target_probability=0.97,
        context_sufficient_probability=0.99, durable_probability=0.95,
        future_utility_score=3.5, review_required=False, review_reason=None,
    )
    result = apply_ruling_to_proposals(
        ruling, proposals, authorized_targets=[{
            "id": "memory-1", "content": "My preferred colour is red.",
            "generation": 7, "status": "active",
        }],
    )
    assert len(result) == 1
    assert result[0].action is ProposalAction.SUPERSEDE
    assert result[0].affected_record_ids == ("memory-1",)
    assert result[0].preconditions[0].generation == 7
    assert result[0].fact == proposals[0].fact


def test_governance_revalidation_fails_closed_on_stale_state() -> None:
    ruling = FormationRulingV2(
        operation="STORE_NEW", memory_class="durable_fact", target_memory_id=None,
        operation_probability=0.9, target_probability=None,
        context_sufficient_probability=0.98, durable_probability=0.96,
        future_utility_score=3.5, review_required=False, review_reason=None,
    )
    receipt = revalidate_ruling(
        ruling, request_id="request-1", classifier="laya",
        expected_generation=4, observed_generation=5,
        allowed_target_ids=[], policy_allowed=True,
    )
    assert receipt.authority_result == "STALE_STATE"
    assert receipt.proposal["operation"] == "STORE_NEW"


def test_typed_choice_escalation_is_bounded_and_non_authoritative() -> None:
    class Client:
        def propose_formation_decision(self, *, payload, **kwargs):
            assert payload["format"] == "atmem-formation-escalation-request-v2"
            assert "authority_decision" not in payload
            return {
                "format": "atbot-formation-decision-proposal-v1",
                "request_id": payload["request_id"],
                "selected_choice_id": "STORE_NEW", "confidence": 0.8,
                "authority_decision": None, "canonical_storage": False,
                "provider": "test", "model": "test", "egress_class": "local",
                "usage": {"input_tokens": 50, "output_tokens": 4, "cost_usd": 0.0},
            }

    question = operation_question()
    request = evaluation_request(
        request_id="request-escalation", scope_id="scope-1",
        canonical_generation=1,
        observation={
            "id": "observation-1", "content": "Remember that I prefer blue.",
            "speaker_role": "user", "source_digest": "sha256:" + "a" * 64,
        },
        retrieved_memories=[], question=question,
    )
    low = _choice(
        question["question_id"], "STORE_NEW",
        {
            "STORE_NEW": 0.3, "UPDATE_EXISTING": 0.14,
            "SUPERSEDE_EXISTING": 0.14, "DUPLICATE": 0.14,
            "DO_NOT_STORE": 0.14, "FORGET_EXISTING": 0.14,
        }, "request-escalation", confidence=0.3,
    )
    response, receipt = AtBotFormationEscalator(
        client=Client(), policy=EscalationPolicy(enabled=True, max_calls=1),
    ).decide_typed(request, low, "calibrated_low_confidence")
    assert response["choice"] == "STORE_NEW"
    assert receipt["used"] is True
    assert receipt["disposition"] == "escalated_proposal"

