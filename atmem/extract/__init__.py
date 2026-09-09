from __future__ import annotations

from atmem.core.policy import classify_source, forget_needle, is_forget_request
from atmem.extract.rules import CandidateFact, extract_facts
from atmem.extract.classify import (
    Classification,
    classify_candidate,
    classify_memory_class,
)
from atmem.extract.context import (
    EvidenceInfluence,
    Resolution,
    ResolutionContext,
    build_resolution_context,
)
from atmem.extract.models import (
    ExtractionProposal,
    MemoryClass,
    ProposalAction,
    ProposalEvidence,
    ProposalPrecondition,
    from_legacy_proposal,
)
from atmem.extract.review import DECISIONS, ReviewPolicy, ReviewService
from atmem.extract.validation import (
    Screening,
    Validation,
    propose_from_atbot,
    propose_from_rules,
    screen_content,
    validate_proposal,
)

__all__ = [
    "CandidateFact",
    "Classification",
    "DECISIONS",
    "EvidenceInfluence",
    "ExtractionProposal",
    "MemoryClass",
    "ProposalAction",
    "ProposalEvidence",
    "ProposalPrecondition",
    "Resolution",
    "ResolutionContext",
    "ReviewPolicy",
    "ReviewService",
    "Screening",
    "Validation",
    "build_resolution_context",
    "classify_candidate",
    "classify_memory_class",
    "classify_source",
    "extract_facts",
    "forget_needle",
    "from_legacy_proposal",
    "is_forget_request",
    "propose_from_atbot",
    "propose_from_rules",
    "screen_content",
    "validate_proposal",
]
