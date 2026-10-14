"""Codex wire probes vet generated fixtures, not the owner's global hooks."""

import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt" or os.environ.get("ATMEM_CODE_SKIP_HOST_PROBES") == "1",
                                reason="Installed-host probes are qualified separately from the portable core")


def test_installed_codex_prompt_hook_reaches_local_model_endpoint(tmp_path):
    if not shutil.which("codex"):
        pytest.skip("Codex is not installed")
    fixtures = Path(__file__).parent / "fixtures"
    endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
    runner = runpy.run_path(str(fixtures / "codex_runner.py"))["run_codex"]
    with endpoint_type() as endpoint:
        result = runner(tmp_path, shlex.join([sys.executable, str(fixtures / "muse_canary_hook.py")]), "Reply probe complete.", endpoint)
        assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-1000:]
        assert (tmp_path / "muse-hook-fired").exists(), result.stderr[-1000:]
        assert any("ATMEM_CODE_CANARY_7e46a92f" in json.dumps(value) for value in endpoint.requests)


def test_installed_codex_capture_then_claude_new_session_recall(tmp_path):
    if not shutil.which("codex") or not shutil.which("claude"):
        pytest.skip("Both installed coding hosts are required")
    pytest.importorskip("sqlcipher3")
    from atmem.code.application import CodeApplication
    from atmem.code.install import CodeInstall
    from atmem.code.hook import enroll
    from atmem.code import hook
    from atmem.code.adapters.claude import ClaudeAdapter
    from atmem.code.adapters.probe import claude_probe
    from atmem.evidence.crypto import load_existing_key
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    database = tmp_path / "memory.db"
    HouseholdApplication.initialize(database, encrypted=True)
    root = tmp_path / "project with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    memory = Memory(database, auto_vectors=False)
    try:
        installer = CodeInstall(memory.store)
        scope = installer.setup(root, subject_id="local", profile_id="shared", agent_id="codex", host="codex", apply=True)["scope"]
        project = scope["project_id"]
        # Production activation must not bypass the user's persistent hook trust.
        memory.store.set_code_installation_enabled(subject_id="local", project_id=project, host="codex", enabled=True)
        credential_file = tmp_path / "codex.credential"
        enroll(CodeApplication(memory, subject_id="local"), project=project, root=str(root), profile="shared", agent="codex",
               host="codex", credential_file=str(credential_file))
        fixtures = Path(__file__).parent / "fixtures"
        command = shlex.join([sys.executable, str(fixtures / "code_hook_capture.py"), str(Path(hook.__file__).resolve()), "--db", str(database), "--subject", "local",
                              "--project-id", project, "--credential-file", str(credential_file)])
        runner = runpy.run_path(str(fixtures / "codex_runner.py"))["run_codex"]
        endpoint_type = runpy.run_path(str(fixtures / "responses_endpoint.py"))["ResponsesEndpoint"]
        with endpoint_type() as endpoint:
            run = runner(root, command, "Remember that my preferred formatter is Ruff.", endpoint)
            assert run.returncode == 0, run.stderr[-2000:]
        app = CodeApplication(memory, subject_id="local")
        records = app.records(project)
        assert records, (root / "code-hook-input.json").read_text() + run.stderr[-2000:]
        assert "Ruff" in records[0]["content"]
        installer.setup(root, subject_id="local", profile_id="shared", agent_id="claude", host="claude", apply=True)
        active = installer.enable(project=root, subject_id="local", host="claude")
        settings = json.loads((root / ".claude/settings.local.json").read_text())
        claude_command = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        argv = shlex.split(claude_command)
        receipt = claude_probe(store=memory.store, subject="local", project=project, root=root,
                              credential=load_existing_key(argv[argv.index("--credential-file") + 1]),
                              initial=ClaudeAdapter(root, claude_command).probe(), command=claude_command,
                              canary_mode=False, prompt_override="Which formatter should I use?", expected_context="Ruff")
        assert receipt.automatic and active["enabled"]
    finally:
        memory.close()
