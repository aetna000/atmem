"""Installed Copilot wire tests; no owner settings or paid inference."""

import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ATMEM_CODE_SKIP_HOST_PROBES") == "1",
                                reason="Installed-host probes are qualified separately from the portable core")


def test_installed_copilot_startup_context_reaches_model(tmp_path):
    if not shutil.which("copilot"):
        pytest.skip("Copilot CLI is not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    fixtures = Path(__file__).parent / "fixtures"
    endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
    runner = runpy.run_path(str(fixtures / "copilot_runner.py"))["run_copilot"]
    command = [sys.executable, str(fixtures / "copilot_canary_hook.py")]
    with endpoint_type() as endpoint:
        result = runner(tmp_path, command, "Reply probe complete.", endpoint)
        assert result.returncode == 0, result.stderr[-3000:] + result.stdout[-1000:]
        assert (tmp_path / "copilot-hook-inputs.jsonl").exists(), result.stderr[-3000:]
        wire = json.dumps(endpoint.requests)
        assert "ATMEM_COPILOT_STARTUP_7e46a92f" in wire
        # Installed 1.0.98 consumes this despite the current reference saying
        # command-hook userPromptSubmitted output is dropped.
        assert "ATMEM_COPILOT_PROMPT_7e46a92f" in wire
        payloads = [json.loads(line) for line in (tmp_path / "copilot-hook-inputs.jsonl").read_text().splitlines()]
        prompt = next(value for value in payloads if "prompt" in value)
        assert prompt["prompt"] == "Reply probe complete."
        assert not set(prompt).intersection({"event", "hook_event_name", "hookEventName", "turn_id", "promptId", "prompt_id"})


def test_installed_copilot_capture_recall_pause_resume_uninstall(tmp_path, monkeypatch):
    if not shutil.which("copilot"):
        pytest.skip("Copilot CLI is not installed")
    pytest.importorskip("sqlcipher3")
    from atmem.code.application import CodeApplication
    from atmem.code.install import CodeInstall
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication

    root = tmp_path / "project with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    try:
        installer = CodeInstall(memory.store)
        project = installer.setup(root, subject_id="local", profile_id="shared", agent_id="copilot",
                                  host="copilot", apply=True)["scope"]["project_id"]
        home = tmp_path / "project with spaces-copilot-home"
        home.mkdir()
        monkeypatch.setenv("COPILOT_HOME", str(home))
        config_path = root / ".github/hooks/atmem-code.json"
        config_path.parent.mkdir(parents=True)
        original = json.dumps({"version": 1, "owner": "preserve", "hooks": {"userPromptSubmitted": [
            {"type": "command", "exec": sys.executable, "args": ["-c", "print('{}')"]}]}}).encode()
        config_path.write_bytes(original)
        with pytest.raises(RuntimeError, match="approve workspace trust"):
            installer.enable(project=root, subject_id="local", host="copilot")
        assert config_path.read_bytes() == original
        (home / "config.json").write_text(json.dumps({"trustedFolders": [str(root.resolve())]}))
        assert installer.enable(project=root, subject_id="local", host="copilot")["enabled"]
        app = CodeApplication(memory, subject_id="local")
        # Fresh setup is index-first; full-content recall remains opt-in.
        app.settings(project, {'context_mode': 'content'})
        fixtures = Path(__file__).parent / "fixtures"
        endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
        runner = runpy.run_path(str(fixtures / "copilot_runner.py"))["run_copilot"]
        with endpoint_type() as endpoint:
            result = runner(root, None, "My preferred formatter is Ruff.", endpoint, configure=False)
            assert result.returncode == 0, result.stderr[-3000:]
            assert endpoint.requests
        records = app.records(project)
        assert len(records) == 1 and "Ruff" in records[0]["content"]
        with endpoint_type() as endpoint:
            result = runner(root, None, "Which formatter should I use?", endpoint, configure=False)
            assert result.returncode == 0, result.stderr[-3000:]
            assert "Ruff" in json.dumps(endpoint.requests)
        # Resume an existing session and submit an identical prompt again.
        sessions = list((home / "session-state").iterdir())
        session = max(sessions, key=lambda path: path.stat().st_mtime).name
        with endpoint_type() as endpoint:
            result = runner(root, None, "Which formatter should I use?", endpoint, configure=False, resume=session)
            assert result.returncode == 0, result.stderr[-3000:]
            assert "Ruff" in json.dumps(endpoint.requests)
        rows = memory.store.code_documents("local", project, "exposure")
        assert len(rows) >= 3
        assert all(row["assurance"] == "submitted" for row in rows if row["state"] == "submitted")
        count = len(app.records(project))
        installer.disable(project=root, subject_id="local", host="copilot")
        with endpoint_type() as endpoint:
            result = runner(root, None, "My preferred test runner is pytest. Which formatter should I use?", endpoint, configure=False)
            assert result.returncode == 0, result.stderr[-3000:]
            assert "Ruff" not in json.dumps(endpoint.requests)
        assert len(app.records(project)) == count
        assert installer.enable(project=root, subject_id="local", host="copilot")["enabled"]
        with endpoint_type() as endpoint:
            result = runner(root, None, "Which formatter should I use?", endpoint, configure=False)
            assert result.returncode == 0, result.stderr[-3000:]
            assert "Ruff" in json.dumps(endpoint.requests)
        installer.disable(project=root, subject_id="local", host="copilot")
        installer.uninstall(project=root, subject_id="local", host="copilot")
        assert config_path.read_bytes() == original
        from atmem.code.adapters.base import HostProbe
        monkeypatch.setattr("atmem.code.adapters.copilot_probe.copilot_probe", lambda **kw: HostProbe(
            "copilot", kw["initial"].version, kw["initial"].platform, False, False, "submitted", None))
        # Use a fresh installer so failure exercises normal registry/probe wiring.
        installer.setup(root, subject_id="local", profile_id="shared", agent_id="copilot", host="copilot", apply=True)
        with pytest.raises(RuntimeError, match="did not verify"):
            CodeInstall(memory.store).enable(project=root, subject_id="local", host="copilot")
        assert config_path.read_bytes() == original
        assert not installer.status(project=root, subject_id="local", host="copilot")["enabled"]
    finally:
        memory.close()


def test_installed_copilot_memory_is_available_to_claude(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("Claude automatic activation is not qualified on Windows")
    if not shutil.which("copilot") or not shutil.which("claude"):
        pytest.skip("Both installed coding hosts are required")
    pytest.importorskip("sqlcipher3")
    from atmem.code.install import CodeInstall
    from atmem.code.adapters.claude import ClaudeAdapter
    from atmem.code.adapters.probe import claude_probe
    from atmem.evidence.crypto import load_existing_key
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    root = tmp_path / "project with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    home = tmp_path / "project with spaces-copilot-home"
    home.mkdir()
    (home / "config.json").write_text(json.dumps({"trustedFolders": [str(root.resolve())]}))
    monkeypatch.setenv("COPILOT_HOME", str(home))
    try:
        installer = CodeInstall(memory.store)
        project = installer.setup(root, subject_id="local", profile_id="shared", agent_id="copilot",
                                  host="copilot", apply=True)["scope"]["project_id"]
        installer.enable(project=root, subject_id="local", host="copilot")
        fixtures = Path(__file__).parent / "fixtures"
        endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
        runner = runpy.run_path(str(fixtures / "copilot_runner.py"))["run_copilot"]
        with endpoint_type() as endpoint:
            result = runner(root, None, "My preferred formatter is Ruff.", endpoint, configure=False)
            assert result.returncode == 0, result.stderr[-3000:]
        from atmem.code.application import CodeApplication
        CodeApplication(memory, subject_id='local').settings(project, {'context_mode': 'content'})
        installer.setup(root, subject_id="local", profile_id="shared", agent_id="claude", host="claude", apply=True)
        assert installer.enable(project=root, subject_id="local", host="claude")["enabled"]
        config = json.loads((root / ".claude/settings.local.json").read_text())
        command = config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        argv = shlex.split(command)
        receipt = claude_probe(store=memory.store, subject="local", project=project, root=root,
                              credential=load_existing_key(argv[argv.index("--credential-file") + 1]),
                              initial=ClaudeAdapter(root, command).probe(), command=command,
                              canary_mode=False,
                              prompt_override="My preferred test runner is pytest. Which formatter should I use?", expected_context="Ruff")
        assert receipt.automatic
        # Both hosts are now normally enabled; shared memory still reaches Copilot.
        with endpoint_type() as endpoint:
            result = runner(root, None, "Which formatter and test runner should I use?", endpoint, configure=False)
            assert result.returncode == 0, result.stderr[-3000:]
            assert "Ruff" in json.dumps(endpoint.requests)
            assert "pytest" in json.dumps(endpoint.requests)
    finally:
        memory.close()
