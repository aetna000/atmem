"""Strict vendor-neutral Laya/Jev V2 evaluation contracts.

This module is dependency-free and is the single validator used by product
inference and research dataset construction.  It validates the exact public
wire projection; model-internal output is converted before it reaches here.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "2.0.0"
REQUEST_FORMAT = "laya-evaluation-request-v2"
QUESTION_TYPES = frozenset({"choice", "noul", "score"})
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROBABILITY_TOLERANCE = 1e-6
_EXPECTED_SCORE_TOLERANCE = 1e-6


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, Any], *, required: set[str],
    optional: set[str] | None = None, name: str,
) -> None:
    optional = optional or set()
    missing = required - set(value)
    unknown = set(value) - required - optional
    if missing:
        raise ValueError(f"{name} is missing fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"{name} contains unknown fields: {sorted(unknown)}")


def _identifier(value: Any, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a bounded non-empty string")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be sha256:<64 lowercase hex>")
    return value


def _unit_interval(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and within [0,1]")
    return result


def _normalized_distribution(
    value: Any, expected_ids: Sequence[str], name: str,
) -> dict[str, float]:
    distribution = _object(value, name)
    if set(distribution) != set(expected_ids):
        raise ValueError(f"{name} must contain exactly the supplied identifiers")
    normalized = {
        key: _unit_interval(item, f"{name}.{key}")
        for key, item in distribution.items()
    }
    if not math.isclose(
        sum(normalized.values()), 1.0, abs_tol=_PROBABILITY_TOLERANCE,
    ):
        raise ValueError(f"{name} must sum to 1")
    return normalized


def validate_question(question: Mapping[str, Any]) -> None:
    question = _object(question, "question")
    question_type = question.get("type")
    if question_type not in QUESTION_TYPES:
        raise ValueError("question.type must be choice, noul, or score")
    common = {"question_id", "type"}
    _identifier(question.get("question_id"), "question.question_id")
    if question_type == "choice":
        _exact_keys(
            question, required=common | {"instructions", "options"},
            name="choice question",
        )
        _identifier(question["instructions"], "question.instructions", maximum=2_000)
        options = question["options"]
        if not isinstance(options, list) or not 2 <= len(options) <= 255:
            raise ValueError("choice question requires 2 to 255 options")
        option_ids: list[str] = []
        for index, raw in enumerate(options):
            option = _object(raw, f"question.options[{index}]")
            _exact_keys(option, required={"id", "description"}, name="choice option")
            option_ids.append(_identifier(option["id"], "choice option id", maximum=128))
            _identifier(option["description"], "choice option description", maximum=1_000)
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("choice option identifiers must be unique")
    elif question_type == "noul":
        _exact_keys(question, required=common | {"instructions"}, name="noul question")
        _identifier(question["instructions"], "question.instructions", maximum=2_000)
    else:
        _exact_keys(
            question, required=common | {"instructions", "criteria"},
            name="score question",
        )
        _identifier(question["instructions"], "question.instructions", maximum=2_000)
        criteria = question["criteria"]
        if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
            raise ValueError("score question requires 2 to 10 criteria")
        for index, description in enumerate(criteria):
            _identifier(description, f"question.criteria[{index}]", maximum=1_000)
        if len(set(criteria)) != len(criteria):
            raise ValueError("score criteria must be unique and ordered")


def validate_evaluation_request(request: Mapping[str, Any]) -> None:
    request = _object(request, "request")
    _exact_keys(request, required={
        "format", "schema_version", "request_id", "formation_plan_version",
        "scope_id", "canonical_generation", "observation", "retrieved_memories",
        "retrieval_receipt", "question",
    }, name="evaluation request")
    if request["format"] != REQUEST_FORMAT or request["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported evaluation request format or schema version")
    _identifier(request["request_id"], "request_id")
    _identifier(request["formation_plan_version"], "formation_plan_version")
    _identifier(request["scope_id"], "scope_id")
    generation = request["canonical_generation"]
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise ValueError("canonical_generation must be a non-negative integer")

    observation = _object(request["observation"], "observation")
    _exact_keys(
        observation, required={"id", "content", "speaker_role", "source_digest"},
        name="observation",
    )
    _identifier(observation["id"], "observation.id")
    _identifier(observation["content"], "observation.content", maximum=100_000)
    if observation["speaker_role"] not in {"user", "assistant", "tool", "system"}:
        raise ValueError("observation.speaker_role is unsupported")
    _digest(observation["source_digest"], "observation.source_digest")

    memories = request["retrieved_memories"]
    if not isinstance(memories, list):
        raise ValueError("retrieved_memories must be an array")
    memory_ids: list[str] = []
    for index, raw in enumerate(memories):
        memory = _object(raw, f"retrieved_memories[{index}]")
        _exact_keys(memory, required={
            "id", "content", "lifecycle", "source_digest", "content_digest",
            "retrieval_score", "memory_class",
        }, name="retrieved memory")
        memory_ids.append(_identifier(memory["id"], "retrieved memory id"))
        _identifier(memory["content"], "retrieved memory content", maximum=100_000)
        if memory["lifecycle"] != "active":
            raise ValueError("only active memories may be supplied")
        if memory["memory_class"] not in {
            "preference", "durable_fact", "procedure", "commitment",
            "relationship", "episode", "temporary_state", "sensitive",
            "non_memory", "unknown",
        }:
            raise ValueError("retrieved memory class is unsupported")
        _digest(memory["source_digest"], "retrieved memory source_digest")
        _digest(memory["content_digest"], "retrieved memory content_digest")
        score = memory["retrieval_score"]
        if (
            isinstance(score, bool) or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            raise ValueError("retrieval_score must be finite")
    if len(set(memory_ids)) != len(memory_ids):
        raise ValueError("retrieved memory identifiers must be unique")

    receipt = _object(request["retrieval_receipt"], "retrieval_receipt")
    _exact_keys(receipt, required={
        "retriever_revision", "requested_top_k", "returned_count", "complete",
        "truncated", "result_digest",
    }, name="retrieval receipt")
    _identifier(receipt["retriever_revision"], "retriever_revision")
    for field in ("requested_top_k", "returned_count"):
        value = receipt[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"retrieval_receipt.{field} must be a non-negative integer")
    if receipt["returned_count"] != len(memories) or receipt["returned_count"] > receipt["requested_top_k"]:
        raise ValueError("retrieval receipt counts do not match retrieved memories")
    if not isinstance(receipt["complete"], bool) or not isinstance(receipt["truncated"], bool):
        raise ValueError("retrieval completeness flags must be booleans")
    if receipt["complete"] and receipt["truncated"]:
        raise ValueError("a complete retrieval cannot be truncated")
    _digest(receipt["result_digest"], "retrieval_receipt.result_digest")
    validate_question(_object(request["question"], "question"))


def validate_typed_response(
    response: Mapping[str, Any], question: Mapping[str, Any], *, request_id: str,
) -> None:
    response = _object(response, "response")
    validate_question(question)
    question_type = question["type"]
    expected_format = f"laya-{question_type}-response-v2"
    common = {"format", "schema_version", "request_id", "question_id", "type"}
    if response.get("format") != expected_format or response.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("response format or schema version does not match question type")
    if response.get("request_id") != request_id or response.get("question_id") != question["question_id"]:
        raise ValueError("response identity does not match request and question")
    if response.get("type") != question_type:
        raise ValueError("response type does not match question type")

    if question_type == "choice":
        _exact_keys(
            response,
            required=common | {"choice", "probabilities", "confidence"},
            name="choice response",
        )
        _unit_interval(response["confidence"], "response.confidence")
        option_ids = [item["id"] for item in question["options"]]
        if response["choice"] not in option_ids:
            raise ValueError("choice response selected an unknown option")
        probabilities = _normalized_distribution(
            response["probabilities"], option_ids, "choice probabilities",
        )
        maximum = max(probabilities.values())
        winners = [
            item for item in option_ids
            if math.isclose(probabilities[item], maximum, abs_tol=1e-12)
        ]
        if len(winners) != 1 or response["choice"] != winners[0]:
            raise ValueError("choice must be the unique probability argmax")
    elif question_type == "noul":
        _exact_keys(response, required=common | {"noul"}, name="noul response")
        _unit_interval(response["noul"], "response.noul")
    else:
        _exact_keys(
            response,
            required=common | {"score", "probabilities", "confidence", "legend"},
            name="score response",
        )
        _unit_interval(response["confidence"], "response.confidence")
        level_ids = [str(index) for index in range(len(question["criteria"]))]
        probabilities = _normalized_distribution(
            response["probabilities"], level_ids, "score probabilities",
        )
        legend = _object(response["legend"], "score legend")
        expected_legend = {
            str(index): description
            for index, description in enumerate(question["criteria"])
        }
        if dict(legend) != expected_legend:
            raise ValueError("score legend must exactly match the supplied criteria")
        score = response["score"]
        if (
            isinstance(score, bool) or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            raise ValueError("response.score must be finite")
        expected = sum(
            index * probabilities[str(index)] for index in range(len(level_ids))
        )
        if not math.isclose(float(score), expected, abs_tol=_EXPECTED_SCORE_TOLERANCE):
            raise ValueError("score does not equal the distribution expected value")


def response_confidence(response: Mapping[str, Any]) -> float | None:
    """Return strict response confidence without inventing a Noul field."""

    if response.get("type") == "noul":
        return None
    return float(response["confidence"])


def question_to_laya(question: Mapping[str, Any]) -> dict[str, Any]:
    """Project the versioned host contract onto Laya's public question shape."""

    validate_question(question)
    question_type = str(question["type"])
    result: dict[str, Any] = {
        "type": question_type,
        "instructions": str(question["instructions"]),
    }
    if question_type == "choice":
        result["criteria"] = {
            str(item["id"]): str(item["description"])
            for item in question["options"]
        }
    elif question_type == "score":
        result["criteria"] = list(question["criteria"])
    return result


def project_laya_answer(
    answer: Mapping[str, Any], question: Mapping[str, Any], *, request_id: str,
) -> dict[str, Any]:
    """Project full in-process Laya output onto the exact strict Jev response."""

    validate_question(question)
    question_type = str(question["type"])
    common: dict[str, Any] = {
        "format": f"laya-{question_type}-response-v2",
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "question_id": str(question["question_id"]),
        "type": question_type,
    }
    if answer.get("type") != question_type:
        raise ValueError("Laya answer type does not match the requested question")
    if question_type == "choice":
        result = {
            **common,
            "choice": answer.get("choice"),
            "probabilities": dict(answer.get("probabilities") or {}),
            "confidence": answer.get("confidence"),
        }
    elif question_type == "noul":
        result = {**common, "noul": answer.get("noul")}
    else:
        result = {
            **common,
            "score": answer.get("score"),
            "probabilities": dict(answer.get("probabilities") or {}),
            "confidence": answer.get("confidence"),
            "legend": dict(answer.get("legend") or {}),
        }
    validate_typed_response(result, question, request_id=request_id)
    return result

