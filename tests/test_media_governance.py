from __future__ import annotations

from hashlib import sha256

import pytest

from atmem import Memory
from atmem.media.access import AccessPolicy, access_content
from atmem.media.models import ArtifactLocator, ArtifactReference, Consent, MediaKind
from atmem.media.processors import process_reference
from atmem.media.service import MediaService


class Processor:
    identity = {"provider": "fixture", "model": "local-v1", "revision": "1", "location": "local"}
    def observe(self, content, media_kind): return [{"text": "Receipt total is 42", "confidence": .9, "evidence_region": {"page": 1}}]


def _reference(content=b"safe"):
    return ArtifactReference("artifact-1","alice","workspace",MediaKind.IMAGE,ArtifactLocator("host","host://artifact/1"),sha256(content).hexdigest(),consent=Consent.GRANTED)


def test_host_custody_processing_retrieval_and_revocation() -> None:
    memory=Memory(":memory:"); service=MediaService(memory.store); reference=_reference(); service.put_reference(reference)
    observations, receipt=process_reference(reference,lambda _ref,_limit:b"safe",Processor(),policy=AccessPolicy(),current_reference=service.get_reference)
    assert not receipt["access"]["copied"] and receipt["egress"]=="local"
    service.store_observations(observations)
    assert service.retrieve("alice","workspace","receipt")[0]["text"]=="Receipt total is 42"
    revoked=service.revoke(reference.artifact_id)
    assert revoked["host_original_deleted"] is False
    assert service.retrieve("alice","workspace","receipt")==[]
    memory.close()


def test_changed_bytes_egress_and_late_consent_fail_closed() -> None:
    reference=_reference()
    with pytest.raises(ValueError,match="changed"):
        access_content(reference,lambda _ref,_limit:b"changed",policy=AccessPolicy())
    class Hosted(Processor): identity={**Processor.identity,"location":"hosted"}
    with pytest.raises(PermissionError,match="egress"):
        process_reference(reference,lambda _ref,_limit:b"safe",Hosted(),policy=AccessPolicy())
    memory=Memory(":memory:"); service=MediaService(memory.store); service.put_reference(reference)
    def changed(_artifact):
        service.revoke(reference.artifact_id); return service.get_reference(reference.artifact_id)
    with pytest.raises(PermissionError,match="consent changed"):
        process_reference(reference,lambda _ref,_limit:b"safe",Processor(),policy=AccessPolicy(),current_reference=changed)
    memory.close()


def test_scope_and_locator_privacy() -> None:
    memory=Memory(":memory:"); service=MediaService(memory.store); service.put_reference(_reference())
    assert service.retrieve("bob","workspace","receipt")==[]
    with pytest.raises(ValueError,match="credentials"):
        ArtifactLocator("host","host://user:secret@artifact/1")
    memory.close()
