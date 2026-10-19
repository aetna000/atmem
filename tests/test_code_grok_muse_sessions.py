"""Partial installed-host evidence; passing tests do not enable these adapters."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ATMEM_CODE_SKIP_HOST_PROBES") == "1",
                                reason="Native CLI probes are qualified separately")


@pytest.mark.parametrize("host", ["grok", pytest.param("muse", marks=pytest.mark.xfail(
    os.name == "nt", strict=True,
    reason="Muse 1.4.8 Windows completes the local model request but project hooks never invoke the wrapper (B01)"))])
def test_controlled_capture_recall_and_pause(tmp_path, monkeypatch, host):
    if not (os.environ.get("ATMEM_TEST_" + host.upper() + "_BINARY") or shutil.which(host)):
        pytest.skip(host + " is not installed")
    pytest.importorskip("sqlcipher3")
    from atmem.code.application import CodeApplication
    from atmem.code.hook import enroll
    from atmem.code import hook
    from atmem.code.install import CodeInstall
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    import atmem.core.keys
    key_file = tmp_path / "fixture-db.key"
    monkeypatch.setattr(atmem.core.keys, "DEFAULT_KEY_PATH", key_file)
    root = tmp_path / "project with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    db = tmp_path / "memory.db"
    HouseholdApplication.initialize(db, encrypted=True)
    memory = Memory(db, auto_vectors=False)
    try:
        installer = CodeInstall(memory.store)
        project = installer.setup(root, subject_id="local", profile_id="shared", agent_id=host,
                                  host=host, apply=True)["scope"]["project_id"]
        with pytest.raises(RuntimeError, match="not yet verified"):
            installer.enable(project=root, subject_id="local", host=host)
        # Explicit fixture bypass: preserve the production activation refusal.
        memory.store.set_code_installation_enabled(subject_id="local", project_id=project, host=host, enabled=True)
        app = CodeApplication(memory, subject_id="local")
        # This host qualification retains the explicit full-content mode.
        app.settings(project, {'context_mode': 'content'})
        credential = tmp_path / (host + ".credential")
        enroll(app, project=project, root=str(root), profile="shared", agent=host,
               host=host, credential_file=str(credential))
        fixtures = Path(__file__).parent / "fixtures"
        argv = [sys.executable, str(fixtures / "grok_muse_atmem_hook.py"), str(key_file), str(Path(hook.__file__).resolve()),
                "--db", str(db), "--subject", "local", "--project-id", project,
                "--credential-file", str(credential)]
        command = runpy.run_path(str(fixtures / "host_process.py"))["hook_command"](argv)
        Endpoint = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
        run_host = runpy.run_path(str(fixtures / "grok_muse_runner.py"))["run_host"]
        receipts = []
        for prompt, recall in [("My preferred formatter is Ruff.", False), ("Which formatter should I use?", host == "muse")]:
            with Endpoint() as endpoint:
                result = run_host(host, root, command, prompt, endpoint)
                receipts.append({"stage": "capture" if len(receipts) == 0 else "fresh_session_recall",
                                 "returncode": result.returncode, "model_requests": len(endpoint.requests),
                                 "formatter_in_request": "Ruff" in json.dumps(endpoint.requests),
                                 "hook_invoked": (root / "code-hook-input.json").exists(),
                                 "canonical_memories": len(app.records(project))})
                (tmp_path / "session-results.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
                assert result.returncode == 0, result.stderr[-3000:] + result.stdout[-1000:]
                assert endpoint.requests
                assert ("Ruff" in json.dumps(endpoint.requests)) is (recall or "Ruff" in prompt)
            records = app.records(project)
            diagnostic = root / "code-hook-output.json"
            assert len(records) == 1 and "Ruff" in records[0]["content"], (
                diagnostic.read_text() if diagnostic.exists() else "Hook wrapper never ran: " + result.stderr[-3000:])
        installer.disable(project=root, subject_id="local", host=host)
        with Endpoint() as endpoint:
            result = run_host(host, root, command, "My preferred test runner is pytest. Which formatter should I use?", endpoint)
            receipts.append({"stage": "paused", "returncode": result.returncode,
                             "model_requests": len(endpoint.requests),
                             "formatter_in_request": "Ruff" in json.dumps(endpoint.requests),
                             "canonical_memories": len(app.records(project))})
            (tmp_path / "session-results.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
            assert result.returncode == 0, result.stderr[-3000:]
            assert endpoint.requests
            assert "Ruff" not in json.dumps(endpoint.requests)
        assert len(app.records(project)) == 1
    finally:
        memory.close()
