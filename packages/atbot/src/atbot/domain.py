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
