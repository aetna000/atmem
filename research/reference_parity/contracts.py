"""Neutral result contract for matched memory-system comparisons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, Mapping

_SUFFICIENCY_STATUSES = {
    "sufficient",
    "partial",
    "conflicted",
    "contradicted",
    "stale",
    "not_found_within_budget",
    "withheld_by_policy",
}


@dataclass(frozen=True, slots=True)
class ResourceCard:
    formation: str
    embedding: str
    planner_navigator: str
    reader: str
    judge: str
    top_k: int
    total_context_tokens: int
    max_model_calls_per_query: int
    max_intelligence_tokens_per_query: int
    max_navigation_operations: int
    timeout_seconds: int
    max_retries: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ResourceCard":
        fields = cls.__dataclass_fields__
        missing = sorted(set(fields) - set(value))
        if missing:
            raise ValueError(f"resource card missing fields: {', '.join(missing)}")
        card = cls(**{name: value[name] for name in fields})
        for name in (
            "top_k",
            "total_context_tokens",
            "max_model_calls_per_query",
            "max_intelligence_tokens_per_query",
            "max_navigation_operations",
            "timeout_seconds",
            "max_retries",
        ):
            if getattr(card, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        return card


@dataclass(frozen=True, slots=True)
class CaseEvidenceResult:
    system: str
    case_id: str
    split: str
    status: str
    selected_ranges: tuple[tuple[str, int, int], ...]
    forbidden_source_ids: tuple[str, ...]
    elapsed_ms: float
    configuration_sha256: str
    error: str | None = None

    def __post_init__(self) -> None:
        if self.split not in {"development", "holdout"}:
            raise ValueError("case result split must be development or holdout")
        if self.status not in _SUFFICIENCY_STATUSES:
            raise ValueError("unsupported sufficiency status")
        if not isfinite(self.elapsed_ms) or self.elapsed_ms < 0:
            raise ValueError("elapsed_ms must be finite and non-negative")
        if not self.configuration_sha256.startswith("sha256:"):
            raise ValueError("case result must bind a sha256 configuration")
        for source_id, start, end in self.selected_ranges:
            if not source_id or start < 0 or end <= start:
                raise ValueError("invalid selected evidence range")

    def to_dict(self) -> dict[str, Any]:
        return {"format": "atmem-reference-case-result-v1", **asdict(self)}


@dataclass(frozen=True, slots=True)
class CassetteEnvelope:
    provider: str
    model_revision: str
    request_sha256: str
    response_sha256: str
    encrypted_external_path: str
    encryption_profile: str
    contains_plaintext_in_repository: bool = False

    def __post_init__(self) -> None:
        for value in (self.request_sha256, self.response_sha256):
            if not value.startswith("sha256:") or len(value) != 71:
                raise ValueError("cassette digests must be sha256 values")
        if self.contains_plaintext_in_repository:
            raise ValueError("reference cassettes must not retain repository plaintext")
        if not self.encrypted_external_path or not self.encryption_profile:
            raise ValueError("cassette must bind encrypted external storage")


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
