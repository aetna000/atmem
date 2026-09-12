from __future__ import annotations

from atmem.incidents.detect import detect_findings


def test_findings_are_deterministic_evidence_linked_and_keep_outcome_unknown() -> None:
    report = {
        "run_id": "run-1",
        "report_sha256": "a" * 64,
        "timeline": [
            {
                "sequence": 2,
                "event_id": "event-2",
                "entry_sha256": "b" * 64,
                "recorded_at": "2026-09-12T00:00:01.000000Z",
                "event_type": "tool.completed",
                "tool_call_id": "call-1",
                "payload": {"outcome": "error"},
            }
        ],
        "attention_points": [
            {
                "code": "tool_errors",
                "title": "A tool reported an error",
                "detail": "The observed completion reported an error.",
                "action": "Inspect the exact event and host logs.",
            }
        ],
    }
    first = detect_findings(report)
    second = detect_findings(report)
    assert first == second
    assert first[0]["classification"] == "observed_failure"
    assert first[0]["event_reference"]["event_id"] == "event-2"
    assert first[0]["external_outcome"] == "unknown"


def test_recovered_error_is_superseded_history_not_remediation() -> None:
    report = {
        "run_id": "run-2",
        "report_sha256": "c" * 64,
        "timeline": [
            {"sequence": 1, "event_id": "error", "event_type": "tool.completed", "tool_call_id": "call-1", "payload": {"outcome": "error"}},
            {"sequence": 2, "event_id": "success", "event_type": "tool.completed", "tool_call_id": "call-1", "payload": {"outcome": "success"}},
        ],
        "attention_points": [],
    }
    finding = detect_findings(report)[0]
    assert finding["classification"] == "recovered_error"
    assert finding["state"] == "superseded"
    assert finding["event_reference"]["event_id"] == "success"
    assert "retry" not in finding
