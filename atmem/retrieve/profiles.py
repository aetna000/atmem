"""Versioned retrieval profiles with independent nomination quotas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class RetrievalProfile:
    profile_id: str
    exact_quota: int
    lexical_quota: int
    semantic_quota: int
    temporal_quota: int
    graph_quota: int
    neighbor_depth: int
    context_bytes: int
    version: ClassVar[str] = "retrieval-profiles-v1"

    def __post_init__(self) -> None:
        values = asdict(self)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0
               for key, value in values.items() if key != "profile_id"):
            raise ValueError("retrieval profile quotas must be non-negative integers")
        if not self.profile_id or self.context_bytes < 256:
            raise ValueError("retrieval profile requires an ID and usable context budget")

    def to_dict(self) -> dict[str, int | str]:
        return {"format": self.version, **asdict(self)}


PROFILES: dict[str, RetrievalProfile] = {
    "fact-and-state-v1": RetrievalProfile("fact-and-state-v1", 12, 16, 12, 12, 4, 1, 8_192),
    "change-and-history-v1": RetrievalProfile("change-and-history-v1", 8, 12, 10, 24, 12, 2, 12_288),
    "procedure-and-rule-v1": RetrievalProfile("procedure-and-rule-v1", 8, 18, 12, 8, 24, 2, 16_384),
    "synthesis-v1": RetrievalProfile("synthesis-v1", 8, 16, 20, 12, 24, 2, 16_384),
}

_NEED_PROFILE = {
    "exact_fact": "fact-and-state-v1",
    "current_state": "fact-and-state-v1",
    "state_change": "change-and-history-v1",
    "ordered_task": "procedure-and-rule-v1",
    "exception_risk": "procedure-and-rule-v1",
    "rule_application": "procedure-and-rule-v1",
    "assumption_check": "fact-and-state-v1",
    "relational_synthesis": "synthesis-v1",
}


def profile_for_need(need_type: str) -> RetrievalProfile:
    try:
        return PROFILES[_NEED_PROFILE[need_type]]
    except KeyError as exc:
        raise ValueError(f"unsupported information need: {need_type}") from exc
