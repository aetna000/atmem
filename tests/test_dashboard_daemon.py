from __future__ import annotations

from pathlib import Path

import pytest

from atmem.dashboard_daemon import manage_dashboard_daemon


class _FakeProcess:
    pid = 4242

    def poll(self):
        return None


def test_dashboard_daemon_start_records_direct_loopback_url(
    tmp_path: Path, monkeypatch
) -> None:
    state_path = tmp_path / "dashboard.json"
    launched: list[list[str]] = []

    def fake_popen(command, *args, **kwargs):
        launched.append(command)
        return _FakeProcess()

    monkeypatch.setattr(
        "atmem.dashboard_daemon.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "atmem.dashboard_daemon._dashboard_url",
        lambda _path, **_kwargs: "http://127.0.0.1:9123/",
    )
    monkeypatch.setattr(
        "atmem.dashboard_daemon._alive", lambda pid: pid == 4242
    )

    result = manage_dashboard_daemon(
        "start", port=9123, daemon_state_path=state_path
    )

    assert result["running"] is True
    assert result["url"] == "http://127.0.0.1:9123/"
    assert result["atmem_version"]
    assert launched[0][1:3] == ["-I", "-m"]
    assert "login_url" not in result
    assert "access_code" not in result
    assert state_path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "dashboard-daemon.log").stat().st_mode & 0o777 == 0o600


def test_dashboard_daemon_remove_preserves_memory_data(tmp_path: Path) -> None:
    state_path = tmp_path / "dashboard.json"
    state_path.write_text(
        '{"format":"atmem-dashboard-daemon-v1","pid":999999,"port":8766}\n',
        encoding="utf-8",
    )

    result = manage_dashboard_daemon("remove", daemon_state_path=state_path)

    assert result["removed"] is True
    assert result["data_preserved"] is True
    assert not state_path.exists()


def test_dashboard_daemon_open_uses_direct_url(
    tmp_path: Path, monkeypatch
) -> None:
    state_path = tmp_path / "dashboard.json"
    state_path.write_text(
        '{"format":"atmem-dashboard-daemon-v1","pid":4242,'
        '"port":8766,"url":"http://127.0.0.1:8766/"}\n',
        encoding="utf-8",
    )
    opened: list[str] = []
    monkeypatch.setattr(
        "atmem.dashboard_daemon._alive", lambda pid: pid == 4242
    )
    monkeypatch.setattr(
        "atmem.dashboard_daemon._open_default_browser",
        lambda url: opened.append(url) or True,
    )

    result = manage_dashboard_daemon("open", daemon_state_path=state_path)

    assert result["opened"] is True
    assert opened == ["http://127.0.0.1:8766/"]


def test_dashboard_daemon_start_fails_closed_without_ready_url(
    tmp_path: Path, monkeypatch
) -> None:
    state_path = tmp_path / "dashboard.json"
    monkeypatch.setattr(
        "atmem.dashboard_daemon.subprocess.Popen",
        lambda *args, **kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        "atmem.dashboard_daemon._dashboard_url",
        lambda _path, **_kwargs: None,
    )
    ticks = iter((0.0, 6.0))
    monkeypatch.setattr(
        "atmem.dashboard_daemon.time.monotonic", lambda: next(ticks)
    )
    monkeypatch.setattr(
        "atmem.dashboard_daemon._alive", lambda _pid: False
    )

    with pytest.raises(ValueError, match="did not publish a usable URL"):
        manage_dashboard_daemon("start", port=9123, daemon_state_path=state_path)

    assert '"running": false' in state_path.read_text(encoding="utf-8")


def test_dashboard_url_ignores_old_log_entries(tmp_path: Path) -> None:
    from atmem.dashboard_daemon import _dashboard_url

    log_path = tmp_path / "dashboard.log"
    log_path.write_text(
        "AtMem dashboard: http://127.0.0.1:8766/\n", encoding="utf-8"
    )
    restart_offset = log_path.stat().st_size

    assert _dashboard_url(log_path, after_bytes=restart_offset) is None

    with log_path.open("a", encoding="utf-8") as stream:
        stream.write("AtMem dashboard: http://127.0.0.1:9123/\n")

    assert _dashboard_url(log_path, after_bytes=restart_offset) == (
        "http://127.0.0.1:9123/"
    )


def test_dashboard_status_flags_a_running_old_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    state_path = tmp_path / "dashboard.json"
    state_path.write_text(
        '{"format":"atmem-dashboard-daemon-v1","pid":4242,'
        '"port":8766,"atmem_version":"2.1.0"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("atmem.dashboard_daemon._alive", lambda _pid: True)
    monkeypatch.setattr(
        "atmem.dashboard_daemon._installed_atmem_version", lambda: "2.2.5"
    )

    result = manage_dashboard_daemon("status", daemon_state_path=state_path)

    assert result["restart_required"] is True
    assert result["current_atmem_version"] == "2.2.5"


def test_dashboard_status_flags_a_different_python_environment(
    tmp_path: Path, monkeypatch
) -> None:
    state_path = tmp_path / "dashboard.json"
    state_path.write_text(
        '{"format":"atmem-dashboard-daemon-v1","pid":4242,'
        '"port":8766,"atmem_version":"2.2.5",'
        '"python_executable":"/old/environment/bin/python"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("atmem.dashboard_daemon._alive", lambda _pid: True)
    monkeypatch.setattr(
        "atmem.dashboard_daemon._installed_atmem_version", lambda: "2.2.5"
    )

    result = manage_dashboard_daemon("status", daemon_state_path=state_path)

    assert result["restart_required"] is True
    assert result["current_python_executable"]


def test_dashboard_contains_semantic_health_evidence_and_safe_actions() -> None:
    from atmem.control.ui import APP_HTML

    assert 'id="semanticHealthCard"' in APP_HTML
    assert 'id="semanticHealthEvidence"' in APP_HTML
    assert 'id="semanticHealthActions"' in APP_HTML
    assert 'get("/api/semantic/health")' in APP_HTML
    assert 'if(action==="discard_partial")button.disabled=true' in APP_HTML


def test_dashboard_semantic_projection_uses_shared_health_contract(tmp_path: Path) -> None:
    from atmem import Memory
    from atmem.control import ControlPlaneManager
    from atmem.semantic import SemanticIndex, inspect_semantic_health

    database = tmp_path / "memory.db"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
        memory_db=database,
    )
    memory = Memory(database)
    memory.remember(
        "local-user",
        "I prefer aisle seats.",
        interpreted_fact="I prefer aisle seats.",
        interpreted_fact_key="travel.seat",
    )
    memory.close()

    expected_memory = Memory(database, auto_vectors=False)
    index = SemanticIndex(f"{database}.vectors.db", policy=expected_memory.policy)
    try:
        expected = inspect_semantic_health(
            index, expected_memory, "local-user"
        ).to_dict()
    finally:
        index.close()
        expected_memory.close()

    assert manager.semantic_health("local-user") == expected
