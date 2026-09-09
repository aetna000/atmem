"""AtBot-owned intelligence types; no canonical memory state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    fact: str
    fact_key: str | None = None
    confidence: float = 0.7
    sensitivity: str = "personal"
    entities: tuple[dict[str, str], ...] = ()
    suggested_action: str = "add"
    related_record_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderResult:
    text: str
    structured: dict[str, Any] | None
    provider: str
    model: str
    egress_class: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class TaskStateDelta:
    """A bounded task-state change AtBot suggests. It is never authoritative.

    AtBot proposes; AtMem validates the exact base revision, scope, transition
    rules, and evidence, and AtMem alone commits. Every field here is a claim
    to be checked, including the confidence.
    """

    task_id: str
    base_revision: int
    operations: tuple[dict[str, Any], ...] = ()
    affected_item_ids: tuple[str, ...] = ()
    confidence: float = 0.5
    reason: str = ""
    # The strongest assurance AtBot may honestly claim for its own reading of
    # an observation. AtMem enforces this ceiling again on admission.
    assurance: str = "model_interpreted"
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atbot-task-state-delta-v1",
            "task_id": self.task_id,
            "base_revision": self.base_revision,
            "operations": [dict(row) for row in self.operations],
            "affected_item_ids": list(self.affected_item_ids),
            "confidence": self.confidence,
            "reason": self.reason,
            "assurance": self.assurance,
            "evidence_ids": list(self.evidence_ids),
        }
