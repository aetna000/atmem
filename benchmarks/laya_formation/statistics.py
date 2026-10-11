"""Paired cluster-bootstrap statistics and machine-checkable claim gates."""

from __future__ import annotations

from collections import defaultdict
import random
from typing import Iterable, Mapping


def paired_cluster_interval(
    candidate: Mapping[str, float], comparator: Mapping[str, float],
    clusters: Mapping[str, str], *, repetitions: int = 10_000, seed: int = 410239,
) -> dict[str, float | int]:
    ids = sorted(set(candidate) & set(comparator))
    if not ids or set(ids) != set(candidate) or set(ids) != set(comparator):
        raise ValueError("paired outcomes must contain the same non-empty identities")
    grouped: dict[str, list[str]] = defaultdict(list)
    for value in ids:
        grouped[clusters[value]].append(value)
    cluster_ids = sorted(grouped)
    rng = random.Random(seed)
    draws = []
    for _ in range(repetitions):
        selected = [rng.choice(cluster_ids) for _ in cluster_ids]
        sampled = [value for cluster in selected for value in grouped[cluster]]
        draws.append(sum(candidate[value] - comparator[value] for value in sampled) / len(sampled))
    draws.sort()
    lower = draws[int(0.025 * repetitions)]
    upper = draws[min(repetitions - 1, int(0.975 * repetitions))]
    point = sum(candidate[value] - comparator[value] for value in ids) / len(ids)
    return {
        "paired_cases": len(ids), "clusters": len(cluster_ids), "repetitions": repetitions,
        "difference": point, "ci95_lower": lower, "ci95_upper": upper,
    }


def rate_by_class(values: Mapping[str, float], classes: Mapping[str, str]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for identity, value in values.items():
        grouped[classes[identity]].append(float(value))
    return {
        name: {"cases": len(rows), "rate": sum(rows) / len(rows)}
        for name, rows in sorted(grouped.items())
    }
