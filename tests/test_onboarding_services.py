from __future__ import annotations

from argparse import Namespace
import json
import subprocess
from types import SimpleNamespace

from atmem import cli
from atmem import atflows_service


def test_companion_navigation_url_only_accepts_numeric_loopback() -> None:
    valid = atflows_service.validated_dashboard_url
    assert valid("http://127.0.0.1:1337/") == "http://127.0.0.1:1337/"
    assert valid("http://127.0.0.1:55123") == "http://127.0.0.1:55123/"
    for unsafe in (None, "https://127.0.0.1:1337/", "http://localhost:1337/", "http://example.com:1337/", "http://127.0.0.1:99999/", "http://user@127.0.0.1:1337/", "http://127.0.0.1:1337/other", "http://127.0.0.1:1337/?redirect=https://example.com"):
        assert valid(unsafe) is None


def test_init_repairs_old_dashboard_and_starts_shared_flows(monkeypatch, capsys) -> None:
    from atmem import dashboard_daemon
    from atmem.control import atbot_service

    monkeypatch.setattr(atbot_service, "AtBotServiceManager", lambda: SimpleNamespace(ensure_running=lambda: {"running": False, "fallback_selected": True}))

    bootstrap = {"created": False, "username": "administrator", "password": None}
    monkeypatch.setattr(
        cli, "_identity_manager",
        lambda _state: SimpleNamespace(identity_service=lambda: SimpleNamespace(bootstrap=lambda: bootstrap)),
    )
    actions: list[str] = []

    def daemon(action: str, **_kwargs):
        actions.append(action)
        if action == "status":
            return {"running": True, "restart_required": True, "port": 8768, "url": "http://127.0.0.1:8768/"}
        return {"running": True, "restart_required": False, "port": 8768, "url": "http://127.0.0.1:8768/", "atmem_version": "2.3.4"}

    monkeypatch.setattr(dashboard_daemon, "manage_dashboard_daemon", daemon)
    passed_urls: list[str] = []
    monkeypatch.setattr(atflows_service, "ensure_started", lambda url: (
        passed_urls.append(url) or {"running": True, "dashboard_url": "http://127.0.0.1:1337/", "proxy_url": "http://127.0.0.1:8080/"}
    ))
    cli._run_identity_init(Namespace(state=None, json=True, no_open=True, port=8766))
    report = json.loads(capsys.readouterr().out)
    assert actions == ["status", "restart"]
    assert passed_urls == ["http://127.0.0.1:8768/"]
    assert report["dashboard"]["atmem_version"] == "2.3.4"
    assert report["atflows"]["dashboard_url"] == "http://127.0.0.1:1337/"


def test_init_reports_selected_port_and_companion_failure(monkeypatch, capsys) -> None:
    from atmem import dashboard_daemon
    from atmem.control import atbot_service

    monkeypatch.setattr(atbot_service, "AtBotServiceManager", lambda: SimpleNamespace(ensure_running=lambda: {"running": False, "fallback_selected": True}))

    monkeypatch.setattr(
        cli, "_identity_manager",
        lambda _state: SimpleNamespace(identity_service=lambda: SimpleNamespace(bootstrap=lambda: {"created": False})),
    )
    monkeypatch.setattr(cli, "_available_loopback_port", lambda _port: 49152)
    monkeypatch.setattr(dashboard_daemon, "manage_dashboard_daemon", lambda action, **kwargs: (
        {"running": False} if action == "status" else
        {"running": True, "port": kwargs["port"], "url": "http://127.0.0.1:49152/"}
    ))
    def fail(_url: str):
        raise RuntimeError("Bun is missing; install Bun >=1.1")
    monkeypatch.setattr(atflows_service, "ensure_started", fail)
    cli._run_identity_init(Namespace(state=None, json=False, no_open=True, port=8766))
    output = capsys.readouterr().out
    assert "8766 was unavailable; AtMem selected 49152" in output
    assert "AtFlows: Bun is missing" in output
    assert "http://127.0.0.1:49152/" in output


def test_fresh_init_starts_both_dashboards_without_extra_account(monkeypatch, capsys) -> None:
    from atmem import dashboard_daemon
    from atmem.control import atbot_service

    monkeypatch.setattr(atbot_service, "AtBotServiceManager", lambda: SimpleNamespace(ensure_running=lambda: {"running": False, "fallback_selected": True}))
    bootstrap = {"created": True, "username": "administrator", "password": "temporary-test-secret"}
    monkeypatch.setattr(cli, "_identity_manager", lambda _state: SimpleNamespace(identity_service=lambda: SimpleNamespace(bootstrap=lambda: bootstrap)))
    monkeypatch.setattr(cli, "_available_loopback_port", lambda preferred: preferred)
    actions: list[str] = []
    def daemon(action: str, **kwargs):
        actions.append(action)
        return {"running": False} if action == "status" else {"running": True, "port": kwargs["port"], "url": "http://127.0.0.1:8766/"}
    monkeypatch.setattr(dashboard_daemon, "manage_dashboard_daemon", daemon)
    monkeypatch.setattr(atflows_service, "ensure_started", lambda url: {
        "running": True, "dashboard_url": "http://127.0.0.1:1337/", "proxy_url": "http://127.0.0.1:8080/", "auth_mode": "atmem", "authority": url,
    })
    cli._run_identity_init(Namespace(state=None, json=True, no_open=True, port=8766))
    report = json.loads(capsys.readouterr().out)
    assert actions == ["status", "start"]
    assert report["atflows"]["authority"] == report["dashboard"]["url"]
    assert report["atflows"]["auth_mode"] == "atmem"
    assert report["errors"] == []


def test_atflows_status_does_not_assume_external_auth_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path))
    monkeypatch.setattr(atflows_service, "_running", lambda: [{
        "instance_id": "outside", "dashboard_port": 1337, "proxy_port": 8080,
        "dashboard_online": True, "proxy_online": True,
    }])
    monkeypatch.setattr(atflows_service, "version", lambda _name: "0.1.1")
    report = atflows_service.status()
    assert report["running"] is True
    assert report["auth_mode"] == "unknown"
    assert report["managed_by_atmem"] is False
    assert "independently started" in report["warning"]


def test_multiple_independent_atflows_servers_do_not_get_an_arbitrary_link(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path))
    monkeypatch.setattr(atflows_service, "_running", lambda: [
        {"instance_id": "one", "dashboard_port": 1337, "proxy_port": 8080, "dashboard_online": True, "proxy_online": True},
        {"instance_id": "two", "dashboard_port": 1447, "proxy_port": 8180, "dashboard_online": True, "proxy_online": True},
    ])
    monkeypatch.setattr(atflows_service, "version", lambda _name: "0.1.1")
    report = atflows_service.status()
    assert report["dashboard_url"] is None
    assert report["running"] is True
    assert "cannot choose one safely" in report["warning"]


def test_status_flags_old_openclaw_bridge_without_claiming_live_verification(monkeypatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/openclaw" if name == "openclaw" else None)
    def run(command, **_kwargs):
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "OpenClaw 2026.9.1\n", "")
        return subprocess.CompletedProcess(command, 0, json.dumps({"plugins": [{
            "id": "memory-atmem", "version": "2.3.2", "enabled": True,
        }]}), "")
    monkeypatch.setattr(cli.subprocess, "run", run)
    report = cli._openclaw_install_status()
    assert report["bridge_version"] == "2.3.2"
    assert report["bridge_compatible"] is False
    assert report["verified"] is False
    assert "atmem openclaw upgrade" in report["next_action"]
