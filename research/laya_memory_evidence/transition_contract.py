"""Strict, host-neutral contracts for stateful memory-decision examples.

The functions intentionally validate plain JSON-compatible mappings.  The same
validators can therefore protect research exports, model adapters, and hosts
that do not import AtMem's product dataclasses.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.laya_formation import contracts_v2 as _runtime_contract


SCHEMA_VERSION = "2.0.0"
REQUEST_FORMAT = "laya-evaluation-request-v2"
TRANSITION_FORMAT = "memory-transition-example-v2"
QUESTION_TYPES = frozenset({"choice", "noul", "score"})
PARTITIONS = frozenset({"train", "validation", "calibration", "sealed_test", "holdback"})
OPERATIONS = frozenset({
    "STORE_NEW",
    "UPDATE_EXISTING",
    "SUPERSEDE_EXISTING",
    "DUPLICATE",
    "DO_NOT_STORE",
    "FORGET_EXISTING",
    "REVIEW",
})
TARGET_REQUIRED = frozenset({
    "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
})
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROBABILITY_TOLERANCE = 1e-6
_EXPECTED_SCORE_TOLERANCE = 1e-6


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, Any], *, required: set[str], optional: set[str] | None = None,
    name: str,
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
    normalized = {key: _unit_interval(item, f"{name}.{key}") for key, item in distribution.items()}
    if not math.isclose(sum(normalized.values()), 1.0, abs_tol=_PROBABILITY_TOLERANCE):
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
        _exact_keys(question, required=common | {"instructions", "options"}, name="choice question")
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
        _exact_keys(question, required=common | {"instructions", "criteria"}, name="score question")
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
    if isinstance(request["canonical_generation"], bool) or not isinstance(request["canonical_generation"], int) or request["canonical_generation"] < 0:
        raise ValueError("canonical_generation must be a non-negative integer")

    observation = _object(request["observation"], "observation")
    _exact_keys(observation, required={"id", "content", "speaker_role", "source_digest"}, name="observation")
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
        _digest(memory["source_digest"], "retrieved memory source_digest")
        _digest(memory["content_digest"], "retrieved memory content_digest")
        score = memory["retrieval_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
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
        if isinstance(receipt[field], bool) or not isinstance(receipt[field], int) or receipt[field] < 0:
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
        _exact_keys(response, required=common | {"choice", "probabilities", "confidence"}, name="choice response")
        _unit_interval(response["confidence"], "response.confidence")
        option_ids = [item["id"] for item in question["options"]]
        choice = response["choice"]
        if choice not in option_ids:
            raise ValueError("choice response selected an unknown option")
        probabilities = _normalized_distribution(response["probabilities"], option_ids, "choice probabilities")
        maximum = max(probabilities.values())
        winners = [item for item in option_ids if math.isclose(probabilities[item], maximum, abs_tol=1e-12)]
        if len(winners) != 1 or choice != winners[0]:
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
            str(index): description for index, description in enumerate(question["criteria"])
        }
        if dict(legend) != expected_legend:
            raise ValueError("score legend must exactly match the supplied criteria")
        score = response["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise ValueError("response.score must be finite")
        expected = sum(index * probabilities[str(index)] for index in range(len(level_ids)))
        if not math.isclose(float(score), expected, abs_tol=_EXPECTED_SCORE_TOLERANCE):
            raise ValueError("score does not equal the distribution expected value")


# Dataset construction and installed inference intentionally share one exact
# validator.  The local helpers above remain temporarily for compatibility with
# historical imports, but these public names are bound to the product contract.
validate_question = _runtime_contract.validate_question
validate_evaluation_request = _runtime_contract.validate_evaluation_request
validate_typed_response = _runtime_contract.validate_typed_response


def validate_transition_example(example: Mapping[str, Any]) -> None:
    example = _object(example, "transition example")
    _exact_keys(example, required={
        "format", "schema_version", "transition_id", "trajectory_id", "partition",
        "pre_state", "request", "expected_response", "expected_operation",
        "expected_target_id", "required_evidence_memory_ids",
        "expected_post_state_digest", "acceptable_abstention", "provenance",
        "retrieval_evidence",
    }, name="transition example")
    if example["format"] != TRANSITION_FORMAT or example["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported transition example format or schema version")
    _identifier(example["transition_id"], "transition_id")
    _identifier(example["trajectory_id"], "trajectory_id")
    if example["partition"] not in PARTITIONS:
        raise ValueError("transition partition is unsupported")
    pre_state = _object(example["pre_state"], "pre_state")
    _exact_keys(pre_state, required={
        "snapshot_id", "snapshot_digest", "vector_snapshot_id",
        "vector_snapshot_digest", "canonical_generation",
        "canonical_state_digest", "canonical_records",
    }, name="pre_state")
    _identifier(pre_state["snapshot_id"], "pre_state.snapshot_id")
    _identifier(pre_state["vector_snapshot_id"], "pre_state.vector_snapshot_id")
    _digest(pre_state["snapshot_digest"], "pre_state.snapshot_digest")
    _digest(pre_state["vector_snapshot_digest"], "pre_state.vector_snapshot_digest")
    _digest(pre_state["canonical_state_digest"], "pre_state.canonical_state_digest")
    records = pre_state["canonical_records"]
    if not isinstance(records, list):
        raise ValueError("pre_state.canonical_records must be an array")
    record_ids = []
    for raw in records:
        record = _object(raw, "pre_state canonical record")
        _exact_keys(
            record, required={"id", "content", "status", "generation", "memory_class"},
            name="pre_state canonical record",
        )
        record_ids.append(_identifier(record["id"], "canonical record id"))
        _identifier(record["content"], "canonical record content", maximum=100_000)
        if record["status"] != "active":
            raise ValueError("published canonical pre-state records must be active")
        _identifier(record["memory_class"], "canonical record memory class")
        if (
            isinstance(record["generation"], bool)
            or not isinstance(record["generation"], int)
            or record["generation"] < 0
        ):
            raise ValueError("canonical record generation must be non-negative")
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("canonical pre-state record identifiers must be unique")
    observed_state_digest = "sha256:" + sha256_hex(canonical_json(records))
    if pre_state["canonical_state_digest"] != observed_state_digest:
        raise ValueError("canonical pre-state digest does not match records")
    request = _object(example["request"], "request")
    validate_evaluation_request(request)
    if pre_state["canonical_generation"] != request["canonical_generation"]:
        raise ValueError("pre-state and request canonical generations differ")
    retrieved_ids = {item["id"] for item in request["retrieved_memories"]}
    if not retrieved_ids.issubset(set(record_ids)):
        raise ValueError("retrieved memories must belong to the canonical pre-state")
    retrieval_evidence = _object(example["retrieval_evidence"], "retrieval_evidence")
    _exact_keys(
        retrieval_evidence, required={"receipt", "digest"},
        name="retrieval_evidence",
    )
    _digest(retrieval_evidence["digest"], "retrieval_evidence.digest")
    frozen_receipt = _object(
        retrieval_evidence["receipt"], "retrieval_evidence.receipt",
    )
    _exact_keys(frozen_receipt, required={
        "format", "request_id", "candidate_set_id", "candidate_digest",
        "canonical_generation", "requested_top_k", "returned_count",
        "complete", "truncated", "retriever_revision",
    }, name="retrieval_evidence.receipt")
    if frozen_receipt["format"] != "atmem-frozen-retrieval-receipt-v2":
        raise ValueError("retrieval evidence has an unsupported receipt format")
    for field in ("request_id", "candidate_set_id", "retriever_revision"):
        _identifier(frozen_receipt[field], f"retrieval_evidence.receipt.{field}")
    _digest(
        frozen_receipt["candidate_digest"],
        "retrieval_evidence.receipt.candidate_digest",
    )
    for field in ("canonical_generation", "requested_top_k", "returned_count"):
        value = frozen_receipt[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"retrieval_evidence.receipt.{field} must be non-negative")
    if frozen_receipt["canonical_generation"] != request["canonical_generation"]:
        raise ValueError("retrieval evidence and request generations differ")
    if (
        frozen_receipt["requested_top_k"] != request["retrieval_receipt"]["requested_top_k"]
        or frozen_receipt["returned_count"] != len(retrieved_ids)
    ):
        raise ValueError("retrieval evidence counts do not match the request")
    if not isinstance(frozen_receipt["complete"], bool) or not isinstance(
        frozen_receipt["truncated"], bool
    ):
        raise ValueError("retrieval evidence completeness flags must be booleans")
    if frozen_receipt["complete"] and frozen_receipt["truncated"]:
        raise ValueError("complete retrieval evidence cannot be truncated")
    validate_typed_response(
        _object(example["expected_response"], "expected_response"),
        _object(request["question"], "question"), request_id=request["request_id"],
    )
    operation = example["expected_operation"]
    if operation not in OPERATIONS:
        raise ValueError("expected_operation is unsupported")
    target = example["expected_target_id"]
    memory_ids = retrieved_ids
    if operation in TARGET_REQUIRED:
        if target not in memory_ids:
            raise ValueError("relational operation requires a retrieved target")
    elif target is not None:
        raise ValueError("non-relational operation cannot select a target")
    evidence_ids = example["required_evidence_memory_ids"]
    if not isinstance(evidence_ids, list) or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("required_evidence_memory_ids must be a unique array")
    if not set(evidence_ids).issubset(memory_ids):
        raise ValueError("required evidence must be present in retrieved state")
    _digest(example["expected_post_state_digest"], "expected_post_state_digest")
    if not isinstance(example["acceptable_abstention"], bool):
        raise ValueError("acceptable_abstention must be boolean")
    provenance = _object(example["provenance"], "provenance")
    _exact_keys(provenance, required={
        "source_id", "source_revision", "conversation_id", "license",
        "adjudication_mode", "content_digest",
    }, name="provenance")
    for field in ("source_id", "source_revision", "conversation_id", "license", "adjudication_mode"):
        _identifier(provenance[field], f"provenance.{field}")
    _digest(provenance["content_digest"], "provenance.content_digest")
