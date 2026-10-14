import json

import pytest


@pytest.mark.parametrize("module,name", [("muse", "MuseAdapter"), ("claude", "ClaudeAdapter"),
                                         ("grok", "GrokAdapter"), ("copilot", "CopilotAdapter"), ("codex", "CodexAdapter")])
def test_host_configuration_preserves_owner_values_and_is_idempotent(tmp_path, module, name, monkeypatch):
    monkeypatch.setattr("atmem.code.adapters.json_hooks.shutil.which", lambda _: None)
    from importlib import import_module
    adapter = getattr(import_module("atmem.code.adapters." + module), name)(tmp_path, "python -m atmem.code.hook --db example.db")
    previous = json.dumps({"version": 1, "owner": "preserve", "hooks": {"OtherEvent": []}}).encode()
    configured = adapter.planned_configuration(previous)
    value = json.loads(configured)
    assert value["owner"] == "preserve" and "OtherEvent" in value["hooks"]
    assert adapter.planned_configuration(configured) == configured
    assert adapter.verify_installed().automatic is False


def test_hook_enrollment_capture_recall_pause_and_retry(code_env, tmp_path):
    from atmem.code.hook import enroll, handle
    from atmem.evidence.crypto import load_existing_key
    env = code_env
    env.memory.store.put_code_installation(subject_id="local", project_id=env.project, host="codex", enabled=True)
    credential_file = tmp_path / "credential"
    enroll(env.app, project=env.project, root=str(env.root), profile="shared", agent="codex", host="codex", credential_file=str(credential_file))
    credential = load_existing_key(credential_file)
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "host-session", "turn_id": "turn-1",
               "cwd": str(env.root), "prompt": "Remember that my preferred formatter is Ruff."}
    assert handle(env.app, project=env.project, credential=credential, payload=payload) == {}
    assert len(env.app.records(env.project)) == 1
    assert handle(env.app, project=env.project, credential=credential, payload=payload) == {}
    assert len(env.app.records(env.project)) == 1
    recalled = handle(env.app, project=env.project, credential=credential, payload={**payload, "turn_id": "turn-2", "prompt": "Which formatter should I use?"})
    assert "Ruff" in recalled["hookSpecificOutput"]["additionalContext"]
    env.memory.store.set_code_installation_enabled(subject_id="local", project_id=env.project, host="codex", enabled=False)
    assert handle(env.app, project=env.project, credential=credential, payload={**payload, "turn_id": "turn-3"}) == {}
    with pytest.raises(PermissionError):
        handle(env.app, project=env.project, credential=b"x" * 32, payload=payload)
