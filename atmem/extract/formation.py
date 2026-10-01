"""Conservative deterministic formation of source-grounded typed memory."""

from __future__ import annotations

import json
import re
import unicodedata
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
    MAX_STRUCTURED_STATE_CHARS,
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
from atmem.extract.structured_projection import (
    structured_control_index,
    structured_surface_index,
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
_CURRENT = re.compile(
    r"\b(?:the\s+)?current\s+(.+?)\s+is\s+(.+?)(?:[.!](?=\s|$)|$)", re.I
)
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
    part_kind: str = "text",
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

    # Hosts may identify a lossless part as structured state or tool output.
    # Preserve the exact JSON as state without application-specific extraction.
    if part_kind in {"state", "tool"}:
        try:
            structured = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            structured = None
        if isinstance(structured, (dict, list)):
            entity = "structured event"
            relation = "structured event"
            fact_relation = relation
            if isinstance(structured, dict):
                if structured:
                    first_key = str(next(iter(structured))).strip()
                    if first_key:
                        relation = first_key
                        fact_relation = relation
                        entity = first_key
                for key in ("id", "name", "title", "url"):
                    value = structured.get(key)
                    if isinstance(value, (str, int, float)) and str(value).strip():
                        entity = str(value).strip()
                        break
                state_index = structured.get("state_index")
                if isinstance(state_index, int) and not isinstance(state_index, bool):
                    fact_relation = f"{relation}:{state_index}"
            if len(text) <= MAX_STRUCTURED_STATE_CHARS:
                if isinstance(structured, dict) and isinstance(
                    structured.get("goal"), str
                ):
                    relation = "trajectory goal"
                    fact_relation = relation
                candidates.append((
                    MemoryUnitKind.ENVIRONMENT_STATE,
                    EnvironmentStatePayload(entity, relation, text),
                    MemoryClass.TEMPORARY_STATE,
                    _fact_key(entity, fact_relation),
                ))
            elif isinstance(structured, dict):
                # Keep the navigational fields independently addressable.  A
                # raw 8 KiB cut through serialized JSON can put ``action`` and
                # ``thought`` inside invalid fragments and then the reader sees
                # only accessibility labels.  The immutable source remains
                # verbatim; typed derivatives preserve field boundaries.
                large_fields = {
                    key: value for key, value in structured.items()
                    if isinstance(value, str)
                    and (
                        key in {"accessibility_tree", "tree"}
                        or len(value) > MAX_STRUCTURED_STATE_CHARS
                    )
                }
                summary = {
                    key: value for key, value in structured.items()
                    if key not in large_fields
                }
                state_index = structured.get("state_index")
                suffix = (
                    str(state_index)
                    if isinstance(state_index, int) and not isinstance(state_index, bool)
                    else "event"
                )
                if summary:
                    summary_text = canonical_json(summary)
                    for chunk_index, chunk in enumerate(
                        _bounded_text_chunks(
                            summary_text, maximum=MAX_STRUCTURED_STATE_CHARS
                        )
                    ):
                        candidates.append((
                            MemoryUnitKind.ENVIRONMENT_STATE,
                            EnvironmentStatePayload(entity, "state summary", chunk),
                            MemoryClass.TEMPORARY_STATE,
                            _fact_key(
                                entity,
                                f"state summary:{suffix}:chunk:{chunk_index:04d}",
                            ),
                        ))
                surface_index = structured_surface_index(structured)
                for chunk_index, chunk in enumerate(
                    _bounded_text_chunks(
                        surface_index, maximum=MAX_STRUCTURED_STATE_CHARS
                    ) if surface_index else ()
                ):
                    candidates.append((
                        MemoryUnitKind.ENVIRONMENT_STATE,
                        EnvironmentStatePayload(
                            entity, "ui surface index", chunk
                        ),
                        MemoryClass.TEMPORARY_STATE,
                        _fact_key(
                            entity,
                            f"ui surface index:{suffix}:chunk:{chunk_index:04d}",
                        ),
                    ))
                control_index = structured_control_index(structured)
                for chunk_index, chunk in enumerate(
                    _bounded_text_chunks(
                        control_index, maximum=MAX_STRUCTURED_STATE_CHARS
                    ) if control_index else ()
                ):
                    candidates.append((
                        MemoryUnitKind.ENVIRONMENT_STATE,
                        EnvironmentStatePayload(
                            entity, "ui control state index", chunk
                        ),
                        MemoryClass.TEMPORARY_STATE,
                        _fact_key(
                            entity,
                            f"ui control state index:{suffix}:chunk:{chunk_index:04d}",
                        ),
                    ))
                for field, field_value in large_fields.items():
                    for chunk_index, chunk in enumerate(
                        _bounded_text_chunks(
                            field_value, maximum=MAX_STRUCTURED_STATE_CHARS
                        )
                    ):
                        candidates.append((
                            MemoryUnitKind.ENVIRONMENT_STATE,
                            EnvironmentStatePayload(entity, field, chunk),
                            MemoryClass.TEMPORARY_STATE,
                            _fact_key(
                                entity,
                                f"{field}:{suffix}:chunk:{chunk_index:04d}",
                            ),
                        ))
                if not candidates:
                    for chunk_index, chunk in enumerate(
                        _bounded_text_chunks(
                            text, maximum=MAX_STRUCTURED_STATE_CHARS
                        )
                    ):
                        candidates.append((
                            MemoryUnitKind.ENVIRONMENT_STATE,
                            EnvironmentStatePayload(entity, relation, chunk),
                            MemoryClass.TEMPORARY_STATE,
                            _fact_key(
                                entity,
                                f"{fact_relation}:chunk:{chunk_index:04d}",
                            ),
                        ))
            else:
                for chunk_index, chunk in enumerate(
                    _bounded_text_chunks(text, maximum=MAX_STRUCTURED_STATE_CHARS)
                ):
                    candidates.append((
                        MemoryUnitKind.ENVIRONMENT_STATE,
                        EnvironmentStatePayload(entity, relation, chunk),
                        MemoryClass.TEMPORARY_STATE,
                        _fact_key(entity, f"{fact_relation}:chunk:{chunk_index:04d}"),
                    ))
            # Structured host state is already represented losslessly. Do not
            # run prose regexes over serialized accessibility trees: phrases
            # such as "status" inside UI text are not top-level state claims.
            return _materialize_candidates(
                candidates,
                text=text,
                formation_id=formation_id,
                source_id=source_id,
                scope=scope,
                evidence=evidence,
                confidence=confidence,
                observed_at=observed_at,
                use_payload_value_for_fact=len(text) > MAX_STRUCTURED_STATE_CHARS,
                structured_derived=len(text) > MAX_STRUCTURED_STATE_CHARS,
            )

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
        polarity = _claim_polarity(value)
        candidates.append((
            MemoryUnitKind.ENVIRONMENT_STATE,
            EnvironmentStatePayload(relation, relation, value, polarity),
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
        polarity = _claim_polarity(value)
        if polarity is Polarity.POSITIVE:
            # "Sydney, not Melbourne" asserts Sydney and rejects an
            # alternative; the negation does not negate the represented slot.
            value = re.split(
                r"\s*,\s*(?:not|rather than|instead of)\b", value,
                maxsplit=1, flags=re.I,
            )[0].strip()
        candidates.append((
            MemoryUnitKind.ATOMIC_FACT,
            AtomicFactPayload("user", relation, value, polarity),
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

    if not candidates:
        # Preserve otherwise unclassified source as an occurrence-scoped
        # observation. This does not promote prose into a durable fact; it
        # keeps exact evidence retrievable and makes formation loss explicit
        # through a neutral typed envelope usable by every agent adapter.
        for chunk_index, chunk in enumerate(_bounded_text_chunks(text)):
            candidates.append((
                MemoryUnitKind.ENVIRONMENT_STATE,
                EnvironmentStatePayload("episode", "observed text", chunk),
                MemoryClass.TEMPORARY_STATE,
                _fact_key("episode", f"observed text:{chunk_index:04d}"),
            ))

    proposals = _materialize_candidates(
        candidates,
        text=text,
        formation_id=formation_id,
        source_id=source_id,
        scope=scope,
        evidence=evidence,
        confidence=confidence,
        observed_at=observed_at,
    )
    covered = sorted(
        (item.evidence[0].start_offset, item.evidence[0].end_offset)
        for item in proposals
    )
    gaps: list[str] = []
    cursor = 0
    for start, end in covered + [(len(text), len(text))]:
        gap = text[cursor:start]
        if any(character.isalnum() for character in gap):
            gaps.extend(_bounded_text_chunks(gap))
        cursor = max(cursor, end)
    if not gaps:
        return proposals
    fallback_candidates = [
        (
            MemoryUnitKind.ENVIRONMENT_STATE,
            EnvironmentStatePayload("episode", "observed text", chunk),
            MemoryClass.TEMPORARY_STATE,
            _fact_key("episode", f"observed text gap:{index:04d}"),
        )
        for index, chunk in enumerate(gaps)
    ]
    return proposals + _materialize_candidates(
        fallback_candidates,
        text=text,
        formation_id=formation_id,
        source_id=source_id,
        scope=scope,
        evidence=evidence,
        confidence=confidence,
        observed_at=observed_at,
        use_payload_value_for_fact=True,
    )


def _materialize_candidates(
    candidates: list[tuple[MemoryUnitKind, Any, MemoryClass, str | None]],
    *,
    text: str,
    formation_id: str,
    source_id: str,
    scope: AuthorityScope,
    evidence: ProposalEvidence,
    confidence: float,
    observed_at: str | None,
    use_payload_value_for_fact: bool = False,
    structured_derived: bool = False,
) -> tuple[ExtractionProposal, ...]:
    proposals: list[ExtractionProposal] = []
    structured_cursor = 0
    for ordinal, (kind, payload, memory_class, fact_key) in enumerate(candidates):
        item_evidence = evidence
        if (
            kind is MemoryUnitKind.ENVIRONMENT_STATE
            and len(text) > 2_000
            and not structured_derived
        ):
            chunk = str(getattr(payload, "value", ""))
            start = text.find(chunk, structured_cursor)
            if start < 0:
                raise ValueError("structured state chunk is not source-grounded")
            end = start + len(chunk)
            structured_cursor = end
            item_evidence = ProposalEvidence(
                source_id=source_id,
                source_sha256=evidence.source_sha256,
                start_offset=start,
                end_offset=end,
                excerpt_sha256=f"sha256:{sha256_hex(chunk)}",
            )
        elif hasattr(payload, "value") and not structured_derived:
            value = str(getattr(payload, "value", ""))
            matches = list(re.finditer(re.escape(value), text, re.I))
            match = None
            if matches:
                subject = str(getattr(payload, "subject", getattr(payload, "entity", "")))
                relation = str(getattr(payload, "relation", ""))
                relation_tokens = set(re.findall(r"[^\W_]+", relation.casefold()))
                if relation.casefold() == "age":
                    relation_tokens.update({"old", "years", "born"})
                subject_tokens = set(re.findall(r"[^\W_]+", subject.casefold()))

                def support_score(candidate: re.Match[str]) -> tuple[int, int]:
                    left = max(
                        text.rfind(".", 0, candidate.start()),
                        text.rfind("!", 0, candidate.start()),
                        text.rfind("?", 0, candidate.start()),
                        text.rfind("\n", 0, candidate.start()),
                    ) + 1
                    right_values = [
                        position for delimiter in ".!?\n"
                        if (position := text.find(delimiter, candidate.end())) >= 0
                    ]
                    right = min(right_values) + 1 if right_values else len(text)
                    tokens = set(re.findall(r"[^\W_]+", text[left:right].casefold()))
                    subject_supported = bool(subject_tokens & tokens) or (
                        subject.casefold() in {"user", "self", "speaker"}
                        and bool(tokens & {"i", "me", "my", "mine"})
                    )
                    return (
                        int(bool(relation_tokens & tokens)) + int(subject_supported),
                        -candidate.start(),
                    )

                match = max(matches, key=support_score)
            if match is not None:
                start = max(
                    text.rfind(".", 0, match.start()),
                    text.rfind("!", 0, match.start()),
                    text.rfind("?", 0, match.start()),
                    text.rfind("\n", 0, match.start()),
                ) + 1
                while start < len(text) and text[start].isspace():
                    start += 1
                ends = [
                    position for delimiter in ".!?\n"
                    if (position := text.find(delimiter, match.end())) >= 0
                ]
                end = min(ends) + 1 if ends else len(text)
                excerpt = text[start:end]
                item_evidence = ProposalEvidence(
                    source_id=source_id,
                    source_sha256=evidence.source_sha256,
                    start_offset=start,
                    end_offset=end,
                    excerpt_sha256=f"sha256:{sha256_hex(excerpt)}",
                )
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
            evidence=(item_evidence,),
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
            evidence=(item_evidence,),
            fact=(
                str(getattr(payload, "value"))
                if use_payload_value_for_fact
                or (
                    kind is MemoryUnitKind.ENVIRONMENT_STATE
                    and getattr(payload, "entity", None) == "episode"
                    and getattr(payload, "relation", None) == "observed text"
                )
                else text
            ),
            fact_key=fact_key,
            unit=unit,
        ))
    return tuple(proposals)


def _claim_polarity(value: str) -> Polarity:
    """Classify negation only when it governs the represented value."""
    return (
        Polarity.NEGATIVE
        if re.match(r"^\s*(?:not|no|never|without)\b", value, re.I)
        else Polarity.POSITIVE
    )


def _fact_key(subject: str, relation: str) -> str:
    """Return a readable key without conflating distinct Unicode claims.

    The legacy slug remains stable for simple ASCII identifiers.  Whenever
    normalization would discard information (``C++``/``C#``, non-Latin text,
    or truncation), a digest of the NFC source tuple makes the key lossless.
    """
    subject_nfc = unicodedata.normalize("NFC", subject).casefold()
    relation_nfc = unicodedata.normalize("NFC", relation).casefold()
    canonical = canonical_json(["durable_fact_identity_v2", subject_nfc, relation_nfc])
    readable_source = f"{subject_nfc}_{relation_nfc}"
    readable = re.sub(r"[^a-z0-9]+", "_", readable_source).strip("_")
    unambiguous_legacy = bool(
        re.fullmatch(r"[a-z0-9]+", subject_nfc)
        and re.fullmatch(r"[a-z0-9]+", relation_nfc)
    )
    lossy = not unambiguous_legacy or not readable or len(readable) > 96
    if not lossy:
        return readable
    prefix = readable[:87] or "fact"
    return f"{prefix}_{sha256_hex(canonical)[:32]}"


def _bounded_text_chunks(value: str, *, maximum: int = 1_900) -> tuple[str, ...]:
    """Return exact, ordered, non-empty slices within typed field limits."""
    if maximum <= 0 or maximum > MAX_STRUCTURED_STATE_CHARS:
        raise ValueError(
            "structured-state chunk size must be between 1 and "
            f"{MAX_STRUCTURED_STATE_CHARS:,}"
        )
    chunks: list[str] = []
    offset = 0
    while offset < len(value):
        end = min(len(value), offset + maximum)
        if end < len(value):
            boundary = max(
                value.rfind(" ", offset, end),
                value.rfind("\n", offset, end),
                value.rfind("\t", offset, end),
            )
            if boundary > offset:
                end = boundary + 1
        chunks.append(value[offset:end])
        offset = end
    return tuple(chunks)
