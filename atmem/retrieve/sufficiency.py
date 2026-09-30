"""Deterministic evidence-slot coverage and contradiction decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from atmem.contracts import InformationNeed, SufficiencyDecision
from atmem.core.canonical import canonical_json, sha256_hex


_EPISODIC_PROJECTION_RELATIONS = frozenset({
    "accessibility_tree",
    "state summary",
    "ui control state index",
    "ui surface index",
})


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
    obligation_matches = [False] * len(need.obligations)

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
        matched_indexes = [
            index for index, obligation in enumerate(need.obligations)
            if _matches_single_obligation(obligation, kind, payload, unit)
        ]
        relevant = set(need.required_slots) & slots
        if relevant and not _matches_obligation(need, kind, payload, unit):
            relevant = set()
        if need.type == "relational_synthesis" and subject and relation:
            relevant = (
                {"supporting_evidence"}
                if _matches_obligation(need, kind, payload, unit) else set()
            )
        if relevant and subject and relation:
            entity_relations.add((subject.casefold(), relation.casefold()))
        # Contradiction status describes evidence relevant to this need.
        # Conflicting background rows must not manufacture an evidence-free
        # contradiction for an unrelated question.
        is_partition = "_chunk_" in str(row.get("fact_key") or "")
        is_episode_projection = (
            kind == "environment_state"
            and relation.casefold() in _EPISODIC_PROJECTION_RELATIONS
        )
        if (
            relevant and subject and relation
            and not is_partition and not is_episode_projection
        ):
            key = (kind, subject.casefold(), relation.casefold())
            prior = identities.get(key)
            if prior is not None and prior[1] != value:
                contradictions.append(record_id)
            else:
                identities[key] = (record_id, value)
        if not relevant:
            continue
        for index in matched_indexes:
            obligation_matches[index] = True
        covered.update(relevant)
        evidence_ids.append(record_id)
        valid_until = unit.get("valid_until")
        if valid_until and _is_past(str(valid_until)):
            stale_ids.append(record_id)

    if need.type == "relational_synthesis" and len(entity_relations) >= 2:
        covered.update({"entities", "relations", "supporting_evidence"})
    required = tuple(need.required_slots)
    if obligation_matches and not all(obligation_matches) and required:
        # The public decision contract remains slot-partitioned. Keep at least
        # one answer-bearing slot uncovered until every explicit obligation is
        # supported instead of inventing a non-contractual pseudo-slot.
        covered.discard("supporting_evidence" if "supporting_evidence" in required else required[-1])
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


_TERM = re.compile(r"[^\W_]+", re.UNICODE)
_ALIASES = {
    "old": "age",
    "aged": "age",
    "years": "age",
    "where": "location",
    "deploying": "deploy",
    "deployment": "deploy",
}
_RELATION_TERMS = {
    "age", "location", "food", "city", "status", "model", "configuration",
    "name", "email", "channel", "deploy", "procedure",
}
_QUERY_NOISE = {
    "what", "which", "how", "where", "when", "is", "are", "do", "does",
    "should", "use", "under", "our", "policy", "compare", "favorite",
    "together", "current", "selected", "value", "my", "me", "i", "user",
    "steps",
}


def _terms(value: object) -> set[str]:
    terms = {_ALIASES.get(token, token) for token in _TERM.findall(str(value).casefold())}
    return {term for term in terms if len(term) > 1}


def _matches_obligation(
    need: InformationNeed, kind: str, payload: dict, unit: dict | None = None
) -> bool:
    """Require answer-bearing evidence to match the routed semantic target.

    Slot shape alone is not relevance: an arbitrary ``subject/relation/value``
    triple must not satisfy a question about age.  This deterministic check is
    intentionally conservative and precedes the richer ranker.
    """
    obligation_matched = bool(need.obligations) and any(
        _matches_single_obligation(obligation, kind, payload, unit)
        for obligation in need.obligations
    )
    if need.obligations and not obligation_matched:
        return False
    payload_polarity = str(payload.get("polarity") or "unknown")
    if need.polarity != "unknown" and payload_polarity != need.polarity:
        return False
    if (
        not need.obligations
        and need.temporal_target
        and need.temporal_target != "current"
    ):
        timestamp = str(
            (unit or {}).get("event_at") or (unit or {}).get("observed_at") or ""
        )
        if not timestamp or not timestamp.startswith(str(need.temporal_target)):
            return False
    if obligation_matched:
        return True
    query_terms = _terms((*need.entities, need.relation_or_action or ""))
    if not query_terms:
        return False
    if kind in {"atomic_fact", "environment_state"}:
        target = _terms((
            payload.get("subject") or payload.get("entity") or "",
            payload.get("relation") or "",
        ))
        if kind == "environment_state":
            value = payload.get("value")
            try:
                structured = json.loads(value) if isinstance(value, str) else value
            except json.JSONDecodeError:
                structured = None
            if isinstance(structured, dict):
                if need.type == "ordered_task":
                    target.update(_terms((
                        structured.get("goal") or "",
                        structured.get("actions") or (),
                        structured.get("outcome") or "",
                    )))
                else:
                    target.update(_terms((
                        structured.get("url") or "",
                        structured.get("title") or "",
                        structured.get("name") or "",
                    )))
    elif kind == "state_transition":
        target = _terms((payload.get("entity") or "", payload.get("relation") or ""))
    elif kind == "procedure":
        target = _terms(payload.get("goal") or "")
    elif kind == "durable_rule":
        target = _terms((
            payload.get("condition") or "",
            payload.get("required_action") or "",
            payload.get("prohibited_action") or "",
        ))
    elif kind == "failure_gotcha":
        target = _terms((payload.get("trigger") or "", payload.get("failure") or ""))
    elif kind == "premise_constraint":
        target = _terms(payload.get("proposition") or "")
    else:
        return False
    if need.type == "relational_synthesis":
        return bool((query_terms - _QUERY_NOISE) & target)
    if kind in {"atomic_fact", "environment_state", "state_transition"}:
        if (
            kind == "environment_state"
            and need.type == "ordered_task"
            and isinstance(locals().get("structured"), dict)
        ):
            return bool((query_terms - _QUERY_NOISE) & target)
        subject_terms = _terms(
            payload.get("subject") or payload.get("entity") or ""
        )
        relation_terms = _terms(payload.get("relation") or "")
        requested_relations = query_terms & _RELATION_TERMS
        requested_entities = query_terms - requested_relations - _QUERY_NOISE
        return (
            (not requested_relations or bool(requested_relations & relation_terms))
            and (not requested_entities or bool(requested_entities & subject_terms))
        )
    return bool((query_terms - _QUERY_NOISE) & target)


def _matches_single_obligation(
    obligation: dict[str, str], kind: str, payload: dict, unit: dict | None = None
) -> bool:
    subject_terms = _terms(payload.get("subject") or payload.get("entity") or "")
    if kind == "environment_state":
        subject_terms.update(_terms(payload.get("value") or ""))
    relation_terms = _terms(payload.get("relation") or "")
    if kind == "environment_state":
        relation_terms.update(_terms(payload.get("value") or ""))
    entity = str(obligation.get("entity") or "").casefold()
    relation = str(obligation.get("relation") or "").casefold()
    action = str(obligation.get("action") or "").casefold()
    polarity = str(obligation.get("polarity") or "unknown")
    temporal_target = str(obligation.get("temporal_target") or "")
    if entity:
        entity_terms = _terms(entity)
        if entity == "user":
            entity_terms.update({"user", "self", "speaker"})
        if not entity_terms & subject_terms:
            return False
    if relation:
        expected = _terms(relation)
        if relation == "age":
            expected.update({"old", "years", "born"})
        required = expected - {"current"}
        if not (
            (required and required <= relation_terms)
            or (not required and bool(expected & relation_terms))
            or (relation == "age" and bool(expected & relation_terms))
        ):
            return False
    if action:
        target = _terms(canonical_json(payload))
        expected_action = _terms(action)
        if not (
            expected_action & target
            or any(
                len(left) >= 4 and (left.startswith(right) or right.startswith(left))
                for left in expected_action for right in target if len(right) >= 4
            )
        ):
            return False
    if polarity != "unknown" and str(payload.get("polarity") or "unknown") != polarity:
        return False
    if temporal_target:
        observed = str(
            (unit or {}).get("event_at") or (unit or {}).get("observed_at") or ""
        )
        if not observed or not observed.startswith(temporal_target):
            return False
    return bool(entity or relation or action)


def matching_obligation_indexes(
    need: InformationNeed, kind: str, payload: dict, unit: dict | None = None
) -> set[int]:
    """Return the explicit evidence obligations discharged by one unit."""
    return {
        index
        for index, obligation in enumerate(need.obligations)
        if _matches_single_obligation(obligation, kind, payload, unit)
    }


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
