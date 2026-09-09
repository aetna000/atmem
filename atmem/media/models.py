"""Governed media reference, custody, consent and observation contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlsplit


class MediaKind(str, Enum):
    IMAGE = "image"; AUDIO = "audio"; VIDEO = "video"; FILE = "file"; TOOL_ARTIFACT = "tool_artifact"
class Custody(str, Enum):
    HOST = "host"; ATMEM_COPY = "atmem_copy"
class Consent(str, Enum):
    GRANTED = "granted"; REVOKED = "revoked"; UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ArtifactLocator:
    scheme: str
    value: str
    expires_at: str | None = None
    def __post_init__(self) -> None:
        if self.scheme not in {"host", "openclaw", "file", "tool"}: raise ValueError("unsupported artifact locator scheme")
        parsed = urlsplit(self.value)
        if parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError("artifact locator must contain no credentials, query or fragment")


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: str; subject_id: str; workspace_id: str; media_kind: MediaKind; locator: ArtifactLocator; content_sha256: str; custody: Custody = Custody.HOST; consent: Consent = Consent.UNKNOWN; consent_generation: int = 1; retention: dict[str, Any] | None = None
    format: str = "atmem-media-reference-v1"
    def __post_init__(self) -> None:
        if len(self.content_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.content_sha256.lower()): raise ValueError("content_sha256 must be lowercase SHA-256")
        if self.consent_generation < 1: raise ValueError("consent_generation must be positive")
    def to_dict(self) -> dict[str, Any]:
        value=asdict(self); value["media_kind"]=self.media_kind.value; value["custody"]=self.custody.value; value["consent"]=self.consent.value; return value


@dataclass(frozen=True, slots=True)
class DerivedObservation:
    observation_id: str; artifact_id: str; subject_id: str; workspace_id: str; text: str; evidence_region: dict[str, Any]; processor: dict[str, str]; prompt_config_sha256: str; confidence: float | None; consent_generation: int; egress: str; created_at: str
    format: str = "atmem-media-derived-observation-v1"
    def to_dict(self) -> dict[str, Any]: return asdict(self)
