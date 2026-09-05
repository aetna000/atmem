"""Decide what a candidate would do to memory, and why.

Classification is deliberately separate from committing. It compares one
candidate against the current eligible values in a bounded
:class:`~atmem.extract.context.ResolutionContext` and returns the action it
would take, the memory class it believes the candidate belongs to, stable
reason codes, and the exact preconditions a commit would have to satisfy.
Nothing here writes; the same result is used for shadow reporting and for a
governed commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from atmem.core.canonical import sha256_hex
from atmem.core.policy import normalize_content
from atmem.extract.context import ResolutionContext
from atmem.extract.models import MemoryClass, ProposalAction, ProposalPrecondition


_TEMPORARY_RE = re.compile(
    r"\b(?:right now|for now|currently|at the moment|today|tonight|this (?:week|"
    r"morning|afternoon|evening)|temporarily|until (?:tomorrow|friday|monday|next)"
    r"|for the next \w+)\b",
    re.I,
)
_PROCEDURE_RE = re.compile(
    r"\b(?:step \d|first .*?(?:then|after that)|the process is|workflow is|"
    r"always run|before you .*?(?:run|deploy|commit)|how i (?:do|handle|run))\b",
    re.I | re.S,
)
_EPISODE_RE = re.compile(
    r"\b(?:yesterday|last (?:night|week|month|year)|earlier today|this morning we|"
    r"we (?:met|discussed|shipped|agreed)|i (?:went|visited|attended|called))\b",
    re.I,
)
_CORRECTION_RE = re.compile(
    r"\b(?:actually|correction|instead|no longer|not .*? any ?more|"
    r"going forward|from now on|changed to|scratch that|i meant)\b",
    re.I | re.S,
)


@dataclass(frozen=True, slots=True)
class Classification:
    """What one candidate would do, expressed before anything is written."""

    action: ProposalAction
    memory_class: MemoryClass
    reason_codes: tuple[str, ...]
    affected_record_ids: tuple[str, ...] = ()
    preconditions: tuple[ProposalPrecondition, ...] = ()
    review_required: bool = False
    influences: tuple[dict[str, Any], ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "memory_class": self.memory_class.value,
            "reason_codes": list(self.reason_codes),
            "affected_record_ids": list(self.affected_record_ids),
            "preconditions": [
                {
                    "record_id": item.record_id,
                    "generation": item.generation,
                    "status": item.status,
                    "content_sha256": item.content_sha256,
                }
                for item in self.preconditions
            ],
            "review_required": self.review_required,
            "influences": [dict(item) for item in self.influences],
        }


def classify_memory_class(source_text: str) -> MemoryClass:
    """Label what kind of memory a statement is, from the words actually used."""
    if _PROCEDURE_RE.search(source_text):
        return MemoryClass.PROCEDURE
    if _TEMPORARY_RE.search(source_text):
        return MemoryClass.TEMPORARY_STATE
    if _EPISODE_RE.search(source_text):
        return MemoryClass.EPISODE
    return MemoryClass.DURABLE_FACT


def classify_candidate(
    *,
    fact: str,
    fact_key: str | None,
    source_text: str,
    context: ResolutionContext,
    memory_class: MemoryClass | None = None,
    full_text: str | None = None,
) -> Classification:
    """Compare one candidate against current eligible values.

    ``source_text`` is the exact span the claim was read from; ``full_text``
    is the whole message it appeared in. Correction cues ("actually", "from
    now on") routinely sit outside the matched span, so intent is read from
    the full message while evidence stays pinned to the span.
    """
    intent_text = full_text if full_text is not None else source_text
    resolution = context.resolve(source_text)
    influences = tuple(item.to_dict() for item in resolution.influences)
    inferred = memory_class or classify_memory_class(intent_text)

    if inferred is MemoryClass.NON_MEMORY:
        return Classification(
            action=ProposalAction.REJECT,
            memory_class=inferred,
            reason_codes=("non_memory_content",),
            influences=influences,
        )
    if resolution.ambiguous:
        return Classification(
            action=ProposalAction.REJECT,
            memory_class=inferred,
            reason_codes=("ambiguous_referent",),
            review_required=True,
            influences=influences,
        )

    normalized = normalize_content(fact)
    for record in context.records:
        if normalize_content(str(record.get("content") or "")) == normalized:
            return Classification(
                action=ProposalAction.NOOP,
                memory_class=inferred,
                reason_codes=("duplicate_of_active_record",),
                affected_record_ids=(str(record["id"]),),
                influences=influences,
            )

    conflicts = context.eligible_records_for_fact_key(fact_key)
    non_durable = inferred is not MemoryClass.DURABLE_FACT
    if conflicts:
        preconditions = tuple(_precondition(record) for record in conflicts)
        affected = tuple(str(record["id"]) for record in conflicts)
        refinement = all(
            _is_refinement(str(record.get("content") or ""), fact)
            for record in conflicts
        )
        corrected = bool(_CORRECTION_RE.search(intent_text))
        if refinement:
            return Classification(
                action=ProposalAction.UPDATE,
                memory_class=inferred,
                reason_codes=("refines_current_value",),
                affected_record_ids=affected,
                preconditions=preconditions,
                review_required=non_durable,
                influences=influences,
            )
        return Classification(
            action=ProposalAction.SUPERSEDE,
            memory_class=inferred,
            reason_codes=(
                ("explicit_correction",) if corrected else ("contradicts_current_value",)
            ),
            affected_record_ids=affected,
            preconditions=preconditions,
            review_required=non_durable,
            influences=influences,
        )

    return Classification(
        action=ProposalAction.ADD,
        memory_class=inferred,
        reason_codes=(
            ("new_fact_for_slot",) if fact_key else ("new_unkeyed_fact",)
        )
        + (("non_durable_class_requires_review",) if non_durable else ()),
        review_required=non_durable,
        influences=influences,
    )


def _precondition(record: dict[str, Any]) -> ProposalPrecondition:
    return ProposalPrecondition(
        record_id=str(record["id"]),
        generation=int(record.get("generation") or 0),
        status=str(record.get("status") or "active"),
        content_sha256=f"sha256:{sha256_hex(str(record.get('content') or ''))}",
    )


def _is_refinement(existing: str, candidate: str) -> bool:
    """True when the candidate keeps the old value and adds detail to it."""
    old = normalize_content(existing).split()
    new = normalize_content(candidate).split()
    if not old or len(new) <= len(old):
        return False
    return _is_subsequence(old, new)


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    iterator = iter(haystack)
    return all(token in iterator for token in needle)
