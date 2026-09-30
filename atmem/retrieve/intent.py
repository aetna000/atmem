"""Deterministic, product-neutral routing from a question to evidence needs."""

from __future__ import annotations

import re
from typing import Iterable

from atmem.contracts import InformationNeed, RetrievalBudget
from atmem.core.canonical import canonical_json, sha256_hex


_POST_ACTION_STATE = re.compile(
    r"\bafter\b.{0,160}\b(?:what|which)\b.{0,120}"
    r"\b(?:value|state|status|option|item|text|label)\b|"
    r"\bafter\b.{0,160}\b(?:what|which)\b.{0,120}"
    r"\b(?:shown|displayed|visible|selected|active|default)\b",
    re.I,
)
_POST_ACTION_ASSIGNMENT = re.compile(
    r"\bwhat\s+value\s+should\b.{0,80}\bset\b", re.I
)
_PRESUPPOSED_SET = re.compile(
    r"\b(?:what|which)\s+(?:are|is)\s+(?:the\s+)?exact\b.{0,80}"
    r"\b(?:items?|names?|options?|records?|entries)\b",
    re.I,
)
_OBSERVED_FAILURE = re.compile(
    r"\b(?:fail(?:ed|ure)?|error|issue|did not|didn't|does not|doesn't|"
    r"not happen|not work|stuck|workaround)\b",
    re.I,
)

_ROUTES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ordered_task", re.compile(r"\b(?:how (?:do|can|should)|steps?|procedure|process|workflow|in what order)\b", re.I)),
    ("state_change", re.compile(r"\b(?:changed?|before|after|previously|used to|history|transition)\b", re.I)),
    ("exception_risk", re.compile(r"\b(?:fail(?:ed|ure)?|error|issue|gotcha|avoid|workaround|did not work|didn't work|risk)\b", re.I)),
    ("rule_application", re.compile(r"\b(?:must|should|allowed|permitted|required|prohibited|which channel|what rule|policy)\b", re.I)),
    ("assumption_check", re.compile(r"\b(?:assum(?:e|ing|ption)|premise|is it true|true or false|false or true|does .* exist|available|applicable)\b", re.I)),
    ("current_state", re.compile(r"\b(?:current|currently|latest|now|today|status|selected|active)\b", re.I)),
    ("relational_synthesis", re.compile(r"\b(?:relationship|relate|compare|difference|across|together|combine)\b", re.I)),
)

_SLOTS: dict[str, tuple[str, ...]] = {
    "exact_fact": ("subject", "relation", "value"),
    "current_state": ("entity", "relation", "current_value", "validity"),
    "state_change": ("entity", "before", "action", "after", "event_time"),
    "ordered_task": ("goal", "ordered_steps", "conditions", "completion"),
    "exception_risk": ("trigger", "failure", "safe_action"),
    "rule_application": ("condition", "required_or_prohibited_action", "applicability"),
    "assumption_check": ("proposition", "polarity", "applicability"),
    "relational_synthesis": ("entities", "relations", "supporting_evidence"),
}

_STOP = frozenset(
    "a an am and are can could did do does for from how i in is it its like me my of on or our should the this to was what when where which who why with would you your".split()
)
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_RELATIONS = frozenset({
    "age", "height", "location", "food", "city", "status", "model",
    "configuration", "name", "email", "channel", "procedure", "color",
    "price", "filter", "purchase",
})
_PRESENTATION_SUFFIX = re.compile(
    r"(?:^|(?<=[.!?])\s+)(?:your final answers?|mark your final answers?|"
    r"format your (?:final )?answer|answer (?:using|in|with)|respond (?:using|in|with))"
    r"\b.*$",
    re.I,
)
_IMPERATIVE_PRESENTATION_SUFFIX = re.compile(
    r"(?:^|(?<=[.!?])\s+)(?:say (?:the|your) (?:answer|number)|"
    r"list (?:the|your) (?:answer|button|link|name)|"
    r"wrap (?:the|your) (?:answer|answers))\b.*$",
    re.I,
)
_ACTION_SPACE_SUFFIX = re.compile(
    r"\baction space\s*:\s*.*?(?=(?:your final answer|mark your final answer|"
    r"format your (?:final )?answer|answer (?:using|in|with)|respond (?:using|in|with))\b|$)",
    re.I,
)
_RETRIEVAL_BOILERPLATE = frozenset({
    "according", "action", "actions", "answer", "based", "below", "boxed",
    "blank", "button", "click", "clicking", "creating", "custom", "default",
    "english", "environment", "field", "final", "form",
    "have", "many", "more", "need", "number", "perform", "portal", "should",
    "loading", "record", "shopping", "shown", "site", "task", "usual", "using",
    "value", "website", "while",
    "workflow", "working", "wrapped", "now", "page",
})
_LITERAL = re.compile(r"`([^`]{2,96})`|\"([^\"]{2,96})\"")
_BETWEEN = re.compile(
    r"\b(?:between|from)\s+[\"`]?(.{2,80}?)[\"`]?\s+(?:and|to)\s+"
    r"[\"`]?(.{2,80}?)[\"`]?(?:\s+(?:in|on|within|from|at)\b|[?.!,;]|$)",
    re.I,
)
_VERSUS = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 _-]{1,64}?)\s+(?:vs\.?|versus)\s+"
    r"([A-Za-z][A-Za-z0-9 _-]{1,64}?)(?:[.!?]|$)",
    re.I,
)


def route_information_need(
    query: str,
    *,
    parent_need_id: str | None = None,
    ordinal: int = 0,
) -> InformationNeed:
    """Classify one query without model calls or benchmark-specific labels."""
    normalized = " ".join(query.split())
    if not normalized:
        raise ValueError("information-need routing requires a non-empty query")
    semantic_query = _PRESENTATION_SUFFIX.sub("", normalized).strip()
    semantic_query = _IMPERATIVE_PRESENTATION_SUFFIX.sub("", semantic_query).strip() or normalized
    # "After" is ambiguous: it can ask for a transition (before/action/after)
    # or merely establish the action that reveals a current value.  Treat the
    # latter as a state lookup so sufficiency requires the requested value and
    # validity, not an irrelevant historical delta.
    need_type = (
        "assumption_check"
        if _PRESUPPOSED_SET.search(semantic_query)
        else "exception_risk"
        if _OBSERVED_FAILURE.search(semantic_query)
        else "current_state"
        if (
            _POST_ACTION_STATE.search(semantic_query)
            and not _POST_ACTION_ASSIGNMENT.search(semantic_query)
        )
        else next(
            (name for name, pattern in _ROUTES if pattern.search(semantic_query)),
            "exact_fact",
        )
    )
    tokens = [token.casefold() for token in _TOKEN.findall(semantic_query)]
    temporal_target = _temporal_target(semantic_query)
    polarity = "negative" if re.search(
        r"\b(?:no|not|never|without|cannot|can't|don't|doesn't|isn't|aren't)\b",
        semantic_query,
        re.I,
    ) else "unknown"
    obligations = _obligations(
        semantic_query, need_type, polarity=polarity,
        temporal_target=temporal_target,
    )
    entities = tuple(dict.fromkeys(
        obligation["entity"] for obligation in obligations if obligation.get("entity")
    ))[:8]
    identity = canonical_json({
        "query": normalized.casefold(),
        "parent_need_id": parent_need_id,
        "ordinal": ordinal,
    })
    return InformationNeed(
        need_id=f"need-{sha256_hex(identity)[:24]}",
        type=need_type,
        entities=entities,
        relation_or_action=_relation_hint(tokens, need_type),
        temporal_target=temporal_target or (
            "current" if need_type == "current_state" else None
        ),
        polarity=polarity,
        expected_form=need_type,
        required_slots=_SLOTS[need_type],
        parent_need_id=parent_need_id,
        obligations=obligations,
        evidence_terms=_evidence_terms(semantic_query),
    )


def decompose_information_need(
    query: str,
    *,
    budget: RetrievalBudget | None = None,
) -> tuple[InformationNeed, tuple[InformationNeed, ...]]:
    """Split explicit compound questions within a declared bounded budget."""
    active_budget = budget or RetrievalBudget()
    parent = route_information_need(query)
    parts = [
        part.strip(" ,;?")
        for part in re.split(r"\s+(?:and|then|also)\s+|[;]", query, flags=re.I)
        if part.strip(" ,;?")
    ]
    if len(parts) <= 1:
        return parent, ()
    children = tuple(
        route_information_need(
            part,
            parent_need_id=parent.need_id,
            ordinal=index,
        )
        for index, part in enumerate(parts[: active_budget.subqueries])
    )
    return parent, children


def required_slots(need_type: str) -> tuple[str, ...]:
    return _SLOTS[need_type]


def plan_retrieval_queries(
    query: str,
    *,
    need: InformationNeed | None = None,
    limit: int = 4,
) -> tuple[str, ...]:
    """Build bounded, deterministic evidence queries from one user question.

    Long natural-language questions dilute persistent-posting scores.  This
    planner retains the original question for recall, then adds only phrases
    stated by the caller: explicit UI literals/anchors, routed entity-relation
    obligations, and a compact content-word query.  It never invents an answer
    or uses benchmark metadata.
    """
    normalized = " ".join(query.split())
    if not normalized:
        raise ValueError("retrieval query planning requires a non-empty query")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("retrieval query limit must be a positive integer")
    active_need = need or route_information_need(normalized)
    planned: list[str] = [normalized]

    planned.extend(comparison_retrieval_queries(normalized))

    anchors = evidence_anchor_queries(normalized)
    if anchors:
        planned.append(" ".join(anchors))

    salient = salient_retrieval_query(normalized)
    if salient:
        planned.append(salient)

    contextual = contextual_retrieval_query(normalized, excluding=salient)
    if contextual:
        planned.append(contextual)

    semantic_for_compact = _ACTION_SPACE_SUFFIX.sub(" ", normalized)
    semantic_for_compact = _PRESENTATION_SUFFIX.sub("", semantic_for_compact).strip()
    semantic_for_compact = _IMPERATIVE_PRESENTATION_SUFFIX.sub(
        "", semantic_for_compact
    ).strip()
    compact = [
        token for token in (
            value.casefold() for value in _TOKEN.findall(semantic_for_compact)
        )
        if token not in _STOP | _RETRIEVAL_BOILERPLATE and len(token) > 2
    ]
    if compact:
        # Preserve both ends: questions often put the application/entity first
        # and the exact requested state or action last.
        bounded = compact if len(compact) <= 16 else compact[:8] + compact[-8:]
        planned.append(" ".join(dict.fromkeys(bounded)))

    obligation_terms: list[str] = []
    for obligation in active_need.obligations:
        obligation_terms.extend(
            str(obligation.get(name) or "").strip()
            for name in ("entity", "relation", "action")
            if str(obligation.get(name) or "").strip()
            and str(obligation.get(name) or "").strip().casefold()
            not in {"user", "person", "agent"}
        )
    if active_need.relation_or_action:
        obligation_terms.append(active_need.relation_or_action)
    if obligation_terms and any(
        term.casefold() not in _STOP | _RETRIEVAL_BOILERPLATE
        for term in obligation_terms
    ):
        planned.append(" ".join(dict.fromkeys(obligation_terms)))

    unique: list[str] = []
    seen: set[str] = set()
    for value in planned:
        identity = value.casefold()
        if value and identity not in seen:
            unique.append(value)
            seen.add(identity)
    return tuple(unique[:limit])


def comparison_retrieval_queries(query: str) -> tuple[str, ...]:
    """Split an explicit comparison into relation-scoped entity probes.

    A joint lexical query for ``A vs B`` often retrieves an A page that merely
    mentions B.  Independent probes preserve the caller's entities and exact
    relation while giving complementary packing a chance to cover both sides.
    No corpus vocabulary or answer term is introduced.
    """
    normalized = " ".join(query.split())
    match = _VERSUS.search(normalized)
    if match is None:
        return ()
    relation_terms = evidence_anchor_queries(normalized)
    relation = " ".join(relation_terms[:1])
    lifecycle = (
        "new record"
        if re.search(r"\b(?:create|creating|new|default)\b", normalized, re.I)
        else ""
    )
    sides: list[str] = []
    for raw in match.groups():
        tokens = [
            token.casefold() for token in _TOKEN.findall(raw)
            if len(token) > 2
            and token.casefold() not in _STOP | _RETRIEVAL_BOILERPLATE
            and token.casefold() not in {"create", "new", "open", "view"}
        ]
        rendered = " ".join(dict.fromkeys(tokens[-4:]))
        if rendered:
            sides.append(" ".join(
                value for value in (rendered, lifecycle, relation) if value
            ))
    return tuple(dict.fromkeys(sides))


def salient_retrieval_query(query: str, *, max_terms: int = 16) -> str:
    """Remove transport/UI instructions while preserving the stated evidence need.

    Agent questions commonly append an entire action schema, output formatting,
    or generic product framing.  Those high-frequency tokens overwhelmed the
    actual goal in lexical indexes (for example, ``notify ... reorder``).  This
    projection is deterministic and corpus-independent: it removes only caller
    presentation/transport language and never adds an answer term.
    """
    normalized = " ".join(query.split())
    if not normalized:
        return ""
    semantic = _ACTION_SPACE_SUFFIX.sub(" ", normalized)
    semantic = _PRESENTATION_SUFFIX.sub("", semantic).strip()
    semantic = _IMPERATIVE_PRESENTATION_SUFFIX.sub("", semantic).strip()

    def content_tokens(value: str) -> list[str]:
        return [
            token.casefold()
            for token in _TOKEN.findall(value)
            if len(token) > 2
            and token.casefold() not in _STOP | _RETRIEVAL_BOILERPLATE
            and not token.isdigit()
        ]

    clauses = [value for value in re.split(r"(?<=[.!?])\s+", semantic) if value]
    clause_tokens = [(value, content_tokens(value)) for value in clauses]
    informative = [
        (value, tokens) for value, tokens in clause_tokens if len(set(tokens)) >= 2
    ]
    # A single intent sentence is a much better lexical probe than the union
    # of product framing, current-position narration, and output instructions.
    # Ties prefer the earlier caller statement.
    explicit_literals = tuple(value.casefold() for value in evidence_anchor_queries(semantic))
    _clause, tokens = max(
        informative,
        key=lambda item: (
            any(literal in item[0].casefold() for literal in explicit_literals),
            "?" in item[0],
            len(set(item[1])),
        ),
        default=(semantic, content_tokens(semantic)),
    )
    # Repetition is useful evidence in the source, but not in an FTS query.
    unique = list(dict.fromkeys(tokens))
    if len(unique) > max_terms:
        # Keep the beginning for application/entity identity and the end for
        # the requested relation/state, after presentation text is gone.
        left = max_terms // 2
        unique = unique[:left] + unique[-(max_terms - left):]
    return " ".join(unique)


def contextual_retrieval_query(
    query: str, *, excluding: str = "", max_terms: int = 12
) -> str:
    """Retain a second, distinct entity/workflow clause for premise checks.

    The final interrogative often names an unsupported value (for example an
    absent lifecycle state), while an earlier sentence identifies the page or
    workflow whose complete surface can disprove it. This projection uses only
    caller text and is therefore suitable for normal product retrieval too.
    """
    normalized = " ".join(query.split())
    semantic = _ACTION_SPACE_SUFFIX.sub(" ", normalized)
    semantic = _PRESENTATION_SUFFIX.sub("", semantic).strip()
    semantic = _IMPERATIVE_PRESENTATION_SUFFIX.sub("", semantic).strip()

    def content(value: str) -> list[str]:
        return list(dict.fromkeys(
            token.casefold() for token in _TOKEN.findall(value)
            if len(token) > 2
            and token.casefold() not in _STOP | _RETRIEVAL_BOILERPLATE
            and not token.isdigit()
        ))

    candidates = []
    for index, clause in enumerate(re.split(r"(?<=[.!?])\s+", semantic)):
        terms = content(clause)
        rendered = " ".join(terms[:max_terms])
        if len(terms) >= 2 and rendered and rendered != excluding:
            generic_preamble = bool(re.match(
                r"\s*i\s+(?:am|'m)\s+(?:using|working|on|in|with)\b",
                clause,
                re.I,
            ))
            candidates.append((not generic_preamble, len(terms), -index, rendered))
    return max(candidates, default=(False, 0, 0, ""))[3]


def evidence_anchor_queries(query: str) -> tuple[str, ...]:
    """Return only caller-stated literals that can prove an exact match.

    These anchors are intentionally narrower than general query rewrites.  A
    candidate covering every anchor is stronger evidence than several partial
    topic matches accumulated across broad rewrites.
    """
    normalized = " ".join(query.split())
    if not normalized:
        return ()
    literals = [
        " ".join(next(value for value in match.groups() if value).split())
        for match in _LITERAL.finditer(normalized)
    ]
    between = _BETWEEN.search(normalized)
    if between:
        literals.extend(" ".join(value.split()) for value in between.groups())
    return tuple(dict.fromkeys(value for value in literals if value))


def _relation_hint(tokens: Iterable[str], need_type: str) -> str | None:
    useful = [token for token in tokens if token not in _STOP]
    if not useful:
        return None
    signal = {
        "ordered_task": {"steps", "procedure", "process", "workflow"},
        "state_change": {"changed", "change", "before", "after", "history"},
        "rule_application": {"rule", "policy", "must", "should"},
    }.get(need_type, set())
    known = next(
        (_ALIASED_RELATIONS.get(token, token) for token in useful
         if _ALIASED_RELATIONS.get(token, token) in _RELATIONS),
        next((token for token in useful if token in signal), None),
    )
    if known is not None:
        return known
    if need_type == "ordered_task":
        return next(
            (token for token in useful if token not in _RETRIEVAL_BOILERPLATE),
            None,
        )
    return None


def _evidence_terms(query: str, *, limit: int = 20) -> tuple[str, ...]:
    """Retain caller-stated terms for query-focused evidence projection.

    These terms never nominate records or invent facts. They only compact an
    already-authorized source record to the controls and nearby labels most
    useful to the reader. Exact literals lead, followed by product-neutral
    content words from the question.
    """
    values: list[str] = []
    for literal in evidence_anchor_queries(query):
        values.extend(token.casefold() for token in _TOKEN.findall(literal))
    values.extend(
        token.casefold() for token in _TOKEN.findall(query)
        if len(token) > 2
        and token.casefold() not in _STOP | _RETRIEVAL_BOILERPLATE
        and not token.isdigit()
    )
    return tuple(dict.fromkeys(values))[:limit]


_ALIASED_RELATIONS = {"old": "age", "aged": "age", "years": "age", "where": "location"}
_RELATION_QUALIFIERS = {
    "backup", "billing", "favorite", "favourite", "home", "personal",
    "preferred", "primary", "secondary", "work",
}


def _temporal_target(query: str) -> str | None:
    exact = re.search(
        r"\b(?:in|on|during|at)\s+(\d{4}-\d{2}-\d{2})\b", query, re.I
    )
    if exact:
        value = exact.group(1)
        return value if 1900 <= int(value[:4]) <= 2199 else None
    year = re.search(r"\b(?:in|on|during|at)\s+(\d{4})\b", query, re.I)
    if year and 1900 <= int(year.group(1)) <= 2199:
        return year.group(1)
    return None


def _obligations(
    query: str, need_type: str, *, polarity: str = "unknown",
    temporal_target: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Extract explicit entity/relation pairs without benchmark vocabulary."""
    # Answer options are hypotheses presented to the reader, not evidence
    # obligations.  Routing them as required actions makes every unchosen
    # alternative look like missing memory.
    semantic_query = re.split(
        r"(?:^|\s)[A-Z][.)]\s+", query, maxsplit=1
    )[0]
    clauses = [
        value.strip(" ,;?") for value in re.split(
            r"\s+(?:and|then|also)\s+|[;]", semantic_query, flags=re.I
        )
        if value.strip(" ,;?")
    ]
    result: list[dict[str, str]] = []
    for clause in clauses:
        tokens = [token.casefold() for token in _TOKEN.findall(clause)]
        literal_relation = _requested_literal_relation(clause)
        relation_index = next(
            (index for index, token in enumerate(tokens)
             if _ALIASED_RELATIONS.get(token, token) in _RELATIONS), None,
        )
        relation = (
            _ALIASED_RELATIONS.get(tokens[relation_index], tokens[relation_index])
            if relation_index is not None else ""
        )
        relation_is_literal = False
        if not relation and need_type in {
            "exact_fact", "current_state", "state_change", "relational_synthesis"
        } and literal_relation:
            # Quoted/backticked field and control names are the caller's most
            # precise relation vocabulary.  Keep them verbatim instead of
            # manufacturing an entity from product narration around them.
            relation = literal_relation
            relation_is_literal = True
        if relation_index is not None:
            qualifiers = [
                token for token in tokens[:relation_index]
                if token in _RELATION_QUALIFIERS
            ]
            if qualifiers:
                relation = " ".join((*qualifiers, relation))
        entity_tokens = [
            token for token in tokens
            if token not in _STOP and _ALIASED_RELATIONS.get(token, token) != relation
            and token not in _RELATIONS
            and token not in {"current", "currently", "latest", "selected", "favorite", "compare", "together"}
            and not re.fullmatch(r"\d{4}(?:-\d{2}-\d{2})?", token)
        ]
        factual = need_type in {
            "exact_fact", "current_state", "state_change", "relational_synthesis"
        }
        # Preserve an unknown relation in the common compact fact shape
        # ("What is Alice salary?") without trying to derive a relation from
        # long product narration.
        if not relation and factual and len(entity_tokens) == 2:
            relation = entity_tokens[1]
        # A first-person product preamble ("I am working in ServiceNow") is
        # not evidence that the requested fact is about the speaker. Reserve
        # the user entity for direct personal predicates; otherwise arbitrary
        # UI questions acquire a bogus user obligation.
        personal_predicate = bool(
            relation
            and (
                re.search(r"\b(?:my|mine)\b", clause, re.I)
                or re.search(r"\bhow\s+(?:old|tall)\s+am\s+i\b", clause, re.I)
                or re.search(r"\bwhere\s+(?:do|am)\s+i\b", clause, re.I)
            )
        )
        entity = (
            "user" if factual and personal_predicate
            else entity_tokens[0]
            if (
                factual and relation and 0 < len(entity_tokens) <= 3
                and not relation_is_literal
            )
            else ""
        )
        # Unknown relations remain unbound. Retrieval still uses the full,
        # salient and literal queries, while sufficiency falls back to partial
        # evidence rather than inventing a precise obligation from prose.
        obligation: dict[str, str] = {}
        if entity:
            obligation["entity"] = entity
        if relation and factual:
            obligation["relation"] = relation
        elif not factual:
            action = _relation_hint(tokens, need_type)
            if action:
                obligation["action"] = action
        if obligation:
            if polarity != "unknown":
                obligation["polarity"] = polarity
            clause_temporal_target = _temporal_target(clause)
            if clause_temporal_target or (len(clauses) == 1 and temporal_target):
                obligation["temporal_target"] = (
                    clause_temporal_target or temporal_target or ""
                )
            result.append(obligation)
    inherited_entity = next(
        (item["entity"] for item in result if item.get("entity")), ""
    )
    if inherited_entity:
        for item in result:
            if item.get("relation") and not item.get("entity"):
                item["entity"] = inherited_entity
    return tuple(result)


def _requested_literal_relation(clause: str) -> str:
    """Return a quoted field/control named in the interrogative clause."""
    question_words = list(re.finditer(r"\b(?:what|which|how|where|when)\b", clause, re.I))
    start = question_words[-1].start() if question_words else 0
    matches = list(_LITERAL.finditer(clause, start))
    for match in matches:
        tail = clause[match.end():match.end() + 32]
        if re.match(
            r"\s*(?:field|control|option|setting|column|property|attribute)\b",
            tail,
            re.I,
        ):
            return " ".join(next(value for value in match.groups() if value).split())
        prefix = clause[max(start, match.start() - 64):match.start()]
        if re.search(
            r"\b(?:shown|displayed|visible|selected|active|value)\b.{0,40}"
            r"\b(?:in|for|of|as)\s*$",
            prefix,
            re.I,
        ):
            return " ".join(next(value for value in match.groups() if value).split())
    return ""
