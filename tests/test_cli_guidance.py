from __future__ import annotations

import json
import sys

import pytest

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
            "bridge_version": "2.2.4",
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
            "atmem_version": "2.2.4",
        },
    )
    monkeypatch.setattr(sys, "argv", ["atmem", "openclaw", "upgrade", "--json"])

    cli.main()

    result = json.loads(capsys.readouterr().out)
    assert result["bridge_version"] == "2.2.4"
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
