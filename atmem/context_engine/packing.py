"""Evidence-complete context packing under one byte budget."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import QueryPlan, SufficiencyDecisionV2
from .retrieval import RetrievalResult


@dataclass(frozen=True, slots=True)
class PackedContext:
    context: str
    included_unit_ids: tuple[str, ...]
    excluded_unit_ids: tuple[str, ...]
    bytes_used: int
    complete: bool


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
    candidates = sorted(
        result.candidates,
        key=lambda item: (
            min((order.get(value, len(order)) for value in item.matched_obligation_ids), default=len(order)),
            item.source_id,
        ),
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
        if used + size > max_bytes:
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
