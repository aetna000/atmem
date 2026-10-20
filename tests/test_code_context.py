from dataclasses import replace


def test_context_budget_lifecycle_and_timeout(code_env, monkeypatch):
    from atmem.code.context import build_context
    from atmem.code.contracts import CodeContextRequest
    import atmem.code.context as context
    env = code_env
    old = env.seed()
    env.app.correct(env.project, old, "My preferred formatter is Black.")
    request = CodeContextRequest("request-1", "session-1", "turn-1", "formatter", 256, env.scope)
    package = build_context(env.memory, request)
    assert "Ruff" not in package.content
    assert len(package.content.encode()) <= 256
    calls = iter([0.0, 2.0])
    monkeypatch.setattr(context.time, "monotonic", lambda: next(calls, 2.0))
    assert build_context(env.memory, request, timeout_ms=1).content == ""


def test_source_dependent_assertions_withhold_on_edit_or_revision_change(code_env):
    import subprocess
    from atmem.code.contracts import CodeContextRequest, CodeObservation
    from atmem.code.context import build_context
    from atmem.code.formation import CodeFormation
    from atmem.code.identity import repository_key
    from atmem.code.receipts import CodeReceipts
    import pytest
    env = code_env
    subprocess.run(["git", "init", "-q", str(env.root)], check=True)
    env.memory.store.bind_code_project(subject_id="local", repository_key=repository_key(env.root), project_id=env.project, remote_sha256=None)
    source = env.root / "module.py"
    source.write_text("# baseline\n")
    subprocess.run(["git", "-C", str(env.root), "add", "module.py"], check=True)
    def commit():
        subprocess.run(["git", "-C", str(env.root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-am", "fixture"], check=True, capture_output=True)
    commit()
    revision = subprocess.run(["git", "-C", str(env.root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    observation = CodeObservation("event-code", "session-1", "turn-1", "codex", "user_turn", "Our project uses SQLite for persistence.",
                                  "2026-10-14T10:00:00Z", "user:turn-1", revision, env.scope)
    assert CodeFormation(env.memory).form(observation)["formed"]
    (env.root / ".claude").mkdir()
    (env.root / ".claude/settings.local.json").write_text('{"hooks":{}}')
    request = CodeContextRequest("request-code", "session-2", "turn-2", "project persistence SQLite", 4096, env.scope)
    package = build_context(env.memory, request, repository_root=str(env.root))
    assert "SQLite" in package.content
    receipts = CodeReceipts(env.memory.store)
    receipts.prepare(request, package, host="codex", repository_root=str(env.root))
    source.write_text("# changed implementation\n")
    assert build_context(env.memory, request, repository_root=str(env.root)).content == ""
    with pytest.raises(PermissionError, match="repository changed"):
        receipts.submitted(request, package, host="codex")
    commit()
    assert build_context(env.memory, request, repository_root=str(env.root)).content == ""
    # Historical assertions remain inspectable; withholding is not deletion.
    assert env.app.records(env.project)[0]["content"] == observation.content
