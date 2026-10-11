from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Iterable

from .models import FormationScenarioV1


_BUCKETS = (("train", 70), ("validation", 10), ("calibration", 10), ("sealed_test", 10))


def split_for_template(template_family: str, *, seed: int) -> str:
    value = int.from_bytes(hashlib.sha256(f"{seed}:{template_family}".encode()).digest()[:8], "big") % 100
    start = 0
    for name, width in _BUCKETS:
        if start <= value < start + width:
            return name
        start += width
    raise AssertionError("split bucket coverage is incomplete")


def assert_group_disjoint(scenarios: Iterable[FormationScenarioV1]) -> None:
    fields = (
        "fictional_identity_group",
        "template_family",
        "semantic_chain_id",
        "paraphrase_cluster_id",
    )
    seen: dict[str, dict[str, set[str]]] = {field: defaultdict(set) for field in fields}
    for row in scenarios:
        for field in fields:
            seen[field][getattr(row, field)].add(row.split)
    collisions = {
        field: sorted(key for key, splits in groups.items() if len(splits) > 1)
        for field, groups in seen.items()
    }
    collisions = {field: keys for field, keys in collisions.items() if keys}
    if collisions:
        raise ValueError(f"dataset split leakage: {collisions}")
