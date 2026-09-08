"""Versioned, content-free contracts for executable product invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class VerdictStatus(str, Enum):
    PROVEN = "proven"
    PARTIALLY_PROVEN = "partially_proven"
    UNPROVEN = "unproven"


@dataclass(frozen=True, slots=True)
class AssertionResult:
    assertion_id: str
    configuration: str
    executed: bool
    passed: bool
    evidence: str
    skipped: bool = False
    detail_code: str | None = None

    def __post_init__(self) -> None:
        if not self.assertion_id.strip() or not self.configuration.strip():
            raise ValueError("assertion_id and configuration are required")
        if self.passed and (not self.executed or self.skipped):
            raise ValueError("a passing assertion must have executed and not be skipped")


@dataclass(frozen=True, slots=True)
class Invariant:
    invariant_id: str
    guarantee: str
    principle: str
    owning_spec: str
    assertions: tuple[str, ...]
    configurations: tuple[str, ...] = ("base",)
    amendments: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.invariant_id.startswith("INV-"):
            raise ValueError("invariant_id must use the INV- prefix")
        if not self.guarantee.strip() or not self.principle.strip():
            raise ValueError("guarantee and principle are required")
        if not self.assertions:
            raise ValueError(f"{self.invariant_id} has no owning assertion")
        if not self.configurations:
            raise ValueError(f"{self.invariant_id} has no declared configuration")
        if len(set(self.assertions)) != len(self.assertions):
            raise ValueError(f"{self.invariant_id} repeats an assertion")


@dataclass(frozen=True, slots=True)
class InvariantVerdict:
    invariant_id: str
    status: VerdictStatus
    guarantee: str
    owning_spec: str
    evidence: tuple[str, ...]
    uncovered_configurations: tuple[str, ...] = ()
    missing_assertions: tuple[str, ...] = ()
    failed_assertions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "status": self.status.value,
            "guarantee": self.guarantee,
            "owning_spec": self.owning_spec,
            "evidence": list(self.evidence),
            "uncovered_configurations": list(self.uncovered_configurations),
            "missing_assertions": list(self.missing_assertions),
            "failed_assertions": list(self.failed_assertions),
        }


@dataclass(frozen=True, slots=True)
class InvariantRegistry:
    version: str
    invariants: tuple[Invariant, ...]
    format: str = field(default="atmem-invariant-registry-v1", init=False)

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("registry version is required")
        ids = [item.invariant_id for item in self.invariants]
        if len(ids) != len(set(ids)):
            raise ValueError("invariant IDs must be unique")

    def by_id(self, invariant_id: str) -> Invariant:
        for invariant in self.invariants:
            if invariant.invariant_id == invariant_id:
                return invariant
        raise KeyError(invariant_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "version": self.version,
            "invariants": [
                {
                    "invariant_id": item.invariant_id,
                    "guarantee": item.guarantee,
                    "principle": item.principle,
                    "owning_spec": item.owning_spec,
                    "assertions": list(item.assertions),
                    "configurations": list(item.configurations),
                    "amendments": [dict(value) for value in item.amendments],
                }
                for item in self.invariants
            ],
        }
