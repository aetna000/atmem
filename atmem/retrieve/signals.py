"""Versioned, bounded adapters for retrieval evidence.

Raw scores never enter calibration directly.  Every source is normalized here
and declares whether it is allowed to establish query support.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from atmem.retrieve.models import SignalContribution

SIGNAL_REGISTRY_VERSION = "atmem-retrieval-signals-v1"
SIGNAL_VERSIONS = {
    "lexical_support": "concept-overlap-v1",
    "typo_tolerant_support": "bounded-edit-distance-v1",
    "semantic_support": "cosine-production-profile-v1",
    "candidate_prior": "governed-candidate-prior-v1",
    "fact_support": "fact-key-overlap-v1",
    "graph_prior": "weighted-rrf-v1",
    "trust_prior": "trust-tier-v1",
    "recency_prior": "ordinal-recency-v1",
    "atbot_rerank": "atbot-eligible-rerank-v1",
}


def bounded_score(value: Any) -> float:
    """Return a finite score in ``[0, 1]``; malformed evidence contributes 0."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(score):
        return 0.0
    return round(min(1.0, max(0.0, score)), 6)


def contribution(
    name: str,
    raw_score: Any,
    *,
    eligible_for_support: bool = True,
    normalize: Callable[[Any], float] = bounded_score,
) -> SignalContribution:
    if name not in SIGNAL_VERSIONS:
        raise ValueError(f"unregistered retrieval signal: {name}")
    try:
        raw = float(raw_score)
        if not math.isfinite(raw):
            raw = None
    except (TypeError, ValueError):
        raw = None
    return SignalContribution(
        name=name,
        version=SIGNAL_VERSIONS[name],
        normalized_score=normalize(raw_score),
        raw_score=raw,
        eligible_for_support=eligible_for_support,
    )


def semantic_contribution(
    similarity: Any, provider: str, *, quality_class: str = ""
) -> SignalContribution:
    diagnostic = provider in {
        "hashing", "hashing-diagnostic", "hash", "deterministic-hashing"
    } or quality_class == "diagnostic"
    return contribution(
        "semantic_support",
        similarity,
        eligible_for_support=not diagnostic,
    )
