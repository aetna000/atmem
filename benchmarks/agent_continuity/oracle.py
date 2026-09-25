"""Evaluator-only truth: worker success text never determines completion."""
from __future__ import annotations

from collections import Counter


def score_effects(expected: dict[str, str], effects: list[dict], blocked: list[str] = ()) -> dict:
    if not expected:
        raise ValueError("zero-write tasks are outside this cohort")
    counts = Counter(e["operation_id"] for e in effects)
    correct = {e["operation_id"] for e in effects
               if expected.get(e["operation_id"]) == e["payload_digest"]}
    duplicate = sum(max(0, counts[op] - 1) for op in expected)
    wrong = sum(expected.get(e["operation_id"]) != e["payload_digest"] for e in effects)
    missing = set(expected) - correct
    return {"intended_operations": len(expected), "committed_effects": len(effects),
            "duplicate_effects": duplicate, "wrong_effects": wrong,
            "missing_operations": sorted(missing),
            "pending_blocked_operations": sorted(missing & set(blocked)),
            "forgotten_operations": sorted(missing - set(blocked)),
            "valid_completion": not missing and not duplicate and not wrong}


def score_context(delivered: list[dict], canonical: dict[str, dict]) -> dict:
    violations = {"stale": 0, "unauthorized": 0, "missing_canonical": 0}
    for item in delivered:
        current = canonical.get(item["id"])
        if current is None:
            violations["missing_canonical"] += 1
            continue
        violations["stale"] += item.get("revision") != current.get("revision")
        violations["unauthorized"] += not current.get("eligible", False)
    return {"delivered": len(delivered), **violations}
