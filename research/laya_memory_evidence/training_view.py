"""Portable Laya training view for stateful V2 memory transitions.

The public transition record remains the source of truth. This module only
adapts its bounded request/question and expected strict response into Laya
0.4.2's documented ``{state, questions, expected}`` training shape.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

from atmem.laya_formation.contracts_v2 import (
    validate_evaluation_request,
    validate_typed_response,
)


V2_QUESTION_IDS = frozenset({
    "formation.context_sufficient.v2",
    "formation.is_durable.v2",
    "formation.memory_class.v2",
    "formation.operation.v2",
    "formation.target.v2",
    "formation.future_utility.v2",
})
V3_QUESTION_IDS = frozenset({"formation.joint_transition.v3"})
SUPPORTED_QUESTION_IDS = V2_QUESTION_IDS | V3_QUESTION_IDS


def iter_decision_rows(
    *, candidate_id: str, authorized_input: dict[str, Any],
    label: dict[str, Any], split: str,
) -> Iterator[dict[str, Any]]:
    """Retain the superseded isolated-label export contract for V1 archives.

    New training must use :func:`to_laya_rows` with stateful V2 transitions.
    This adapter exists only so the already-published authentic-row audit
    exporter remains reproducible; its rows are not eligible for V2 training.
    """

    disposition = str(label["disposition"])
    memory_class = str(label["memory_class"])
    meaning = dict(label.get("meaning") or {})
    durable = str(meaning.get("durability") or "").casefold() == "durable"
    prior = list(authorized_input.get("prior_user_turn_ids") or ())
    target = str(prior[-1]) if prior and disposition in {"UPDATE", "DUPLICATE", "FORGET"} else "target:none"
    questions = (
        ("operation", ["STORE", "UPDATE", "DUPLICATE", "DO_NOT_STORE", "FORGET", "REVIEW"], disposition),
        ("memory_class", ["preference", "durable_fact", "procedure", "commitment", "relationship", "episode", "temporary_state", "sensitive", "non_memory"], memory_class),
        ("is_durable", ["false", "true"], "true" if durable else "false"),
        ("target_selection", [*prior, "target:none", "REVIEW"], target),
    )
    for question_id, choice_ids, expected in questions:
        if expected not in choice_ids:
            expected = "REVIEW" if "REVIEW" in choice_ids else choice_ids[-1]
        yield {
            "example_id": f"{candidate_id}:{question_id}",
            "scenario_id": candidate_id,
            "authorized_input": authorized_input,
            "question_id": question_id,
            "question_type": "choice",
            "choice_ids": choice_ids,
            "expected_choice_ids": [expected],
            "allow_abstain": True,
            "split": split,
            "superseded_contract": "isolated-label-v1",
        }


def _model_state(request: dict[str, Any]) -> dict[str, Any]:
    """Return exactly the bounded semantic state visible at inference."""

    return {
        "observation": request["observation"],
        "retrieved_memories": request["retrieved_memories"],
    }


def _laya_question(question: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": question["type"],
        "instructions": question["instructions"],
    }
    if question["type"] == "choice":
        result["criteria"] = {
            option["id"]: option["description"] for option in question["options"]
        }
    elif question["type"] == "score":
        result["criteria"] = list(question["criteria"])
    return result


def _expected_value(response: dict[str, Any]) -> Any:
    if response["type"] == "choice":
        probabilities = [float(value) for value in response["probabilities"].values()]
        if sorted(probabilities) != [0.0] * (len(probabilities) - 1) + [1.0]:
            raise ValueError("training Choice targets must be one-hot adjudicated labels")
        return response["choice"]
    if response["type"] == "noul":
        probability = float(response["noul"])
        if probability not in {0.0, 1.0}:
            raise ValueError("training Noul targets must be hard adjudicated labels")
        return bool(probability)
    score = float(response["score"])
    if not score.is_integer():
        raise ValueError("training Score targets must be one adjudicated rubric level")
    probabilities = [float(value) for value in response["probabilities"].values()]
    if sorted(probabilities) != [0.0] * (len(probabilities) - 1) + [1.0]:
        raise ValueError("training Score targets must be one-hot adjudicated labels")
    return int(score)


def to_laya_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert exported typed decision rows to upstream Laya 0.4.2 rows."""

    converted: list[dict[str, Any]] = []
    for row in rows:
        request = dict(row["request"])
        response = dict(row["expected_response"])
        validate_evaluation_request(request)
        question = dict(request["question"])
        question_id = str(question["question_id"])
        if question_id not in SUPPORTED_QUESTION_IDS:
            raise ValueError(f"unsupported stateful memory question: {question_id}")
        validate_typed_response(
            response, question, request_id=str(request["request_id"]),
        )
        converted.append({
            "state": _model_state(request),
            "questions": {question_id: _laya_question(question)},
            "expected": {question_id: _expected_value(response)},
        })
    return converted


def option_ids(row: dict[str, Any]) -> list[str]:
    """Return stable metric labels in the exact Laya output order."""

    question = row["request"]["question"]
    if question["type"] == "choice":
        return [str(item["id"]) for item in question["options"]]
    if question["type"] == "noul":
        return ["false", "true"]
    return [str(index) for index in range(len(question["criteria"]))]


def question_definitions(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for row in rows:
        question = dict(row["request"]["question"])
        question_id = str(question["question_id"])
        if question_id == "formation.target.v2":
            question = {
                "question_id": question_id, "type": "choice",
                "instructions": question["instructions"],
                "options": "dynamic authorized opaque memory identifiers; 2-255",
            }
        elif question_id == "formation.joint_transition.v3":
            question = {
                "question_id": question_id,
                "type": "choice",
                "instructions": question["instructions"],
                "options": (
                    "dynamic opaque action-target identifiers; server-side bindings; "
                    "2-255 options; at most 32 authorized targets"
                ),
            }
        existing = definitions.setdefault(question_id, question)
        if existing != question:
            raise ValueError(f"question schema changed within dataset: {question_id}")
    return definitions
