"""Producer-sequenced delivery contracts and deterministic replay decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex


class DeliveryDecision(str, Enum):
    ACCEPTED = "accepted"
    REPLAYED = "replayed"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class ProducerEvent:
    producer_instance_id: str
    producer_epoch: str
    producer_sequence: int
    event_id: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("producer_instance_id", "producer_epoch", "event_id"):
            value = str(getattr(self, name) or "").strip()
            if not value or len(value) > 512:
                raise ValueError(f"{name} is required and must be at most 512 characters")
        if isinstance(self.producer_sequence, bool) or self.producer_sequence < 1:
            raise ValueError("producer_sequence must be a positive integer")

    @property
    def body_sha256(self) -> str:
        return sha256_hex(canonical_json(dict(self.body)))


@dataclass(frozen=True, slots=True)
class CoverageGap:
    reason: str
    producer_instance_id: str
    producer_epoch: str
    first_sequence: int | None = None
    last_sequence: int | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        for name in ("reason", "producer_instance_id", "producer_epoch"):
            value = str(getattr(self, name) or "").strip()
            if not value or len(value) > 512:
                raise ValueError(f"{name} is required and must be at most 512 characters")
            object.__setattr__(self, name, value)
        if self.first_sequence is not None and self.first_sequence < 1:
            raise ValueError("first_sequence must be positive")
        if self.last_sequence is not None and self.last_sequence < 1:
            raise ValueError("last_sequence must be positive")
        if (
            self.first_sequence is not None
            and self.last_sequence is not None
            and self.last_sequence < self.first_sequence
        ):
            raise ValueError("last_sequence must not precede first_sequence")
        if self.detail is not None:
            object.__setattr__(self, "detail", str(self.detail).strip()[:512] or None)
