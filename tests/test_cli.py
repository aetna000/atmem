from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "atmem.cli", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

def test_cli_version_reports_installed_distribution_version() -> None:
    from importlib.metadata import version

    result = _run("--version")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"atmem {version('atmem')}"


def test_delegated_cli_is_explicit_scoped_and_secret_safe(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "delegated.json"
    monkeypatch.setenv("ATMEM_DELEGATED_CONFIG", str(config))
    trust = json.loads(
        (ROOT / "docs/contracts/delegated-context-provider-v1/trust.json").read_text()
    )
    key_file = tmp_path / "storizon.pub"
    key_file.write_text(trust["public_key_base64"], encoding="utf-8")

    initial = _run("delegated", "status", "--json")
    assert initial.returncode == 0
    assert json.loads(initial.stdout)["enabled"] is False
    registered = _run(
        "delegated", "register",
        "--provider-version", trust["provider_version"],
        "--instance-id", trust["provider_instance_id"],
        "--key-id", trust["key_id"],
        "--public-key-file", str(key_file),
        "--endpoint", "http://127.0.0.1:8788/v1/delegated-context",
        "--workspace", trust["workspace_ids"][0],
        "--agent", trust["agent_ids"][0],
        "--user", trust["user_ids"][0],
        "--json",
    )
    assert registered.returncode == 0, registered.stderr
    registration_id = json.loads(registered.stdout)["registration_id"]
    assert trust["public_key_base64"] not in registered.stdout
    enabled = _run("delegated", "enable", registration_id, "--json")
    assert json.loads(enabled.stdout)["enabled"] is True
    assert _run("delegated", "remove", registration_id, "--yes").returncode == 2
    assert _run("delegated", "disable", registration_id).returncode == 0
    assert _run("delegated", "remove", registration_id, "--yes").returncode == 0


def test_cli_remember_recall_forget_roundtrip(tmp_path: Path) -> None:
    db = str(tmp_path / "mem.db")

    stored = _run("remember", db, "user-1", "My favorite color is teal.", "--session", "s1")
    assert stored.returncode == 0, stored.stderr
    assert json.loads(stored.stdout)["records"]

    recalled = _run("recall", db, "user-1", "What is my favorite color?")
    assert recalled.returncode == 0
    assert "teal" in json.loads(recalled.stdout)[0]["content"]

    forgotten = _run("forget", db, "user-1", "--utterance", "Forget my favorite color.")
    assert forgotten.returncode == 0
    payload = json.loads(forgotten.stdout)
    assert payload["deleted"] is True
    assert payload["receipt"]["format"] == "atmem-deletion-receipt-v1"

    listed = _run("list", db, "user-1")
    assert json.loads(listed.stdout) == []

    verified = _run("verify", db)
    assert verified.returncode == 0
    assert json.loads(verified.stdout)["valid"] is True


def test_cli_log_action(tmp_path: Path) -> None:
    db = str(tmp_path / "mem.db")
    result = _run(
        "log-action", db, "user-1", "tool_call",
        "--payload", '{"tool": "calendar.create"}', "--session", "s1",
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["event_id"].startswith("aud_")

    audit = _run("audit", db, "user-1")
    events = json.loads(audit.stdout)["audit_log"]
    assert events[0]["event_type"] == "agent.tool_call"


def test_generic_control_cli_covers_review_sync_and_audit_export(tmp_path: Path) -> None:
    from atmem.control.manager import ControlPlaneManager

    state = tmp_path / "state.json"
    control_root = tmp_path / "control"
    memory_db = tmp_path / "memory.db"
    started = _run(
        "control",
        "shadow",
        "--host",
        "generic",
        "--state",
        str(state),
        "--control-root",
        str(control_root),
        "--memory-db",
        str(memory_db),
        "--json",
    )
    assert started.returncode == 0, started.stderr
    manager = ControlPlaneManager(state)
    captured = manager.capture(
        "Remember that my preferred shell is zsh.",
        authenticated_user=True,
        agent_id="main",
    )

    reviews = _run("control", "memory-reviews", "--state", str(state), "--json")
    assert reviews.returncode == 0, reviews.stderr
    assert json.loads(reviews.stdout)["records"][0]["record_id"] == captured["candidate_ids"][0]

    synced = _run("control", "memory-sync", "--state", str(state), "--json")
    assert synced.returncode == 0, synced.stderr
    assert json.loads(synced.stdout)["audit_verified"] is True

    output = tmp_path / "audit.ndjson"
    exported = _run(
        "control",
        "memory-audit",
        "--state",
        str(state),
        "--format",
        "ndjson",
        "--output",
        str(output),
        "--json",
    )
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout)["exported"] is True
    assert '"metadata"' in output.read_text()


def test_cli_read_only_search_trace_and_report_files(tmp_path: Path) -> None:
    db = str(tmp_path / "mem.db")
    stored = _run(
        "remember",
        db,
        "user-1",
        "My preferred airport is Sydney.",
        "--session",
        "s1",
        "--turn",
        "1",
    )
    record_id = json.loads(stored.stdout)["records"][0]["id"]
    assert _run(
        "recall", db, "user-1", "Which airport?", "--session", "s1"
    ).returncode == 0
    assert _run(
        "log-action",
        db,
        "user-1",
        "tool_call",
        "--payload",
        '{"tool":"flights.search","status":"ok"}',
        "--session",
        "s1",
        "--turn",
        "2",
    ).returncode == 0

    before = json.loads(_run("audit", db, "user-1").stdout)["audit_log"]
    searched = _run(
        "search", db, "preferred airport", "--subject", "user-1", "--format", "json"
    )
    assert searched.returncode == 0, searched.stderr
    search_report = json.loads(searched.stdout)
    assert search_report["format"] == "atmem-search-v1"
    assert search_report["audit_chain_valid"] is True
    assert any(
        item["kind"] == "memory" and item["id"] == record_id
        for item in search_report["results"]
    )
    after = json.loads(_run("audit", db, "user-1").stdout)["audit_log"]
    assert len(after) == len(before), "audit search must not record a memory recall"

    text_path = tmp_path / "memories.txt"
    written = _run(
        "memories", db, "--subject", "user-1", "--output", str(text_path)
    )
    assert written.returncode == 0, written.stderr
    assert written.stdout == ""
    assert "User's preferred airport is Sydney." in text_path.read_text()

    json_path = tmp_path / "trace.json"
    traced = _run(
        "trace",
        db,
        "airport",
        "--subject",
        "user-1",
        "--output",
        str(json_path),
    )
    assert traced.returncode == 0, traced.stderr
    trace_report = json.loads(json_path.read_text())
    assert trace_report["format"] == "atmem-trace-v1"
    kinds = {item["kind"] for item in trace_report["timeline"]}
    assert {"memory", "retrieval", "event"} <= kinds
    assert any(
        item["data"].get("event_type") == "agent.tool_call"
        for item in trace_report["timeline"]
    )
