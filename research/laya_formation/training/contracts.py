from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


FORMAT_MANIFEST = "atmem-laya-training-run-v1"
FORMAT_METRICS = "atmem-laya-metric-report-v1"
FORMAT_CALIBRATION = "atmem-laya-calibration-bundle-v1"

SAME_BACKEND_TOLERANCE = {
    "minimum_choice_agreement": 0.999,
    "maximum_normalized_score_delta": 1e-4,
}
CROSS_BACKEND_TOLERANCE = {
    "minimum_choice_agreement": 0.995,
    "maximum_primary_aggregate_delta_points": 0.2,
}
MIN_CALIBRATION_ITEMS_PER_QUESTION = 100
SECRET_PATTERNS = {
    "hugging_face_token": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "credential_assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,}\]]+"
    ),
}


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def assert_finite(values: Iterable[float], *, label: str) -> None:
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError(f"{label} contains a nonfinite value")


def class_distribution(labels: Sequence[str]) -> dict[str, float]:
    if not labels:
        raise ValueError("labels must not be empty")
    counts = Counter(labels)
    return {name: counts[name] / len(labels) for name in sorted(counts)}


def collapse_report(expected: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    if len(expected) != len(predicted) or not expected:
        raise ValueError("expected and predicted must be non-empty and equally sized")
    expected_dist = class_distribution(expected)
    predicted_dist = class_distribution(predicted)
    expected_classes = set(expected_dist)
    predicted_classes = set(predicted_dist)
    max_predicted_share = max(predicted_dist.values())
    prior_l1 = sum(abs(predicted_dist.get(name, 0.0) - share) for name, share in expected_dist.items())
    return {
        "expected_distribution": expected_dist,
        "predicted_distribution": predicted_dist,
        "missing_expected_classes": sorted(expected_classes - predicted_classes),
        "maximum_predicted_class_share": max_predicted_share,
        "class_prior_l1": prior_l1,
        "collapsed": len(predicted_classes) == 1 and len(expected_classes) > 1,
    }


def truncation_report(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    truncated = [str(row["example_id"]) for row in records if bool(row.get("truncated"))]
    return {
        "items": len(records),
        "truncated_items": len(truncated),
        "truncated_example_ids": truncated,
        "truncation_rate": len(truncated) / len(records) if records else 0.0,
    }


def calibration_power(counts: Mapping[str, int]) -> dict[str, Any]:
    underpowered = sorted(name for name, count in counts.items() if count < MIN_CALIBRATION_ITEMS_PER_QUESTION)
    return {
        "minimum_items_per_question": MIN_CALIBRATION_ITEMS_PER_QUESTION,
        "counts": dict(sorted(counts.items())),
        "underpowered_questions": underpowered,
        "sufficient": not underpowered,
    }


def secret_findings(value: Any) -> list[dict[str, str]]:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    findings = []
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.append({"pattern": name})
    return findings


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "format", "run_id", "created_at", "code_revision", "base_model", "laya",
        "dataset", "questions_digest", "environment", "objective", "hyperparameters",
        "seeds", "split_digests", "hardware", "checkpoints", "metrics",
        "calibration", "export_inventory", "parent_run", "reproducibility_tolerances",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ValueError(f"training manifest missing fields: {missing}")
    if manifest["format"] != FORMAT_MANIFEST:
        raise ValueError("unknown training manifest format")
    if manifest["objective"] not in {"soft-ce", "rlcd"}:
        raise ValueError("unsupported objective")
    if manifest["reproducibility_tolerances"] != {
        "same_backend": SAME_BACKEND_TOLERANCE,
        "cross_backend": CROSS_BACKEND_TOLERANCE,
    }:
        raise ValueError("reproducibility tolerances do not match the frozen FR-019 contract")
    findings = secret_findings(manifest)
    if findings:
        raise ValueError(f"training manifest contains secret-like material: {findings}")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
