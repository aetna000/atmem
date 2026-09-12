"""Closed role, capture-mode and scope contracts for protected evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CaptureMode(str, Enum):
    FULL = "full"
    METADATA = "metadata"
    OFF = "off"


class EvidenceRole(str, Enum):
    VIEWER = "viewer"
    INVESTIGATOR = "investigator"
    EVIDENCE_COLLECTOR = "evidence_collector"


class EvidenceOperation(str, Enum):
    VIEW = "view"
    SEARCH = "search"
    RECONSTRUCT = "reconstruct"
    REPLAY_MANIFEST = "replay_manifest"
    ENCRYPTED_EXPORT = "encrypted_export"
    PLAINTEXT_EXPORT = "plaintext_export"
    GRANT = "grant"
    RETENTION = "retention"
    DELETE = "delete"
    ROTATE = "rotate"
    LOCK = "lock"
    UNLOCK = "unlock"


_ROLE_OPERATIONS = {
    EvidenceRole.VIEWER: frozenset(
        {EvidenceOperation.VIEW, EvidenceOperation.SEARCH}
    ),
    EvidenceRole.INVESTIGATOR: frozenset(
        {
            EvidenceOperation.VIEW,
            EvidenceOperation.SEARCH,
            EvidenceOperation.RECONSTRUCT,
            EvidenceOperation.REPLAY_MANIFEST,
            EvidenceOperation.ENCRYPTED_EXPORT,
        }
    ),
    EvidenceRole.EVIDENCE_COLLECTOR: frozenset(EvidenceOperation),
}


def _identifier(name: str, value: str) -> str:
    clean = str(value or "").strip()
    if not clean or len(clean) > 512 or any(ord(char) < 32 for char in clean):
        raise ValueError(f"{name} must be a printable identifier of at most 512 characters")
    return clean


@dataclass(frozen=True, slots=True)
class EvidenceScope:
    tenant_id: str
    subject_id: str
    workspace_id: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _identifier("tenant_id", self.tenant_id))
        object.__setattr__(self, "subject_id", _identifier("subject_id", self.subject_id))
        for name in ("workspace_id", "run_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _identifier(name, value))

    def permits(self, target: "EvidenceScope") -> bool:
        if self.tenant_id != target.tenant_id or self.subject_id != target.subject_id:
            return False
        if self.workspace_id is not None and self.workspace_id != target.workspace_id:
            return False
        if self.run_id is not None and self.run_id != target.run_id:
            return False
        return True

    def to_dict(self) -> dict[str, str | None]:
        return {
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
        }


@dataclass(frozen=True, slots=True)
class EvidencePrincipal:
    principal_id: str
    role: EvidenceRole
    scope: EvidenceScope

    def __post_init__(self) -> None:
        object.__setattr__(self, "principal_id", _identifier("principal_id", self.principal_id))
        if not isinstance(self.role, EvidenceRole):
            object.__setattr__(self, "role", EvidenceRole(self.role))

    def authorize(self, operation: EvidenceOperation, target: EvidenceScope) -> None:
        if not self.scope.permits(target) or operation not in _ROLE_OPERATIONS[self.role]:
            raise PermissionError(
                "evidence operation is not authorized for this principal and scope"
            )

    @property
    def operations(self) -> frozenset[EvidenceOperation]:
        return _ROLE_OPERATIONS[self.role]
