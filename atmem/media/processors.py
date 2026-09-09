"""Replaceable processor boundary with explicit authorization and egress."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Protocol
import uuid

from .access import AccessPolicy, access_content
from .models import ArtifactReference, Consent, DerivedObservation


class MediaProcessor(Protocol):
    @property
    def identity(self) -> dict[str, str]: ...
    def observe(self, content: bytes, media_kind: str) -> list[dict[str, Any]]: ...


def process_reference(reference: ArtifactReference, resolver: Callable[[ArtifactReference, int], bytes], processor: MediaProcessor, *, policy: AccessPolicy, current_reference: Callable[[str], ArtifactReference] | None = None, redactor: Callable[[bytes], bytes] | None = None) -> tuple[list[DerivedObservation], dict[str, Any]]:
    identity = dict(processor.identity); hosted = identity.get("location") == "hosted"
    if hosted and not policy.allow_hosted_egress: raise PermissionError("hosted media egress was not approved")
    content, access_receipt = access_content(reference, resolver, policy=policy)
    authorized = redactor(content) if redactor else content
    raw = processor.observe(authorized, reference.media_kind.value)
    if current_reference is not None:
        current = current_reference(reference.artifact_id)
        if current.consent is not Consent.GRANTED or current.consent_generation != reference.consent_generation: raise PermissionError("consent changed while media was processed")
    now = datetime.now(timezone.utc).isoformat(); config_sha = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(); observations=[]
    for item in raw:
        confidence = item.get("confidence")
        if confidence is not None and not 0 <= float(confidence) <= 1: raise ValueError("processor confidence is invalid")
        observations.append(DerivedObservation(f"obs_{uuid.uuid4().hex}", reference.artifact_id, reference.subject_id, reference.workspace_id, str(item.get("text") or ""), dict(item.get("evidence_region") or {}), identity, config_sha, float(confidence) if confidence is not None else None, reference.consent_generation, "hosted" if hosted else "local", now))
    return observations, {"format": "atmem-media-processing-receipt-v1", "artifact_id": reference.artifact_id, "access": access_receipt, "processor": identity, "prompt_config_sha256": config_sha, "egress": "hosted" if hosted else "local", "redacted": redactor is not None, "observation_count": len(observations)}
