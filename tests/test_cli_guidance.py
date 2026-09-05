from __future__ import annotations

import json
import sys

import pytest

from atmem import Memory
from atmem import cli


def test_bare_cli_is_a_guided_start_screen(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["atmem"])

    cli.main()

    output = capsys.readouterr().out
    assert "What do you want to do?" in output
    assert "atmem atbot setup" in output
    assert "atmem openclaw install" in output
    assert "atmem dashboard" in output
    assert "no memory injection is enabled" in output


def test_openclaw_upgrade_preserves_mode_and_reports_verified_bridge(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import atmem.openclaw_install

    monkeypatch.setattr(
        atmem.openclaw_install,
        "refresh_openclaw_bridge_and_test",
        lambda **_kwargs: {
            "format": "atmem-openclaw-bridge-refresh-v1",
            "refreshed": True,
            "previous_bridge_version": "2.1.0",
            "bridge_version": "2.2.5",
            "mode": "active",
            "gateway_verified": True,
            "test_flight": {
                "verdict": "completed_successfully",
                "valid": True,
            },
        },
    )
    monkeypatch.setattr(
        cli,
        "_restart_running_dashboard_after_upgrade",
        lambda: {
            "format": "atmem-dashboard-upgrade-v1",
            "was_running": True,
            "restarted": True,
            "atmem_version": "2.2.5",
        },
    )
    monkeypatch.setattr(sys, "argv", ["atmem", "openclaw", "upgrade", "--json"])

    cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["bridge_version"] == "2.2.5"
    assert result["mode"] == "active"
    assert result["test_flight"]["valid"] is True
    assert result["dashboard"]["restarted"] is True


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["atbot"], "Choose local AI, a hosted API, or safe fallback"),
        (["openclaw"], "Inspect the OpenClaw memory mirror"),
        (["openclaw", "memory"], "Search the mirrored memory by ordinary words"),
        (["control"], "Start safe observation without changing model context"),
        (["blackbox"], "Show recorder coverage and evidence-chain integrity"),
        (["index"], "Build and activate a verified versioned index epoch"),
        (["semantic"], "Set up, diagnose, and safely rebuild semantic retrieval"),
        (["proposals"], "Inspect and decide governed memory proposals awaiting review"),
        (["dashboard", "daemon"], "{start,open,stop,restart,status,remove}"),
    ],
)
def test_incomplete_command_groups_show_help_instead_of_an_error(
    arguments: list[str],
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["atmem", *arguments])

    cli.main()

    captured = capsys.readouterr()
    assert expected in captured.out
    assert captured.err == ""


def test_semantic_status_human_and_json_share_health_vocabulary(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "memory.db"
    Memory(database, auto_vectors=False).close()
    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "semantic", "status", str(database), "--subject", "u1", "--json"],
    )
    cli.main()
    machine = json.loads(capsys.readouterr().out)

    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "semantic", "status", str(database), "--subject", "u1"],
    )
    cli.main()
    human = capsys.readouterr().out

    assert machine["status"] == "missing"
    assert machine["actions"] == ["rebuild"]
    assert "Semantic index: missing" in human
    assert "Next actions: rebuild" in human


def test_semantic_rebuild_and_verify_have_stable_human_and_json_contracts(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember(
        "u1",
        "I prefer aisle seats.",
        interpreted_fact="I prefer aisle seats.",
        interpreted_fact_key="travel.seat",
    )
    memory.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "semantic", "rebuild", str(database), "--subject", "u1",
            "--provider", "hashing", "--model", "128", "--json",
        ],
    )
    cli.main()
    rebuilt = json.loads(capsys.readouterr().out)
    assert rebuilt["format"] == "atmem-semantic-rebuild-v1"
    assert rebuilt["health"]["status"] == "weak"

    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "semantic", "verify", str(database), "--subject", "u1", "--json"],
    )
    cli.main()
    verified = json.loads(capsys.readouterr().out)
    assert verified["format"] == "atmem-semantic-health-v1"
    assert verified["status"] == "weak"

    monkeypatch.setattr(
        sys,
        "argv",
        ["atmem", "semantic", "verify", str(database), "--subject", "u1"],
    )
    cli.main()
    assert "Semantic index: weak" in capsys.readouterr().out


def test_proposal_review_is_drivable_from_the_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    from atmem.contracts import AuthorityScope
    from atmem.extract import build_resolution_context, propose_from_rules

    path = tmp_path / "memories.db"
    scope = AuthorityScope("user-1", "agent-1", "workspace-1")
    message = "My current medication is atorvastatin."
    memory = Memory(path, auto_vectors=False)
    try:
        context = build_resolution_context(memory.store, scope.subject_id, scope=scope)
        [proposal] = propose_from_rules(
            message, scope=scope, source_id="source-1", context=context
        )
        submitted = memory.submit_extraction_proposal(proposal, source_text=message)
    finally:
        memory.close()
    assert submitted["review_state"] == "pending_review"

    monkeypatch.setattr(
        sys, "argv", ["atmem", "proposals", "queue", str(path), "--json"]
    )
    cli.main()
    queue = json.loads(capsys.readouterr().out)
    assert queue["count"] == 1
    assert queue["proposals"][0]["allowed_decisions"] == [
        "approve",
        "edit_and_approve",
        "reject",
    ]

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atmem", "proposals", "decide", str(path), submitted["proposal_id"],
            "approve", "--actor", "ops@example.com", "--reason", "confirmed",
            "--json",
        ],
    )
    cli.main()
    decided = json.loads(capsys.readouterr().out)
    assert decided["review_state"] == "committed"
    assert decided["reviews"][0]["actor"] == "ops@example.com"


def test_terminal_and_dashboard_report_the_same_proposal_state(tmp_path) -> None:
    """One review service backs both surfaces, so their views cannot drift."""
    from atmem.contracts import AuthorityScope
    from atmem.extract import ReviewService, build_resolution_context, propose_from_rules

    path = tmp_path / "memories.db"
    scope = AuthorityScope("user-1", "agent-1", "workspace-1")
    message = "My current medication is atorvastatin."
    memory = Memory(path, auto_vectors=False)
    try:
        context = build_resolution_context(memory.store, scope.subject_id, scope=scope)
        [proposal] = propose_from_rules(
            message, scope=scope, source_id="source-1", context=context
        )
        memory.submit_extraction_proposal(proposal, source_text=message)
        service = ReviewService(memory)
        queue = service.queue(scope.subject_id)
        detail = service.inspect(queue["proposals"][0]["proposal_id"])
    finally:
        memory.close()

    row = queue["proposals"][0]
    for field in ("review_state", "action", "memory_class", "reason_codes",
                  "allowed_decisions", "evidence"):
        assert row[field] == detail[field], field
