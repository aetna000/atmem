"""Translate verified-flight facts into bounded, evidence-linked findings."""

from __future__ import annotations

from typing import Any, Mapping

from atmem.core.canonical import canonical_json, sha256_hex


def detect_findings(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    timeline = list(report.get("timeline") or [])
    by_call: dict[str, list[dict[str, Any]]] = {}
    for event in timeline:
        call_id = str(event.get("tool_call_id") or "")
        if call_id:
            by_call.setdefault(call_id, []).append(event)
    recovered_calls: set[str] = set()
    for call_id, events in by_call.items():
        outcomes = [str((event.get("payload") or {}).get("outcome") or "") for event in events]
        if any(outcome in {"error", "failed"} for outcome in outcomes) and any(
            outcome in {"success", "succeeded", "completed"} for outcome in outcomes
        ):
            recovered_calls.add(call_id)

    findings: list[dict[str, Any]] = []
    for point in report.get("attention_points") or []:
        code = str(point.get("code") or "unknown")
        classification = {
            "tool_errors": "observed_failure",
            "flight_failed": "observed_failure",
            "tool_lifecycle_mismatch": "missing_evidence",
            "recording_stopped": "missing_evidence",
            "flight_incomplete": "missing_evidence",
        }.get(code, "evidence_gap")
        evidence = _event_for_point(code, timeline)
        finding_id = f"finding:{report.get('run_id')}:{code}"
        findings.append(
            {
                "format": "atmem-incident-finding-v1",
                "finding_id": finding_id,
                "execution_id": report.get("run_id"),
                "classification": classification,
                "state": "open",
                "assurance": "observed" if evidence else "derived_from_verified_flight",
                "title": point.get("title"),
                "statement": point.get("detail"),
                "next_action": point.get("action"),
                "event_reference": _reference(evidence),
                "external_outcome": "unknown",
                "revision_sha256": sha256_hex(
                    canonical_json({"finding_id": finding_id, "report": report.get("report_sha256")})
                ),
            }
        )
    for call_id in sorted(recovered_calls):
        event = by_call[call_id][-1]
        finding_id = f"finding:{report.get('run_id')}:recovered:{call_id}"
        findings.append(
            {
                "format": "atmem-incident-finding-v1",
                "finding_id": finding_id,
                "execution_id": report.get("run_id"),
                "classification": "recovered_error",
                "state": "superseded",
                "assurance": "observed",
                "title": "A reported tool error was followed by success",
                "statement": "The same authenticated tool-call identity later reported a successful completion; this is history, not an unresolved failure.",
                "next_action": "Inspect both observations if the external effect still matters.",
                "event_reference": _reference(event),
                "external_outcome": "unknown",
                "revision_sha256": sha256_hex(
                    canonical_json({"finding_id": finding_id, "report": report.get("report_sha256")})
                ),
            }
        )
    return findings


def _event_for_point(code: str, timeline: list[dict[str, Any]]) -> dict[str, Any] | None:
    if code == "tool_errors":
        return next(
            (event for event in timeline if str((event.get("payload") or {}).get("outcome") or "") in {"error", "failed"}),
            None,
        )
    if code in {"tool_lifecycle_mismatch", "recording_stopped"}:
        return next((event for event in reversed(timeline) if event.get("event_type") == "tool.requested"), timeline[-1] if timeline else None)
    return timeline[-1] if timeline else None


def _reference(event: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "sequence": event.get("sequence"),
        "event_id": event.get("event_id"),
        "entry_sha256": event.get("entry_sha256"),
        "recorded_at": event.get("recorded_at"),
        "turn_id": event.get("turn_id"),
        "tool_call_id": event.get("tool_call_id"),
    }
