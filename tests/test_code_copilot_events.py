"""Portable contract/safety tests for Copilot's journal-backed identity."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from atmem.code.adapters.copilot_events import normalize_event, require_workspace_trust


def journal(tmp_path, monkeypatch, *, prompt="My preferred formatter is Ruff."):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "home"))
    session, invocation = str(uuid4()), str(uuid4())
    payload = {"sessionId": session, "timestamp": 1234, "cwd": str(tmp_path), "prompt": prompt}
    header = {"type": "session.start", "data": {"sessionId": session, "copilotVersion": "1.0.98"}}
    start = {"type": "hook.start", "data": {"hookType": "userPromptSubmitted", "input": payload,
                                                "hookInvocationId": invocation}}
    path = tmp_path / "home/session-state" / session / "events.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(header) + "\n" + json.dumps(start) + "\n")
    return path, {**payload, "event": "userPromptSubmitted"}, start


def test_identity_replay_and_distinct_identical_prompts(tmp_path, monkeypatch):
    path, payload, start = journal(tmp_path, monkeypatch)
    first = normalize_event(payload)
    assert normalize_event(payload) == first
    # An earlier owner hook completed; the current live invocation is unique.
    with path.open("a") as stream:
        stream.write(json.dumps({"type": "hook.end", "data": {"hookInvocationId": first["turn_id"]}}) + "\n")
        start["data"]["hookInvocationId"] = str(uuid4())
        stream.write(json.dumps(start) + "\n")
    assert normalize_event(payload)["turn_id"] != first["turn_id"]


@pytest.mark.parametrize("change", ["missing", "ambiguous", "wrong_version", "wrong_session", "mismatched_content", "symlink", "no_event", "traversal"])
def test_unverified_journal_is_refused(tmp_path, monkeypatch, change):
    path, payload, start = journal(tmp_path, monkeypatch)
    if change == "missing":
        path.unlink()
    elif change == "ambiguous":
        start["data"]["hookInvocationId"] = str(uuid4())
        with path.open("a") as stream:
            stream.write(json.dumps(start) + "\n")
    elif change in {"wrong_version", "wrong_session"}:
        text = path.read_text()
        path.write_text(text.replace('"1.0.98"', '"9.9.9"') if change == "wrong_version"
                        else text.replace(payload["sessionId"], str(uuid4()), 1))
    elif change == "mismatched_content":
        payload["prompt"] = "Different text"
    elif change == "symlink":
        original = path.with_name("original.jsonl")
        path.rename(original)
        try:
            path.symlink_to(original)
        except OSError:
            pytest.skip("symlinks unavailable on this platform")
    elif change == "no_event":
        del payload["event"]
    else:
        payload["sessionId"] = "../../other"
    with pytest.raises((ValueError, OSError)):
        normalize_event(payload)


def test_bounded_journal_tail(tmp_path, monkeypatch):
    path, payload, start = journal(tmp_path, monkeypatch)
    header = path.read_text().splitlines()[0]
    path.write_text(header + "\n" + json.dumps({"type": "system.message", "data": {"text": "x" * 2_100_000}})
                    + "\n" + json.dumps(start) + "\n" + '{"partial":')
    assert normalize_event(payload)["turn_id"] == start["data"]["hookInvocationId"]


def test_workspace_trust_is_required_and_never_written(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "home"))
    with pytest.raises(RuntimeError, match="approve workspace trust"):
        require_workspace_trust(tmp_path)
    assert not (tmp_path / "home").exists()
    (tmp_path / "home").mkdir()
    config = tmp_path / "home/config.json"
    config.write_text('// Managed automatically\n{ /*owner*/ "url":"https://example.com/*keep*/",\n'
                      '"trustedFolders": [' + json.dumps(str(tmp_path)) + ',],\n}')
    before = config.read_bytes()
    require_workspace_trust(tmp_path)
    assert config.read_bytes() == before
    (tmp_path / "home/settings.json").write_text('{"disableAllHooks":true}')
    with pytest.raises(RuntimeError, match="hooks are disabled"):
        require_workspace_trust(tmp_path)


def test_post_tool_result_is_evidence_not_a_canonical_fact(code_env, tmp_path, monkeypatch):
    from atmem.code.hook import enroll, handle
    from atmem.evidence.crypto import load_existing_key
    env = code_env
    env.memory.store.put_code_installation(subject_id="local", project_id=env.project, host="copilot", enabled=True)
    credential_file = tmp_path / "credential"
    enroll(env.app, project=env.project, root=str(env.root), profile="shared", agent="copilot", host="copilot",
           credential_file=str(credential_file))
    path, payload, start = journal(tmp_path, monkeypatch)
    native = {key: value for key, value in payload.items() if key not in {"event", "prompt"}}
    native.update(toolName="bash", toolResult={"resultType": "success", "textResultForLlm": "Our project uses SQLite."})
    start["data"].update(hookType="postToolUse", input=native)
    path.write_text(path.read_text() + json.dumps(start) + "\n")
    assert handle(env.app, project=env.project, credential=load_existing_key(credential_file),
                  payload={**native, "event": "postToolUse"}) == {}
    assert env.app.records(env.project) == []
    rows = env.memory.store.list_code_observations(subject_id="local", project_id=env.project,
                                                  profile_id="shared", agent_id="copilot", state="refused", limit=10)
    assert len(rows) == 1


def test_copilot_replay_pause_secrets_and_scope(code_env, tmp_path, monkeypatch):
    from atmem.code.hook import enroll, handle
    from atmem.evidence.crypto import load_existing_key
    env = code_env
    env.memory.store.put_code_installation(subject_id="local", project_id=env.project, host="copilot", enabled=True)
    credential_file = tmp_path / "credential"
    enroll(env.app, project=env.project, root=str(env.root), profile="shared", agent="copilot", host="copilot",
           credential_file=str(credential_file))
    credential = load_existing_key(credential_file)
    path, payload, start = journal(tmp_path, monkeypatch)
    assert handle(env.app, project=env.project, credential=credential, payload=payload) == {}
    assert handle(env.app, project=env.project, credential=credential, payload=payload) == {}
    assert len(env.app.records(env.project)) == 1
    # Missing/forged invocation cannot create records.
    with pytest.raises(ValueError):
        handle(env.app, project=env.project, credential=credential, payload={**payload, "prompt": "forged"})
    with pytest.raises(PermissionError):
        handle(env.app, project=env.project, credential=b"x" * 32, payload=payload)
    # A real second event carries a distinct host-issued ID and recalls once.
    start["data"]["input"]["prompt"] = "Which formatter should I use?"
    start["data"]["hookInvocationId"] = str(uuid4())
    path.write_text(path.read_text() + json.dumps(start) + "\n")
    second = {**start["data"]["input"], "event": "userPromptSubmitted"}
    output = handle(env.app, project=env.project, credential=credential, payload=second)
    assert "Ruff" in output["additionalContext"]
    env.memory.store.set_code_installation_enabled(subject_id="local", project_id=env.project, host="copilot", enabled=False)
    assert handle(env.app, project=env.project, credential=credential, payload=second) == {}
    saved = path.read_bytes()
    path.unlink()
    assert handle(env.app, project=env.project, credential=credential, payload=second) == {}
    path.write_bytes(saved)
    env.memory.store.set_code_installation_enabled(subject_id="local", project_id=env.project, host="copilot", enabled=True)
    start["data"]["input"]["prompt"] = "My API key is sk-proj-" + "A1b2C3d4" * 12
    start["data"]["hookInvocationId"] = str(uuid4())
    path.write_text(path.read_text() + json.dumps(start) + "\n")
    assert handle(env.app, project=env.project, credential=credential,
                  payload={**start["data"]["input"], "event": "userPromptSubmitted"}) == {}
    assert len(env.app.records(env.project)) == 1
    start["data"]["input"]["cwd"] = str(tmp_path / "unrelated")
    (tmp_path / "unrelated").mkdir()
    start["data"]["hookInvocationId"] = str(uuid4())
    path.write_text(path.read_text() + json.dumps(start) + "\n")
    with pytest.raises(PermissionError):
        handle(env.app, project=env.project, credential=credential,
               payload={**start["data"]["input"], "event": "userPromptSubmitted"})
