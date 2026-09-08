"""Versioned entity, relation, path and identity-mutation contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    record_id: str
    evidence_id: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class Entity:
    entity_id: str
    subject_id: str
    canonical_name: str
    normalized_name: str
    entity_type: str
    aliases: tuple[str, ...]
    lifecycle: str
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class Relation:
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    confidence: float | None
    valid_from: str | None
    valid_to: str | None
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class AuthorizedPath:
    entities: tuple[str, ...]
    relations: tuple[str, ...]
    record_ids: tuple[str, ...]
    byte_length: int
    reason_codes: tuple[str, ...]
    format: str = "atmem-graph-path-v1"
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class IdentityMutationReceipt:
    mutation_id: str
    subject_id: str
    action: str
    preview_sha256: str
    affected_entity_ids: tuple[str, ...]
    lineage: tuple[dict[str, str], ...]
    generation_id: str | None
    status: str
    format: str = "atmem-graph-identity-mutation-v1"
    def to_dict(self) -> dict[str, Any]: return asdict(self)
