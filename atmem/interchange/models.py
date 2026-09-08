"""Versioned neutral archive, scope and receipt contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from atmem.core.canonical import canonical_json, sha256_hex


@dataclass(frozen=True, slots=True)
class ScopeMap:
    subject_id: str
    workspace_id: str
    agent_id: str
    tenant_id: str = "local"

    def __post_init__(self) -> None:
        if not all((self.subject_id.strip(), self.workspace_id.strip(), self.agent_id.strip(), self.tenant_id.strip())):
            raise ValueError("an explicit complete scope map is required")

    def to_dict(self) -> dict[str, str]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ArchiveRecord:
    source_id: str
    content: str
    scope: ScopeMap
    status: str = "active"
    source: str = "neutral"
    metadata: dict[str, Any] | None = None
    history: tuple[dict[str, Any], ...] = ()
    evidence: tuple[dict[str, Any], ...] = ()

    @property
    def sha256(self) -> str: return sha256_hex(canonical_json(self.to_dict()))
    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "content": self.content, "scope": self.scope.to_dict(), "status": self.status, "source": self.source, "metadata": self.metadata or {}, "history": list(self.history), "evidence": list(self.evidence)}


@dataclass(frozen=True, slots=True)
class ArchiveManifest:
    archive_id: str
    created_at: str
    record_count: int
    records_sha256: str
    source: str
    format: str = "atmem-memory-archive-v1"
    version: str = "1"

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ImportReceipt:
    run_id: str
    archive_sha256: str
    options_sha256: str
    scope_map: ScopeMap
    counts: dict[str, int]
    affected_record_ids: tuple[str, ...]
    checkpoint: int
    verification: dict[str, Any]
    rollback: bool = False
    format: str = "atmem-memory-import-receipt-v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self); value["scope_map"] = self.scope_map.to_dict(); value["affected_record_ids"] = list(self.affected_record_ids); return value
