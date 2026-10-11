from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex


SPLITS = ("train", "validation", "calibration", "sealed_test")
OPERATIONS = ("ADD", "UPDATE", "SUPERSEDE", "NOOP", "REJECT")
MEMORY_CLASSES = ("durable_fact", "temporary_state", "episode", "procedure", "non_memory")


def digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + sha256_hex(canonical_json(dict(value)))


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    event_id: str
    text: str
    actor: str
    scope: str
    timestamp: str

    def __post_init__(self) -> None:
        if not all((self.event_id, self.text, self.actor, self.scope, self.timestamp)):
            raise ValueError("evidence event fields are required")


@dataclass(frozen=True, slots=True)
class FormationScenarioV1:
    scenario_id: str
    fictional_identity_group: str
    template_family: str
    semantic_chain_id: str
    paraphrase_cluster_id: str
    evidence_events: tuple[EvidenceEvent, ...]
    initial_state: Mapping[str, Any]
    expected_final_state: Mapping[str, Any]
    scope_fixture: Mapping[str, str]
    difficulty: str
    safety_tags: tuple[str, ...]
    generator_version: str
    seed: int
    split: str
    license_provenance: str = "Apache-2.0 synthetic generator; no real-user data"

    def __post_init__(self) -> None:
        if self.split not in SPLITS:
            raise ValueError("unknown dataset split")
        if not self.evidence_events:
            raise ValueError("scenario requires evidence")
        if self.difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("unknown difficulty")

    def to_dict(self) -> dict[str, Any]:
        return json.loads(canonical_json(asdict(self)))


@dataclass(frozen=True, slots=True)
class TypedDecisionExampleV1:
    example_id: str
    scenario_id: str
    question_id: str
    question_type: str
    authorized_input: Mapping[str, Any]
    choice_ids: tuple[str, ...]
    expected_choice_ids: tuple[str, ...]
    allow_abstain: bool
    oracle_receipt: Mapping[str, Any]
    audit_rationale: str
    split: str
    content_digest: str

    def __post_init__(self) -> None:
        if self.split not in SPLITS:
            raise ValueError("unknown dataset split")
        if self.question_type not in {"choice", "noul", "score"}:
            raise ValueError("unsupported question type")
        if not self.choice_ids or len(set(self.choice_ids)) != len(self.choice_ids):
            raise ValueError("choices must be non-empty and unique")
        if not self.expected_choice_ids or not set(self.expected_choice_ids).issubset(self.choice_ids):
            raise ValueError("expected choices must belong to the finite choice set")
        expected = digest(self.content_without_digest())
        if self.content_digest != expected:
            raise ValueError("decision content digest mismatch")

    def content_without_digest(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "scenario_id": self.scenario_id,
            "question_id": self.question_id,
            "question_type": self.question_type,
            "authorized_input": dict(self.authorized_input),
            "choice_ids": list(self.choice_ids),
            "expected_choice_ids": list(self.expected_choice_ids),
            "allow_abstain": self.allow_abstain,
            "oracle_receipt": dict(self.oracle_receipt),
            "audit_rationale": self.audit_rationale,
            "split": self.split,
        }

    def to_dict(self) -> dict[str, Any]:
        return json.loads(canonical_json(asdict(self)))
