from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Iterable, Sequence

from .generator import DISPOSITIONS
from .validation import _lexical_baseline_accuracy


def _evidence_text(row: dict[str, Any]) -> str:
    return "\n".join(item["text"] for item in row["state"]["authorized_evidence"])


def _identifier_values(value: Any, key: str = "") -> list[str]:
    if isinstance(value, dict):
        result = []
        for child_key, child in value.items():
            result.extend(_identifier_values(child, str(child_key)))
        return result
    if isinstance(value, list):
        return [item for child in value for item in _identifier_values(child, key)]
    return [str(value)] if key == "scope" or key.endswith("_id") else []


def qualify_training_data(
    synthetic_rows: Iterable[dict[str, Any]], *,
    transfer_rows: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Adversarial pre-training evaluation of data, not model quality."""

    rows = list(synthetic_rows)
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        families[row["semantic_family_id"]].append(row)
    counterfactual_core = 0
    counterfactual_failures = []
    for family, items in families.items():
        by_label = {item["expected"]["disposition"]: item for item in items}
        if not {"STORE", "UPDATE", "DUPLICATE"} <= set(by_label):
            counterfactual_failures.append(family)
            continue
        evidence = {_evidence_text(by_label[label]) for label in ("STORE", "UPDATE", "DUPLICATE")}
        if len(evidence) != 1:
            counterfactual_failures.append(family)
            continue
        store_candidates = by_label["STORE"]["state"]["authorized_candidates"]
        update_candidates = by_label["UPDATE"]["state"]["authorized_candidates"]
        duplicate_candidates = by_label["DUPLICATE"]["state"]["authorized_candidates"]
        if store_candidates or len(update_candidates) != 1 or len(duplicate_candidates) != 1:
            counterfactual_failures.append(family)
            continue
        if update_candidates[0]["content"] == duplicate_candidates[0]["content"]:
            counterfactual_failures.append(family)
            continue
        counterfactual_core += 1
    forbidden = re.compile(r"\b(?:" + "|".join(re.escape(label) for label in DISPOSITIONS) + r")\b")
    answer_token_hits = [
        row["example_id"] for row in rows
        if forbidden.search(_evidence_text(row))
    ]
    lexical = _lexical_baseline_accuracy(rows)
    core = [
        row for row in rows
        if row["expected"]["disposition"] in {"STORE", "UPDATE", "DUPLICATE"}
    ]
    evidence_only_core = _lexical_baseline_accuracy(core, text_selector=_evidence_text)
    label_words = tuple(label.casefold() for label in DISPOSITIONS)
    identifier_label_hits = [
        row["example_id"] for row in rows
        if any(
            label in identifier.casefold()
            for identifier in _identifier_values(row["state"])
            for label in label_words
        )
    ]
    transfer_workers: dict[str, set[str]] = defaultdict(set)
    for row in transfer_rows:
        provenance = row.get("provenance") or {}
        transfer_workers[str(provenance.get("upstream_split"))].add(row["state"]["scope"]["subject_id"])
    passed = (
        not counterfactual_failures
        and not answer_token_hits
        and not identifier_label_hits
        and lexical < 0.80
        and evidence_only_core <= 0.34
        and (not transfer_rows or all(transfer_workers.values()))
    )
    return {
        "format": "atmem-laya-data-qualification-eval-v1",
        "passed": passed,
        "synthetic_examples": len(rows),
        "counterfactual_families_passed": counterfactual_core,
        "counterfactual_family_failures": counterfactual_failures[:20],
        "answer_label_token_hits": answer_token_hits[:20],
        "identifier_label_hits": identifier_label_hits[:20],
        "lexical_validation_accuracy": round(lexical, 6),
        "lexical_accuracy_ceiling": 0.80,
        "evidence_only_core_accuracy": round(evidence_only_core, 6),
        "evidence_only_core_ceiling": 0.34,
        "transfer_examples": len(transfer_rows),
        "transfer_subject_counts": {
            split: len(subjects) for split, subjects in sorted(transfer_workers.items())
        },
        "claims": {
            "data_gate_only": True,
            "model_generalization_established": False,
            "independent_human_evaluation_required": True,
        },
    }
