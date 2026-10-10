"""Source-backed obligation sufficiency; similarity never decides completion."""

from __future__ import annotations

import re

from atmem.core.canonical import canonical_json, sha256_hex

from .contracts import QueryPlan, SufficiencyDecisionV2
from .retrieval import RetrievalResult


def decide_sufficiency(
    plan: QueryPlan, result: RetrievalResult, *,
    lifecycle_stale: bool = False, policy_withheld: bool = False,
) -> SufficiencyDecisionV2:
    required = tuple(item.obligation_id for item in plan.obligations if item.required)
    covered_set = {
        obligation_id
        for item in result.candidates
        for obligation_id in item.matched_obligation_ids
        if obligation_id in required
    } - set(result.withheld_obligation_ids)
    covered = tuple(item for item in required if item in covered_set)
    missing = tuple(item for item in required if item not in covered_set)
    grounding_candidates = tuple(
        item for item in result.candidates
        if set(item.matched_obligation_ids) & set(required)
    )
    evidence_ids = tuple(dict.fromkeys(
        item.unit_id for item in (grounding_candidates or result.candidates)
    ))
    status = "partial" if evidence_ids else "not_found_within_budget"
    conflicting: tuple[str, ...] = ()
    reason_codes: list[str] = []
    if policy_withheld:
        status = "withheld_by_policy"
        covered = ()
        missing = required
        evidence_ids = ()
        reason_codes.append("authority_withheld")
    elif lifecycle_stale:
        status = "stale"
        reason_codes.append("lifecycle_generation_stale")
    elif not missing:
        premise = any(item.kind == "premise_check" for item in plan.obligations)
        negative_evidence = any(
            re.search(r"\b(no|not|never|only|without|cannot|can't)\b", item.text.casefold())
            for item in grounding_candidates
        )
        if premise and negative_evidence:
            status = "contradicted"
            reason_codes.append("positive_contradicting_evidence")
        else:
            # Two different exact numeric or channel values supporting the same
            # need are a conflict, unless one explicitly marks itself a correction.
            # A second side can be returned as bounded supplementary evidence
            # without carrying the primary obligation tag.  For an explicitly
            # approval-sensitive question, include only retrieved statements
            # that themselves use an approval term; otherwise a nearby date or
            # unrelated number could manufacture a conflict.
            conflict_sensitive = any(
                re.search(
                    r"^(?:what|which)\s+(?:is|was|are|were)\s+the\s+approved\b",
                    (item.relation_or_action or "").casefold(),
                )
                for item in plan.obligations
            )
            conflict_candidates = grounding_candidates
            if conflict_sensitive:
                conflict_candidates = tuple(dict.fromkeys(
                    (*grounding_candidates, *(
                        item for item in result.candidates
                        if re.search(r"\bapprov(?:e|es|ed|ing)\b", item.text, re.IGNORECASE)
                    ))
                ))
            texts = [item.text for item in conflict_candidates]
            values = {
                match.group(0).casefold()
                for text in texts
                for match in re.finditer(r"(?:#\w[\w-]*|\b\d+(?:\.\d+)?\b)", text)
            }
            corrected = any("correction:" in text.casefold() or "replacing" in text.casefold() for text in texts)
            if conflict_sensitive and len(values) > 1 and len(texts) > 1 and not corrected:
                status = "conflicted"
                conflicting = tuple(dict.fromkeys(
                    item.unit_id for item in conflict_candidates
                ))
                evidence_ids = conflicting
                reason_codes.append("distinct_source_values")
            else:
                status = "sufficient"
    elif set(missing) & set(result.withheld_obligation_ids):
        status = "partial"
        reason_codes.append("source_episode_incomplete")
    elif evidence_ids:
        reason_codes.append(
            "missing_required_obligations"
        )
    else:
        reason_codes.append("search_budget_exhausted" if result.exhausted else "no_indexed_evidence")
    decision_id = "suff3_" + sha256_hex(canonical_json({
        "plan": plan.plan_id, "evidence": evidence_ids, "status": status,
    }))[:32]
    return SufficiencyDecisionV2(
        decision_id=decision_id,
        status=status,
        required_obligation_ids=required,
        covered_obligation_ids=covered,
        missing_obligation_ids=missing,
        evidence_unit_ids=evidence_ids,
        conflicting_unit_ids=conflicting,
        reason_codes=tuple(reason_codes),
    )
