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
    need_type = next(
        (name for name, pattern in _ROUTES if pattern.search(normalized)),
        "exact_fact",
    )
    tokens = [token.casefold() for token in _TOKEN.findall(normalized)]
    entities = tuple(dict.fromkeys(token for token in tokens if token not in _STOP))[:8]
    polarity = "negative" if re.search(
        r"\b(?:no|not|never|without|cannot|can't|don't|doesn't|isn't|aren't)\b",
        normalized,
        re.I,
    ) else "unknown"
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
        temporal_target="current" if need_type == "current_state" else None,
        polarity=polarity,
        expected_form=need_type,
        required_slots=_SLOTS[need_type],
        parent_need_id=parent_need_id,
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
    return next((token for token in useful if token not in signal), useful[0])
