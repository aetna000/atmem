from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .generator import DISPOSITIONS


def score_dispositions(
    gold_rows: Sequence[dict[str, Any]], predictions: Mapping[str, str],
) -> dict[str, Any]:
    """Score frozen predictions with abstention retained as an explicit outcome."""

    confusion = {label: Counter() for label in DISPOSITIONS}
    missing = []
    for row in gold_rows:
        identity = str(row["example_id"])
        expected = str(row["expected"]["disposition"])
        predicted = predictions.get(identity)
        if predicted is None:
            predicted = "ABSTAIN"
            missing.append(identity)
        if predicted not in {*DISPOSITIONS, "ABSTAIN"}:
            raise ValueError(f"invalid prediction for {identity}: {predicted}")
        confusion[expected][predicted] += 1
    per_class = {}
    f1_values = []
    for label in DISPOSITIONS:
        tp = confusion[label][label]
        fn = sum(confusion[label].values()) - tp
        fp = sum(confusion[other][label] for other in DISPOSITIONS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "support": sum(confusion[label].values()),
            "precision": precision, "recall": recall, "f1": f1,
        }
    total = len(gold_rows)
    correct = sum(confusion[label][label] for label in DISPOSITIONS)
    abstained = sum(confusion[label]["ABSTAIN"] for label in DISPOSITIONS)
    harmful_false_store = sum(
        confusion[label]["STORE"] for label in ("DO_NOT_STORE", "REVIEW")
    )
    harmful_denominator = sum(
        sum(confusion[label].values()) for label in ("DO_NOT_STORE", "REVIEW")
    )
    return {
        "format": "atmem-laya-disposition-eval-v1",
        "rows": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(f1_values) / len(f1_values),
        "coverage": (total - abstained) / total if total else 0.0,
        "abstentions": abstained,
        "harmful_false_store_rate": (
            harmful_false_store / harmful_denominator if harmful_denominator else 0.0
        ),
        "per_class": per_class,
        "confusion": {label: dict(sorted(counts.items())) for label, counts in confusion.items()},
        "missing_prediction_ids": missing,
    }
