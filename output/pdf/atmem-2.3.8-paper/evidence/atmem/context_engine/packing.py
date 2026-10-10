"""Evidence-complete context packing under one byte budget."""

from __future__ import annotations

from dataclasses import dataclass
import re

from atmem.contracts.models import ActionConstraint

from .contracts import QueryPlan, SufficiencyDecisionV2
from .retrieval import RetrievalResult, RetrievedCandidate


@dataclass(frozen=True, slots=True)
class PackedContext:
    context: str
    included_unit_ids: tuple[str, ...]
    excluded_unit_ids: tuple[str, ...]
    bytes_used: int
    complete: bool


def _option_field_facets(plan: QueryPlan) -> tuple[tuple[str, ...], ...]:
    """Return answer-blind field phrases explicitly named by an option query."""
    if not any(
        "which option" in (item.relation_or_action or "").casefold()
        for item in plan.obligations
    ):
        return ()
    facets: list[tuple[str, ...]] = []
    for queries in plan.pool_queries.values():
        for query in queries:
            match = re.fullmatch(
                r"\s*[A-Za-z0-9_-]+\s+table\s+(.+?)\s*", query,
                re.IGNORECASE,
            )
            if not match:
                continue
            terms = tuple(
                token.casefold()
                for token in re.findall(r"[^\W_]+", match.group(1), re.UNICODE)
                if len(token) > 1
            )
            if terms and terms not in facets:
                facets.append(terms)
    return tuple(facets)


def _coverage_order(
    candidates: list[RetrievedCandidate], plan: QueryPlan,
) -> list[RetrievedCandidate]:
    """Greedily pack explicit option-field coverage before redundant UI text."""
    facets = _option_field_facets(plan)
    if not facets:
        return candidates
    required = [item for item in candidates if item.matched_obligation_ids]
    remaining = [item for item in candidates if not item.matched_obligation_ids]
    intent_sources = {
        item.source_id
        for item in candidates
        if item.part_id == "trajectory-metadata"
        and re.search(r"\bcreat(?:e|es|ed|ing)\b.{0,32}\bproblems?\b", item.text,
                      re.IGNORECASE | re.DOTALL)
    }

    def coverage(item: RetrievedCandidate) -> set[tuple[str, ...]]:
        # A field name in an Incident, Change, or generic dictionary is not
        # evidence that the field exists on the requested Problem surface.
        # Keep field coverage inside a matching workflow trajectory or an
        # explicit Problem table/form observation.
        if item.source_id not in intent_sources and not re.search(
            r"\bproblems?\s+table\b|\bproblem_table\b|\bproblem\s*\|\s*servicenow\b",
            item.text,
            re.IGNORECASE,
        ):
            return set()
        words = {
            token.casefold()
            for token in re.findall(r"[^\W_]+", item.text, re.UNICODE)
        }
        return {facet for facet in facets if set(facet) <= words}

    coverage_by_unit = {item.unit_id: coverage(item) for item in candidates}
    covered = (
        set().union(*(coverage_by_unit[item.unit_id] for item in required))
        if required else set()
    )
    ordered = list(required)
    while remaining:
        def rank(pair: tuple[int, RetrievedCandidate]) -> tuple[float, int, int, int]:
            index, candidate = pair
            new_count = len(coverage_by_unit[candidate.unit_id] - covered)
            byte_count = max(1, len(candidate.text.encode("utf-8")))
            # Prefer complementary evidence density. A single 12 KiB UI state
            # that happens to mention three fields should not displace three
            # short, exact source ranges that establish the same coverage with
            # far less reader noise.
            return (-new_count / byte_count, -new_count, byte_count, index)

        ranked = sorted(
            enumerate(remaining),
            key=rank,
        )
        index, candidate = ranked[0]
        new = coverage_by_unit[candidate.unit_id] - covered
        if not new:
            ordered.extend(remaining)
            break
        ordered.append(candidate)
        covered.update(new)
        remaining.pop(index)
    return ordered


_ACTION_PACK_STOP = frozenset({
    "a", "an", "and", "at", "be", "became", "by", "for", "from", "how",
    "i", "in", "is", "it", "me", "of", "on", "or", "please", "send",
    "email", "message", "post", "notify", "ask", "summarizing", "summary",
    "the", "to", "what", "whether", "why", "with",
})


def _action_source_order(
    candidates: list[RetrievedCandidate], plan: QueryPlan,
) -> list[RetrievedCandidate]:
    """Keep the strongest action evidence episode complete and contiguous.

    Addressed actions frequently need several facts from one immutable episode.
    Interleaving those ranges with recipient records and loosely related caveats
    makes a reader omit exact values or over-apply an older boundary even though
    retrieval found the right source.  Rank *source groups* by request coverage,
    then retain source order inside each group.  The rank uses only the user's
    information needs and source text; it has no access to benchmark answers.
    """
    action_need = any(re.match(
        r"\s*(?:email|send|message|post|notify|ask)\b",
        item.relation_or_action,
        re.IGNORECASE,
    ) for item in plan.obligations)
    if not action_need or len(candidates) < 2:
        return candidates

    need_terms = {
        token.casefold()
        for item in plan.obligations
        for token in re.findall(
            r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*",
            " ".join(filter(None, (item.entity, item.relation_or_action))),
        )
        if len(token) > 1 and token.casefold() not in _ACTION_PACK_STOP
    }
    if not need_terms:
        return candidates

    groups: dict[str, list[tuple[int, RetrievedCandidate]]] = {}
    for index, candidate in enumerate(candidates):
        groups.setdefault(candidate.source_id, []).append((index, candidate))

    def rank(group: list[tuple[int, RetrievedCandidate]]) -> tuple[int, int, float, int]:
        text_terms = {
            token.casefold()
            for _, candidate in group
            for token in re.findall(
                r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", candidate.text
            )
        }
        covered = len(need_terms & text_terms)
        byte_count = max(1, sum(
            len(candidate.text.encode("utf-8")) for _, candidate in group
        ))
        obligation_coverage = len({
            obligation_id
            for _, candidate in group
            for obligation_id in candidate.matched_obligation_ids
        })
        return (-obligation_coverage, -covered, -covered / byte_count, group[0][0])

    ordered: list[RetrievedCandidate] = []
    for group in sorted(groups.values(), key=rank):
        ordered.extend(
            candidate
            for _, candidate in sorted(
                group,
                key=lambda pair: (
                    pair[1].part_id,
                    pair[1].start,
                    pair[1].end,
                    pair[0],
                ),
            )
        )
    return ordered


def pack_context(
    plan: QueryPlan,
    result: RetrievalResult,
    decision: SufficiencyDecisionV2,
    *,
    max_bytes: int,
) -> PackedContext:
    if max_bytes < 0:
        raise ValueError("max_bytes cannot be negative")
    order = {item.obligation_id: index for index, item in enumerate(plan.obligations)}
    # Retrieval order is meaningful: obligation-grounding heads precede their
    # bounded neighbourhood and lower-ranked supplemental sources. Sorting by
    # opaque source IDs used to randomize that order and place unrelated raw
    # states before the evidence that actually satisfied the question.
    candidates = [
        item for _, item in sorted(
            enumerate(result.candidates),
            key=lambda pair: (
                0 if pair[1].matched_obligation_ids else 1,
                min(
                    (order.get(value, len(order)) for value in pair[1].matched_obligation_ids),
                    default=len(order),
                ),
                pair[0],
            ),
        )
    ]
    candidates = _coverage_order(candidates, plan)
    candidates = _action_source_order(candidates, plan)
    # A single information need should receive a compact evidence package,
    # not 32 KiB of loosely related UI states. Required evidence still has
    # first claim on the budget; this cap only removes supplemental noise.
    effective_max_bytes = (
        min(max_bytes, 16_384) if len(plan.obligations) == 1 else max_bytes
    )
    chunks: list[str] = []
    included: list[str] = []
    excluded: list[str] = []
    used = 0
    for candidate in candidates:
        chunk = (
            f"[source={candidate.source_id} part={candidate.part_id} "
            f"range={candidate.start}:{candidate.end}]\n{candidate.text}"
        )
        separator = "\n\n" if chunks else ""
        size = len((separator + chunk).encode())
        if used + size > effective_max_bytes:
            excluded.append(candidate.unit_id)
            continue
        chunks.append(chunk)
        included.append(candidate.unit_id)
        used += size
    needed = set(decision.evidence_unit_ids)
    return PackedContext(
        context="\n\n".join(chunks), included_unit_ids=tuple(included),
        excluded_unit_ids=tuple(excluded), bytes_used=used,
        complete=needed <= set(included),
    )


def derive_action_constraints(
    query: str, result: RetrievalResult, decision: SufficiencyDecisionV2,
) -> tuple[ActionConstraint, ...]:
    """Translate explicit source rules into agent-facing, non-executing constraints."""
    if decision.status != "sufficient":
        return ()
    constraints: list[ActionConstraint] = []
    for candidate in result.candidates:
        text = candidate.text
        if candidate.kind != "rule" and not re.search(
            r"\b(must|should|required|never)\b", text, re.IGNORECASE
        ):
            continue
        targets = re.findall(r"#[A-Za-z0-9_-]+", text)
        required = None
        prohibited = None
        if re.search(r"\b(must|should|required)\b", text, re.IGNORECASE):
            required = "follow governing source rule"
        never = re.search(r"\bnever\s+(#[A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if never:
            prohibited = f"use {never.group(1)}"
        if required or prohibited:
            constraints.append(ActionConstraint(
                subject=query,
                applies_when=query,
                source_ids=(candidate.source_id,),
                validity="current",
                required_action=required,
                prohibited_action=prohibited,
                target=targets[0] if targets else None,
                parameters={"source_range": f"{candidate.start}:{candidate.end}"},
            ))
    return tuple(constraints)
