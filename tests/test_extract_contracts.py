from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.contracts import (
    AuthorityScope,
    InterpreterIdentity,
    MemoryProposal,
    SourceBinding,
)
from atmem.extract.models import (
    ExtractionProposal,
    MemoryClass,
    ProposalAction,
    ProposalEvidence,
    ProposalPrecondition,
    from_legacy_proposal,
)


DIGEST = f"sha256:{'a' * 64}"


def _scope() -> AuthorityScope:
    return AuthorityScope("user-1", "agent-1", "private")


def _evidence() -> ProposalEvidence:
    return ProposalEvidence("source-1", DIGEST, 0, 12, DIGEST)


def test_v2_proposal_serializes_explicit_action_class_evidence_and_precondition() -> None:
    proposal = ExtractionProposal(
        proposal_id="proposal-2",
        idempotency_key="opaque-2",
        scope=_scope(),
        action=ProposalAction.UPDATE,
        memory_class=MemoryClass.DURABLE_FACT,
        confidence=0.91,
        reason_codes=("explicit_correction",),
        evidence=(_evidence(),),
        fact="User now prefers window seats.",
        fact_key="travel::seat",
        affected_record_ids=("memory-1",),
        preconditions=(ProposalPrecondition("memory-1", 4, "active", DIGEST),),
        review_required=True,
    )

    payload = proposal.to_dict()
    assert payload["format"] == "atmem-memory-proposal-v2"
    assert payload["action"] == "UPDATE"
    assert payload["memory_class"] == "durable_fact"
    assert payload["evidence"][0]["start_offset"] == 0
    assert proposal.digest().startswith("sha256:")


def test_mutating_proposal_requires_evidence_and_update_preconditions() -> None:
    with pytest.raises(ValueError, match="evidence"):
        ExtractionProposal(
            "proposal-2", "opaque-2", _scope(), ProposalAction.ADD,
            MemoryClass.DURABLE_FACT, 0.8, ("explicit_preference",), (),
            fact="User prefers window seats.",
        )
    with pytest.raises(ValueError, match="preconditions"):
        ExtractionProposal(
            "proposal-3", "opaque-3", _scope(), ProposalAction.SUPERSEDE,
            MemoryClass.DURABLE_FACT, 0.8, ("explicit_correction",), (_evidence(),),
            fact="User prefers window seats.", affected_record_ids=("memory-1",),
        )


def test_legacy_proposal_normalizes_without_changing_v1_contract() -> None:
    legacy = MemoryProposal(
        proposal_id="proposal-1",
        idempotency_key="opaque-1",
        scope=_scope(),
        fact="User prefers aisle seats.",
        source_ids=("source-1",),
        interpreter=InterpreterIdentity("rules", "rules-v1", "prompt-v1"),
        source_binding=SourceBinding("host_authenticated_turn", DIGEST),
    )
    normalized = from_legacy_proposal(legacy, evidence=(_evidence(),))

    assert legacy.to_dict()["format"] == "atmem-memory-proposal-v1"
    assert normalized.action is ProposalAction.ADD
    schema = json.loads(
        (Path(__file__).parents[1] / "atmem/schemas/v1/memory-proposal.json").read_text()
    )
    formats = {branch["$ref"].rsplit("/", 1)[-1] for branch in schema["oneOf"]}
    assert formats == {"v1", "v2"}
