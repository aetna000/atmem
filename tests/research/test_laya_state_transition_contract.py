import copy
import hashlib
import json

import pytest

from research.laya_memory_evidence.transition_contract import (
    validate_evaluation_request,
    validate_transition_example,
    validate_typed_response,
)


DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64


def _canonical_digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _request(question=None):
    return {
        "format": "laya-evaluation-request-v2",
        "schema_version": "2.0.0",
        "request_id": "request-1",
        "formation_plan_version": "memory-formation-plan-v2",
        "scope_id": "scope-1",
        "canonical_generation": 7,
        "observation": {
            "id": "observation-1",
            "content": "Actually, call me Sara rather than Mona.",
            "speaker_role": "user",
            "source_digest": DIGEST,
        },
        "retrieved_memories": [{
            "id": "memory-1",
            "content": "The user prefers to be called Mona.",
            "lifecycle": "active",
            "source_digest": DIGEST,
            "content_digest": OTHER_DIGEST,
            "retrieval_score": 0.94,
            "memory_class": "preference",
        }],
        "retrieval_receipt": {
            "retriever_revision": "retriever-v1",
            "requested_top_k": 8,
            "returned_count": 1,
            "complete": True,
            "truncated": False,
            "result_digest": DIGEST,
        },
        "question": question or {
            "question_id": "formation.operation.v2",
            "type": "choice",
            "instructions": "Select the memory transition.",
            "options": [
                {"id": "STORE_NEW", "description": "Create a distinct memory."},
                {"id": "SUPERSEDE_EXISTING", "description": "Replace the active state."},
            ],
        },
    }


def _choice_response():
    return {
        "format": "laya-choice-response-v2",
        "schema_version": "2.0.0",
        "request_id": "request-1",
        "question_id": "formation.operation.v2",
        "type": "choice",
        "choice": "SUPERSEDE_EXISTING",
        "probabilities": {"STORE_NEW": 0.08, "SUPERSEDE_EXISTING": 0.92},
        "confidence": 0.89,
    }


def _transition():
    canonical_records = [{
        "id": "memory-1", "content": "The user prefers to be called Mona.",
        "status": "active", "generation": 0,
        "memory_class": "preference",
    }]
    return {
        "format": "memory-transition-example-v2",
        "schema_version": "2.0.0",
        "transition_id": "transition-1",
        "trajectory_id": "trajectory-1",
        "partition": "train",
        "pre_state": {
            "snapshot_id": "sqlite-snapshot-1",
            "snapshot_digest": DIGEST,
            "vector_snapshot_id": "vector-snapshot-1",
            "vector_snapshot_digest": OTHER_DIGEST,
            "canonical_generation": 7,
            "canonical_state_digest": _canonical_digest(canonical_records),
            "canonical_records": canonical_records,
        },
        "request": _request(),
        "expected_response": _choice_response(),
        "expected_operation": "SUPERSEDE_EXISTING",
        "expected_target_id": "memory-1",
        "required_evidence_memory_ids": ["memory-1"],
        "expected_post_state_digest": DIGEST,
        "acceptable_abstention": False,
        "retrieval_evidence": {
            "receipt": {
                "format": "atmem-frozen-retrieval-receipt-v2",
                "request_id": "retrieval-request-1",
                "candidate_set_id": "candidate-set-1",
                "candidate_digest": DIGEST,
                "canonical_generation": 7,
                "requested_top_k": 8,
                "returned_count": 1,
                "complete": True,
                "truncated": False,
                "retriever_revision": "retriever-v1",
            },
            "digest": OTHER_DIGEST,
        },
        "provenance": {
            "source_id": "public-authentic-source",
            "source_revision": "revision-1",
            "conversation_id": "conversation-1",
            "license": "reviewed-license",
            "adjudication_mode": "codex-only",
            "content_digest": OTHER_DIGEST,
        },
    }


def test_accepts_stateful_choice_transition():
    validate_transition_example(_transition())


def test_request_rejects_language_metadata_from_model_visible_state():
    request = _request()
    request["observation"]["language"] = "en"
    with pytest.raises(ValueError, match="unknown fields"):
        validate_evaluation_request(request)


def test_request_rejects_incomplete_retrieval_claimed_complete_and_truncated():
    request = _request()
    request["retrieval_receipt"]["truncated"] = True
    with pytest.raises(ValueError, match="complete retrieval"):
        validate_evaluation_request(request)


def test_choice_rejects_partial_probability_distribution():
    response = _choice_response()
    del response["probabilities"]["STORE_NEW"]
    with pytest.raises(ValueError, match="exactly"):
        validate_typed_response(response, _request()["question"], request_id="request-1")


def test_choice_rejects_selected_non_argmax():
    response = _choice_response()
    response["choice"] = "STORE_NEW"
    with pytest.raises(ValueError, match="argmax"):
        validate_typed_response(response, _request()["question"], request_id="request-1")


def test_noul_probability_is_probability_statement_is_true():
    question = {
        "question_id": "formation.is_durable.v2",
        "type": "noul",
        "instructions": "Is the observation likely to remain useful?",
    }
    response = {
        "format": "laya-noul-response-v2",
        "schema_version": "2.0.0",
        "request_id": "request-1",
        "question_id": "formation.is_durable.v2",
        "type": "noul",
        "noul": 0.86,
    }
    validate_typed_response(response, question, request_id="request-1")


def test_noul_strict_jev_response_rejects_separate_confidence():
    question = {
        "question_id": "formation.is_durable.v2",
        "type": "noul",
        "instructions": "Is the observation likely to remain useful?",
    }
    response = {
        "format": "laya-noul-response-v2",
        "schema_version": "2.0.0",
        "request_id": "request-1",
        "question_id": "formation.is_durable.v2",
        "type": "noul",
        "noul": 0.86,
        "confidence": 0.81,
    }
    with pytest.raises(ValueError, match="unknown fields"):
        validate_typed_response(response, question, request_id="request-1")


def test_score_must_equal_distribution_expected_value():
    question = {
        "question_id": "formation.future_utility.v2",
        "type": "score",
        "instructions": "Rate future utility.",
        "criteria": ["low", "medium", "high"],
    }
    response = {
        "format": "laya-score-response-v2",
        "schema_version": "2.0.0",
        "request_id": "request-1",
        "question_id": "formation.future_utility.v2",
        "type": "score",
        "score": 1.6,
        "probabilities": {"0": 0.1, "1": 0.2, "2": 0.7},
        "confidence": 0.82,
        "legend": {"0": "low", "1": "medium", "2": "high"},
    }
    validate_typed_response(response, question, request_id="request-1")
    response["score"] = 1.7
    with pytest.raises(ValueError, match="expected value"):
        validate_typed_response(response, question, request_id="request-1")


def test_score_rejects_legend_drift():
    question = {
        "question_id": "formation.future_utility.v2",
        "type": "score",
        "instructions": "Rate future utility.",
        "criteria": ["low", "high"],
    }
    response = {
        "format": "laya-score-response-v2",
        "schema_version": "2.0.0",
        "request_id": "request-1",
        "question_id": "formation.future_utility.v2",
        "type": "score",
        "score": 0.8,
        "probabilities": {"0": 0.2, "1": 0.8},
        "confidence": 0.76,
        "legend": {"0": "high", "1": "low"},
    }
    with pytest.raises(ValueError, match="legend"):
        validate_typed_response(response, question, request_id="request-1")


def test_relational_transition_requires_retrieved_target():
    example = _transition()
    example["expected_target_id"] = "memory-not-retrieved"
    with pytest.raises(ValueError, match="retrieved target"):
        validate_transition_example(example)


def test_free_form_reasoning_and_generated_memory_are_rejected():
    example = _transition()
    example["expected_response"]["reasoning"] = "hidden chain of thought"
    with pytest.raises(ValueError, match="unknown fields"):
        validate_transition_example(example)
    example = _transition()
    example["expected_response"]["new_memory"] = "The user is called Sara."
    with pytest.raises(ValueError, match="unknown fields"):
        validate_transition_example(example)


def test_pre_state_generation_must_match_request():
    example = copy.deepcopy(_transition())
    example["pre_state"]["canonical_generation"] = 6
    with pytest.raises(ValueError, match="generations differ"):
        validate_transition_example(example)


def test_bounded_retrieval_may_be_subset_of_canonical_pre_state():
    example = copy.deepcopy(_transition())
    example["pre_state"]["canonical_records"].append({
        "id": "memory-2", "content": "Unrelated preference.",
        "status": "active", "generation": 0, "memory_class": "preference",
    })
    example["pre_state"]["canonical_state_digest"] = _canonical_digest(
        example["pre_state"]["canonical_records"]
    )
    validate_transition_example(example)


def test_retrieval_evidence_must_match_request_generation_and_count():
    example = copy.deepcopy(_transition())
    example["retrieval_evidence"]["receipt"]["canonical_generation"] = 6
    with pytest.raises(ValueError, match="generations differ"):
        validate_transition_example(example)
    example = copy.deepcopy(_transition())
    example["retrieval_evidence"]["receipt"]["returned_count"] = 0
    with pytest.raises(ValueError, match="counts do not match"):
        validate_transition_example(example)
