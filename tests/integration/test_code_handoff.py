from dataclasses import replace


def test_two_host_sessions_share_project_memory_but_preserve_private_lane(code_env, tmp_path):
    from atmem.code.hook import enroll, handle
    from atmem.evidence.crypto import load_existing_key
    env = code_env
    credentials = {}
    for host in ("codex", "claude"):
        env.memory.store.put_code_installation(subject_id="local", project_id=env.project, host=host, enabled=True)
        path = tmp_path / (host + ".credential")
        enroll(env.app, project=env.project, root=str(env.root), profile="shared", agent=host, host=host, credential_file=str(path))
        credentials[host] = load_existing_key(path)
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "codex-session", "turn_id": "turn-1",
               "cwd": str(env.root), "prompt": "Remember that my preferred formatter is Ruff."}
    handle(env.app, project=env.project, credential=credentials["codex"], payload=payload)
    env.seed("Remember that my preferred editor is SecretPrivateEditor.", profile="private", agent="codex")
    result = handle(env.app, project=env.project, credential=credentials["claude"],
                    payload={**payload, "session_id": "claude-session", "prompt": "Which formatter and editor should I use?"})
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "Ruff" in context and "SecretPrivateEditor" not in context
    assert "source" in context


def test_review_workflow_changes_admission_and_can_be_completed(code_env, tmp_path):
    from atmem.code.hook import enroll, handle
    from atmem.evidence.crypto import load_existing_key
    env = code_env
    env.memory.store.put_code_installation(subject_id="local", project_id=env.project, host="codex", enabled=True)
    key = tmp_path / "credential"
    enroll(env.app, project=env.project, root=str(env.root), profile="shared", agent="codex", host="codex", credential_file=str(key))
    env.app.settings(env.project, {"review_workflow": True})
    handle(env.app, project=env.project, credential=load_existing_key(key), payload={
        "hook_event_name": "UserPromptSubmit", "session_id": "session-1", "turn_id": "turn-1", "cwd": str(env.root),
        "prompt": "Remember that my preferred formatter is Ruff."})
    assert env.app.records(env.project) == []
    reviews = env.app.dispatch("reviews", {"project_id": env.project})["reviews"]
    assert len(reviews) == 1
    env.app.dispatch("review", {"project_id": env.project, "event_id": reviews[0]["event_id"], "decision": "approve"})
    assert "Ruff" in env.app.records(env.project)[0]["content"]
