from __future__ import annotations

from atmem.core.policy import classify_source, forget_needle, is_forget_request
from atmem.extract.rules import CandidateFact, extract_facts
from atmem.extract.models import (
    ExtractionProposal,
    MemoryClass,
    ProposalAction,
    ProposalEvidence,
    ProposalPrecondition,
    from_legacy_proposal,
)

__all__ = [
    "CandidateFact",
    "ExtractionProposal",
    "MemoryClass",
    "ProposalAction",
    "ProposalEvidence",
    "ProposalPrecondition",
    "classify_source",
    "extract_facts",
    "forget_needle",
    "from_legacy_proposal",
    "is_forget_request",
]
