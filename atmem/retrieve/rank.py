"""General-purpose recall ranking.

Candidate generation has top-k semantics over active records. Injection does
not: the original query must establish calibrated support, and trust/recency
can only reorder supported candidates. Retrieval events retain a bounded score
sample.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from atmem.retrieve.calibration import load_calibration
from atmem.retrieve.models import CandidateDecision, RetrievalDecision, SupportClass
from atmem.retrieve.signals import contribution, semantic_contribution

TEXT_WEIGHT = 0.75
TRUST_WEIGHT = 0.15
RECENCY_WEIGHT = 0.10

_TRUST_SCORES = {
    "trusted_user": 1.0,
    "user_confirmed": 0.9,
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """
    a about after all am an and any are as at be been before but by can could
    did do does for from had has have he her his how i if in is it its me my
    no not of on or our should so that the their them then there they this to
    up us was we were what when where which who why will with would you your
    """.split()
)

_CONCEPT_ALIASES = {
    "favourite": "preference",
    "favorite": "preference",
    "fav": "preference",
    "prefer": "preference",
    "preferred": "preference",
    "preference": "preference",
    "like": "preference",
    "likes": "preference",
    "lunch": "food",
    "meal": "food",
    "eat": "food",
    "food": "food",
    "burger": "food",
    "burgers": "food",
    "automobile": "car",
    "automobiles": "car",
    "vehicle": "car",
    "vehicles": "car",
    "cars": "car",
}


@dataclass(frozen=True)
class ScoredRecord:
    record: dict[str, Any]
    score: float
    text_score: float
    trust_score: float
    recency_score: float


def decide_retrieval(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    allow_background: bool = False,
) -> RetrievalDecision:
    """Classify original-query support before optional intelligence reranks.

    Candidate priors are used only after relevance is established. Expanded
    queries are deliberately ignored here: they may find a record but cannot
    prove that it answers the user's original question.
    """
    calibration = load_calibration()
    direct = float(calibration["direct_threshold"])
    background = float(calibration["background_threshold"])
    semantic_gate = float(calibration["production_semantic_threshold"])
    query_concepts = _concept_tokens(query)
    decisions: list[CandidateDecision] = []
    for candidate in candidates:
        signals = dict(candidate.get("signals") or {})
        fact_key = str(signals.get("fact_key") or candidate.get("fact_key") or "")
        content = str(candidate.get("content") or "")
        content_concepts = _concept_tokens(content)
        lexical = _concept_overlap(query_concepts, content_concepts)
        fact_support = _concept_overlap(
            query_concepts, _concept_tokens(fact_key.replace("_", " "))
        )
        semantic = float(
            signals.get("semantic_similarity")
            or ((signals.get("semantic_evidence") or {}).get("similarity") or 0.0)
        )
        provider = str(
            signals.get("semantic_provider")
            or ((signals.get("semantic_evidence") or {}).get("provider") or "")
        )
        quality_class = str(
            signals.get("semantic_quality_class")
            or ((signals.get("semantic_evidence") or {}).get("quality_class") or "")
        )
        semantic_signal = semantic_contribution(
            semantic, provider, quality_class=quality_class
        )
        diagnostic = not semantic_signal.eligible_for_support
        semantic_support = (
            semantic_signal.normalized_score
            if semantic_signal.eligible_for_support and semantic >= semantic_gate
            else 0.0
        )
        relevance = max(lexical, fact_support, semantic_support)
        if relevance >= direct:
            support = SupportClass.DIRECT
            reasons = ["original_query_supported"]
        elif relevance >= background:
            support = SupportClass.BACKGROUND
            reasons = ["background_only"]
        else:
            support = SupportClass.NONE
            reasons = ["no_relevance_signal"]
        if diagnostic:
            reasons.append("diagnostic_semantic_ignored")
        prior_signal = contribution("candidate_prior", candidate.get("score") or 0.0)
        prior = prior_signal.normalized_score
        lexical_signal = contribution("lexical_support", lexical)
        typo_signal = contribution(
            "typo_tolerant_support",
            1.0 if lexical > 0.0 and not (query_concepts & content_concepts) else 0.0,
        )
        fact_signal = contribution("fact_support", fact_support)
        graph = signals.get("graph") or candidate.get("graph") or {}
        graph_signal = contribution(
            "graph_prior", graph.get("score", 0.0) if isinstance(graph, dict) else 0.0
        )
        trust_signal = contribution(
            "trust_prior", _TRUST_SCORES.get(str(candidate.get("trust_tier") or ""), 0.4)
        )
        recency_signal = contribution("recency_prior", signals.get("recency_score", 0.0))
        atbot_signal = contribution("atbot_rerank", signals.get("atbot_score", 0.0))
        rank_score = (
            float(calibration["relevance_weight"]) * relevance
            + float(calibration["prior_weight"]) * prior
            if support is not SupportClass.NONE
            else 0.0
        )
        decisions.append(
            CandidateDecision(
                record_id=str(candidate.get("record_id") or candidate.get("id") or ""),
                support_class=support,
                relevance_score=round(relevance, 6),
                rank_score=round(rank_score, 6),
                signals={
                    "lexical_support": round(lexical, 6),
                    "typo_tolerant_support": 1.0 if (
                        lexical > 0.0 and not (query_concepts & content_concepts)
                    ) else 0.0,
                    "semantic_support": round(semantic_support, 6),
                    "fact_support": round(fact_support, 6),
                    "graph_prior": graph_signal.normalized_score,
                    "trust_prior": trust_signal.normalized_score,
                    "recency_prior": recency_signal.normalized_score,
                    "atbot_rerank": atbot_signal.normalized_score,
                    "candidate_prior": round(prior, 6),
                },
                signal_contributions=(
                    lexical_signal,
                    typo_signal,
                    fact_signal,
                    semantic_signal,
                    graph_signal,
                    trust_signal,
                    recency_signal,
                    atbot_signal,
                    prior_signal,
                ),
                reason_codes=tuple(reasons),
            )
        )
    decisions.sort(key=lambda row: (-row.rank_score, row.record_id))
    direct_selected = tuple(
        row.record_id for row in decisions if row.support_class is SupportClass.DIRECT
    )
    background_selected = tuple(
        row.record_id for row in decisions if row.support_class is SupportClass.BACKGROUND
    )
    selected = direct_selected or (background_selected if allow_background else ())
    overall = SupportClass.DIRECT if direct_selected else (
        SupportClass.BACKGROUND
        if any(row.support_class is SupportClass.BACKGROUND for row in decisions)
        else SupportClass.NONE
    )
    reasons = ("direct_support_found",) if direct_selected else (
        (("background_context_permitted",) if allow_background else ("background_context_withheld",))
        if overall is SupportClass.BACKGROUND
        else ("no_relevance_signal",)
    )
    return RetrievalDecision(
        format="atmem-retrieval-decision-v1",
        calibration_version=str(calibration["version"]),
        support_class=overall,
        ranked_record_ids=selected,
        candidates=tuple(decisions),
        reason_codes=reasons,
    )


def _concept_tokens(value: str) -> set[str]:
    result: set[str] = set()
    for token in query_tokens(value):
        stemmed = _stem(token)
        result.add(stemmed)
        result.add(_CONCEPT_ALIASES.get(token, _CONCEPT_ALIASES.get(stemmed, stemmed)))
    return result


def _concept_overlap(query_concepts: set[str], content_concepts: set[str]) -> float:
    """Return bounded concept support, including conservative typo recovery.

    Typo matching is deliberately limited to concepts of five or more
    characters. Longer tokens receive a two-edit budget; shorter eligible
    tokens receive one. It repairs inputs such as ``pizzaa`` and ``burggger``
    without turning an unrelated short clue such as ``Royal`` into a
    nearest-memory lookup.
    """
    if not query_concepts:
        return 0.0
    matched = 0
    for query_concept in query_concepts:
        if query_concept in content_concepts or any(
            _within_typo_budget(query_concept, content_concept)
            for content_concept in content_concepts
        ):
            matched += 1
    return matched / len(query_concepts)


def _within_typo_budget(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 5:
        return False
    budget = 2 if max(len(left), len(right)) >= 7 else 1
    if abs(len(left) - len(right)) > budget:
        return False
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        if min(current) > budget:
            return False
        previous = current
    return previous[-1] <= budget


def query_tokens(query: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(query.lower())
        if token not in _STOPWORDS
    ]


def token_overlap_components(query: str, content: str) -> tuple[int, int]:
    """Return matched and total normalized query terms for fallback scoring."""
    query_stems = {_stem(token) for token in query_tokens(query)}
    content_stems = {_stem(token) for token in _TOKEN_RE.findall(content.lower())}
    return len(query_stems & content_stems), len(query_stems)


def rank_records(
    query: str,
    records: list[dict[str, Any]],
    *,
    fts_scores: dict[str, float] | None = None,
) -> list[ScoredRecord]:
    """Score every candidate record against the query, best first.

    `fts_scores` are raw relevance scores from the store's full-text index
    (higher is better). When absent, a token-overlap fallback with light
    stemming is used so behavior degrades gracefully without FTS5.
    """
    if not records:
        return []

    tokens = query_tokens(query)
    if fts_scores is not None:
        max_raw = max(fts_scores.values(), default=0.0)
        text_scores = {
            record_id: (raw / max_raw if max_raw > 0 else 0.0)
            for record_id, raw in fts_scores.items()
        }
    else:
        text_scores = {
            str(record.get("id")): _overlap_score(
                tokens,
                " ".join(
                    (
                        str(record.get("content") or ""),
                        str(record.get("fact_key") or "").replace("_", " "),
                    )
                ),
            )
            for record in records
        }

    by_recency = sorted(
        records,
        key=lambda record: (str(record.get("created_at") or ""), str(record.get("id"))),
    )
    recency_rank = {
        str(record.get("id")): index for index, record in enumerate(by_recency)
    }
    recency_denominator = max(len(records) - 1, 1)

    scored: list[ScoredRecord] = []
    for record in records:
        record_id = str(record.get("id"))
        text_score = text_scores.get(record_id, 0.0)
        trust_score = _TRUST_SCORES.get(str(record.get("trust_tier")), 0.4)
        recency_score = recency_rank[record_id] / recency_denominator
        score = (
            TEXT_WEIGHT * text_score
            + TRUST_WEIGHT * trust_score
            + RECENCY_WEIGHT * recency_score
        )
        scored.append(
            ScoredRecord(
                record=record,
                score=round(score, 6),
                text_score=round(text_score, 6),
                trust_score=round(trust_score, 6),
                recency_score=round(recency_score, 6),
            )
        )

    scored.sort(
        key=lambda item: (
            -item.score,
            str(item.record.get("created_at") or ""),
            str(item.record.get("id")),
        )
    )
    return scored


def _overlap_score(tokens: list[str], content: str) -> float:
    if not tokens:
        return 0.0
    query_stems = {_stem(token) for token in tokens}
    content_stems = {_stem(token) for token in _TOKEN_RE.findall(content.lower())}
    if not query_stems:
        return 0.0
    return _concept_overlap(query_stems, content_stems)


def _stem(token: str) -> str:
    """Tiny suffix stemmer, only for the no-FTS fallback path."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "i"
    if len(token) > 3 and token.endswith("y"):
        return token[:-1] + "i"
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token
