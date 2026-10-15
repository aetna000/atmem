"""Actual CLI sessions distinguish controlled wiring from normal activation."""

import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ATMEM_CODE_SKIP_HOST_PROBES") == "1",
                                reason="Installed host sessions are qualified separately")


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_controlled_host_capture_new_session_recall_and_pause(tmp_path, host):
    if not shutil.which(host):
        pytest.skip(host + " is not installed")
    pytest.importorskip("sqlcipher3")
    from atmem.code.application import CodeApplication
    from atmem.code.hook import enroll
    from atmem.code import hook
    from atmem.code.install import CodeInstall
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
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
        app = CodeApplication(memory, subject_id="local")
        if host == "codex" or os.name == "nt":
            with pytest.raises(RuntimeError, match="not yet verified"):
                installer.enable(project=root, subject_id="local", host=host)
        # Deliberate fixture-only activation: do not claim normal onboarding.
        memory.store.set_code_installation_enabled(subject_id="local", project_id=project, host=host, enabled=True)
        credential = tmp_path / (host + ".credential")
        enroll(app, project=project, root=str(root), profile="shared", agent=host, host=host, credential_file=str(credential))
        argv = [sys.executable, str(Path(hook.__file__).resolve()), "--db", str(db), "--subject", "local",
                "--project-id", project, "--credential-file", str(credential)]
        fixtures = Path(__file__).parent / "fixtures"
        if host == "codex":
            argv.insert(1, str(fixtures / "code_hook_capture.py"))
        endpoint_name = "AnthropicEndpoint" if host == "claude" else "ResponsesEndpoint"
        endpoint_file = "anthropic_endpoint.py" if host == "claude" else "responses_endpoint.py"
        endpoint_type = runpy.run_path(str(fixtures / endpoint_file))[endpoint_name]
        runner = runpy.run_path(str(fixtures / (host + "_runner.py")))["run_" + host]
        shape_command = runpy.run_path(str(fixtures / "host_process.py"))["hook_command"]
        command = argv if host == "claude" else shape_command(argv)
        for prompt, expected_context in [("My preferred formatter is Ruff.", False), ("Which formatter should I use?", True)]:
            with endpoint_type() as endpoint:
                result = runner(root, command, prompt, endpoint)
                assert result.returncode == 0, result.stderr[-3000:] + result.stdout[-1000:]
                assert endpoint.requests
                if expected_context:
                    assert "Ruff" in json.dumps(endpoint.requests)
            records = app.records(project)
            assert len(records) == 1 and "Ruff" in records[0]["content"], result.stderr[-5000:] + result.stdout[-1000:]
        installer.disable(project=root, subject_id="local", host=host)
        with endpoint_type() as endpoint:
            result = runner(root, command, "My preferred test runner is pytest. Which formatter should I use?", endpoint)
            assert result.returncode == 0, result.stderr[-3000:]
            assert "Ruff" not in json.dumps(endpoint.requests)
        assert len(app.records(project)) == 1
    finally:
        memory.close()


@pytest.mark.parametrize("trust_bypass", [False, True])
def test_codex_hook_trust_requires_explicit_fixture_bypass(tmp_path, trust_bypass):
    if not shutil.which("codex"):
        pytest.skip("Codex is not installed")
    fixtures = Path(__file__).parent / "fixtures"
    endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
    runner = runpy.run_path(str(fixtures / "codex_runner.py"))["run_codex"]
    argv = [sys.executable, str(fixtures / "muse_canary_hook.py")]
    command = runpy.run_path(str(fixtures / "host_process.py"))["hook_command"](argv)
    with endpoint_type() as endpoint:
        result = runner(tmp_path, command, "Reply probe complete.", endpoint, trust_bypass=trust_bypass)
        assert result.returncode == 0, result.stderr[-3000:]
        assert endpoint.requests
        assert ("ATMEM_CODE_CANARY_7e46a92f" in json.dumps(endpoint.requests)) is trust_bypass
    assert (tmp_path / "muse-hook-fired").exists() is trust_bypass
