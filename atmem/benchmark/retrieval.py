"""Deterministic calibration and held-out retrieval-quality evaluation."""

from __future__ import annotations

from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from atmem.retrieve import SupportClass, decide_retrieval


def run_retrieval_quality_benchmark(
    dataset_path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(dataset_path) if dataset_path else Path(
        str(files("atmem.benchmark").joinpath("data", "retrieval-heldout-v1.json"))
    )
    dataset = json.loads(source.read_text(encoding="utf-8"))
    if dataset.get("format") != "atmem-retrieval-quality-cases-v1":
        raise ValueError("unsupported retrieval quality dataset")
    reciprocal_ranks: list[float] = []
    no_answer: list[bool] = []
    outcomes = []
    for case in dataset["cases"]:
        decision = decide_retrieval(case["query"], case["candidates"])
        expected = case.get("expected_record_id")
        if expected:
            rank = next(
                (index for index, value in enumerate(decision.ranked_record_ids, 1) if value == expected),
                None,
            )
            reciprocal_ranks.append(0.0 if rank is None or rank > 5 else 1.0 / rank)
            passed = rank == 1
        else:
            passed = decision.support_class is SupportClass.NONE
            no_answer.append(passed)
        outcomes.append({
            "id": case["id"], "passed": passed,
            "support_class": decision.support_class.value,
            "ranked_record_ids": list(decision.ranked_record_ids),
        })
    return {
        "format": "atmem-retrieval-quality-report-v1",
        "dataset": dataset["name"],
        "answerable_cases": len(reciprocal_ranks),
        "no_answer_cases": len(no_answer),
        "mrr_at_5": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "no_answer_accuracy": sum(no_answer) / len(no_answer),
        "passed": all(row["passed"] for row in outcomes),
        "outcomes": outcomes,
    }
