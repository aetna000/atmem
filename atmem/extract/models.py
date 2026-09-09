"""Typed, evidence-bound contracts for governed memory extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
from typing import Any, ClassVar

from atmem.contracts import AuthorityScope, MemoryProposal
from atmem.core.canonical import canonical_json, sha256_hex


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class MemoryClass(str, Enum):
    DURABLE_FACT = "durable_fact"
    TEMPORARY_STATE = "temporary_state"
    EPISODE = "episode"
    PROCEDURE = "procedure"
    NON_MEMORY = "non_memory"


class ProposalAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    SUPERSEDE = "SUPERSEDE"
    REJECT = "REJECT"
    NOOP = "NOOP"


@dataclass(frozen=True, slots=True)
class ProposalEvidence:
    source_id: str
    source_sha256: str
    start_offset: int
    end_offset: int
    excerpt_sha256: str

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("evidence source_id is required")
        _require_digest("source_sha256", self.source_sha256)
        _require_digest("excerpt_sha256", self.excerpt_sha256)
        if self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise ValueError("evidence offsets must identify a non-empty source span")


@dataclass(frozen=True, slots=True)
class ProposalPrecondition:
    record_id: str
    generation: int
    status: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not self.record_id or not self.status:
            raise ValueError("precondition record_id and status are required")
        if self.generation < 0:
            raise ValueError("precondition generation cannot be negative")
        _require_digest("content_sha256", self.content_sha256)


@dataclass(frozen=True, slots=True)
class ExtractionProposal:
    """A single explicit extraction outcome; it never commits by itself."""

    format: ClassVar[str] = "atmem-memory-proposal-v2"
    proposal_id: str
    idempotency_key: str
    scope: AuthorityScope
    action: ProposalAction
    memory_class: MemoryClass
    confidence: float
    reason_codes: tuple[str, ...]
    evidence: tuple[ProposalEvidence, ...]
    fact: str | None = None
    fact_key: str | None = None
    affected_record_ids: tuple[str, ...] = ()
    preconditions: tuple[ProposalPrecondition, ...] = ()
    review_required: bool = False

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.idempotency_key:
            raise ValueError("proposal_id and idempotency_key are required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.reason_codes:
            raise ValueError("at least one bounded reason code is required")
        if not self.evidence:
            raise ValueError("at least one exact source evidence span is required")
        mutations = {ProposalAction.ADD, ProposalAction.UPDATE, ProposalAction.SUPERSEDE}
        if self.action in mutations and (not self.fact or len(self.fact) > 2_000):
            raise ValueError("mutating proposals require a fact of at most 2,000 characters")
        if self.action in {ProposalAction.UPDATE, ProposalAction.SUPERSEDE}:
            if not self.affected_record_ids or not self.preconditions:
                raise ValueError("updates require affected records and lifecycle preconditions")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["format"] = self.format
        value["action"] = self.action.value
        value["memory_class"] = self.memory_class.value
        return value

    def digest(self) -> str:
        return f"sha256:{sha256_hex(canonical_json(self.to_dict()))}"


def from_legacy_proposal(
    proposal: MemoryProposal,
    *,
    evidence: tuple[ProposalEvidence, ...],
) -> ExtractionProposal:
    """Normalize a v1 proposal without silently strengthening its assurance."""

    actions = {
        "add": ProposalAction.ADD,
        "supports": ProposalAction.NOOP,
        "duplicate": ProposalAction.NOOP,
        "extends": ProposalAction.UPDATE,
        "contradicts": ProposalAction.SUPERSEDE,
        "supersedes": ProposalAction.SUPERSEDE,
        "uncertain": ProposalAction.REJECT,
    }
    action = actions[proposal.suggested_action]
    requires_target = action in {ProposalAction.UPDATE, ProposalAction.SUPERSEDE}
    if requires_target:
        # v1 carried no generation-bound preconditions, so it cannot safely
        # be promoted into a mutation without a later validation stage.
        action = ProposalAction.REJECT
    return ExtractionProposal(
        proposal_id=proposal.proposal_id,
        idempotency_key=proposal.idempotency_key,
        scope=proposal.scope,
        action=action,
        memory_class=MemoryClass.DURABLE_FACT,
        confidence=proposal.confidence,
        reason_codes=(f"legacy_{proposal.suggested_action}",),
        evidence=evidence,
        fact=proposal.fact,
        fact_key=proposal.fact_key,
        affected_record_ids=(),
        review_required=(proposal.suggested_action == "uncertain" or requires_target),
    )


def _require_digest(name: str, value: str) -> None:
    if not _DIGEST.fullmatch(str(value)):
        raise ValueError(f"{name} must use sha256:<64 lowercase hex>")
