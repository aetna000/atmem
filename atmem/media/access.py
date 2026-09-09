"""Host-controlled bounded content access with exact-byte receipts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable

from .models import ArtifactReference, Consent, Custody


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    maximum_bytes: int = 10 * 1024 * 1024
    copy_original: bool = False
    allow_hosted_egress: bool = False


def access_content(reference: ArtifactReference, resolver: Callable[[ArtifactReference, int], bytes], *, policy: AccessPolicy, malware_scan: Callable[[bytes], bool] | None = None, copy_sink: Callable[[ArtifactReference, bytes], str] | None = None) -> tuple[bytes, dict[str, object]]:
    if reference.consent is not Consent.GRANTED: raise PermissionError("media consent is not granted")
    if policy.maximum_bytes < 1: raise ValueError("maximum_bytes must be positive")
    content = resolver(reference, policy.maximum_bytes)
    if not isinstance(content, bytes) or len(content) > policy.maximum_bytes: raise ValueError("host returned invalid or oversized media bytes")
    digest = sha256(content).hexdigest()
    if digest != reference.content_sha256: raise ValueError("artifact bytes changed at the locator")
    if malware_scan is not None and not malware_scan(content): raise ValueError("artifact rejected by malware policy")
    copied_locator = None
    if policy.copy_original:
        if copy_sink is None: raise ValueError("copy policy requires an explicit controlled copy sink")
        copied_locator = copy_sink(reference, content)
    return content, {"format": "atmem-media-access-receipt-v1", "artifact_id": reference.artifact_id, "content_sha256": digest, "bytes_accessed": len(content), "custody": reference.custody.value, "copied": copied_locator is not None, "copied_locator_sha256": sha256(str(copied_locator).encode()).hexdigest() if copied_locator else None}
