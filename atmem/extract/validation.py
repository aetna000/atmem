"""One validator for every proposer, rules or model.

AtBot may propose; AtMem decides. Rule output and model output are normalized
into the same :class:`~atmem.extract.models.ExtractionProposal` and are then
screened by the same policy: instruction-shaped content, prompt injection,
secrets, and explicit "do not remember" signals are refused before admission,
untrusted sources can never produce an unreviewed mutation, and a proposal
that cannot cite an exact span is not a proposal at all.

The deterministic rules path is the fallback. When AtBot is absent, times out,
or returns malformed output, this module still emits typed outcomes with
stable reasons instead of silently adding or silently dropping memory.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from atmem.contracts import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.core.fact_keys import canonicalize_fact_key
from atmem.extract.classify import Classification, classify_candidate
from atmem.extract.context import ResolutionContext
from atmem.extract.models import (
    ExtractionProposal,
    MemoryClass,
    ProposalAction,
    ProposalEvidence,
)
from atmem.extract.rules import CandidateFact, extract_facts


MAX_FACT_LENGTH = 2_000

_INSTRUCTION_RE = re.compile(
    r"(?:ignore (?:all )?(?:previous|prior|above)|disregard (?:all )?(?:previous|prior)"
    r"|you are now|you must (?:always|never)|from now on,? (?:you|always)"
    r"|do not tell the (?:user|human)|new instructions?:|system prompt"
    r"|im_start|im_end|^\s*(?:system|assistant)\s*:)",
    re.I | re.M,
)
_SECRET_RE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9]{16,}\b"
    r"|\b(?:password|passphrase|api[ _-]?key|secret|access token|bearer token)\b\s*"
    r"(?:is|=|:)\s*\S+)",
    re.I,
)
_EXCLUSION_RE = re.compile(
    r"(?:do(?:n'?t| not) (?:remember|store|save|record) (?:this|that|it)?"
    r"|off the record|not for memory|keep this (?:out of|off) (?:memory|the record))",
    re.I,
)


@dataclass(frozen=True, slots=True)
class Screening:
    """The policy verdict on raw content, before any memory shape is assumed."""

    admissible: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "admissible": self.admissible,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class Validation:
    """Whether a normalized proposal may be committed, and under what terms."""

    valid: bool
    review_required: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "review_required": self.review_required,
            "reason_codes": list(self.reason_codes),
        }


def screen_content(text: str, *, trusted: bool = False) -> Screening:
    """Refuse instruction-shaped, secret-bearing, or excluded content.

    Untrusted text is data. Finding an instruction inside it is a reason to
    quarantine the text, never a reason to follow it. A trusted user turn is
    different in kind: "you must always use metric units" is that user stating
    a preference, not a third party seizing the agent, so the instruction
    screen applies only to untrusted sources. Secrets and explicit exclusion
    signals are refused from every source, including the user.
    """
    reasons: list[str] = []
    if not trusted and _INSTRUCTION_RE.search(text):
        reasons.append("instruction_shaped_content")
    if _SECRET_RE.search(text):
        reasons.append("secret_material_detected")
    if _EXCLUSION_RE.search(text):
        reasons.append("explicit_exclusion_signal")
    return Screening(not reasons, tuple(reasons))


def propose_from_rules(
    message: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    context: ResolutionContext,
    source_type: str | None = None,
    fallback_reason: str | None = None,
) -> tuple[ExtractionProposal, ...]:
    """Normalize the deterministic extractor into governed proposals."""
    extra = (fallback_reason,) if fallback_reason else ()
    screening = screen_content(message)
    if not screening.admissible:
        return (
            _refusal(
                message,
                scope=scope,
                source_id=source_id,
                reason_codes=screening.reason_codes + extra,
            ),
        )
    candidates = extract_facts(message, source_type=source_type)
    if not candidates:
        return (
            _outcome(
                message,
                scope=scope,
                source_id=source_id,
                span=(0, len(message)) if message else None,
                action=ProposalAction.NOOP,
                memory_class=MemoryClass.NON_MEMORY,
                reason_codes=("no_extractable_claim",) + extra,
                confidence=0.0,
            ),
        )
    return tuple(
        _from_candidate(
            candidate,
            message,
            scope=scope,
            source_id=source_id,
            context=context,
            extra_reasons=extra,
        )
        for candidate in candidates
    )


def propose_from_atbot(
    facts: Iterable[Any],
    message: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    context: ResolutionContext,
    source_type: str | None = None,
) -> tuple[ExtractionProposal, ...]:
    """Normalize AtBot output through the same gate as the rules path.

    Model output is untrusted structure over untrusted text. Rows that are
    malformed, unsupported by the source, or policy-refused become explicit
    typed refusals; they never widen what the proposer may change.
    """
    screening = screen_content(message)
    if not screening.admissible:
        return (
            _refusal(
                message,
                scope=scope,
                source_id=source_id,
                reason_codes=screening.reason_codes,
            ),
        )
    proposals: list[ExtractionProposal] = []
    for row in facts:
        fact = " ".join(str(_attr(row, "fact") or "").split())
        confidence = _confidence(_attr(row, "confidence"))
        if not fact or len(fact) > MAX_FACT_LENGTH or confidence is None:
            proposals.append(
                _refusal(
                    message,
                    scope=scope,
                    source_id=source_id,
                    reason_codes=("malformed_model_output",),
                )
            )
            continue
        fact_screening = screen_content(fact)
        if not fact_screening.admissible:
            proposals.append(
                _refusal(
                    message,
                    scope=scope,
                    source_id=source_id,
                    reason_codes=fact_screening.reason_codes,
                )
            )
            continue
        span = _support_span(message, fact)
        if span is None:
            # A claim the source does not support cannot cite evidence for
            # itself, so it is refused rather than admitted on model say-so.
            proposals.append(
                _refusal(
                    message,
                    scope=scope,
                    source_id=source_id,
                    reason_codes=("unsupported_by_source",),
                )
            )
            continue
        try:
            fact_key = canonicalize_fact_key(_attr(row, "fact_key"))
        except ValueError:
            fact_key = None
        classification = classify_candidate(
            fact=fact,
            fact_key=fact_key,
            source_text=message[span[0] : span[1]],
            context=context,
            full_text=message,
        )
        sensitivity = str(_attr(row, "sensitivity") or "personal")
        sensitive = sensitivity in {"sensitive", "restricted"}
        review = classification.review_required or sensitive
        proposals.append(
            _build(
                message,
                scope=scope,
                source_id=source_id,
                span=span,
                fact=fact,
                fact_key=fact_key,
                classification=classification,
                confidence=confidence,
                extra_reasons=("model_interpreted",)
                + (("sensitive_content_requires_review",) if sensitive else ()),
                review_required=review,
            )
        )
    if not proposals:
        proposals.append(
            _outcome(
                message,
                scope=scope,
                source_id=source_id,
                span=(0, len(message)) if message else None,
                action=ProposalAction.NOOP,
                memory_class=MemoryClass.NON_MEMORY,
                reason_codes=("model_returned_no_claim",),
                confidence=0.0,
            )
        )
    return tuple(proposals)


def validate_proposal(
    proposal: ExtractionProposal,
    *,
    source_text: str,
    context: ResolutionContext,
    scope: AuthorityScope,
    review_confidence: float = 0.6,
) -> Validation:
    """Re-derive every claim a proposal makes before it may be committed."""
    reasons: list[str] = []
    review = bool(proposal.review_required)

    if proposal.scope.to_dict() != scope.to_dict():
        reasons.append("scope_mismatch")
    if context.subject_id != scope.subject_id:
        reasons.append("resolution_context_outside_scope")

    source_digest = f"sha256:{sha256_hex(source_text)}"
    for evidence in proposal.evidence:
        if evidence.source_sha256 != source_digest:
            reasons.append("evidence_source_digest_mismatch")
            continue
        if evidence.end_offset > max(len(source_text), 1):
            reasons.append("evidence_span_out_of_range")
            continue
        excerpt = source_text[evidence.start_offset : evidence.end_offset]
        expected = f"sha256:{sha256_hex(excerpt or source_text or ' ')}"
        if evidence.excerpt_sha256 != expected:
            reasons.append("evidence_excerpt_digest_mismatch")

    screening = screen_content(source_text)
    if not screening.admissible:
        reasons.extend(screening.reason_codes)
    if proposal.fact:
        fact_screening = screen_content(proposal.fact)
        if not fact_screening.admissible:
            reasons.extend(fact_screening.reason_codes)

    mutations = {ProposalAction.ADD, ProposalAction.UPDATE, ProposalAction.SUPERSEDE}
    if proposal.action in mutations:
        if proposal.confidence < review_confidence:
            review = True
        for precondition in proposal.preconditions:
            record = next(
                (
                    row
                    for row in context.records
                    if str(row["id"]) == precondition.record_id
                ),
                None,
            )
            if record is None:
                reasons.append("precondition_record_not_eligible")
                continue
            if int(record.get("generation") or 0) != precondition.generation:
                reasons.append("stale_proposal_generation")
            if str(record.get("status")) != precondition.status:
                reasons.append("precondition_status_changed")
            digest = f"sha256:{sha256_hex(str(record.get('content') or ''))}"
            if digest != precondition.content_sha256:
                reasons.append("precondition_content_changed")
        for record_id in proposal.affected_record_ids:
            if all(str(row["id"]) != record_id for row in context.records):
                reasons.append("affected_record_not_eligible")

    if "ambiguous_referent" in proposal.reason_codes:
        review = True
    return Validation(not reasons, review, tuple(dict.fromkeys(reasons)))


def _from_candidate(
    candidate: CandidateFact,
    message: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    context: ResolutionContext,
    extra_reasons: tuple[str, ...] = (),
) -> ExtractionProposal:
    span = candidate.source_span or ((0, len(message)) if message else None)
    source_text = candidate.source_text or message
    classification = classify_candidate(
        fact=candidate.content,
        fact_key=candidate.fact_key,
        source_text=source_text,
        context=context,
        full_text=message,
    )
    untrusted = candidate.trust_tier != "trusted_user"
    reasons = (
        extra_reasons
        + (("untrusted_source_requires_review",) if untrusted else ())
        + (() if candidate.source_span else ("evidence_span_unavailable",))
    )
    return _build(
        message,
        scope=scope,
        source_id=source_id,
        span=span,
        fact=candidate.content,
        fact_key=candidate.fact_key,
        classification=classification,
        confidence=candidate.confidence,
        extra_reasons=reasons,
        review_required=classification.review_required or untrusted,
    )


def _build(
    message: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    span: tuple[int, int] | None,
    fact: str,
    fact_key: str | None,
    classification: Classification,
    confidence: float,
    extra_reasons: tuple[str, ...],
    review_required: bool,
) -> ExtractionProposal:
    action = classification.action
    reason_codes = tuple(dict.fromkeys(classification.reason_codes + extra_reasons))
    # REJECT carries no fact: a refused claim must not travel as memory text.
    fact_value = None if action is ProposalAction.REJECT else fact
    return _outcome(
        message,
        scope=scope,
        source_id=source_id,
        span=span,
        action=action,
        memory_class=classification.memory_class,
        reason_codes=reason_codes,
        confidence=confidence,
        fact=fact_value,
        fact_key=fact_key,
        affected_record_ids=classification.affected_record_ids,
        preconditions=classification.preconditions,
        review_required=review_required,
    )


def _refusal(
    message: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    reason_codes: tuple[str, ...],
) -> ExtractionProposal:
    return _outcome(
        message,
        scope=scope,
        source_id=source_id,
        span=(0, len(message)) if message else None,
        action=ProposalAction.REJECT,
        memory_class=MemoryClass.NON_MEMORY,
        reason_codes=reason_codes,
        confidence=0.0,
        review_required=False,
    )


def _outcome(
    message: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    span: tuple[int, int] | None,
    action: ProposalAction,
    memory_class: MemoryClass,
    reason_codes: tuple[str, ...],
    confidence: float,
    fact: str | None = None,
    fact_key: str | None = None,
    affected_record_ids: tuple[str, ...] = (),
    preconditions: tuple[Any, ...] = (),
    review_required: bool = False,
) -> ExtractionProposal:
    # An empty source still has to produce one explicit outcome, so the span
    # degenerates to a single sentinel character rather than to "no evidence".
    text = message if message else " "
    start, end = span if span else (0, len(text))
    end = max(end, start + 1)
    evidence = ProposalEvidence(
        source_id=source_id,
        source_sha256=f"sha256:{sha256_hex(message)}",
        start_offset=start,
        end_offset=end,
        excerpt_sha256=f"sha256:{sha256_hex(text[start:end] or text)}",
    )
    identity = sha256_hex(
        canonical_json(
            {
                "scope": scope.to_dict(),
                "source_id": source_id,
                "span": [start, end],
                "action": action.value,
                "fact": fact,
                "fact_key": fact_key,
            }
        )
    )
    return ExtractionProposal(
        proposal_id=f"prop_{identity[:32]}",
        idempotency_key=f"sha256:{identity}",
        scope=scope,
        action=action,
        memory_class=memory_class,
        confidence=float(confidence),
        reason_codes=reason_codes or ("unspecified",),
        evidence=(evidence,),
        fact=fact,
        fact_key=fact_key,
        affected_record_ids=affected_record_ids,
        preconditions=tuple(preconditions),
        review_required=review_required,
    )


def _attr(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 1.0 else None


def _support_span(message: str, fact: str) -> tuple[int, int] | None:
    """Find the span of the message that actually supports a model claim."""
    if not message or not fact:
        return None
    lowered = message.casefold()
    direct = lowered.find(fact.casefold())
    if direct >= 0:
        return (direct, direct + len(fact))
    tokens = re.findall(r"[a-z0-9@.+_-]{3,}", fact.casefold())
    if not tokens:
        return None
    found = [
        (position, position + len(token))
        for position, token in ((lowered.find(token), token) for token in tokens)
        if position >= 0
    ]
    if len(found) < max(1, (len(tokens) + 1) // 2):
        return None
    return (min(start for start, _ in found), max(end for _, end in found))
