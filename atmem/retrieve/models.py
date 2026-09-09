"""Host-neutral calibrated retrieval decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SupportClass(str, Enum):
    DIRECT = "direct_support"
    BACKGROUND = "background_context"
    NONE = "no_useful_memory"


@dataclass(frozen=True, slots=True)
class SignalContribution:
    name: str
    version: str
    normalized_score: float
    raw_score: float | None = None
    eligible_for_support: bool = True


@dataclass(frozen=True, slots=True)
class EmbeddingIdentity:
    provider: str
    model: str
    revision: str
    dimensions: int
    distance: str
    normalization: str
    query_prefix: str
    document_prefix: str
    preprocessing_version: str
    epoch_id: str


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    record_id: str
    support_class: SupportClass
    relevance_score: float
    rank_score: float
    signals: dict[str, float]
    signal_contributions: tuple[SignalContribution, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["support_class"] = self.support_class.value
        value["signal_contributions"] = [
            asdict(signal) for signal in self.signal_contributions
        ]
        return value


@dataclass(frozen=True, slots=True)
class RetrievalDecision:
    format: str
    calibration_version: str
    support_class: SupportClass
    ranked_record_ids: tuple[str, ...]
    candidates: tuple[CandidateDecision, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "calibration_version": self.calibration_version,
            "support_class": self.support_class.value,
            "ranked_record_ids": list(self.ranked_record_ids),
            "candidates": [row.to_dict() for row in self.candidates],
            "reason_codes": list(self.reason_codes),
        }
