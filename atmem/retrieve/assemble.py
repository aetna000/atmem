"""Coverage-first, source-linked Context Package V2 assembly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import html

from atmem.contracts import (
    ActionConstraint,
    ContextPackageV2,
    InformationNeed,
    RetrievalBudget,
    SufficiencyDecision,
)
from atmem.core.canonical import sha256_hex
from atmem.retrieve.sufficiency import (
    covered_slots,
    decide_sufficiency,
    matching_obligation_indexes,
)


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
    full_sufficiency = decide_sufficiency(need, typed_rows)
    sufficiency = decide_sufficiency(need, chosen)
    chosen_ids = {str(row["record_id"]) for row in chosen}
    conflict_evidence = set(full_sufficiency.evidence_ids) | set(
        full_sufficiency.contradiction_ids
    )
    if (
        full_sufficiency.status == "contradictory"
        and conflict_evidence <= chosen_ids
    ):
        # A byte limit may prevent serializing every side of a conflict. It
        # must never turn a known contradiction into a confident answer.
        sufficiency = full_sufficiency
    elif full_sufficiency.status == "contradictory":
        # Never present one side of a known conflict as sufficient merely
        # because its counterpart did not fit the byte budget.
        sufficiency = _unsupported_decision(
            need, "known_conflict_did_not_fit_context_budget"
        )
        chosen = []
    elif sufficiency.status == "unsupported" and chosen:
        sufficiency = _fallback_decision(need, chosen)
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
        packed_set = set(packed_ids)
        if (
            full_sufficiency.status == "contradictory"
            and conflict_evidence <= packed_set
        ):
            sufficiency = full_sufficiency
        elif full_sufficiency.status == "contradictory":
            return _unsupported_package(
                context_id=context_id, scope=scope, generation=generation,
                expires_at=expires_at, preparation_id=preparation_id,
                profile_id=profile_id, need=need,
                sufficiency=_unsupported_decision(
                    need, "known_conflict_did_not_fit_context_budget"
                ),
                budget=budget, typed_rows=typed_rows,
            )
        elif sufficiency.status == "unsupported" and chosen:
            sufficiency = _fallback_decision(need, chosen)
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
    full_decision = decide_sufficiency(need, rows)
    answer_bearing = set(full_decision.evidence_ids) | set(
        full_decision.contradiction_ids
    )
    # Sufficiency is deliberately conservative.  A lexical/typed candidate
    # that does not discharge a deterministic obligation may still contain
    # useful wording for the reader, so keep authorized nominees as bounded
    # background instead of turning an imperfect router into empty context.
    remaining = sorted(
        rows,
        key=lambda row: (
            str(row["record_id"]) not in answer_bearing,
            int(row.get("rank") or len(rows) + 1),
            str(row["record_id"]),
        ),
    )
    chosen: list[dict] = []
    covered: set[str] = set()
    covered_obligations: set[int] = set()
    used_sources: set[str] = set()
    approximate_bytes = 256
    mandatory_conflicts = set(full_decision.contradiction_ids)
    while remaining:
        ranked = []
        for index, row in enumerate(remaining):
            unit = row["unit"]
            slots = covered_slots(str(unit.get("kind") or ""), unit.get("payload") or {}, unit)
            new_slots = len((slots & set(need.required_slots)) - covered)
            obligations = matching_obligation_indexes(
                need, str(unit.get("kind") or ""), unit.get("payload") or {}, unit
            )
            new_obligations = len(obligations - covered_obligations)
            sources = {
                str(item.get("source_id")) for item in unit.get("evidence") or ()
            }
            diversity = len(sources - used_sources)
            size = max(1, len(str(unit).encode("utf-8")))
            priority = -int(row.get("rank") or (index + 1))
            answer_priority = int(str(row["record_id"]) in answer_bearing)
            ranked.append((
                new_obligations, answer_priority, new_slots, priority, diversity,
                -size, -index, row, slots, sources, obligations,
            ))
        best = max(ranked, key=lambda value: value[:7])
        (
            _new_obligation, _answer, _new, _priority, _diversity,
            negative_size, _index, row, slots, sources, obligations,
        ) = best
        size = -negative_size + 96
        remaining.remove(row)
        if approximate_bytes + size > context_bytes:
            continue
        chosen.append(row)
        approximate_bytes += size
        covered.update(slots & set(need.required_slots))
        covered_obligations.update(obligations)
        used_sources.update(sources)
        chosen_ids = {str(value["record_id"]) for value in chosen}
        if (
            decide_sufficiency(need, chosen).status == "sufficient"
            and mandatory_conflicts <= chosen_ids
        ):
            break
    return chosen


def _unsupported_decision(
    need: InformationNeed, reason: str
) -> SufficiencyDecision:
    return SufficiencyDecision(
        decision_id=f"sufficiency-{sha256_hex(need.need_id + ':' + reason)[:24]}",
        need_id=need.need_id,
        status="unsupported",
        required_slots=need.required_slots,
        covered_slots=(),
        missing_slots=need.required_slots,
        evidence_ids=(),
        reason_codes=(reason,),
    )


def _fallback_decision(
    need: InformationNeed, rows: list[dict]
) -> SufficiencyDecision:
    """Label authorized lexical nominees as unverified background evidence."""
    evidence_ids = tuple(dict.fromkeys(str(row["record_id"]) for row in rows))
    return SufficiencyDecision(
        decision_id=f"sufficiency-{sha256_hex(need.need_id + ':' + '|'.join(evidence_ids))[:24]}",
        need_id=need.need_id,
        status="partial",
        required_slots=need.required_slots,
        covered_slots=(),
        missing_slots=need.required_slots,
        evidence_ids=evidence_ids,
        reason_codes=("authorized_lexical_fallback_unverified",),
    )


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
        steps = "; ".join(
            f"{step.get('ordinal')}. {step.get('instruction')}"
            + (f" when {step.get('condition')}" if step.get("condition") else "")
            for step in payload.get("steps") or ()
        )
        prerequisites = ", ".join(payload.get("prerequisites") or ()) or "none recorded"
        completion = ", ".join(payload.get("completion_evidence") or ()) or "none recorded"
        failures = ", ".join(payload.get("failure_conditions") or ()) or "none recorded"
        return (
            f"Goal: {payload.get('goal')}; Prerequisites: {prerequisites}; "
            f"Steps: {steps}; Completion evidence: {completion}; "
            f"Failure conditions: {failures}"
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
