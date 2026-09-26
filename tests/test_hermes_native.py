import json
import os
from pathlib import Path
import subprocess
import threading

import pytest

from atmem.hermes_install import install, inspect_install


def native(home, mode):
    runtime = os.environ.get("HERMES_PYTHON")
    source = os.environ.get("HERMES_SOURCE")
    if not runtime or not source:
        pytest.skip("HERMES_PYTHON and HERMES_SOURCE required for managed-host qualification")
    script = Path(__file__).with_name("native_hermes_probe.py").resolve()
    # Activate the already-installed dependency graph, then isolate host data.
    # Full bootstrap treats an empty Home as a new runtime and installs dependencies.
    bootstrap = ("import sys,os,runpy; from pathlib import Path; source=sys.argv.pop(1); "
                 "sys.path.insert(0,source); import hermes_bootstrap; "
                 "os.environ['HERMES_HOME']=sys.argv.pop(1); "
                 "runpy.run_path(sys.argv.pop(1),run_name='__main__')")
    result = subprocess.run([runtime, "-I", "-c", bootstrap, source, str(home), str(script), mode],
                            env={**os.environ, "HERMES_HOME": os.environ.get("HERMES_RUNTIME_HOME", str(Path(source).parent)),
                                 "HERMES_ENABLE_PROJECT_PLUGINS": "0"},
                            capture_output=True, text=True, timeout=60, cwd=home)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_actual_native_discovery(tmp_path):
    home = tmp_path.resolve()
    install(home, apply=True)
    assert '"dashboard_status": "unavailable"' in native(home, "discovery")
    assert inspect_install(home)["state"] == "installed"  # bytecode is not an edit


def test_host_forced_selection_is_not_governed_activation(tmp_path):
    home = tmp_path.resolve()
    install(home, apply=True)
    assert '"host_forced_selection_falls_back": true' in native(home, "forced_selection")


def test_native_provider_capture_review_and_new_process_recall(tmp_path, monkeypatch):
    from atmem.control import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer
    from atmem.adapters.hermes.service import HermesService
    from atmem.service import APIPrincipal
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.propose",
                        lambda self, message: {"proposals": [], "companion": {"available": False}})
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
                        lambda self, query: {"expanded_queries": [query], "content_received": False})
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.query",
                        lambda self, query, candidates: {"ranked_record_ids": [r["record_id"] for r in candidates],
                                                        "companion": {"available": False}})
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path / "state.json",
                                        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db")
    workspace = manager.agent_topology()["workspaces"][0]
    admin = APIPrincipal("operator", "admin", workspace["subject_id"])
    service = HermesService(manager)
    grant = service.provision(admin, profile_id="native-test", agent_id="main",
                              workspace_id=workspace["workspace_id"], accept_reduced_capture=True)
    service.configure(admin, grant["binding"]["binding_id"], enabled=True)
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    install(home, apply=True)
    private = home / ".atmem"
    private.mkdir(mode=0o700)
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html="test")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = {"format": "atmem-hermes-connection-v1", "hermes_home": str(home),
              "endpoint": f"http://127.0.0.1:{server.server_port}", "profile_id": "native-test"}
    for name, text in (("connection.json", json.dumps(config)), ("credential", grant["credential"])):
        path = private / name
        path.write_text(text)
        path.chmod(0o600)
    try:
        assert '"capture_flushed": true' in native(home, "capture")
        # Admission remains the normal product review, never supplied by the provider.
        candidates = manager.candidates()
        assert candidates
        for candidate in candidates:
            manager.review_memory(candidate["id"], "approve")
        manager.activate()
        assert '"new_process_new_session_recall": true' in native(home, "recall")
        assert '"unsupported_mode_withholds": true' in native(home, "unsupported")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
