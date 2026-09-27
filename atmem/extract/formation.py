"""Conservative deterministic formation of source-grounded typed memory."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from atmem.contracts import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.extract.models import (
    AtomicFactPayload,
    DurableRulePayload,
    EnvironmentStatePayload,
    EvidenceStatus,
    ExtractionProposal,
    FailureGotchaPayload,
    MemoryClass,
    MemoryUnit,
    MemoryUnitKind,
    Polarity,
    PremiseConstraintPayload,
    ProcedurePayload,
    ProcedureStep,
    ProposalAction,
    ProposalEvidence,
    StateTransitionPayload,
)


_NUMBERED_STEP = re.compile(r"(?:^|\s)(\d{1,2})[.)]\s+(.+?)(?=(?:\s+\d{1,2}[.)]\s)|$)", re.S)
_RULE = re.compile(
    r"\b(?:when|if)\s+(.+?),\s*(?:(must|should|always|never|do not|don't)\s+)(.+?)(?:[.!]|$)",
    re.I,
)
_TRANSITION = re.compile(
    r"\b(.+?)\s+(?:changed|moved|transitioned)\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+(?:after|by)\s+(.+?))?(?:[.!]|$)",
    re.I,
)
_GOTCHA = re.compile(
    r"\b(?:when|if)\s+(.+?),\s*(.+?\b(?:fails?|failed|errors?|breaks?))\s*[;.]\s*(?:instead|use|workaround:)\s*(.+?)(?:[.!]|$)",
    re.I,
)
_CURRENT = re.compile(r"\b(?:the\s+)?current\s+(.+?)\s+is\s+(.+?)(?:[.!]|$)", re.I)
_MY_FACT = re.compile(r"\bmy\s+([\w -]{1,64}?)\s+is\s+(.+?)(?:[.!]|$)", re.I)
_AGE = re.compile(r"\bI am\s+(\d{1,3})\s+years? old\b", re.I)
_PREMISE = re.compile(
    r"\b(?:assume|provided that|only if)\s+(.+?)(?:[.!]|$)", re.I
)
_LABELED_FACT = re.compile(
    r"\b(?:the\s+)?(.+?\b(?:id|identifier|number|code))\s+is\s+([^.;]+)", re.I
)
_INLINE_RULE = re.compile(
    r"\b(.+?)\s+(must|should|always|never|must not|should not)\s+(.+?)(?:[.!]|$)",
    re.I,
)
_CURRENTLY_USES = re.compile(
    r"\b(.+?)\s+currently\s+uses\s+(.+?)(?:\s+with\s+(.+))?$", re.I
)
_STATUS_STATE = re.compile(
    r"\b(.+?)\s+is\s+((?:pending|active|inactive|blocked|disabled|enabled|"
    r"available|unavailable|ready|failed|complete|completed)\b.+?)(?:[.!]|$)",
    re.I,
)
_PREFERENCE_TRANSITION = re.compile(
    r"\bI used to prefer\s+(.+?)[.!]\s*I\s+(changed\s+my\s+preference)\s+to\s+(.+?)(?:[.!]|$)",
    re.I,
)
_BEFORE_AFTER_TRANSITION = re.compile(
    r"\bBefore\s+(.+?)[.!]\s*(.+?)\s+(?:returned|produced|created)\s+(.+?)[.!]"
    r"(?:\s*(?:The\s+)?(.+?)\s+(?:then\s+)?(?:showed|contained|reported)\s+(.+?)(?:[.!]|$))?",
    re.I,
)
_FIRST_THEN_PROCEDURE = re.compile(
    r"\b(?:for|to)\s+(.+?):\s*first\s+(.+?),\s*then\s+(.+?),\s*then\s+(.+?)(?:[.!]|$)",
    re.I,
)
_SEMICOLON_PROCEDURE = re.compile(r"\b(?:to|for)\s+(.+?):\s*(.+)", re.I)
_PROHIBITION_RECOVERY = re.compile(
    r"\b(?:if|when)\s+(.+?),\s*(do not|don't|never)\s+(.+?);\s*(.+?)(?:[.!]|$)",
    re.I,
)
_TIMEOUT_RECOVERY = re.compile(
    r"\b(.+?timeout)\s+(.+?)[.!]\s*(.+?\bbefore\s+(?:retrying|retry))\b(?:[.!]|$)",
    re.I,
)
_NEGATIVE_CONFIGURATION = re.compile(
    r"\b(.+?)\s+(?:has|have)\s+no\s+(.+?\bconfigured)(?:[.!]|$)", re.I
)
_APPLICABILITY = re.compile(
    r"\b(.+?rule)\s+applies\s+only\s+to\s+(.+?),\s+not\s+(.+?)(?:[.!]|$)", re.I
)


def form_typed_proposals(
    text: str,
    *,
    scope: AuthorityScope,
    source_id: str,
    formation_id: str,
    confidence: float = 1.0,
    observed_at: str | None = None,
) -> tuple[ExtractionProposal, ...]:
    """Form only structures whose complete fields occur in the source.

    Ambiguous prose returns no proposal. The formation receipt, not a guessed
    memory, reports that visible loss to callers.
    """
    source = " ".join(text.split())
    if not source:
        return ()
    evidence = ProposalEvidence(
        source_id=source_id,
        source_sha256=f"sha256:{sha256_hex(text)}",
        start_offset=0,
        end_offset=len(text),
        excerpt_sha256=f"sha256:{sha256_hex(text)}",
    )
    candidates: list[tuple[MemoryUnitKind, Any, MemoryClass, str | None]] = []

    steps = _NUMBERED_STEP.findall(source)
    goal_match = re.match(r"(?:to|procedure for)\s+(.+?),\s*1[.)]", source, re.I)
    if len(steps) >= 2 and goal_match:
        ordered = tuple(
            ProcedureStep(index, instruction.strip(" ."))
            for index, (_reported, instruction) in enumerate(steps, start=1)
        )
        candidates.append((
            MemoryUnitKind.PROCEDURE,
            ProcedurePayload(goal_match.group(1).strip(), ordered),
            MemoryClass.PROCEDURE,
            None,
        ))
    elif (ordered := _FIRST_THEN_PROCEDURE.search(source)):
        candidates.append((
            MemoryUnitKind.PROCEDURE,
            ProcedurePayload(
                ordered.group(1).strip(),
                tuple(
                    ProcedureStep(index, instruction.strip(" ."))
                    for index, instruction in enumerate(ordered.groups()[1:], start=1)
                ),
            ),
            MemoryClass.PROCEDURE,
            None,
        ))
    elif (sequence := _SEMICOLON_PROCEDURE.search(source)):
        raw_steps = [part.strip(" .") for part in sequence.group(2).split(";")]
        if len(raw_steps) >= 2 and all(raw_steps):
            procedure_steps = []
            for index, instruction in enumerate(raw_steps, start=1):
                condition = None
                condition_match = re.match(r"if\s+(.+?),\s*(.+)", instruction, re.I)
                if condition_match:
                    condition = condition_match.group(1).strip()
                    instruction = condition_match.group(2).strip()
                instruction = re.sub(r"\bonly\s+after\s+", "after ", instruction, flags=re.I)
                procedure_steps.append(ProcedureStep(index, instruction, condition))
            candidates.append((
                MemoryUnitKind.PROCEDURE,
                ProcedurePayload(sequence.group(1).strip(), tuple(procedure_steps)),
                MemoryClass.PROCEDURE,
                None,
            ))

    gotcha = _GOTCHA.search(source)
    if gotcha:
        candidates.append((
            MemoryUnitKind.FAILURE_GOTCHA,
            FailureGotchaPayload(
                gotcha.group(1).strip(), gotcha.group(2).strip(),
                required_action=gotcha.group(3).strip(),
            ),
            MemoryClass.DURABLE_FACT,
            None,
        ))
    elif (prohibition := _PROHIBITION_RECOVERY.search(source)):
        candidates.append((
            MemoryUnitKind.FAILURE_GOTCHA,
            FailureGotchaPayload(
                prohibition.group(1).strip(),
                f"{prohibition.group(2)} {prohibition.group(3)}".strip(),
                required_action=prohibition.group(4).strip(),
                prohibited_action=prohibition.group(3).strip(),
            ),
            MemoryClass.DURABLE_FACT,
            None,
        ))
    elif (timeout := _TIMEOUT_RECOVERY.search(source)):
        candidates.append((
            MemoryUnitKind.FAILURE_GOTCHA,
            FailureGotchaPayload(
                timeout.group(1).strip(), timeout.group(2).strip(),
                required_action=timeout.group(3).strip(),
            ),
            MemoryClass.DURABLE_FACT,
            None,
        ))

    transition = _TRANSITION.search(source)
    if transition:
        entity = transition.group(1).strip()
        before = transition.group(2).strip()
        after = transition.group(3).strip()
        action = (transition.group(4) or "changed").strip()
        candidates.append((
            MemoryUnitKind.STATE_TRANSITION,
            StateTransitionPayload(entity, entity, before, action, after),
            MemoryClass.TEMPORARY_STATE,
            _fact_key(entity, entity),
        ))
    elif (preference := _PREFERENCE_TRANSITION.search(source)):
        candidates.append((
            MemoryUnitKind.STATE_TRANSITION,
            StateTransitionPayload(
                "user", "preference", preference.group(1).strip(),
                preference.group(2).strip(), preference.group(3).strip(),
            ),
            MemoryClass.TEMPORARY_STATE,
            "user_preference",
        ))
    elif (observed := _BEFORE_AFTER_TRANSITION.search(source)):
        before = observed.group(1).strip()
        action = observed.group(2).strip()
        after = observed.group(3).strip()
        entity = (observed.group(4) or action).strip()
        corroborated_after = (observed.group(5) or after).strip()
        if after.casefold() == corroborated_after.casefold():
            candidates.append((
                MemoryUnitKind.STATE_TRANSITION,
                StateTransitionPayload(entity, "state", before, action, after),
                MemoryClass.TEMPORARY_STATE,
                _fact_key(entity, "state"),
            ))

    rule = _RULE.search(source)
    if rule and not gotcha and not _PROHIBITION_RECOVERY.search(source):
        modal = rule.group(2).casefold()
        action = rule.group(3).strip()
        payload = (
            DurableRulePayload(rule.group(1).strip(), prohibited_action=action)
            if modal in {"never", "do not", "don't"}
            else DurableRulePayload(rule.group(1).strip(), required_action=action)
        )
        candidates.append((MemoryUnitKind.DURABLE_RULE, payload, MemoryClass.DURABLE_FACT, None))
    elif not gotcha and not _PROHIBITION_RECOVERY.search(source):
        inline_rule = _INLINE_RULE.search(source)
        if inline_rule:
            modal = inline_rule.group(2).casefold()
            subject = inline_rule.group(1).strip()
            action = inline_rule.group(3).strip()
            exception = None
            not_match = re.match(r"(.+?),\s*not\s+(.+)", action, re.I)
            if not_match:
                action, exception = not_match.group(1).strip(), not_match.group(2).strip()
            action = re.sub(r"^be\s+posted\s+to\s+", "post to ", action, flags=re.I)
            if exception and action.casefold().startswith("post to "):
                exception = f"post to {exception}"
            prohibited = modal in {"never", "must not", "should not"}
            candidates.append((
                MemoryUnitKind.DURABLE_RULE,
                DurableRulePayload(
                    subject,
                    required_action=None if prohibited else action,
                    prohibited_action=action if prohibited else exception,
                ),
                MemoryClass.DURABLE_FACT,
                None,
            ))

    current = _CURRENT.search(source)
    if current:
        relation, value = current.group(1).strip(), current.group(2).strip()
        candidates.append((
            MemoryUnitKind.ENVIRONMENT_STATE,
            EnvironmentStatePayload(relation, relation, value),
            MemoryClass.TEMPORARY_STATE,
            _fact_key("environment", relation),
        ))
    elif (uses := _CURRENTLY_USES.search(source)):
        entity = uses.group(1).strip()
        configuration = uses.group(2).strip()
        qualifier = (uses.group(3) or "").strip(" .")
        model_match = re.search(r"\bmodel\s+(.+)$", qualifier, re.I)
        relation = "model" if model_match else "configuration"
        value = model_match.group(1).strip() if model_match else " ".join(
            value for value in (configuration, qualifier) if value
        )
        candidates.append((
            MemoryUnitKind.ENVIRONMENT_STATE,
            EnvironmentStatePayload(entity, relation, value),
            MemoryClass.TEMPORARY_STATE,
            _fact_key(entity, relation),
        ))
    elif (status := _STATUS_STATE.search(source)):
        entity, value = status.group(1).strip(), status.group(2).strip()
        candidates.append((
            MemoryUnitKind.ENVIRONMENT_STATE,
            EnvironmentStatePayload(entity, "status", value),
            MemoryClass.TEMPORARY_STATE,
            _fact_key(entity, "status"),
        ))

    age = _AGE.search(source)
    if age:
        candidates.append((
            MemoryUnitKind.ATOMIC_FACT,
            AtomicFactPayload("user", "age", age.group(1)),
            MemoryClass.DURABLE_FACT,
            "user_age",
        ))
    elif (fact := _MY_FACT.search(source)):
        relation, value = fact.group(1).strip(), fact.group(2).strip()
        candidates.append((
            MemoryUnitKind.ATOMIC_FACT,
            AtomicFactPayload("user", relation, value),
            MemoryClass.DURABLE_FACT,
            _fact_key("user", relation),
        ))
    elif (fact := _LABELED_FACT.search(source)):
        label, value = fact.group(1).strip(), fact.group(2).strip()
        relation_label = re.sub(r"^(?:the\s+)?(?:customer|user|account)\s+", "", label, flags=re.I)
        relation = re.sub(r"\s+", "_", relation_label.casefold())
        candidates.append((
            MemoryUnitKind.ATOMIC_FACT,
            AtomicFactPayload(label, relation, value),
            MemoryClass.DURABLE_FACT,
            _fact_key(label, relation),
        ))

    premise = _PREMISE.search(source)
    if premise:
        candidates.append((
            MemoryUnitKind.PREMISE_CONSTRAINT,
            PremiseConstraintPayload(premise.group(1).strip(), Polarity.POSITIVE),
            MemoryClass.DURABLE_FACT,
            None,
        ))
    elif (negative := _NEGATIVE_CONFIGURATION.search(source)):
        candidates.append((
            MemoryUnitKind.PREMISE_CONSTRAINT,
            PremiseConstraintPayload(
                negative.group(2).strip(), Polarity.NEGATIVE,
                applies_when=negative.group(1).strip(),
            ),
            MemoryClass.DURABLE_FACT,
            None,
        ))
    elif (applicability := _APPLICABILITY.search(source)):
        candidates.append((
            MemoryUnitKind.PREMISE_CONSTRAINT,
            PremiseConstraintPayload(
                applicability.group(1).strip(), Polarity.POSITIVE,
                applies_when=applicability.group(2).strip(),
                excluded_when=applicability.group(3).strip(),
            ),
            MemoryClass.DURABLE_FACT,
            None,
        ))

    proposals: list[ExtractionProposal] = []
    for ordinal, (kind, payload, memory_class, fact_key) in enumerate(candidates):
        identity = canonical_json({
            "formation_id": formation_id,
            "source_id": source_id,
            "ordinal": ordinal,
            "kind": kind.value,
            "payload": asdict(payload),
        })
        suffix = sha256_hex(identity)[:24]
        unit = MemoryUnit(
            unit_id=f"unit-{suffix}",
            formation_id=formation_id,
            kind=kind,
            scope=scope,
            payload=payload,
            evidence=(evidence,),
            confidence=confidence,
            evidence_status=EvidenceStatus.OBSERVED,
            observed_at=observed_at,
            event_at=observed_at if kind is MemoryUnitKind.STATE_TRANSITION else None,
        )
        proposals.append(ExtractionProposal(
            proposal_id=f"proposal-{suffix}",
            idempotency_key=f"formation-{suffix}",
            scope=scope,
            action=ProposalAction.ADD,
            memory_class=memory_class,
            confidence=confidence,
            reason_codes=("deterministic_typed_formation",),
            evidence=(evidence,),
            fact=text,
            fact_key=fact_key,
            unit=unit,
        ))
    return tuple(proposals)


def _fact_key(subject: str, relation: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", f"{subject}_{relation}".casefold()).strip("_")
    return value[:128]
