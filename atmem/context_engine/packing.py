"""Evidence-complete context packing under one byte budget."""

from __future__ import annotations

from dataclasses import dataclass
import re

from atmem.contracts.models import ActionConstraint

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
