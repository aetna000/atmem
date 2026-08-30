from __future__ import annotations

from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts import (
    AuthorityScope,
    ContextRequest,
    ExposureConfirmation,
    InterpreterIdentity,
    MemoryProposal,
    RecallRequest,
    SourceBinding,
    SourceCaptureRequest,
    capabilities,
)


def _scope(workspace: str = "private") -> AuthorityScope:
    return AuthorityScope("user-1", "atbot-1", workspace)


def _capture(memory: Memory, text: str = "I prefer aisle seats."):
    request = SourceCaptureRequest(
        source_id="source-1",
        idempotency_key="capture-1",
        scope=_scope(),
        message=text,
        session_id="session-1",
        turn_id="turn-1",
    )
    return request, memory.capture_source(request)


def _proposal(source_sha256: str, **changes) -> MemoryProposal:
    base = MemoryProposal(
        proposal_id="proposal-1",
        idempotency_key="proposal-opaque-1",
        scope=_scope(),
        fact="User prefers aisle seats.",
        fact_key="travel::seat-preference",
        confidence=0.94,
        source_ids=("source-1",),
        interpreter=InterpreterIdentity(
            provider="ollama",
            model="qwen3:local",
            prompt_version="atbot-extract-v1",
        ),
        source_binding=SourceBinding(
            method="host_authenticated_turn",
            source_sha256=source_sha256,
            assurance="host_authenticated",
        ),
    )
    return replace(base, **changes)


def test_capabilities_are_versioned_and_local_vector_first() -> None:
    value = capabilities()
    assert value["format"] == "atmem-capabilities-v1"
    assert value["protocol_versions"] == ["1"]
    assert value["features"]["default_local_vectors"] is True


def test_source_and_proposal_replay_are_durable_and_typed(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    request, captured = _capture(memory)
    assert memory.capture_source(request).replayed is True

    proposal = _proposal(captured.source_sha256)
    admission = memory.submit_proposal(proposal)
    replay = memory.submit_proposal(proposal)

    assert admission.decision == "active"
    assert len(admission.record_ids) == 1
    assert replay.replayed is True
    assert replay.record_ids == admission.record_ids
    memory.close()


def test_idempotency_key_reuse_with_changed_payload_fails_closed(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    request, captured = _capture(memory)
    changed_source = replace(request, message="I prefer window seats.")
    with pytest.raises(ValueError, match="different payload"):
        memory.capture_source(changed_source)

    proposal = _proposal(captured.source_sha256)
    memory.submit_proposal(proposal)
    changed = replace(proposal, fact="User prefers window seats.")
    with pytest.raises(ValueError, match="different payload"):
        memory.submit_proposal(changed)
    memory.close()


def test_poisoned_fact_key_cannot_supersede_an_unrelated_memory(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    _, captured = _capture(memory)
    first = memory.submit_proposal(_proposal(captured.source_sha256))

    second_source = SourceCaptureRequest(
        source_id="source-2",
        idempotency_key="capture-2",
        scope=_scope(),
        message="My passport expires in 2030.",
    )
    second_capture = memory.capture_source(second_source)
    poisoned = _proposal(
        second_capture.source_sha256,
        proposal_id="proposal-2",
        idempotency_key="proposal-2",
        fact="User passport expires in 2030.",
        source_ids=("source-2",),
        suggested_action="supersedes",
        related_record_ids=first.record_ids,
    )
    result = memory.submit_proposal(poisoned)

    assert result.decision == "conflict"
    assert result.review_required is True
    assert memory.store.get_record("user-1", first.record_ids[0])["status"] == "active"
    memory.close()


def test_governed_recall_context_and_exact_exposure_vertical_slice(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    _, captured = _capture(memory)
    admitted = memory.submit_proposal(_proposal(captured.source_sha256))

    candidates = memory.eligible_candidates(
        RecallRequest(
            request_id="recall-1",
            scope=_scope(),
            query="Which seat should I book?",
            min_score=0.0,
        )
    )
    assert [row.record_id for row in candidates.candidates] == list(
        admitted.record_ids
    )
    package = memory.prepare_context_v1(
        ContextRequest(
            context_id="context-1",
            candidate_set_id=candidates.candidate_set_id,
            scope=_scope(),
            record_ids=admitted.record_ids,
        )
    )
    assert package.context.encode("utf-8") == package.context.encode("utf-8")
    assert "aisle seats" in package.context

    confirmation = ExposureConfirmation(
        confirmation_id="confirmation-1",
        preparation_id=package.preparation_id,
        scope=_scope(),
        context_sha256=package.context_sha256,
        host_run_id="run-1",
    )
    receipt = memory.confirm_exposure_v1(confirmation)
    assert receipt.context_sha256 == package.context_sha256
    assert memory.confirm_exposure_v1(confirmation).replayed is True
    memory.close()


def test_cross_workspace_source_and_candidate_reuse_fails_closed(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    _, captured = _capture(memory)
    proposal = replace(_proposal(captured.source_sha256), scope=_scope("other"))
    with pytest.raises(ValueError, match="outside the authority scope"):
        memory.submit_proposal(proposal)
    memory.close()
