import json
import os
from pathlib import Path

import pytest

from atmem.hermes_install import (
    RECEIPT, SETUP_FORMAT, _dashboard_endpoint, _publish, _upgrade_managed_plugin,
    guided_restore, guided_setup,
    inspect_install, install,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="inactive installer not native Windows qualified")


def snapshot(home):
    return {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}


def test_preview_and_install_preserve_native_files(tmp_path):
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    (home / "config.yaml").write_text("memory:\n  provider: builtin\n")
    (home / ".env").write_text("DO_NOT_READ_OR_CHANGE=canary")
    (home / "MEMORY.md").write_text("original")
    before = snapshot(home)
    assert not install(home)["applied"]
    assert snapshot(home) == before
    assert not (home / "plugins").exists()
    assert install(home, apply=True)["applied"]
    for name, content in before.items():
        assert (home / name).read_bytes() == content
    assert not install(home, apply=True)["applied"]
    assert not (home / ".atmem").exists()


def test_modified_unmanaged_and_extra_sources_refuse(tmp_path):
    home = tmp_path.resolve()
    target = home / "plugins" / "atmem"
    target.mkdir(parents=True)
    assert inspect_install(home)["state"] == "conflict"
    with pytest.raises(ValueError):
        install(home, apply=True)
    target.rmdir()
    install(home, apply=True)
    (target / "extra.py").write_text("malicious = True")
    with pytest.raises(ValueError):
        install(home, apply=True)
    (target / "extra.py").unlink()
    (target / "client.py").write_text("edited")
    assert inspect_install(home)["state"] == "conflict"


def test_cache_and_intact_old_payload(tmp_path):
    home = tmp_path.resolve()
    install(home, apply=True)
    target = home / "plugins" / "atmem"
    cache = target / "__pycache__"
    cache.mkdir()
    (cache / "client.cpython-314.pyc").write_bytes(b"cache")
    assert inspect_install(home)["state"] == "installed"
    import hashlib
    (target / "client.py").write_bytes(b"old installed version")
    receipt = json.loads((target / RECEIPT).read_text())
    receipt["sha256"]["client.py"] = hashlib.sha256(b"old installed version").hexdigest()
    (target / RECEIPT).write_text(json.dumps(receipt))
    assert inspect_install(home)["state"] == "upgrade_required"
    upgraded = _upgrade_managed_plugin(home)
    assert upgraded["state"] == "installed"
    assert upgraded["upgraded"] is True
    assert Path(upgraded["plugin_backup"]).is_dir()


def test_unsafe_parent_and_target_refuse(tmp_path):
    home = tmp_path.resolve()
    parent = home / "plugins"
    parent.mkdir()
    parent.chmod(0o777)
    with pytest.raises(ValueError):
        install(home, apply=True)
    parent.chmod(0o700)
    (parent / "atmem").symlink_to(home)
    with pytest.raises(ValueError):
        install(home, apply=True)


def test_publication_never_replaces_even_empty_directory(tmp_path):
    stage, target = tmp_path / "stage", tmp_path / "target"
    stage.mkdir()
    target.mkdir()
    with pytest.raises(OSError):
        _publish(stage, target)
    assert stage.is_dir() and target.is_dir()


def test_interrupted_publication_is_invisible_and_retryable(tmp_path, monkeypatch):
    import atmem.hermes_install as module
    home = tmp_path.resolve()
    publish = module._publish
    monkeypatch.setattr(module, "_publish", lambda *a: (_ for _ in ()).throw(RuntimeError("interrupted")))
    with pytest.raises(RuntimeError):
        install(home, apply=True)
    assert not (home / "plugins" / "atmem").exists()
    stages = list((home / "plugins").glob("__atmem_stage_*"))
    assert len(stages) == 1 and (stages[0] / RECEIPT).exists()
    monkeypatch.setattr(module, "_publish", publish)
    assert install(home, apply=True)["applied"]
    assert stages[0].exists()  # Unknown/interrupted stages never auto-deleted.


def test_failure_after_publication_keeps_valid_install(tmp_path, monkeypatch):
    import atmem.hermes_install as module
    home = tmp_path.resolve()
    sync = module._sync_directory
    def interrupted(path):
        if path.name == "plugins":
            raise RuntimeError("interrupted after rename")
        sync(path)
    monkeypatch.setattr(module, "_sync_directory", interrupted)
    with pytest.raises(RuntimeError):
        install(home, apply=True)
    assert inspect_install(home)["state"] == "installed"


def test_bad_home_and_lock_paths(tmp_path):
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(home)
    for path in (alias, Path.home(), Path("/")):
        with pytest.raises(ValueError):
            install(path, apply=True)
    home.chmod(0o770)
    with pytest.raises(ValueError):
        install(home, apply=True)
    home.chmod(0o700)
    parent = home / "plugins"
    parent.mkdir()
    (parent / ".atmem-install.lock").symlink_to(home / "config.yaml")
    with pytest.raises(OSError):
        install(home, apply=True)
    assert not (home / "config.yaml").exists()


def test_dashboard_endpoint_reuses_recorded_port(monkeypatch):
    calls = []
    values = iter([
        {"running": False, "port": 9876},
        {"running": True, "port": 9876},
    ])

    def manage(action, **kwargs):
        calls.append((action, kwargs))
        return next(values)

    monkeypatch.setattr("atmem.dashboard_daemon.manage_dashboard_daemon", manage)
    class Reachable:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: Reachable())
    assert _dashboard_endpoint(start=True) == "http://127.0.0.1:9876"
    assert calls == [("status", {}), ("start", {"port": 9876})]


def test_partial_retry_rebacks_up_current_config(tmp_path, monkeypatch):
    from atmem.control import ControlPlaneManager

    manager = ControlPlaneManager.start(
        host="generic", state_path=tmp_path / "state.json",
        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db",
    )
    monkeypatch.setattr("atmem.control.ControlPlaneManager", lambda: manager)
    monkeypatch.setattr(
        "atmem.hermes_install._hermes_config",
        lambda _home, action, *values: "mem0" if action == "get" else "",
    )
    home = tmp_path / "hermes"
    private = home / ".atmem"
    private.mkdir(parents=True)
    (home / "config.yaml").write_text("model: edited-between-attempts\n")
    (private / "setup-receipt.json").write_text(json.dumps({
        "format": SETUP_FORMAT,
        "phase": "planned",
        "restored": False,
        "previous_provider": "mem0",
        "config_backup": str(private / "stale.enc.json"),
        "config_before_sha256": "stale",
    }))
    observed = []

    def stop_after_backup(_manager, selected_home):
        observed.append((selected_home / "config.yaml").read_text())
        raise RuntimeError("stop after fresh backup")

    monkeypatch.setattr("atmem.hermes_install._backup_config", stop_after_backup)
    with pytest.raises(RuntimeError, match="stop after fresh backup"):
        guided_setup(home, apply=True, endpoint="http://127.0.0.1:8768")
    assert observed == ["model: edited-between-attempts\n"]


def test_cli_preview_status_and_apply(tmp_path):
    import subprocess
    import sys
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    absent_atmem = tmp_path / "absent_atmem"
    env = {**os.environ, "ATMEM_HOME": str(absent_atmem)}
    base = [sys.executable, "-m", "atmem.cli", "hermes"]
    def run(command, *options):
        return subprocess.run(base + [command, "--hermes-home", str(home), "--json", *options],
                              env=env, capture_output=True, text=True, timeout=20)
    for command in ("status", "install"):
        result = run(command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["applied"] is False
    assert not list(home.iterdir())
    assert not absent_atmem.exists()
    assert run("status", "--apply").returncode != 0
    assert json.loads(run("install", "--apply").stdout)["applied"] is True
    assert json.loads(run("status").stdout)["state"] == "installed"
    assert not absent_atmem.exists()


def test_guided_setup_connects_once_and_keeps_credentials_out_of_receipt(tmp_path, monkeypatch):
    import threading
    from atmem.control import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer

    manager = ControlPlaneManager.start(
        host="generic", state_path=tmp_path / "state.json",
        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db",
    )
    monkeypatch.setattr("atmem.control.ControlPlaneManager", lambda: manager)
    providers = {"value": "mem0"}
    def config(_home, action, *values):
        if action == "get":
            return providers["value"]
        assert action == "set" and values[0] == "memory.provider"
        providers["value"] = values[1]
        return ""
    monkeypatch.setattr("atmem.hermes_install._hermes_config", config)
    home = tmp_path / "hermes"
    home.mkdir()
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html="test")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}"
        result = guided_setup(home, apply=True, memory="shared", endpoint=endpoint)
        assert result["mode"] == "shadow"
        assert result["agent_id"].startswith("hermes-")
        assert result["subject_id"] == manager.state().subject_id
        assert providers["value"] == "atmem"
        secret = (home / ".atmem" / "credential").read_text().strip()
        receipt = (home / ".atmem" / "setup-receipt.json").read_text()
        assert secret.startswith("hermes_")
        assert secret not in receipt
        second = guided_setup(
            home, apply=True, activate=True, memory="shared", endpoint=endpoint
        )
        assert second["binding_id"] == result["binding_id"]
        assert second["mode"] == "active"
        assert (home / ".atmem" / "credential").read_text().strip() == secret
        topology_before = manager.agent_topology()
        with pytest.raises(RuntimeError, match="restore hermes"):
            guided_setup(home, apply=True, memory="isolated", endpoint=endpoint)
        assert manager.agent_topology() == topology_before
        assert providers["value"] == "atmem"
        assert service_status(home, endpoint)["mode"] == "active"
        monkeypatch.setattr(
            "atmem.hermes_install._verify_turn",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("verification failed")),
        )
        with pytest.raises(RuntimeError, match="verification failed"):
            guided_setup(
                home, apply=True, activate=True, memory="shared",
                endpoint=endpoint, verify_turn=True,
            )
        failed_receipt = json.loads((home / ".atmem" / "setup-receipt.json").read_text())
        assert failed_receipt["previous_provider"] == "mem0"
        assert failed_receipt["phase"] == "verification_failed"
        assert failed_receipt["mode"] == "shadow"
        assert providers["value"] == "mem0"
        assert service_status(home, endpoint)["mode"] == "shadow"
        restored = guided_restore(home, apply=True)
        assert restored["restore_provider"] == "mem0"
        assert restored["restored"] is True
        assert providers["value"] == "mem0"
        assert service_status(home, endpoint)["mode"] == "inactive"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_live_turn_verification_requires_activation(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    with pytest.raises(ValueError, match="requires --activate"):
        guided_setup(home, apply=True, verify_turn=True)
    assert not (home / ".atmem").exists()


def test_guided_setup_defaults_to_isolated_scope_and_quarantines_native_memory(
    tmp_path, monkeypatch
):
    import threading
    from atmem.control import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer

    manager = ControlPlaneManager.start(
        host="generic", state_path=tmp_path / "state.json",
        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db",
    )
    monkeypatch.setattr("atmem.control.ControlPlaneManager", lambda: manager)
    provider = {"value": "(built-in / default)"}
    def config(_home, action, *values):
        if action == "get":
            return provider["value"]
        provider["value"] = values[1]
        return ""
    monkeypatch.setattr("atmem.hermes_install._hermes_config", config)
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "USER.md").write_text("The user prefers jasmine tea.\n", encoding="utf-8")
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html="test")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}"
        result = guided_setup(home, apply=True, endpoint=endpoint)
        assert result["memory"] == "isolated"
        assert result["subject_id"] != manager.state().subject_id
        assert result["agent_id"].startswith("hermes-")
        assert result["files"] == 1
        assert result["native_imports"][0]["path"] == "USER.md"
        assert (home / "USER.md").read_text() == "The user prefers jasmine tea.\n"
        from atmem.memory import Memory
        _, memory_path = manager._memory_authority_scope(
            manager.state(), subject_id=result["subject_id"], agent_id=result["agent_id"]
        )
        memory_store = Memory(memory_path)
        try:
            imported = memory_store.list(result["subject_id"], include_inactive=True)
            assert imported
            assert {row["status"] for row in imported} == {"quarantined"}
            assert memory_store.recall(result["subject_id"], "jasmine tea") == []
        finally:
            memory_store.close()
        second = guided_setup(home, apply=True, endpoint=endpoint)
        assert second["native_imports"][0]["result"] == "already_proposed"
        assert service_status(home, endpoint)["workspace_id"] == result["workspace_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def service_status(home, endpoint):
    from atmem.adapters.hermes.client import HermesRPCClient
    connection = json.loads((home / ".atmem" / "connection.json").read_text())
    credential = (home / ".atmem" / "credential").read_text().strip()
    return HermesRPCClient(
        endpoint, credential, profile_id=connection["profile_id"]
    ).status()
