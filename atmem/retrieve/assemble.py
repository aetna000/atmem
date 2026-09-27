"""Coverage-first, source-linked Context Package V2 assembly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import html

from atmem.contracts import (
    ActionConstraint,
    ContextPackageV2,
    InformationNeed,
    RetrievalBudget,
)
from atmem.core.canonical import sha256_hex
from atmem.retrieve.sufficiency import covered_slots, decide_sufficiency


def assemble_context_v2(
    *,
    context_id: str,
    scope,
    need: InformationNeed,
    profile_id: str,
    typed_rows: list[dict],
    budget: RetrievalBudget,
    generation: int,
    preparation_id: str,
) -> ContextPackageV2:
    chosen = _complementary_rows(need, typed_rows, budget.context_bytes)
    sufficiency = decide_sufficiency(need, chosen)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(
        timespec="microseconds"
    )
    if sufficiency.status == "unsupported":
        return _unsupported_package(
            context_id=context_id,
            scope=scope,
            generation=generation,
            expires_at=expires_at,
            preparation_id=preparation_id,
            profile_id=profile_id,
            need=need,
            sufficiency=sufficiency,
            budget=budget,
            typed_rows=typed_rows,
        )

    selected_ids = tuple(str(row["record_id"]) for row in chosen)
    source_ids = tuple(dict.fromkeys(
        str(evidence["source_id"])
        for row in chosen
        for evidence in row["unit"].get("evidence") or ()
    ))
    provenance = tuple(
        {
            "record_id": str(row["record_id"]),
            "source_id": str(evidence["source_id"]),
            "start_offset": int(evidence["start_offset"]),
            "end_offset": int(evidence["end_offset"]),
            "excerpt_sha256": str(evidence["excerpt_sha256"]),
        }
        for row in chosen
        for evidence in row["unit"].get("evidence") or ()
    )
    proposed_constraints = tuple(
        constraint
        for row in chosen
        if (constraint := _action_constraint(row, sufficiency.status)) is not None
    )
    context, packed_ids, constraints = _serialize(
        need, sufficiency, chosen, proposed_constraints, budget.context_bytes
    )
    if packed_ids != selected_ids:
        chosen = [row for row in chosen if str(row["record_id"]) in packed_ids]
        sufficiency = decide_sufficiency(need, chosen)
        source_ids = tuple(dict.fromkeys(
            str(evidence["source_id"])
            for row in chosen for evidence in row["unit"].get("evidence") or ()
        ))
        provenance = tuple(
            item for item in provenance if item["record_id"] in packed_ids
        )
        proposed_constraints = tuple(
            constraint for row in chosen
            if (constraint := _action_constraint(row, sufficiency.status)) is not None
        )
        if sufficiency.status == "unsupported":
            return _unsupported_package(
                context_id=context_id,
                scope=scope,
                generation=generation,
                expires_at=expires_at,
                preparation_id=preparation_id,
                profile_id=profile_id,
                need=need,
                sufficiency=sufficiency,
                budget=budget,
                typed_rows=typed_rows,
            )
        context, repacked_ids, constraints = _serialize(
            need, sufficiency, chosen, proposed_constraints, budget.context_bytes
        )
        packed_ids = repacked_ids
    excluded = tuple(
        str(row["record_id"]) for row in typed_rows
        if str(row["record_id"]) not in packed_ids
    )
    return ContextPackageV2(
        context_id=context_id, scope=scope, record_ids=packed_ids, context=context,
        context_sha256=f"sha256:{sha256_hex(context)}",
        serializer_version="atmem-context-structured-v2", generation=generation,
        expires_at=expires_at, preparation_id=preparation_id,
        profile_id=profile_id, need=need, sufficiency=sufficiency,
        source_ids=source_ids, budget=budget,
        selected_units=tuple(row["unit"] for row in chosen),
        provenance=provenance, excluded_evidence_ids=excluded,
        action_constraints=constraints,
        reason_codes=("coverage_first_packing",),
    )


def _complementary_rows(
    need: InformationNeed, rows: list[dict], context_bytes: int
) -> list[dict]:
    remaining = list(rows)
    chosen: list[dict] = []
    covered: set[str] = set()
    used_sources: set[str] = set()
    approximate_bytes = 256
    while remaining:
        ranked = []
        for index, row in enumerate(remaining):
            unit = row["unit"]
            slots = covered_slots(str(unit.get("kind") or ""), unit.get("payload") or {}, unit)
            new_slots = len((slots & set(need.required_slots)) - covered)
            sources = {
                str(item.get("source_id")) for item in unit.get("evidence") or ()
            }
            diversity = len(sources - used_sources)
            size = max(1, len(str(unit).encode("utf-8")))
            ranked.append((new_slots, diversity, -size, -index, row, slots, sources))
        best = max(ranked, key=lambda value: value[:4])
        _new, _diversity, negative_size, _index, row, slots, sources = best
        size = -negative_size + 96
        remaining.remove(row)
        if approximate_bytes + size > context_bytes:
            continue
        chosen.append(row)
        approximate_bytes += size
        covered.update(slots & set(need.required_slots))
        used_sources.update(sources)
    return chosen


def _serialize(need, sufficiency, rows, constraints, budget: int) -> tuple[str, tuple[str, ...], tuple[ActionConstraint, ...]]:
    parts = [
        '<atmem-context format="v2">\n',
        f'<need type="{html.escape(need.type)}" sufficiency="{sufficiency.status}">\n',
        f"Required evidence: {', '.join(need.required_slots)}\n",
    ]
    packed_ids: list[str] = []
    packed_constraints: list[ActionConstraint] = []
    if sufficiency.missing_slots:
        parts.append(f"Missing evidence: {', '.join(sufficiency.missing_slots)}\n")
    parts.append("</need>\n")
    closing = "</atmem-context>\n"
    for row in rows:
        unit = row["unit"]
        block = (
            f'<memory id="{html.escape(str(row["record_id"]))}" kind="{html.escape(str(unit.get("kind") or ""))}">\n'
            f"{html.escape(_unit_text(unit))}\n"
            f"Sources: {', '.join(html.escape(str(item['source_id'])) for item in unit.get('evidence') or ())}\n"
            "</memory>\n"
        )
        if len(("".join(parts) + block + closing).encode("utf-8")) <= budget:
            parts.append(block)
            packed_ids.append(str(row["record_id"]))
    for constraint in constraints:
        block = (
            "<action-constraint>\n"
            f"Applies when: {html.escape(constraint.applies_when)}\n"
            + (f"Required action: {html.escape(constraint.required_action)}\n" if constraint.required_action else "")
            + (f"Prohibited action: {html.escape(constraint.prohibited_action)}\n" if constraint.prohibited_action else "")
            + "</action-constraint>\n"
        )
        if len(("".join(parts) + block + closing).encode("utf-8")) <= budget:
            parts.append(block)
            packed_constraints.append(constraint)
    parts.append(closing)
    return "".join(parts), tuple(packed_ids), tuple(packed_constraints)


def _unsupported_package(
    *,
    context_id: str,
    scope,
    generation: int,
    expires_at: str,
    preparation_id: str,
    profile_id: str,
    need: InformationNeed,
    sufficiency,
    budget: RetrievalBudget,
    typed_rows: list[dict],
) -> ContextPackageV2:
    return ContextPackageV2(
        context_id=context_id,
        scope=scope,
        record_ids=(),
        context="",
        context_sha256=f"sha256:{sha256_hex('')}",
        serializer_version="atmem-context-structured-v2",
        generation=generation,
        expires_at=expires_at,
        preparation_id=preparation_id,
        profile_id=profile_id,
        need=need,
        sufficiency=sufficiency,
        source_ids=(),
        budget=budget,
        selected_units=(),
        provenance=(),
        excluded_evidence_ids=tuple(str(row["record_id"]) for row in typed_rows),
        reason_codes=("no_context_injected_without_support",),
    )


def _unit_text(unit: dict) -> str:
    payload = unit.get("payload") or {}
    kind = unit.get("kind")
    if kind in {"atomic_fact", "environment_state"}:
        return f"{payload.get('subject') or payload.get('entity')} {payload.get('relation')}: {payload.get('value')} ({payload.get('polarity')})"
    if kind == "state_transition":
        return f"{payload.get('entity')} {payload.get('before')} --{payload.get('action')}--> {payload.get('after')}"
    if kind == "procedure":
        return f"Goal: {payload.get('goal')}; " + "; ".join(
            f"{step.get('ordinal')}. {step.get('instruction')}" for step in payload.get("steps") or ()
        )
    if kind == "durable_rule":
        return f"When {payload.get('condition')}; required={payload.get('required_action')}; prohibited={payload.get('prohibited_action')}; exceptions={payload.get('exceptions')}"
    if kind == "failure_gotcha":
        return f"When {payload.get('trigger')}; failure={payload.get('failure')}; required={payload.get('required_action')}; prohibited={payload.get('prohibited_action')}"
    return f"Premise ({payload.get('polarity')}): {payload.get('proposition')}; applies={payload.get('applies_when')}; excluded={payload.get('excluded_when')}"


def _action_constraint(row: dict, status: str) -> ActionConstraint | None:
    if status != "sufficient":
        return None
    unit = row["unit"]
    payload = unit.get("payload") or {}
    if unit.get("kind") not in {"durable_rule", "failure_gotcha"}:
        return None
    sources = tuple(str(item["source_id"]) for item in unit.get("evidence") or ())
    condition = str(payload.get("condition") or payload.get("trigger") or "")
    return ActionConstraint(
        subject="governing memory rule",
        applies_when=condition,
        source_ids=sources,
        validity="current",
        required_action=payload.get("required_action"),
        prohibited_action=payload.get("prohibited_action"),
    )
