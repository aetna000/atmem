from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.control.blackbox import (
    EVENT_FORMAT,
    format_flight_report,
    normalize_event,
    verify_flight,
)
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


def test_blackbox_accepts_task_transition_metadata_but_never_raw_task_content() -> None:
    event = normalize_event(
        migration_id="migration-1",
        host="pydantic-ai",
        event_type="task.transition.decision",
        run_id="run-task-1",
        session_id="session-task-1",
        tool_call_id=None,
        payload={
            "task_id": "task-1",
            "task_outcome": "accepted",
            "task_base_revision": 2,
            "task_resulting_revision": 3,
            "task_reason_codes": ["transition_accepted"],
            "task_decision_sha256": "a" * 64,
            "task_evidence_ids": ["evidence-1"],
            "task_affected_item_ids": ["item-1"],
        },
    )
    assert event["payload"]["task_id"] == "task-1"
    assert event["payload"]["task_resulting_revision"] == 3
    assert event["content_storage"] == "digests-and-bounded-metadata-only"

    with pytest.raises(ValueError, match="unsupported blackbox payload field"):
        normalize_event(
            migration_id="migration-1",
            host="pydantic-ai",
            event_type="task.transition.decision",
            run_id="run-task-1",
            session_id=None,
            tool_call_id=None,
            payload={"task_raw_content": "secret task instructions"},
        )

    with pytest.raises(ValueError, match="task_base_revision must be at least 1"):
        normalize_event(
            migration_id="migration-1",
            host="pydantic-ai",
            event_type="task.transition.decision",
            run_id="run-task-1",
            session_id=None,
            tool_call_id=None,
            payload={"task_id": "task-1", "task_base_revision": 0},
        )


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
    tool_point = next(
        point
        for point in report["attention_points"]
        if point["code"] == "tool_lifecycle_mismatch"
    )
    assert "filesystem.write (call tool-gap) was requested at event" in tool_point[
        "detail"
    ]
    assert "no completion was observed" in tool_point["detail"]


def test_open_flight_reports_one_recording_gap_not_tool_failure(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    manager.record_blackbox_event(
        event_type="turn.input",
        run_id="run-open",
        session_id="session-open",
        payload={"prompt_sha256": "0" * 64, "prompt_chars": 12},
    )
    manager.record_blackbox_event(
        event_type="context.disposition",
        run_id="run-open",
        session_id="session-open",
        payload={
            "disposition": "no_relevant_memory",
            "context_block_sha256": "1" * 64,
            "context_envelope_sha256": "2" * 64,
            "context_chars": 0,
            "candidate_ids": [],
        },
    )
    manager.record_blackbox_event(
        event_type="model.input",
        run_id="run-open",
        session_id="session-open",
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "prompt_sha256": "3" * 64,
            "prompt_chars": 12,
            "system_sha256": "4" * 64,
            "system_chars": 10,
            "history_sha256": "5" * 64,
            "history_count": 0,
            "images_count": 0,
            "tools_count": 1,
        },
    )
    for call_id in ("call-a", "call-b", "call-c"):
        manager.record_blackbox_event(
            event_type="tool.requested",
            run_id="run-open",
            session_id="session-open",
            tool_call_id=call_id,
            payload={
                "tool_name": "exec",
                "params_sha256": "6" * 64,
                "param_keys": ["command"],
            },
        )

    report = manager.verify_blackbox_flight("run-open")

    assert report["coverage_matrix"]["components"]["tools"] == "missing"
    assert report["coverage_matrix"]["overall_status"] == "incomplete"
    assert [point["code"] for point in report["attention_points"]] == [
        "recording_stopped"
    ]
    assert "3 commands were requested" in report["attention_points"][0]["detail"]
    assert "No tool failure" in report["attention_points"][0]["detail"]


def test_flight_story_uses_local_openclaw_failure_when_hooks_stop(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    manager.record_blackbox_event(
        event_type="turn.input",
        run_id="run-local",
        session_id="session-local",
        payload={"prompt_sha256": "0" * 64, "prompt_chars": 36},
    )
    trajectory_root = tmp_path / "agents"
    sessions = trajectory_root / "main" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "session-local.trajectory.jsonl").write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {
                    "runId": "run-local",
                    "type": "session.started",
                    "ts": "2026-08-16T09:38:01Z",
                    "provider": "openai",
                    "modelId": "gpt-test",
                    "data": {},
                },
                {
                    "runId": "run-local",
                    "type": "session.ended",
                    "ts": "2026-08-16T09:40:01Z",
                    "data": {"status": "error", "promptError": "tool call aborted"},
                },
            )
        ),
        encoding="utf-8",
    )
    (sessions / "session-local.jsonl").write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {
                    "message": {
                        "role": "user",
                        "content": "create another agent called research",
                        "idempotencyKey": "run-local:user",
                    }
                },
                {
                    "message": {
                        "role": "toolResult",
                        "toolName": "bash",
                        "isError": True,
                        "content": [{"text": '{"status": "declined"}'}],
                    }
                },
            )
        ),
        encoding="utf-8",
    )

    story = manager.blackbox_flight_story(
        "run-local", trajectory_root=trajectory_root
    )

    assert story["request_text"] == "create another agent called research"
    assert story["provider"] == "openai"
    assert story["model"] == "gpt-test"
    assert story["duration_ms"] == 120000
    assert story["blocked_by"] == (
        "OpenClaw declined the requested commands; no change was made."
    )


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


def test_blackbox_coalesces_openclaw_wrapper_and_canonical_tool_hooks(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    run_id = "run-wrapper-pair"
    manager.record_blackbox_event(
        event_type="turn.input",
        run_id=run_id,
        payload={"prompt_sha256": "0" * 64, "prompt_chars": 10},
    )
    manager.record_blackbox_event(
        event_type="context.disposition",
        run_id=run_id,
        context_receipt_id="receipt-1",
        payload={
            "disposition": "not_applicable",
            "context_envelope_sha256": "1" * 64,
            "context_chars": 0,
            "candidate_ids": [],
        },
    )
    manager.record_blackbox_event(
        event_type="model.input",
        run_id=run_id,
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "prompt_sha256": "2" * 64,
            "prompt_chars": 10,
            "system_sha256": "3" * 64,
            "system_chars": 10,
            "history_sha256": "4" * 64,
            "history_count": 0,
            "images_count": 0,
            "tools_count": 1,
        },
    )
    for tool_name in ("openclawmemory_remember", "memory_remember"):
        manager.record_blackbox_event(
            event_type="tool.requested",
            run_id=run_id,
            tool_call_id="call-wrapper",
            payload={
                "tool_name": tool_name,
                "tool_canonical_name": "memory_remember",
                "params_sha256": "5" * 64,
                "param_keys": ["fact"],
                "derived_path_sha256": [],
            },
        )
    for tool_name, result_sha256 in (
        ("memory_remember", "6" * 64),
        ("openclawmemory_remember", "7" * 64),
    ):
        manager.record_blackbox_event(
            event_type="tool.completed",
            run_id=run_id,
            tool_call_id="call-wrapper",
            payload={
                "tool_name": tool_name,
                "tool_canonical_name": "memory_remember",
                "result_sha256": result_sha256,
                "outcome": "completed",
                "duration_ms": 1,
            },
        )
    manager.record_blackbox_event(
        event_type="model.output",
        run_id=run_id,
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "response_sha256": "8" * 64,
            "assistant_visible_text_sha256": "8" * 64,
            "response_chars": 2,
            "response_count": 1,
        },
    )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id=run_id,
        payload={
            "success": True,
            "cancelled": False,
            "messages_sha256": "9" * 64,
            "messages_count": 4,
        },
    )

    report = manager.verify_blackbox_flight(run_id)
    assert report["verdict"] == "completed_successfully"
    assert report["coverage_matrix"]["components"]["tools"] == "covered"
    assert report["tools"]["requested"] == 1
    assert report["tools"]["completed"] == 1
    assert report["tools"]["request_observations"] == 2
    assert report["tools"]["completion_observations"] == 2
    assert report["tools"]["conflicting_completions"] == []
    assert report["tools"]["coalesced_wrapper_calls"] == [
        {
            "tool_call_id": "call-wrapper",
            "tool_name": "memory_remember",
            "observed_names": ["memory_remember", "openclawmemory_remember"],
            "request_observations": 2,
            "completion_observations": 2,
            "outcome": "completed",
        }
    ]
    assert report["attention_points"] == []


def test_blackbox_acknowledgement_clears_active_queue_but_retains_history(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    manager.record_blackbox_event(
        event_type="model.output",
        run_id="run-review",
        payload={
            "provider": "openai",
            "model": "gpt-test",
            "response_sha256": "a" * 64,
            "assistant_visible_text_sha256": "a" * 64,
            "response_chars": 1,
            "response_count": 1,
        },
    )
    manager.record_blackbox_event(
        event_type="tool.requested",
        run_id="run-review",
        tool_call_id="call-unclosed",
        payload={
            "tool_name": "email.send",
            "params_sha256": "b" * 64,
            "param_keys": ["recipient"],
            "derived_path_sha256": [],
        },
    )
    manager.record_blackbox_event(
        event_type="turn.ended",
        run_id="run-review",
        payload={
            "success": True,
            "cancelled": False,
            "messages_sha256": "c" * 64,
            "messages_count": 2,
        },
    )

    before = manager.verify_blackbox_flight("run-review")
    active = before["operator_review"]["active_attention_points"]
    assert active
    for point in active:
        manager.acknowledge_blackbox_attention(
            "run-review", point["code"], actor="auditor-1"
        )

    after = manager.verify_blackbox_flight("run-review")
    assert after["attention_points"]
    assert after["operator_review"]["active_attention_points"] == []
    acknowledged = after["operator_review"]["acknowledged_attention_points"]
    assert {point["code"] for point in acknowledged} == {
        point["code"] for point in active
    }
    assert all(
        point["acknowledgement"]["actor"] == "auditor-1"
        for point in acknowledged
    )
    index = manager.blackbox_runs()
    assert index["runs"][0]["attention_points"] == []
    assert len(index["runs"][0]["acknowledged_attention_points"]) == len(active)
    assert index["attention"]["affected_runs"] == 0


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


def test_blackbox_run_history_supports_load_more_pagination(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    for run_id in ("run-1", "run-2", "run-3"):
        manager.record_blackbox_event(
            event_type="turn.input",
            run_id=run_id,
            payload={"prompt_sha256": "a" * 64, "prompt_chars": 1},
        )

    first = manager.blackbox_runs(limit=2)
    second = manager.blackbox_runs(limit=2, offset=2)

    assert [row["run_id"] for row in first["runs"]] == ["run-3", "run-2"]
    assert first["offset"] == 0
    assert first["has_more"] is True
    assert [row["run_id"] for row in second["runs"]] == ["run-1"]
    assert second["offset"] == 2
    assert second["has_more"] is False


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
