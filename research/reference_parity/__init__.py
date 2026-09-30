"""Evaluator-only reference parity utilities.

Nothing in this package is imported by the AtMem runtime.  It exists to keep
benchmark provenance, result normalization, and comparison policy outside the
product implementation.
"""

from .contracts import (
    BaselineResult,
    CaseEvidenceResult,
    CassetteEnvelope,
    ResourceCard,
    compare_candidate,
)
from .normalizer import NormalizedRange, normalize_evidence, normalizer_identity

__all__ = [
    "BaselineResult",
    "CaseEvidenceResult",
    "CassetteEnvelope",
    "NormalizedRange",
    "ResourceCard",
    "compare_candidate",
    "normalize_evidence",
    "normalizer_identity",
]
