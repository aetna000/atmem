"""Neutral result contract for matched memory-system comparisons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class BaselineResult:
    benchmark: str
    system: str
    sample_id: str
    sample_size: int
    passed: int
    primary_score: float
    source_revision: str
    configuration_sha256: str
    model: str
    status: str = "complete"
    median_latency_seconds: float | None = None
    context_tokens: int | None = None
    cost_usd: float | None = None
    claim_class: str = "frozen_development_sample"

    def __post_init__(self) -> None:
        if self.status not in {"complete", "incomplete", "invalid"}:
            raise ValueError("unsupported result status")
        if self.sample_size <= 0 or not 0 <= self.passed <= self.sample_size:
            raise ValueError("invalid sample counts")
        if not isfinite(self.primary_score) or not 0 <= self.primary_score <= 1:
            raise ValueError("primary_score must be within [0, 1]")
        observed = self.passed / self.sample_size
        if abs(observed - self.primary_score) > 1e-9:
            raise ValueError("primary_score must equal passed / sample_size")
        if not self.source_revision or not self.configuration_sha256:
            raise ValueError("result must bind source and configuration")
        for value in (self.median_latency_seconds, self.cost_usd):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError("cost and latency must be finite and non-negative")
        if self.context_tokens is not None and self.context_tokens < 0:
            raise ValueError("context_tokens must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-reference-result-v1", **asdict(self)}


def compare_candidate(
    candidate: BaselineResult,
    reference: BaselineResult,
    *,
    relative_target: float = 0.10,
) -> dict[str, float | bool | str]:
    """Compare only results with identical benchmark and frozen sample IDs."""
    if candidate.status != "complete" or reference.status != "complete":
        raise ValueError("comparison requires complete results")
    if (candidate.benchmark, candidate.sample_id, candidate.sample_size) != (
        reference.benchmark,
        reference.sample_id,
        reference.sample_size,
    ):
        raise ValueError("comparison requires the same benchmark and frozen sample")
    absolute_delta = candidate.primary_score - reference.primary_score
    relative_delta = (
        absolute_delta / reference.primary_score
        if reference.primary_score > 0
        else (float("inf") if candidate.primary_score > 0 else 0.0)
    )
    return {
        "candidate": candidate.system,
        "reference": reference.system,
        "absolute_point_delta": absolute_delta * 100,
        "relative_delta": relative_delta,
        "parity": candidate.primary_score >= reference.primary_score,
        "target_relative_improvement": relative_target,
        "target_met": relative_delta >= relative_target,
    }
