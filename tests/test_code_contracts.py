from __future__ import annotations

from hashlib import sha256

import pytest

from atmem.code.contracts import (
    CodeError,
    CodeContextPackage,
    CodeContextRequest,
    CodeMemoryCandidate,
    CodeObservation,
    CodeScope,
)


def _scope() -> CodeScope:
    return CodeScope("user-1", "project-1", "shared", "claude")


def test_observation_round_trip_is_closed_and_versioned() -> None:
    item = CodeObservation(
        "event-1", "session-1", "turn-1", "claude", "user_turn",
        "Please use the project's configured formatter.",
        "2026-10-14T00:00:00Z", "host:turn-1", "abc123", _scope(),
    )
    assert CodeObservation.from_dict(item.to_dict()) == item
    changed = item.to_dict()
    changed["unknown"] = "ignored?"
    with pytest.raises(ValueError, match="fields"):
        CodeObservation.from_dict(changed)


def test_context_request_requires_bounded_task_and_scope() -> None:
    request = CodeContextRequest("request-1", "session-1", "turn-1", "Fix a test", 2048, _scope())
    assert CodeContextRequest.from_dict(request.to_dict()) == request
    with pytest.raises(ValueError, match="max_context_bytes"):
        CodeContextRequest("request-1", "session-1", "turn-1", "Fix a test", True, _scope())


def test_context_package_cannot_change_bytes_after_digest() -> None:
    content = "One source-linked memory."
    digest = sha256(content.encode()).hexdigest()
    assert CodeContextPackage("request-1", content, digest, ("record-1",)).content == content
    with pytest.raises(ValueError, match="digest mismatch"):
        CodeContextPackage("request-1", content + "x", digest, ("record-1",))


def test_candidate_must_bind_to_exact_observation_digest() -> None:
    digest = sha256(b"source").hexdigest()
    assert CodeMemoryCandidate("event-1", "User prefers concise updates.", "preference", digest, _scope()).source_sha256 == digest
    with pytest.raises(ValueError, match="source_sha256"):
        CodeMemoryCandidate("event-1", "User prefers concise updates.", "preference", "bad", _scope())


def test_error_contract_is_closed_and_versioned() -> None:
    error = CodeError("event-1", "UNAUTHORIZED", False)
    assert CodeError.from_dict(error.to_dict()) == error
    with pytest.raises(ValueError, match="unsupported"):
        CodeError("event-1", "arbitrary", False)
