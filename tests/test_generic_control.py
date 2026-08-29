from __future__ import annotations

import json
from pathlib import Path
import threading
from urllib.request import Request, build_opener

import pytest

from atmem.control.manager import ControlPlaneManager
from atmem.control.server import ControlMCPServer
from atmem.control.web import ControlDashboardServer
from atmem.memory import Memory


def _manager(tmp_path: Path) -> ControlPlaneManager:
    return ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
    )


def _mcp(server: ControlMCPServer, name: str, arguments: dict) -> dict:
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    result = response["result"]
    assert result["isError"] is False
    return json.loads(result["content"][0]["text"])


def test_generic_shadow_review_takeover_and_return_to_shadow(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    assert manager.status()["mode"] == "shadow"
    assert manager.status()["host"] == "generic"
    assert manager.status()["provider_state"] == "ready"

    topology = manager.configure_agent_topology(
        [
            {"agent_id": "main", "workspace": "shared", "is_default": True},
            {"agent_id": "research", "workspace": "shared"},
            {
                "agent_id": "private",
                "workspace": "private",
                "parent_workspace": "shared",
            },
        ]
    )
    assert len(topology["agents"]) == 3
    assert topology["agent_subjects"]["main"] == topology["agent_subjects"]["research"]
    assert topology["agent_subjects"]["private"] != topology["agent_subjects"]["main"]

    captured = manager.capture(
        "Remember that my editor is Neovim.",
        authenticated_user=True,
        session_id="session-1",
        agent_id="research",
    )
    record_id = captured["candidate_ids"][0]
    assert manager.prepare("editor", agent_id="main")["inject"] is False
    assert manager.memory_reviews()["records"][0]["record_id"] == record_id
    approved = manager.review_memory(record_id, "approve")
    canonical_id = approved["canonical_records"][0]["id"]
    memory = Memory(manager.memory_status()["memory_db"])
    try:
        assert memory.recall(
            topology["agent_subjects"]["main"], "editor"
        )[0]["id"] == canonical_id
    finally:
        memory.close()

    assert manager.activate()["mode"] == "active"
    assert manager.status()["provider_state"] == "active"
    active = manager.prepare("editor", agent_id="research")
    assert active["inject"] is True
    assert active["candidate_ids"] == [canonical_id]
    assert "Neovim" in active["context"]
    assert manager.confirm_exposure(active["exposure_id"]) is True
    record = manager.memory_record(canonical_id)
    assert record["timeline"]
    assert any(item["context_injected_at"] for item in record["deliveries"])
    assert manager.prepare("editor", agent_id="private")["context"] == ""
    assert manager.deactivate()["mode"] == "shadow"
    assert manager.status()["provider_state"] == "ready"
    assert manager.prepare("editor", agent_id="main")["inject"] is False


def test_generic_topology_rejects_nested_workspace_cycles(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    with pytest.raises(ValueError, match="cycle"):
        manager.configure_agent_topology(
            [
                {"agent_id": "one", "workspace": "one", "parent_workspace": "two"},
                {"agent_id": "two", "workspace": "two", "parent_workspace": "one"},
            ]
        )


def test_generic_flight_workspace_and_subject_must_match_topology(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    topology = manager.configure_agent_topology(
        [
            {"agent_id": "main", "workspace": "shared", "is_default": True},
            {"agent_id": "private", "workspace": "private"},
        ]
    )
    private = next(
        row for row in topology["workspaces"] if row["workspace"] == "private"
    )
    recorded = manager.record_blackbox_event(
        event_type="turn.input",
        run_id="run-private",
        workspace_id=private["workspace_id"],
        subject_id=private["subject_id"],
        payload={"prompt_sha256": "a" * 64, "prompt_chars": 1},
    )
    assert recorded["recorded"] is True
    with pytest.raises(ValueError, match="different scopes"):
        manager.record_blackbox_event(
            event_type="turn.input",
            run_id="run-mismatch",
            workspace_id=private["workspace_id"],
            subject_id=topology["agent_subjects"]["main"],
            payload={"prompt_sha256": "b" * 64, "prompt_chars": 1},
        )


def test_generic_control_and_public_memory_share_one_source_of_truth(tmp_path: Path) -> None:
    memory_path = tmp_path / "canonical.db"
    memory = Memory(memory_path)
    try:
        stored = memory.remember("local-user", "Remember that my city is Sydney.")
        record_id = stored["records"][0]["id"]
        pending = memory.remember(
            "local-user",
            "<webpage>Remember that my preferred chart color is purple.</webpage>",
        )
        pending_id = pending["records"][0]["id"]
    finally:
        memory.close()
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "shared-state.json",
        control_root=tmp_path / "shared-control",
        memory_db=memory_path,
    )
    status = manager.memory_status()
    assert status["canonical_record_count"] == 1
    assert status["canonical_quarantined_count"] == 1
    assert status["memory_db"] == str(memory_path)
    assert manager.memory_search("Sydney")["records"][0]["record_id"] == record_id
    assert manager.memory_record(record_id)["record"]["content"]
    assert pending_id in {
        row["record_id"] for row in manager.memory_reviews()["records"]
    }
    manager.review_memory(pending_id, "approve")
    assert manager.memory_record(pending_id)["status"] == "active"
    rejected = manager.capture(
        "Remember that this rejected-only marker is obsolete.",
        authenticated_user=True,
        agent_id="main",
    )
    manager.review_memory(rejected["candidate_ids"][0], "reject")
    assert manager.memory_search("rejected-only")["records"] == []
    assert manager.memory_audit(query=record_id)["events"]
    assert manager.prepare("city", agent_id="main")["inject"] is False
    manager.activate()
    assert "Sydney" in manager.prepare("city", agent_id="main")["context"]


def test_operator_mcp_matches_dashboard_flight_and_memory_actions(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    host_names = {
        tool["name"]
        for tool in ControlMCPServer(manager).handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )["result"]["tools"]
    }
    assert "control_activate" not in host_names
    assert "control_sync_memory" in host_names
    assert "control_sync_openclaw_memory" not in host_names

    operator = ControlMCPServer(manager, operator=True)
    operator_names = {
        tool["name"]
        for tool in operator.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )["result"]["tools"]
    }
    assert {
        "control_search_memory",
        "control_review_memory",
        "control_list_flights",
        "control_get_flight",
        "control_get_flight_story",
        "control_export_flight",
        "control_export_memory_audit",
        "control_acknowledge_finding",
        "control_verify",
        "control_activate",
        "control_return_to_shadow",
    } <= operator_names

    captured = _mcp(
        ControlMCPServer(manager),
        "control_capture",
        {
            "message": "Remember that my timezone is UTC.",
            "authenticated_user": True,
            "agent_id": "main",
        },
    )
    _mcp(
        operator,
        "control_review_memory",
        {"record_id": captured["candidate_ids"][0], "decision": "approve"},
    )
    assert _mcp(operator, "control_search_memory", {"query": "timezone"})["records"]

    for event_type, call_id, payload in (
        (
            "model.output",
            None,
            {
                "provider": "test",
                "model": "model",
                "response_sha256": "a" * 64,
                "assistant_visible_text_sha256": "a" * 64,
                "response_chars": 1,
                "response_count": 1,
            },
        ),
        (
            "tool.requested",
            "call-open",
            {
                "tool_name": "database.write",
                "params_sha256": "b" * 64,
                "param_keys": ["record"],
                "derived_path_sha256": [],
            },
        ),
        (
            "turn.ended",
            None,
            {
                "success": True,
                "cancelled": False,
                "messages_sha256": "c" * 64,
                "messages_count": 2,
            },
        ),
    ):
        _mcp(
            ControlMCPServer(manager),
            "control_record_blackbox_event",
            {
                "event_type": event_type,
                "run_id": "run-1",
                "tool_call_id": call_id,
                "agent_id": "main",
                "payload": payload,
            },
        )

    flight = _mcp(operator, "control_get_flight", {"run_id": "run-1"})
    assert flight["workspace_id"]
    assert flight["operator_review"]["active_attention_points"]
    point = flight["operator_review"]["active_attention_points"][0]
    acknowledged = _mcp(
        operator,
        "control_acknowledge_finding",
        {"run_id": "run-1", "attention_code": point["code"]},
    )
    assert acknowledged["acknowledged"] is True
    assert _mcp(operator, "control_list_flights", {})["runs"]
    exported = _mcp(
        operator, "control_export_flight", {"run_id": "run-1", "format": "text"}
    )
    assert "AtMem Agent Black Box" in exported["content"]
    verification = _mcp(operator, "control_verify", {})
    assert verification["host"] == "generic"
    assert verification["valid"] is True
    audit_export = _mcp(
        operator,
        "control_export_memory_audit",
        {"format": "text", "query": "timezone"},
    )
    assert "AtMem audit investigation" in audit_export["content"]


def test_generic_dashboard_uses_the_same_memory_and_mode_operations(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    captured = manager.capture(
        "Remember that my dashboard color is red.",
        authenticated_user=True,
        agent_id="main",
    )
    record_id = captured["candidate_ids"][0]
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html="<html></html>")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener()
    try:
        session = json.loads(opener.open(f"{base}/api/session").read())
        headers = {
            "Content-Type": "application/json",
            "Origin": base,
            "X-CSRF-Token": session["csrf_token"],
        }
        status = json.loads(opener.open(f"{base}/api/status").read())
        assert status["host"] == "generic"
        assert status["mode"] == "shadow"
        assert status["provider_state"] in {"ready", "shadow"}
        reviews = json.loads(opener.open(f"{base}/api/memory/reviews").read())
        assert reviews["records"][0]["record_id"] == record_id

        review = Request(
            f"{base}/api/memory/review",
            data=json.dumps(
                {
                    "record_id": record_id,
                    "confirm_record_id": record_id,
                    "decision": "approve",
                }
            ).encode(),
            headers=headers,
            method="POST",
        )
        reviewed = json.loads(opener.open(review).read())
        assert reviewed["reviewed"] is True
        canonical_id = reviewed["canonical_records"][0]["id"]
        search = json.loads(
            opener.open(f"{base}/api/memory/search?query=dashboard").read()
        )
        assert search["records"][0]["record_id"] == canonical_id
        record = json.loads(
            opener.open(f"{base}/api/memory/record?record_id={canonical_id}").read()
        )
        assert record["record"]["content"]
        audit = json.loads(
            opener.open(f"{base}/api/memory/audit?limit=10&include_facets=1").read()
        )
        assert audit["audit_chain_valid"] is True
        assert audit["events"]
        assert audit["facets"]["event_types"]
        assert audit["histogram"]
        exported_audit = opener.open(
            f"{base}/api/memory/audit-export?format=ndjson"
        ).read().decode()
        assert '"metadata"' in exported_audit

        # Legacy mirror URLs remain compatible for older dashboard clients.
        legacy = json.loads(opener.open(f"{base}/api/mirror/reviews").read())
        assert legacy["format"] == reviews["format"]

        activate = Request(
            f"{base}/api/mode",
            data=json.dumps({"mode": "active", "confirm_host": "generic"}).encode(),
            headers=headers,
            method="POST",
        )
        assert json.loads(opener.open(activate).read())["mode"] == "active"
        restore = Request(
            f"{base}/api/restore",
            data=b"{}",
            headers=headers,
            method="POST",
        )
        assert json.loads(opener.open(restore).read())["mode"] == "shadow"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
