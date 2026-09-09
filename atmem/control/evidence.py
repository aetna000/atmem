"""Stable and run-specific digests for control-plane evidence.

Callers construct the stable projection explicitly.  This is deliberate:
receipt formats have different volatile fields, and recursively dropping a
generic set of names can silently weaken a future evidence format.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex


ZERO_SHA256 = "0" * 64

_TASK_REVISION_FIELDS = {
    "task_revision",
    "task_base_revision",
    "task_resulting_revision",
}
_TASK_DIGEST_FIELDS = {
    "task_context_sha256",
    "task_state_sha256",
    "task_proposal_sha256",
    "task_decision_sha256",
}
_TASK_LIST_FIELDS = {
    "task_reason_codes",
    "task_evidence_ids",
    "task_affected_item_ids",
}


def validate_task_evidence_payload(payload: Mapping[str, Any]) -> None:
    """Validate the identity and links on a task-related audit projection.

    The canonical task ledger carries richer typed contracts. This validator
    protects their content-minimizing cross-surface projection: any task field
    must be bound to one exact task, revisions cannot be invented below the
    protocol floor, and linked objects travel only by digest or bounded ID.
    """
    task_fields = {key: value for key, value in payload.items() if key.startswith("task_")}
    if not task_fields:
        return
    task_id = str(task_fields.get("task_id") or "").strip()
    if not task_id or len(task_id) > 512:
        raise ValueError("task evidence requires one bounded task_id")
    for key in _TASK_REVISION_FIELDS & task_fields.keys():
        try:
            revision = int(task_fields[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a task revision") from exc
        if revision < 1:
            raise ValueError(f"{key} must be at least 1")
    for key in _TASK_DIGEST_FIELDS & task_fields.keys():
        if not re.fullmatch(r"[0-9a-f]{64}", str(task_fields[key]).lower()):
            raise ValueError(f"{key} must bind a SHA-256 digest")
    for key in _TASK_LIST_FIELDS & task_fields.keys():
        value = task_fields[key]
        if not isinstance(value, list) or any(not str(item).strip() for item in value):
            raise ValueError(f"{key} must be an array of non-empty identifiers")


def seal_report(
    body: Mapping[str, Any], *, stable_evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a report carrying stable-state and complete-run digests."""

    if "report_sha256" in body or "evidence_sha256" in body:
        raise ValueError("report body must not contain precomputed digests")
    stable = deepcopy(dict(stable_evidence))
    evidence_sha256 = sha256_hex(canonical_json(stable))
    report = {**deepcopy(dict(body)), "evidence_sha256": evidence_sha256}
    report_sha256 = sha256_hex(canonical_json(report))
    return {**report, "report_sha256": report_sha256}


def verify_report(
    report: Mapping[str, Any], *, stable_evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Verify both digests using the format-specific stable projection."""

    body = deepcopy(dict(report))
    reported_report = str(body.pop("report_sha256", ""))
    reported_evidence = str(body.pop("evidence_sha256", ""))
    expected_evidence = sha256_hex(canonical_json(dict(stable_evidence)))
    expected_report = sha256_hex(
        canonical_json({**body, "evidence_sha256": reported_evidence})
    )
    errors: list[str] = []
    if reported_evidence != expected_evidence:
        errors.append("evidence_sha256 mismatch")
    if reported_report != expected_report:
        errors.append("report_sha256 mismatch")
    return {
        "valid": not errors,
        "evidence_sha256": reported_evidence,
        "report_sha256": reported_report,
        "errors": errors,
    }


def evidence_entry_sha256(
    *,
    previous_sha256: str,
    migration_id: str,
    kind: str,
    sequence: int,
    body_sha256: str,
) -> str:
    """Bind one stored evidence body to its chain identity and position."""

    return sha256_hex(
        canonical_json(
            {
                "prev_sha256": previous_sha256,
                "migration_id": migration_id,
                "kind": kind,
                "sequence": sequence,
                "body_sha256": body_sha256,
            }
        )
    )
