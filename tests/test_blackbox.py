from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.control.blackbox import EVENT_FORMAT, format_flight_report, verify_flight
from atmem.control.manager import ControlPlaneManager
from atmem.control.store import ControlStore


def _manager(tmp_path: Path) -> ControlPlaneManager:
    return ControlPlaneManager.start(
        host="openclaw",
        state_path=tmp_path / "control.json",
        control_root=tmp_path / "migrations",
        subject_id="user-1",
    )


def test_blackbox_records_content_minimizing_verified_flight(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    prompt = "send the private report"
    response = "Done. I sent the report."
    manager.record_blackbox_event(
        event_type="turn.input",
        run_id="run-1",
        session_id="session-1",
        turn_id="turn-1",
        payload={"prompt_sha256": "0" * 64, "prompt_chars": len(prompt)},
    )
    manager.record_blackbox_event(
        event_type="context.disposition",
        run_id="run-1",
        session_id="session-1",
        turn_id="turn-1",
        retrieval_id="retrieval-1",
        context_event_id="context-1",
        context_receipt_id="receipt-1",
        payload={
            "disposition": "injected",
            "context_block_sha256": "8" * 64,
            "context_envelope_sha256": "9" * 64,
            "context_chars": 42,
            "candidate_ids": ["record-1"],
            "digest_profile": "atmem-context-envelope-canonical-json-v1",
        },
    )
    manager.record_blackbox_event(
        event_type="model.input",
        run_id="run-1",
        session_id="session-1",
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "prompt_sha256": "1" * 64,
            "prompt_chars": len(prompt),
            "system_sha256": "2" * 64,
            "system_chars": 100,
            "history_sha256": "3" * 64,
            "history_count": 2,
            "images_count": 0,
            "tools_count": 1,
        },
    )
    manager.record_blackbox_event(
        event_type="tool.requested",
        run_id="run-1",
        session_id="session-1",
        tool_call_id="tool-1",
        payload={
            "tool_name": "email.send",
            "params_sha256": "4" * 64,
            "param_keys": ["recipient", "subject"],
            "derived_path_sha256": [],
        },
    )
    manager.record_blackbox_event(
        event_type="tool.completed",
        run_id="run-1",
        session_id="session-1",
        tool_call_id="tool-1",
        payload={
            "tool_name": "email.send",
            "result_sha256": "5" * 64,
            "outcome": "completed",
            "duration_ms": 42,
        },
    )
    manager.record_blackbox_event(
        event_type="model.output",
        run_id="run-1",
        session_id="session-1",
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "response_sha256": "6" * 64,
            "assistant_visible_text_sha256": "6" * 64,
            "model_output_bundle_sha256": "8" * 64,
            "response_digest_profile": "atmem-assistant-visible-text-utf8-v1",
            "response_chars": len(response),
            "response_count": 1,
            "usage": {"input": 100, "output": 20, "total": 120},
        },
    )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-1",
        session_id="session-1",
        payload={
            "success": True,
            "cancelled": False,
            "messages_sha256": "7" * 64,
            "messages_count": 4,
        },
    )

    report = manager.verify_blackbox_flight("run-1")
    assert report["timeline_chain_valid"] is True
    assert report["structurally_complete"] is True
    assert report["verdict"] == "completed_successfully"
    assert report["coverage_matrix"]["overall_status"] == "covered"
    assert report["context"]["disposition"] == "injected"
    assert report["correlation"]["retrieval_ids"] == ["retrieval-1"]
    assert report["attention_points"] == []
    assert report["coverage"]["response_digest_bound"] is True
    assert report["raw_content_stored"] is False
    serialized = json.dumps(report)
    assert prompt not in serialized
    assert response not in serialized
    assert "private report" not in serialized
    assert "does not prove that an external real-world outcome occurred" in report[
        "claim_boundary"
    ]
    assert "email.send" in format_flight_report(report)


def test_blackbox_reports_missing_completion_without_claiming_success(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    manager.record_blackbox_event(
        event_type="model.output",
        run_id="run-gap",
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "response_sha256": "e" * 64,
            "assistant_visible_text_sha256": "e" * 64,
            "response_chars": 1,
            "response_count": 1,
        },
    )
    manager.record_blackbox_event(
        event_type="tool.requested",
        run_id="run-gap",
        tool_call_id="tool-gap",
        payload={
            "tool_name": "filesystem.write",
            "params_sha256": "a" * 64,
            "param_keys": ["path"],
            "derived_path_sha256": ["d" * 64],
        },
    )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-gap",
        payload={
            "success": True,
            "cancelled": False,
            "messages_sha256": "b" * 64,
            "messages_count": 1,
        },
    )
    report = manager.verify_blackbox_flight("run-gap")
    assert report["verdict"] == "incomplete_evidence"
    assert report["structurally_complete"] is False
    assert report["tools"]["missing_completions"] == ["tool-gap"]
    assert {point["code"] for point in report["attention_points"]} == {
        "flight_incomplete",
        "tool_lifecycle_mismatch",
        "context_unknown",
    }


def test_blackbox_rejects_raw_or_unknown_payload_fields(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    with pytest.raises(ValueError, match="unsupported blackbox payload"):
        manager.record_blackbox_event(
            event_type="model.output",
            run_id="run-raw",
            payload={"response_text": "secret"},
        )


def test_blackbox_classifies_failed_and_cancelled_lifecycle(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    for run_id in ("run-failed", "run-cancelled"):
        manager.record_blackbox_event(
            event_type="context.disposition",
            run_id=run_id,
            payload={
                "disposition": "not_applicable",
                "context_block_sha256": "f" * 64,
                "context_envelope_sha256": "f" * 64,
                "context_chars": 0,
                "candidate_ids": [],
            },
        )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-failed",
        payload={
            "success": False,
            "cancelled": False,
            "failure_kind": "provider_error",
            "reason": "upstream unavailable",
            "messages_sha256": "d" * 64,
            "messages_count": 0,
        },
    )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-cancelled",
        payload={
            "success": False,
            "cancelled": True,
            "failure_kind": "cancelled",
            "messages_sha256": "e" * 64,
            "messages_count": 0,
        },
    )

    failed = manager.verify_blackbox_flight("run-failed")
    cancelled = manager.verify_blackbox_flight("run-cancelled")
    assert failed["verdict"] == "failed"
    assert failed["lifecycle"]["failure_kind"] == "provider_error"
    assert failed["attention_points"][0]["code"] == "flight_failed"
    assert cancelled["verdict"] == "cancelled"
    assert cancelled["lifecycle"]["cancelled"] is True


def test_blackbox_reports_duplicate_and_conflicting_tool_observations(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    manager.record_blackbox_event(
        event_type="model.output",
        run_id="run-duplicates",
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "response_sha256": "4" * 64,
            "assistant_visible_text_sha256": "4" * 64,
            "response_chars": 1,
            "response_count": 1,
        },
    )
    for tool_name, params_sha256 in (
        ("openclawweb_fetch", "1" * 64),
        ("web_fetch", "1" * 64),
        ("web_fetch", "2" * 64),
    ):
        manager.record_blackbox_event(
            event_type="tool.requested",
            run_id="run-duplicates",
            tool_call_id="call-1",
            payload={
                "tool_name": tool_name,
                "tool_canonical_name": "web_fetch",
                "params_sha256": params_sha256,
                "param_keys": ["url"],
            },
        )
    manager.record_blackbox_event(
        event_type="tool.completed",
        run_id="run-duplicates",
        tool_call_id="call-1",
        payload={
            "tool_name": "web_fetch",
            "tool_canonical_name": "web_fetch",
            "result_sha256": "3" * 64,
            "outcome": "completed",
        },
    )

    report = manager.verify_blackbox_flight("run-duplicates")
    assert report["tools"]["duplicate_requests"] == ["call-1"]
    assert report["tools"]["conflicting_requests"] == ["call-1"]
    assert report["coverage_matrix"]["components"]["tools"] == "failed"
    assert any(
        point["code"] == "tool_lifecycle_mismatch"
        for point in report["attention_points"]
    )


def test_blackbox_attention_flags_model_change_from_stable_recent_baseline(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    for run_id, model in (
        ("baseline-1", "gpt-stable"),
        ("baseline-2", "gpt-stable"),
        ("changed", "gpt-unexpected"),
    ):
        manager.record_blackbox_event(
            event_type="model.output",
            run_id=run_id,
            payload={
                "provider": "openai",
                "model": model,
                "response_sha256": "f" * 64,
                "assistant_visible_text_sha256": "f" * 64,
                "response_chars": 1,
                "response_count": 1,
            },
        )

    report = manager.verify_blackbox_flight("changed")
    assert report["model"]["changed_from_recent_baseline"] is True
    assert any(
        point["code"] == "model_provider_changed"
        for point in report["attention_points"]
    )


def test_blackbox_collapses_legacy_coverage_gaps_into_upgrade_action() -> None:
    report = verify_flight(
        run_id="legacy-run",
        entries=[
            {
                "sequence": 1,
                "entry_sha256": "a" * 64,
                "body": {
                    "format": "atmem-agent-blackbox-event-v1",
                    "event_type": "turn.ended",
                    "run_id": "legacy-run",
                    "recorded_at": "2026-08-15T00:00:00Z",
                    "payload": {
                        "success": True,
                        "cancelled": False,
                        "messages_sha256": "b" * 64,
                        "messages_count": 1,
                    },
                },
            }
        ],
        chain={"valid": True},
    )
    assert report["compatibility"]["legacy_flight"] is True
    assert [point["code"] for point in report["attention_points"]] == [
        "legacy_evidence_contract"
    ]


def test_blackbox_index_counts_root_causes_not_repeated_symptoms(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    for run_id in ("incomplete-1", "incomplete-2"):
        manager.record_blackbox_event(
            event_type="model.output",
            run_id=run_id,
            payload={
                "provider": "openai",
                "model": "gpt-test",
                "response_sha256": "d" * 64,
                "assistant_visible_text_sha256": "d" * 64,
                "response_chars": 1,
                "response_count": 1,
            },
        )
        manager.record_blackbox_event(
            event_type="turn.ended",
            run_id=run_id,
            payload={
                "success": True,
                "cancelled": False,
                "messages_sha256": "c" * 64,
                "messages_count": 1,
            },
        )
    index = manager.blackbox_runs()
    assert index["attention"]["total"] == 2
    assert index["attention"]["occurrences"] == 4
    assert index["attention"]["affected_runs"] == 2


def test_blackbox_global_chain_detects_tampering(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-tamper",
        payload={
            "success": True,
            "cancelled": False,
            "messages_sha256": "c" * 64,
            "messages_count": 1,
        },
    )
    state = manager.state()
    store = ControlStore(Path(state.control_dir) / "evidence.db")
    try:
        entry = store.list_evidence(state.migration_id, kind="agent_blackbox")[0]
        body = dict(entry["body"])
        assert body["format"] == EVENT_FORMAT
        body["event_type"] = "turn.rewritten"
        store._conn.execute(
            "UPDATE evidence SET body_json = ? WHERE id = ?",
            (json.dumps(body, separators=(",", ":"), sort_keys=True), entry["id"]),
        )
        store._conn.commit()
    finally:
        store.close()
    report = manager.verify_blackbox_flight("run-tamper")
    assert report["timeline_chain_valid"] is False
    assert report["verdict"] == "tampered_or_invalid_chain"
