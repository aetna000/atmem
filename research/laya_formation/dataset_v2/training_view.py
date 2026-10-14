from __future__ import annotations

from typing import Any, Iterable, Iterator

from .generator import DISPOSITIONS


QUESTION_INSTRUCTIONS_V2 = {
    "disposition_v2": (
        "Choose the safe memory disposition using only authorized evidence, its provenance, "
        "and the contents of authorized active candidates."
    ),
}


def iter_decision_rows(examples: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Create the single v2 disposition head expected by Laya.

    Memory-class annotations remain in the source corpus for audit and future
    work. They are not trained until natural data covers those classes without
    the severe preference skew introduced by LAPS.
    """

    for row in examples:
        if row.get("format") != "atmem-laya-training-example-v2":
            raise ValueError("unknown v2 training example")
        common = {
            "scenario_id": row["example_id"],
            "authorized_input": row["state"],
            "allow_abstain": True,
            "split": row["split"],
            "semantic_family_id": row["semantic_family_id"],
        }
        yield {
            **common,
            "example_id": row["example_id"] + ":disposition_v2",
            "question_id": "disposition_v2",
            "question_type": "choice",
            "choice_ids": list(DISPOSITIONS),
            "expected_choice_ids": [row["expected"]["disposition"]],
        }


def to_laya_rows_v2(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for row in rows:
        question_id = str(row["question_id"])
        if question_id not in QUESTION_INSTRUCTIONS_V2:
            raise ValueError(f"unknown v2 question: {question_id}")
        expected = list(row["expected_choice_ids"])
        if len(expected) != 1:
            raise ValueError("v2 requires exactly one target per decision head")
        choices = list(row["choice_ids"])
        converted.append({
            "state": row["authorized_input"],
            "questions": {
                question_id: {
                    "type": "choice",
                    "instructions": QUESTION_INSTRUCTIONS_V2[question_id],
                    "criteria": {
                        choice: choice.replace("_", " ").casefold()
                        for choice in choices
                    },
                }
            },
            "expected": {question_id: expected[0]},
        })
    return converted
