"""Deterministic, product-neutral routing from a question to evidence needs."""

from __future__ import annotations

import re
from typing import Iterable

from atmem.contracts import InformationNeed, RetrievalBudget
from atmem.core.canonical import canonical_json, sha256_hex


_ROUTES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ordered_task", re.compile(r"\b(?:how (?:do|can|should)|steps?|procedure|process|workflow|in what order)\b", re.I)),
    ("state_change", re.compile(r"\b(?:changed?|before|after|previously|used to|history|transition)\b", re.I)),
    ("exception_risk", re.compile(r"\b(?:fail(?:ed|ure)?|error|issue|gotcha|avoid|workaround|did not work|didn't work|risk)\b", re.I)),
    ("rule_application", re.compile(r"\b(?:must|should|allowed|permitted|required|prohibited|which channel|what rule|policy)\b", re.I)),
    ("assumption_check", re.compile(r"\b(?:assum(?:e|ing|ption)|premise|is it true|does .* exist|available|applicable)\b", re.I)),
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
    "a an am and are can could did do does for from how i in is it me my of on or should the this to was what when where which who why with you your".split()
)
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_RELATIONS = frozenset({
    "age", "height", "location", "food", "city", "status", "model",
    "configuration", "name", "email", "channel", "procedure", "color",
    "price", "filter", "purchase", "item",
})
_PRESENTATION_SUFFIX = re.compile(
    r"(?:^|(?<=[.!?])\s+)(?:your final answer|mark your final answer|"
    r"format your (?:final )?answer|answer (?:using|in|with)|respond (?:using|in|with))"
    r"\b.*$",
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
    semantic_query = _PRESENTATION_SUFFIX.sub("", normalized).strip() or normalized
    need_type = next(
        (name for name, pattern in _ROUTES if pattern.search(semantic_query)),
        "exact_fact",
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


def _relation_hint(tokens: Iterable[str], need_type: str) -> str | None:
    useful = [token for token in tokens if token not in _STOP]
    if not useful:
        return None
    signal = {
        "ordered_task": {"steps", "procedure", "process", "workflow"},
        "state_change": {"changed", "change", "before", "after", "history"},
        "rule_application": {"rule", "policy", "must", "should"},
    }.get(need_type, set())
    return next(
        (_ALIASED_RELATIONS.get(token, token) for token in useful
         if _ALIASED_RELATIONS.get(token, token) in _RELATIONS),
        next((token for token in useful if token not in signal), useful[0]),
    )


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
    clauses = [
        value.strip(" ,;?") for value in re.split(r"\s+(?:and|then|also)\s+|[;]", query, flags=re.I)
        if value.strip(" ,;?")
    ]
    result: list[dict[str, str]] = []
    for clause in clauses:
        tokens = [token.casefold() for token in _TOKEN.findall(clause)]
        relation_index = next(
            (index for index, token in enumerate(tokens)
             if _ALIASED_RELATIONS.get(token, token) in _RELATIONS), None,
        )
        relation = (
            _ALIASED_RELATIONS.get(tokens[relation_index], tokens[relation_index])
            if relation_index is not None else ""
        )
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
        entity = (
            "user" if factual and any(token in {"i", "me", "my", "mine"} for token in tokens)
            else entity_tokens[0] if factual and entity_tokens else ""
        )
        if not relation and factual and entity_tokens:
            if entity == "user":
                relation = " ".join(entity_tokens[-2:])
            elif len(entity_tokens) > 1:
                relation = " ".join(entity_tokens[1:])
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
