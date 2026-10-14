from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import math
import re
from typing import Any, Iterable, Sequence

from atmem.core.canonical import canonical_json, sha256_hex

from .generator import DISPOSITIONS, MEMORY_CLASSES


_WORD = re.compile(r"[a-z0-9]+")


def _texts(state: dict[str, Any]) -> list[str]:
    evidence = [str(row["text"]) for row in state["authorized_evidence"]]
    candidates = [canonical_json(row["content"]) for row in state["authorized_candidates"]]
    return evidence + candidates


def _shingles(text: str, width: int = 5) -> set[str]:
    words = _WORD.findall(text.casefold())
    return {" ".join(words[i:i + width]) for i in range(max(1, len(words) - width + 1))}


def maximum_contamination_similarity(examples: Sequence[dict[str, Any]], frozen_rows: Sequence[dict[str, Any]]) -> float:
    frozen = [_shingles(str(row["text"])) for row in frozen_rows]
    maximum = 0.0
    for row in examples:
        current = _shingles(" ".join(_texts(row["state"])))
        for reference in frozen:
            union = current | reference
            maximum = max(maximum, len(current & reference) / len(union) if union else 1.0)
    return maximum


def _lexical_baseline_accuracy(
    examples: Sequence[dict[str, Any]], *, text_selector: Any | None = None,
) -> float:
    """Evaluate a deliberately shallow token/label lookup across grouped splits."""

    train = [row for row in examples if row["split"] == "train"]
    validation = [row for row in examples if row["split"] == "validation"]
    token_label: dict[str, Counter[str]] = defaultdict(Counter)
    priors = Counter(row["expected"]["disposition"] for row in train)
    select = text_selector or (lambda row: " ".join(_texts(row["state"])))
    for row in train:
        label = row["expected"]["disposition"]
        for token in set(_WORD.findall(str(select(row)).casefold())):
            token_label[token][label] += 1
    correct = 0
    for row in validation:
        scores = {label: math.log(count + 1) for label, count in priors.items()}
        for token in set(_WORD.findall(str(select(row)).casefold())):
            counts = token_label.get(token)
            if counts:
                for label in scores:
                    scores[label] += math.log(counts[label] + 1)
        predicted = max(sorted(scores), key=scores.get)
        correct += predicted == row["expected"]["disposition"]
    return correct / len(validation) if validation else 1.0


def validate_examples(
    examples: Iterable[dict[str, Any]], *, frozen_rows: Sequence[dict[str, Any]],
    contamination_ceiling: float = 0.35, lexical_ceiling: float = 0.90,
) -> dict[str, Any]:
    rows = list(examples)
    if not rows:
        raise ValueError("dataset is empty")
    ids: set[str] = set()
    family_splits: dict[str, str] = {}
    family_labels: dict[str, set[str]] = defaultdict(set)
    exact_inputs: set[str] = set()
    normalized_evidence: Counter[str] = Counter()
    for row in rows:
        digest = row.get("content_digest")
        body = {key: value for key, value in row.items() if key != "content_digest"}
        if digest != "sha256:" + sha256_hex(canonical_json(body)):
            raise ValueError("content digest mismatch")
        if row["example_id"] in ids:
            raise ValueError("duplicate example ID")
        ids.add(row["example_id"])
        family = row["semantic_family_id"]
        split = row["split"]
        prior = family_splits.setdefault(family, split)
        if prior != split:
            raise ValueError("semantic family crosses dataset splits")
        label = row["expected"]["disposition"]
        memory_class = row["expected"]["memory_class"]
        if label not in DISPOSITIONS or memory_class not in MEMORY_CLASSES:
            raise ValueError("unknown label")
        family_labels[family].add(label)
        input_digest = hashlib.sha256(canonical_json(row["state"]).encode()).hexdigest()
        if input_digest in exact_inputs:
            raise ValueError("duplicate authorized input")
        exact_inputs.add(input_digest)
        for text in _texts(row["state"]):
            normalized = " ".join(_WORD.findall(text.casefold()))
            normalized_evidence[normalized] += 1
    if any(labels != set(DISPOSITIONS) for labels in family_labels.values()):
        raise ValueError("every semantic family must contain all counterfactual dispositions")
    most_repeated = max(normalized_evidence.values())
    if most_repeated > 5:
        raise ValueError(f"one semantic text is repeated {most_repeated} times")
    similarity = maximum_contamination_similarity(rows, frozen_rows)
    if similarity > contamination_ceiling:
        raise ValueError(f"frozen-corpus contamination similarity {similarity:.3f} exceeds {contamination_ceiling:.3f}")
    lexical_accuracy = _lexical_baseline_accuracy(rows)
    if lexical_accuracy >= lexical_ceiling:
        raise ValueError(f"shallow lexical baseline accuracy {lexical_accuracy:.3f} exceeds {lexical_ceiling:.3f}")
    return {
        "format": "atmem-laya-dataset-v2-validation",
        "examples": len(rows),
        "semantic_families": len(family_labels),
        "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
        "disposition_counts": dict(sorted(Counter(row["expected"]["disposition"] for row in rows).items())),
        "maximum_frozen_similarity": round(similarity, 6),
        "lexical_baseline_accuracy": round(lexical_accuracy, 6),
        "frozen_rows_used_for_training": 0,
        "maximum_exact_semantic_repetition": most_repeated,
    }
