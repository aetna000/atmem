"""Deterministic information-need routing for Context Engine V3."""

from __future__ import annotations

import re

from atmem.core.canonical import sha256_hex

from .contracts import EvidenceObligation, QueryPlan

_QUESTION_WORDS = frozenset({"what", "which", "where", "when", "how", "who", "why", "whether"})
_PLAN_STOP = frozenset({
    "a", "am", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "i", "in", "is", "it", "my", "of", "on", "or", "our", "please",
    "that", "the", "their", "this", "to", "we", "with", "you", "send",
    "email", "post", "create", "update", "inspect", "review", "find", "would", "like",
})


def _strip_host_scaffolding(query: str) -> str:
    value = re.sub(r"^\s*\[\d{4}-\d{2}-\d{2}\]\s*", "", query).strip()
    # Tool schemas and answer-format instructions describe the evaluator/host,
    # not additional memory requirements. Letting them enter the plan creates
    # impossible obligations such as remembering every available click verb.
    value = re.split(r"\n\s*Action Space\s*:", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = re.split(
        r"\n\s*(?:Your final answer|Put your final answer|Mark your final answer)\b",
        value, maxsplit=1, flags=re.IGNORECASE,
    )[0]
    return value.strip()


def _need_clauses(query: str) -> tuple[str, ...]:
    """Split explicit memory needs without inventing hidden requirements."""
    value = _strip_host_scaffolding(query)
    if re.search(
        r"\bif\b[^?\n]*\bchange(?:d|s|ing)?\b[^?\n]*\bfrom\b[^?\n]*"
        r"\bto\b[^?\n]*,\s*(?:what|which|how|where|when)\b",
        value,
        re.IGNORECASE,
    ):
        # The interrogative depends on the conditional state transition. Keep
        # it as one evidence obligation instead of treating “what amount” as
        # an unrelated second fact query.
        return (" ".join(value.split()),)
    pieces = re.split(
        r"(?:[.;]\s+|,\s+(?:and\s+)?(?=(?:include|identify|name|state|explain|"
        r"briefly|whether|what|which|where|when|how|who|why|copy|cc)\b)|"
        r"\s+and\s+(?=(?:include|identify|name|state|explain|whether|what|which|"
        r"where|when|how|who|why|copy|cc)\b))",
        value,
        flags=re.IGNORECASE,
    )
    clauses = []
    pending_context: str | None = None
    for piece in pieces:
        normalized = " ".join(piece.split()).strip(" ,.;")
        significant = [
            token for token in re.findall(r"[A-Za-z0-9#@_.-]+", normalized)
            if token.casefold() not in _PLAN_STOP
        ]
        lowered = normalized.casefold()
        if lowered.startswith("today is "):
            continue
        if lowered.startswith(("i am ", "i have ", "i would ")) and "?" not in normalized:
            pending_context = ". ".join(filter(None, (pending_context, normalized)))
            continue
        if lowered.startswith("according to ") and "?" not in normalized:
            pending_context = ". ".join(filter(None, (pending_context, normalized)))
            continue
        memory_cue = bool(
            _QUESTION_WORDS & {token.casefold() for token in significant}
            or re.search(
                r"\b(required|established|usual|earliest|current|historical|"
                r"decision|evidence|status|scope|outcome|approved|accountability|"
                r"measurement|pending|closed|open|former|prior|final|claiming|"
                r"correct|review|inspect|find|told|remember|reassessment|"
                r"running\s+plan|summari[sz](?:e|ing)|mature\s+read)\b",
                lowered,
            )
        )
        if len(significant) >= 2 and memory_cue:
            clauses.append(
                f"{pending_context}. {normalized}" if pending_context else normalized
            )
            pending_context = None
        elif len(significant) >= 2:
            # Preserve immediately preceding user-supplied context as part of
            # the next explicit need rather than promoting it to a standalone
            # requirement that could make every action fail closed.
            pending_context = normalized
    return tuple(dict.fromkeys(clauses[:4])) or (value,)


def _kind(value: str) -> str:
    lowered = value.casefold()
    if (
        lowered.startswith("how ")
        or re.search(r"\b(steps?|procedure|in order)\b", lowered)
        or re.search(r"\bhow many (?:more )?(?:actions?|steps?)\b", lowered)
        or ("workflow" in lowered and re.search(r"\b(actions?|steps?)\b", lowered))
    ):
        return "ordered_steps"
    if (
        "what changed" in lowered
        or re.search(r"\b(before|after|transition)\b", lowered)
        or (
            re.search(r"\bchange(?:d|s|ing)?\b", lowered)
            and re.search(r"\bfrom\b.+\bto\b", lowered)
        )
    ):
        return "before_action_after"
    if re.search(r"\b(wireless-only|without|no\s+\w+|not\s+approved)\b", lowered):
        return "premise_check"
    if lowered.startswith("why ") or "explain" in lowered:
        return "claim_support"
    if re.search(r"\b(required|must|should|permitted|allowed|prohibited)\b", lowered):
        return "condition_action"
    return "subject_relation_value"


def _entity(value: str) -> str:
    identifiers = re.findall(r"(?:[A-Za-z][\w-]*(?:#[0-9]+|@[\w.-]+)|`[^`]+`)", value)
    if identifiers:
        return identifiers[0].strip("`")
    words = [
        token for token in re.findall(r"[A-Za-z0-9_-]+", value)
        if token.casefold() not in _PLAN_STOP | _QUESTION_WORDS
    ]
    return words[0] if words else "query"


def targeted_facets(query: str) -> tuple[str, ...]:
    """Derive answer-blind search facets from explicit alternatives and fields.

    These are search nominations, not additional sufficiency obligations. A
    question asking which one of several alternatives has a property normally
    has evidence for the matching alternative only; requiring evidence for
    every distractor would incorrectly fail closed.
    """
    values: list[str] = []
    # Action requests often refer to an identity indirectly ("our CEO", "the
    # integration contact", or "the usual person on the external thread").
    # Preserve those compact, answer-blind phrases as independent nominations;
    # otherwise the surrounding action prose can bury the exact name/address
    # record in a long history.  These are search facets, never inferred values
    # or additional sufficiency obligations.
    for contact in re.finditer(
        r"\b(?:the|a|an)\s+([A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+){0,3}\s+contact)\b",
        query,
        re.IGNORECASE,
    ):
        value = " ".join(contact.group(1).split()).strip(" ,.;")
        if value:
            values.append(value)
    for indirect in re.finditer(
        r"\b(?:usual|default|normal)\s+(?:person|contact|recipient)\s+on\s+"
        r"(?:the\s+)?([^?.;,\n]{2,64})",
        query,
        re.IGNORECASE,
    ):
        value = " ".join(indirect.group(1).split()).strip(" ,.;")
        if value:
            values.append(value)
            # Thread/conversation wording and stored email wording are common
            # host-level paraphrases of the same communication surface. Keep
            # both as independent lexical nominations without guessing the
            # recipient or address.
            email_surface = re.sub(
                r"\b(?:thread|conversation)\b", "email", value,
                flags=re.IGNORECASE,
            )
            if email_surface != value:
                values.extend((email_surface, f"{email_surface} CC"))
    for role in re.finditer(
        r"\b(?:send|message|email|notify|copy|cc|ask)\s+"
        r"(?:our|my|the)\s+([A-Za-z][A-Za-z0-9_-]*)\b",
        query,
        re.IGNORECASE,
    ):
        values.append(role.group(1))
    for approval in re.finditer(
        r"\bwho\s+should\s+(?:approve|own|authorize|review)\s+"
        r"(.+?)(?=\s+before\b|\s+after\b|\s+when\b|[?.;,]|$)",
        query,
        re.IGNORECASE,
    ):
        value = " ".join(approval.group(1).split()).strip(" ,.;")
        if value:
            values.append(value)
    temporal_subject = re.search(
        r"\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)\s+\d{1,2},?\s+\d{4}"
        r"(?:\s+[A-Za-z0-9_-]+){1,3}?)(?=\s+(?:authoriz(?:e|ed|es|ing)|"
        r"allow(?:ed|s|ing)?|open(?:ed|s|ing)?|mean(?:t|s|ing)?|"
        r"establish(?:ed|es|ing)?|require(?:d|s|ing)?|change(?:d|s|ing)?|"
        r"show(?:ed|s|ing)?|prov(?:e|ed|es|ing))\b|[?.;,]|$)",
        query,
        re.IGNORECASE,
    )
    if temporal_subject:
        values.append(" ".join(temporal_subject.group(1).split()))
    workflow = re.search(
        r"\bcreat(?:e|ing)\s+(?:a\s+|new\s+|a\s+new\s+)?"
        r"([A-Za-z][A-Za-z_-]*)(?:\s+requests?)?\b",
        query,
        re.IGNORECASE,
    )
    if workflow:
        values.append(f"create {workflow.group(1).casefold()}")
    # Preserve the user's task intent as a compact nomination query. Long
    # questions often wrap a short action in UI, location, and answer-format
    # prose; searching only the full sentence lets framing words dominate the
    # fallback ranking.
    intent = re.search(
        r"\b(?:would like to|want to|need to)\s+([^?.\n]+)",
        query,
        re.IGNORECASE,
    )
    if intent:
        value = " ".join(intent.group(1).split()).strip(" ,.;")
        if 2 <= len(value.split()) <= 32:
            values.append(value)
    transition = re.search(
        r"\bfrom\s+(?:the\s+default\s+)?([^,?.\n]{1,64}?)\s+to\s+"
        r"([^,?.\n]{1,64})",
        query,
        re.IGNORECASE,
    )
    if transition:
        before = " ".join(transition.group(1).split()).strip(" ,.;")
        after = " ".join(transition.group(2).split()).strip(" ,.;")
        if before and after:
            # Nominate both sides together so a post-action state containing
            # the changed control and its relative price outranks unrelated
            # states that mention only one operating value.
            values.extend((f"{before} {after}", after, before))
    alternatives = re.search(r"\(([^()\n]*?/[^()\n]*?)\)", query)
    if alternatives:
        entities = [
            " ".join(item.split()).strip(" ,.;")
            for item in alternatives.group(1).split("/")
        ]
        entities = [item for item in entities if 1 < len(item) <= 48]
        focus = re.search(
            # ``intergrate`` is a common transposition in natural questions.
            # Treat it as the same explicit relation instead of dropping every
            # answer-blind alternative facet because of one misspelling.
            r"\b(?:integrates?|integration|intergrates?)\s+with\s+([^?.\n]+)",
            query, re.IGNORECASE,
        )
        focus_text = " ".join(focus.group(1).split()) if focus else ""
        if 2 <= len(entities) <= 12 and focus_text:
            values.append(focus_text)
            values.extend(f"{focus_text} {entity}" for entity in entities)

    option_lines = re.findall(
        r"(?m)^\s*[A-Z]\s*[.)]\s*([^\n]+)$", query,
    )
    if option_lines:
        table = re.search(
            r"\b(?:on|in)\s+the\s+([A-Za-z0-9_-]+)\s+table\b",
            query, re.IGNORECASE,
        )
        prefix = f"{table.group(1)} table" if table else ""
        fields: list[str] = []
        for line in option_lines:
            fields.extend(
                " ".join(item.split()).strip(" ,.;")
                for item in re.split(r"\s*,\s*|\s*/\s*", line)
            )
        unique_fields = tuple(dict.fromkeys(item for item in fields if len(item) > 1))
        # Search the exact field phrase first. Surface qualification is applied
        # later from the compact workflow facet/source identity; requiring the
        # words "Problem table" to occur in the same 4 KiB source range can
        # hide a real field merely because the form title is in an earlier
        # structural range.
        values.extend(unique_fields)
        values.extend(f"{prefix} {field}".strip() for field in unique_fields)
    return tuple(dict.fromkeys(values))


class DeterministicPlanner:
    identity = "context-planner-deterministic-v1"

    def plan(self, query: str) -> QueryPlan:
        normalized = " ".join(_strip_host_scaffolding(query).split())
        if not normalized:
            raise ValueError("query is required")
        obligations: list[EvidenceObligation] = []
        comparison = re.search(
            r"\bcompare\s+(?:the\s+)?([A-Za-z0-9_-]+)\s+and\s+"
            r"(?:the\s+)?([A-Za-z0-9_-]+)",
            normalized,
            re.IGNORECASE,
        )
        if comparison is None and normalized.casefold().startswith("compare "):
            comparison = re.search(
                r"\b([A-Z][A-Za-z0-9_-]+)\s+and\s+"
                r"(?:the\s+)?([A-Z][A-Za-z0-9_-]+)\b",
                normalized,
            )
        if comparison:
            for index, entity in enumerate(comparison.groups(), 1):
                obligations.append(EvidenceObligation(
                    obligation_id=f"comparison-{index}", kind="comparison_side",
                    entity=entity.title(), relation_or_action="compare",
                ))
        else:
            for index, clause in enumerate(_need_clauses(normalized), 1):
                kind = _kind(clause)
                temporal = re.search(
                    r"\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?|"
                    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
                    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
                    r"nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?",
                    clause, re.IGNORECASE,
                )
                obligations.append(EvidenceObligation(
                    obligation_id=f"need-{index}", kind=kind,
                    entity=(
                        None
                        if kind in {"ordered_steps", "before_action_after"}
                        else _entity(clause)
                    ),
                    relation_or_action=clause,
                    temporal_target=temporal.group(0) if temporal else None,
                    polarity="negative" if kind == "premise_check" else "unknown",
                ))
        obligation_queries = (
            () if comparison else
            tuple(item.relation_or_action or normalized for item in obligations)
        )
        routed_queries = tuple(dict.fromkeys((
            *targeted_facets(query), normalized, *obligation_queries,
        )))
        pools = {
            "raw_state": routed_queries,
            "fact": routed_queries,
            "entity": routed_queries,
            "transition": routed_queries if any(o.kind == "before_action_after" for o in obligations) else (),
            "procedure": routed_queries if any(o.kind == "ordered_steps" for o in obligations) else (),
            "rule": routed_queries,
            "gotcha": routed_queries if any(o.kind == "claim_support" for o in obligations) else (),
            "premise": routed_queries if any(o.kind == "premise_check" for o in obligations) else (),
        }
        digest = "sha256:" + sha256_hex(normalized)
        return QueryPlan(
            plan_id="plan3_" + digest[7:39], query_sha256=digest,
            obligations=tuple(obligations), pool_queries=pools,
            planner_identity=self.identity, deterministic_fallback=True,
        )
