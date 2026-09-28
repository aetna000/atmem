"""Deterministic evidence-slot coverage and contradiction decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from atmem.contracts import InformationNeed, SufficiencyDecision
from atmem.core.canonical import canonical_json, sha256_hex


def decide_sufficiency(
    need: InformationNeed,
    typed_rows: list[dict],
) -> SufficiencyDecision:
    covered: set[str] = set()
    evidence_ids: list[str] = []
    stale_ids: list[str] = []
    identities: dict[tuple[str, str, str], tuple[str, str]] = {}
    contradictions: list[str] = []
    entity_relations: set[tuple[str, str]] = set()

    for row in typed_rows:
        record_id = str(row["record_id"])
        unit = row["unit"]
        kind = str(unit.get("kind") or "")
        payload = unit.get("payload") or {}
        slots = covered_slots(kind, payload, unit)
        subject = str(payload.get("subject") or payload.get("entity") or "")
        relation = str(payload.get("relation") or "")
        value = canonical_json({
            "value": payload.get("value", payload.get("after")),
            "polarity": payload.get("polarity"),
        })
        if subject and relation:
            entity_relations.add((subject.casefold(), relation.casefold()))
        relevant = set(need.required_slots) & slots
        if need.type == "relational_synthesis" and subject and relation:
            relevant = {"supporting_evidence"}
        # Contradiction status describes evidence relevant to this need.
        # Conflicting background rows must not manufacture an evidence-free
        # contradiction for an unrelated question.
        is_partition = "_chunk_" in str(row.get("fact_key") or "")
        if relevant and subject and relation and not is_partition:
            key = (kind, subject.casefold(), relation.casefold())
            prior = identities.get(key)
            if prior is not None and prior[1] != value:
                contradictions.append(record_id)
            else:
                identities[key] = (record_id, value)
        if not relevant:
            continue
        covered.update(relevant)
        evidence_ids.append(record_id)
        valid_until = unit.get("valid_until")
        if valid_until and _is_past(str(valid_until)):
            stale_ids.append(record_id)

    if need.type == "relational_synthesis" and len(entity_relations) >= 2:
        covered.update({"entities", "relations", "supporting_evidence"})
    required = tuple(need.required_slots)
    missing = tuple(slot for slot in required if slot not in covered)
    covered_ordered = tuple(slot for slot in required if slot in covered)
    evidence = tuple(dict.fromkeys(
        record_id for record_id in evidence_ids if record_id not in contradictions
    ))
    contradiction_ids = tuple(dict.fromkeys(contradictions))
    if contradiction_ids:
        status = "contradictory"
    elif stale_ids and not any(record_id not in stale_ids for record_id in evidence_ids):
        status = "stale"
    elif not covered_ordered:
        status = "unsupported"
        evidence = ()
    elif missing:
        status = "partial"
    else:
        status = "sufficient"
    identity = canonical_json({
        "need": need.to_dict(),
        "evidence": evidence,
        "contradictions": contradiction_ids,
        "covered": covered_ordered,
    })
    return SufficiencyDecision(
        decision_id=f"sufficiency-{sha256_hex(identity)[:24]}",
        need_id=need.need_id,
        status=status,
        required_slots=required,
        covered_slots=covered_ordered,
        missing_slots=missing,
        evidence_ids=evidence,
        contradiction_ids=contradiction_ids,
        reason_codes=_reason_codes(status, missing),
    )


def covered_slots(kind: str, payload: dict, unit: dict) -> set[str]:
    present = lambda name: payload.get(name) not in (None, "", [], {})
    if kind == "atomic_fact":
        result = {name for name in ("subject", "relation", "value") if present(name)}
        if present("subject"):
            result.add("entity")
        if present("value"):
            result.update({"current_value", "validity"})
        return result
    if kind == "environment_state":
        result = {"validity"}
        if present("entity"):
            result.update({"entity", "subject"})
        if present("relation"):
            result.add("relation")
        if present("value"):
            result.update({"current_value", "value"})
            # Structured host observations remain environment evidence, but
            # their explicit fields can satisfy the matching information need
            # without promoting them into an executable action constraint.
            value = payload.get("value")
            try:
                structured = json.loads(value) if isinstance(value, str) else value
            except json.JSONDecodeError:
                structured = None
            if isinstance(structured, dict):
                if structured.get("goal"):
                    result.add("goal")
                if isinstance(structured.get("actions"), list) and structured["actions"]:
                    result.add("ordered_steps")
                if structured.get("outcome") not in (None, ""):
                    result.add("completion")
        return result
    if kind == "state_transition":
        result = {name for name in ("entity", "before", "action", "after") if present(name)}
        if unit.get("event_at") or unit.get("observed_at"):
            result.add("event_time")
        return result
    if kind == "procedure":
        result = set()
        if present("goal"):
            result.add("goal")
        if payload.get("steps"):
            result.add("ordered_steps")
        if payload.get("prerequisites") or any(step.get("condition") for step in payload.get("steps") or ()):
            result.add("conditions")
        if payload.get("completion_evidence"):
            result.add("completion")
        return result
    if kind == "failure_gotcha":
        result = {name for name in ("trigger", "failure") if present(name)}
        if present("required_action") or present("prohibited_action"):
            result.add("safe_action")
        return result
    if kind == "durable_rule":
        result = set()
        if present("condition"):
            result.update({"condition", "applicability"})
        if present("required_action") or present("prohibited_action"):
            result.add("required_or_prohibited_action")
        return result
    if kind == "premise_constraint":
        result = {name for name in ("proposition", "polarity") if present(name)}
        if present("applies_when") or present("excluded_when"):
            result.add("applicability")
        return result
    return set()


def _is_past(value: str) -> bool:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc) < datetime.now(timezone.utc)


def _reason_codes(status: str, missing: tuple[str, ...]) -> tuple[str, ...]:
    if status == "sufficient":
        return ("required_slots_covered",)
    if status == "unsupported":
        return ("no_answer_bearing_typed_evidence",)
    if status == "contradictory":
        return ("conflicting_current_evidence",)
    if status == "stale":
        return ("only_expired_evidence",)
    return ("missing_required_slots", *(f"missing:{slot}" for slot in missing))
