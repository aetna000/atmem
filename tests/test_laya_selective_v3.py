from __future__ import annotations

import hashlib

import pytest

from atmem.laya_formation.selective_v3 import (
    DEFAULT_LEARNED_OPERATIONS,
    JointChoiceResultV3,
    build_joint_choice_v3,
    evaluate_joint_choice_v3,
)


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _memory(index: int, score: float) -> dict:
    text = f"memory {index}"
    return {
        "id": f"real-memory-{index}", "content": text, "lifecycle": "active",
        "source_digest": _digest(f"source {index}"),
        "content_digest": _digest(text), "retrieval_score": score,
        "memory_class": "durable_fact",
    }


def _observation() -> dict:
    text = "Use metric units for all measurements."
    return {
        "id": "obs-1", "content": text, "speaker_role": "user",
        "source_digest": _digest(text),
    }


def test_joint_choice_is_bounded_opaque_and_deterministic() -> None:
    memories = [_memory(index, 1.0 - index / 100.0) for index in range(70)]
    left = build_joint_choice_v3(
        request_id="request-1", scope_id="scope-1", canonical_generation=4,
        observation=_observation(), retrieved_memories=memories,
    )
    right = build_joint_choice_v3(
        request_id="request-1", scope_id="scope-1", canonical_generation=4,
        observation=_observation(), retrieved_memories=list(reversed(memories)),
    )
    assert left.request == right.request
    assert left.bindings == right.bindings
    assert len(left.request["retrieved_memories"]) == 32
    assert len(left.request["question"]["options"]) == (
        2 + 32 * (len(DEFAULT_LEARNED_OPERATIONS) - 2)
    )
    assert len(left.request["question"]["options"]) <= 255
    assert all(item["id"].startswith("target_") for item in left.request["retrieved_memories"])
    serialized = str(left.request)
    assert "real-memory-" not in serialized


def test_required_exact_target_survives_top_k() -> None:
    memories = [_memory(index, 1.0 - index / 100.0) for index in range(40)]
    bundle = build_joint_choice_v3(
        request_id="request-2", scope_id="scope-1", canonical_generation=4,
        observation=_observation(), retrieved_memories=memories,
        required_target_ids={"real-memory-39"},
    )
    assert "real-memory-39" in {item.target_memory_id for item in bundle.bindings}


def test_more_than_32_required_targets_fails_before_model_call() -> None:
    memories = [_memory(index, 1.0 - index / 100.0) for index in range(40)]
    with pytest.raises(ValueError, match="required targets exceed"):
        build_joint_choice_v3(
            request_id="request-3", scope_id="scope-1", canonical_generation=4,
            observation=_observation(), retrieved_memories=memories,
            required_target_ids={item["id"] for item in memories},
        )


def test_evaluation_calls_engine_exactly_once_and_maps_target() -> None:
    bundle = build_joint_choice_v3(
        request_id="request-4", scope_id="scope-1", canonical_generation=4,
        observation=_observation(), retrieved_memories=[_memory(1, 0.9)],
    )
    selected = next(
        item for item in bundle.bindings
        if item.operation == "UPDATE_EXISTING"
    )
    calls = 0

    def engine(request: dict) -> dict:
        nonlocal calls
        calls += 1
        option_ids = [item["id"] for item in request["question"]["options"]]
        probabilities = {identity: 0.0 for identity in option_ids}
        probabilities[selected.option_id] = 1.0
        return {
            "format": "laya-choice-response-v2", "schema_version": "2.0.0",
            "request_id": request["request_id"],
            "question_id": request["question"]["question_id"], "type": "choice",
            "choice": selected.option_id, "probabilities": probabilities,
            "confidence": 0.98,
        }

    result = evaluate_joint_choice_v3(engine, bundle, confidence_threshold=0.8)
    assert calls == 1
    assert result.operation == "UPDATE_EXISTING"
    assert result.target_memory_id == "real-memory-1"
    assert result.disposition == "model_delegated"


def test_invalid_or_low_confidence_output_never_authorizes() -> None:
    bundle = build_joint_choice_v3(
        request_id="request-5", scope_id="scope-1", canonical_generation=4,
        observation=_observation(), retrieved_memories=[_memory(1, 0.9)],
    )

    def invalid_engine(request: dict) -> dict:
        options = [item["id"] for item in request["question"]["options"]]
        return {
            "format": "laya-choice-response-v2", "schema_version": "2.0.0",
            "request_id": request["request_id"],
            "question_id": request["question"]["question_id"], "type": "choice",
            "choice": options[0],
            "probabilities": {identity: 0.1 for identity in options},
            "confidence": 0.2,
        }

    result = evaluate_joint_choice_v3(invalid_engine, bundle)
    assert isinstance(result, JointChoiceResultV3)
    assert result.operation == "REVIEW"
    assert result.disposition == "runtime_failed"
    assert result.target_memory_id is None
