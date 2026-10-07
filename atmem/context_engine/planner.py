"""Deterministic information-need routing for Context Engine V3."""

from __future__ import annotations

import re

from atmem.core.canonical import sha256_hex

from .contracts import EvidenceObligation, QueryPlan


_QUESTION_WORDS = frozenset({"what", "which", "where", "when", "how", "who", "why", "whether"})
_PLAN_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "i", "in", "is", "it", "my", "of", "on", "or", "our", "please",
    "that", "the", "their", "this", "to", "we", "with", "you", "send",
    "email", "post", "create", "update", "inspect", "review", "find",
})


def _need_clauses(query: str) -> tuple[str, ...]:
    """Split explicit memory needs without inventing hidden requirements."""
    value = re.sub(r"^\s*\[\d{4}-\d{2}-\d{2}\]\s*", "", query).strip()
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
    if lowered.startswith("how ") or re.search(r"\b(steps?|procedure|in order)\b", lowered):
        return "ordered_steps"
    if "what changed" in lowered or re.search(r"\b(before|after|transition)\b", lowered):
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


class DeterministicPlanner:
    identity = "context-planner-deterministic-v1"

    def plan(self, query: str) -> QueryPlan:
        normalized = " ".join(query.split())
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
                    entity=_entity(clause), relation_or_action=clause,
                    temporal_target=temporal.group(0) if temporal else None,
                    polarity="negative" if kind == "premise_check" else "unknown",
                ))
        routed_queries = (
            (normalized,)
            if comparison
            else tuple(dict.fromkeys(
                (normalized, *(item.relation_or_action or normalized for item in obligations))
            ))
        )
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
