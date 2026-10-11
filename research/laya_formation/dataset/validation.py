from __future__ import annotations

from collections import defaultdict
import hashlib
import re
from typing import Iterable

from .models import FormationScenarioV1, TypedDecisionExampleV1
from .oracle import compile_decisions
from .splits import assert_group_disjoint


_SECRET = re.compile(r"(?i)(?:api[_-]?key|password|secret)\s*[:=]\s*[A-Za-z0-9_./+-]{8,}")
_VARIABLE = re.compile(r"(?i)(?:scenario\s+)?[0-9]+|synthetic-(?:value|prior)-[0-9]+|conflict-synthetic-value-[0-9]+")


def near_duplicate_fingerprint(text: str) -> str:
    normalized = _VARIABLE.sub("<VAR>", text.casefold())
    words = re.findall(r"[a-z<>]+", normalized)
    shingles = sorted(" ".join(words[index:index + 3]) for index in range(max(1, len(words) - 2)))
    return hashlib.sha256("\n".join(shingles).encode()).hexdigest()


def validate_dataset(
    scenarios: Iterable[FormationScenarioV1], examples: Iterable[TypedDecisionExampleV1]
) -> dict[str, int]:
    scenario_rows = list(scenarios)
    example_rows = list(examples)
    assert_group_disjoint(scenario_rows)
    by_scenario: dict[str, list[TypedDecisionExampleV1]] = defaultdict(list)
    exact: dict[str, str] = {}
    near: dict[str, str] = {}
    for row in scenario_rows:
        material = "\n".join(event.text.casefold().strip() for event in row.evidence_events)
        digest = hashlib.sha256(material.encode()).hexdigest()
        prior = exact.setdefault(digest, row.split)
        if prior != row.split:
            raise ValueError("exact scenario content crosses dataset splits")
        near_digest = near_duplicate_fingerprint(material)
        near_prior = near.setdefault(near_digest, row.split)
        if near_prior != row.split:
            raise ValueError("near-duplicate scenario content crosses dataset splits")
        if _SECRET.search(material):
            raise ValueError("credential-like value detected in synthetic content")
    for row in example_rows:
        by_scenario[row.scenario_id].append(row)
    if set(by_scenario) != {row.scenario_id for row in scenario_rows}:
        raise ValueError("decision/scenario membership mismatch")
    scenario_map = {row.scenario_id: row for row in scenario_rows}
    for scenario_id, decisions in by_scenario.items():
        expected = compile_decisions(scenario_map[scenario_id])
        if decisions != list(expected):
            raise ValueError("decision rows differ from independent oracle compilation")
    return {"scenarios": len(scenario_rows), "decisions": len(example_rows), "critical_findings": 0}
