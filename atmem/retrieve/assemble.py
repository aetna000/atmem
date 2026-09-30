"""Coverage-first, source-linked Context Package V2 assembly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import html
import json
import re

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


_MAX_CONTEXT_UNITS = 12


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
    # Preserve the actual conflicting pair. Requiring every same-valued
    # supporting duplicate made large histories collapse to empty context.
    conflict_evidence = _conflict_evidence_ids(
        typed_rows, set(full_sufficiency.contradiction_ids)
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
    evidence_group_counts: dict[tuple[str, str, str], int] = {}
    approximate_bytes = 256
    mandatory_conflicts = _conflict_evidence_ids(
        rows, set(full_decision.contradiction_ids)
    )
    while remaining:
        if len(chosen) >= _MAX_CONTEXT_UNITS:
            break
        ranked = []
        for index, row in enumerate(remaining):
            unit = row["unit"]
            evidence_group = _evidence_group(unit)
            group_count = evidence_group_counts.get(evidence_group, 0)
            group_limit = _evidence_group_limit(unit)
            if group_count >= group_limit and str(row["record_id"]) not in mandatory_conflicts:
                continue
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
            group_diversity = int(group_count == 0)
            # Budget what the reader will actually receive.  Canonical typed
            # units retain exact source-linked state, while large browser
            # accessibility trees have a compact ordered-label projection at
            # serialization time.  Charging the full stored JSON here made a
            # 16 KiB context reject useful lower-ranked evidence even when its
            # reader projection was only a few hundred bytes.
            size = _estimated_unit_bytes(unit)
            priority = -int(row.get("rank") or (index + 1))
            answer_priority = int(str(row["record_id"]) in answer_bearing)
            # The candidate rank is the relevance contract produced by the
            # bounded hybrid retriever.  Slot-shaped evidence from an
            # unrelated state must not displace a stronger seed merely because
            # it happens to expose more generic fields.  Once relevance is
            # fixed, prefer complementary obligations/slots and diversity.
            if chosen:
                selection_key = (
                    new_obligations, answer_priority, new_slots,
                    group_diversity, priority, diversity, -size, -index,
                )
            else:
                # A deterministic router is necessarily imperfect on novel UI
                # language.  Preserve the retriever's strongest seed before
                # using inferred obligations to diversify the remainder.
                selection_key = (
                    priority, answer_priority, new_obligations, new_slots,
                    group_diversity, diversity, -size, -index,
                )
            ranked.append((*selection_key, row, slots, sources, obligations))
        if not ranked:
            break
        best = max(ranked, key=lambda value: value[:8])
        (
            _first, _second, _third, _fourth, _fifth, _sixth,
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
        group = _evidence_group(row["unit"])
        evidence_group_counts[group] = evidence_group_counts.get(group, 0) + 1
        chosen_ids = {str(value["record_id"]) for value in chosen}
        if (
            decide_sufficiency(need, chosen).status == "sufficient"
            and mandatory_conflicts <= chosen_ids
        ):
            break
    return chosen


def _conflict_evidence_ids(rows: list[dict], contradiction_ids: set[str]) -> set[str]:
    """Return each conflicting record and the earliest opposing value."""
    if not contradiction_ids:
        return set()
    result = set(contradiction_ids)
    by_id = {str(row["record_id"]): row for row in rows}
    for record_id in contradiction_ids:
        conflicting = by_id.get(record_id)
        if conflicting is None:
            continue
        unit = conflicting["unit"]
        payload = unit.get("payload") or {}
        identity = (
            str(unit.get("kind") or ""),
            str(payload.get("subject") or payload.get("entity") or "").casefold(),
            str(payload.get("relation") or "").casefold(),
        )
        value = json.dumps(
            {"value": payload.get("value", payload.get("after")),
             "polarity": payload.get("polarity")},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        for candidate in rows:
            candidate_unit = candidate["unit"]
            candidate_payload = candidate_unit.get("payload") or {}
            candidate_identity = (
                str(candidate_unit.get("kind") or ""),
                str(candidate_payload.get("subject") or candidate_payload.get("entity") or "").casefold(),
                str(candidate_payload.get("relation") or "").casefold(),
            )
            candidate_value = json.dumps(
                {"value": candidate_payload.get("value", candidate_payload.get("after")),
                 "polarity": candidate_payload.get("polarity")},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )
            if candidate_identity == identity and candidate_value != value:
                result.add(str(candidate["record_id"]))
                break
    return result


def _evidence_group(unit: dict) -> tuple[str, str, str]:
    """Group equivalent reader surfaces while retaining distinct state kinds.

    Browser trajectories often contain many chunks or revisits of the same URL.
    Packing every one crowds out the second fact needed by comparison and
    invalid-premise questions.  The immutable records remain available; this
    key only diversifies one bounded context package.
    """
    payload = unit.get("payload") or {}
    subject = str(payload.get("subject") or payload.get("entity") or "").strip().casefold()
    relation = str(payload.get("relation") or "").strip().casefold()
    relation_family = relation.split(":", 1)[0]
    return str(unit.get("kind") or ""), subject, relation_family


def _evidence_group_limit(unit: dict) -> int:
    payload = unit.get("payload") or {}
    relation = str(payload.get("relation") or "").strip().casefold()
    if relation in {"accessibility_tree", "tree"}:
        return 2
    if relation.startswith("state summary"):
        return 3
    if relation == "ui surface index":
        return 4
    return 2


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
    guidance = _evidence_guidance(need)
    if guidance:
        parts.append("<evidence-policy>\n")
        parts.extend(f"- {html.escape(item)}\n" for item in guidance)
        parts.append("</evidence-policy>\n")
    closing = "</atmem-context>\n"
    for row in rows:
        unit = row["unit"]
        block = (
            f'<memory id="{html.escape(str(row["record_id"]))}" kind="{html.escape(str(unit.get("kind") or ""))}">\n'
            f"{html.escape(_unit_text(unit, focus_terms=need.evidence_terms))}\n"
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


def _evidence_guidance(need: InformationNeed) -> tuple[str, ...]:
    """State reusable evidence semantics without supplying an answer.

    Similarity-ranked UI evidence is easy for a reader to over-interpret.  A
    visible field is not proof that it changed, an early preview is not the
    final recovery step, and a question's premise is not source evidence.  The
    directives below make those distinctions explicit while remaining fully
    query- and corpus-independent.
    """
    common = (
        "Use only observed evidence; do not substitute common product practice.",
    )
    if need.type == "state_change":
        return common + (
            "A visible field or possible value is not a transition.",
            "Report a change only when an action or before/after evidence records it; otherwise report that no change is evidenced.",
        )
    if need.type == "exception_risk":
        return common + (
            "Prefer a later observed recovery or outcome over an earlier preview or screenshot hypothesis.",
            "A visible control is not proof that invoking it was the missing action.",
        )
    if need.type == "assumption_check":
        return common + (
            "Treat the entities asserted by the question as a premise to verify, not as facts.",
            "A complete relevant result surface can disprove the premise; a partial surface can only leave it unsupported.",
        )
    return common


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


def _unit_text(unit: dict, *, focus_terms: tuple[str, ...] = ()) -> str:
    payload = unit.get("payload") or {}
    kind = unit.get("kind")
    if kind in {"atomic_fact", "environment_state"}:
        value = str(payload.get("value") or "")
        if kind == "environment_state":
            value = _reader_state_projection(
                value,
                structured_hint=str(payload.get("relation") or "")
                == "accessibility_tree",
                focus_terms=focus_terms,
            )
        return f"{payload.get('subject') or payload.get('entity')} {payload.get('relation')}: {value} ({payload.get('polarity')})"
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


def _estimated_unit_bytes(unit: dict) -> int:
    """Cheap bounded packing estimate; exact projection happens after selection."""
    payload = unit.get("payload") or {}
    raw = payload.get("value")
    if raw is None:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    # Large UI trees compact sharply. Charging a bounded estimate prevents
    # regex-projecting every nominee during combinatorial selection while the
    # exact serializer still enforces the hard byte budget.
    return min(4_096, max(128, len(str(raw).encode("utf-8"))))


def _reader_state_projection(
    value: str, *, structured_hint: bool = False,
    focus_terms: tuple[str, ...] = (),
) -> str:
    """Compact browser trees without changing their canonical source record.

    Accessibility snapshots spend most of their bytes on node identifiers,
    indentation, roles and interaction flags.  The reader primarily needs the
    ordered visible labels.  Keeping their order preserves adjacency and
    procedure evidence, while immutable source/evidence offsets remain
    available for audit and reconstruction.
    """
    structured = None
    try:
        structured = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        pass
    prefixes: list[str] = []
    if isinstance(structured, dict):
        goal = structured.get("goal")
        if goal is not None and str(goal).strip():
            prefixes.append(f"Goal: {' '.join(str(goal).split())}")
        actions = structured.get("actions")
        if isinstance(actions, list) and actions:
            prefixes.append(
                "Ordered actions: "
                + "; ".join(
                    f"{index}. {' '.join(str(action).split())}"
                    for index, action in enumerate(actions, start=1)
                    if str(action).strip()
                )
            )
        outcome = structured.get("outcome")
        if outcome is not None and str(outcome).strip():
            prefixes.append(f"Outcome: {' '.join(str(outcome).split())}")
        start_url = structured.get("start_url")
        if start_url is not None and str(start_url).strip():
            prefixes.append(f"Start URL: {' '.join(str(start_url).split())}")
        for key, label in (
            ("state_index", "State index"),
            ("step", "Step"),
            ("url", "URL"),
            ("action", "Action"),
            ("thought", "Thought"),
            ("thoughts", "Thoughts"),
        ):
            field = structured.get(key)
            if field is not None and str(field).strip():
                prefixes.append(f"{label}: {' '.join(str(field).split())}")
        tree = structured.get("accessibility_tree")
        decoded = str(tree if tree is not None else value)
    else:
        decoded = value
    decoded = (
        decoded.replace("\\\\n", "\n")
        .replace("\\\\t", "\t")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\\\"', '"')
    )
    controls: list[str] = []
    control_pattern = re.compile(
        r"\b(button|link|textbox|searchbox|combobox|listbox|checkbox|radio|"
        r"menuitem|tab|spinbutton|slider|option)\s+'([^'\n]{0,512})'([^\n]*)",
        re.I,
    )
    attribute_pattern = re.compile(
        r"\b(value|checked|selected|disabled|expanded|pressed)="
        r"(?:'([^']*)'|\"([^\"]*)\"|([^,\s]+))",
        re.I,
    )
    for role, raw_label, tail in control_pattern.findall(decoded):
        label = " ".join(raw_label.split())
        label = re.sub(r"^(?:\\\\u[0-9a-fA-F]{4}|[\ue000-\uf8ff])\s*", "", label)
        attributes: list[str] = []
        for name, single, double, bare in attribute_pattern.findall(tail):
            value = single if single != "" else double if double != "" else bare
            # An explicitly empty value is answer-bearing (for example a blank
            # default field), so distinguish it from a missing attribute.
            if name.casefold() == "value" and value == "":
                value = "<blank>"
            attributes.append(f"{name.casefold()}={value}")
        if (
            not attributes
            and label
            and role.casefold() in {"textbox", "searchbox"}
        ):
            # Accessibility snapshots omit ``value`` for an empty text input.
            # Preserve that explicit UI state instead of reducing the field to
            # a label, which makes blank defaults impossible to answer.
            attributes.append("value=<blank>")
        # Ordered labels below already preserve buttons and links.  Repeat a
        # control here only when it carries state that label-only projection
        # would lose (selected value, blank value, checked/disabled, etc.).
        if not attributes:
            continue
        rendered = f"{role.casefold()} '{label}'"
        if attributes:
            rendered += " [" + ", ".join(attributes) + "]"
        if controls and controls[-1].casefold() == rendered.casefold():
            continue
        controls.append(rendered)
    if controls:
        focused_controls = _focused_neighbourhood(
            controls, focus_terms, radius=1, fallback=24, maximum=64
        )
        prefixes.append("UI controls with state: " + " | ".join(focused_controls))
    # Anchor quotes to accessibility roles.  A generic quote matcher pairs the
    # closing quote of an empty label with the opening quote on the next role,
    # accidentally retaining the verbose syntax we are removing.
    labels: list[str] = []
    for match in re.findall(
        r"\b(?:RootWebArea|[A-Za-z][A-Za-z0-9_-]*)\s+'([^'\n]{0,512})'",
        decoded,
    ):
        label = " ".join(match.split())
        # Browser trees commonly expose an icon glyph, its accessible label,
        # and the same StaticText label as three adjacent nodes.  Remove the
        # private-use glyph prefix and collapse only adjacent duplicates.  We
        # deliberately retain non-adjacent repetition because counts and
        # repeated states can be answer-bearing.
        label = re.sub(r"^(?:\\\\u[0-9a-fA-F]{4}|[\ue000-\uf8ff])\s*", "", label)
        if not label:
            continue
        if labels and labels[-1].casefold() == label.casefold():
            continue
        labels.append(label)
    if labels:
        focused_labels = _focused_neighbourhood(
            labels, focus_terms, radius=2, fallback=32, maximum=96
        )
        prefixes.append("UI labels in source order: " + " | ".join(focused_labels))
    elif decoded.strip():
        compact_observation = " ".join(decoded.split())
        if isinstance(structured, dict) and tree is not None:
            prefixes.append("UI observation: " + compact_observation)
        elif not prefixes:
            prefixes.append(compact_observation)
    return "; ".join(prefixes)


def _focused_neighbourhood(
    values: list[str], focus_terms: tuple[str, ...], *, radius: int,
    fallback: int, maximum: int,
) -> list[str]:
    """Keep matching UI evidence and bounded adjacent source-order context."""
    normalized_terms = tuple(
        value.casefold() for value in focus_terms if len(value.strip()) > 2
    )
    indexes = {
        index
        for index, value in enumerate(values)
        if any(term in value.casefold() for term in normalized_terms)
    }
    if not indexes:
        return values[:fallback]
    expanded: set[int] = set()
    for index in indexes:
        expanded.update(range(max(0, index - radius), min(len(values), index + radius + 1)))
    return [values[index] for index in sorted(expanded)[:maximum]]


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
