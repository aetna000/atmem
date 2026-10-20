import subprocess


def test_graph_freshness_ignores_and_source_references(code_env):
    from atmem.code.graph import CodeGraph
    env = code_env
    subprocess.run(["git", "init", str(env.root)], capture_output=True, check=True)
    # Identity changes when a non-Git directory becomes a Git repository.
    from atmem.code.identity import repository_key
    env.memory.store.bind_code_project(subject_id="local", repository_key=repository_key(env.root),
                                       project_id=env.project, remote_sha256=None)
    (env.root / "main.py").write_text("import os\ndef run():\n    return os.getcwd()\n")
    (env.root / ".gitignore").write_text("ignored.py\n")
    (env.root / "ignored.py").write_text("def hidden(): pass\n")
    (env.root / "readme.txt").write_text("plain text")
    subprocess.run(["git", "-C", str(env.root), "add", "main.py", ".gitignore"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(env.root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "fixture"], check=True, capture_output=True)
    env.app.settings(env.project, {"graph_enabled": True})
    graph = CodeGraph(env.app, env.project)
    graph.index(str(env.root))
    result = graph.query(str(env.root), "run")
    assert result["status"] == "current"
    assert result["nodes"][0]["path"] == "main.py"
    assert graph.query(str(env.root), "hidden")["nodes"] == []
    fallback = graph.query(str(env.root), "readme.txt")
    assert fallback["nodes"][0]["language_support"] == "file_only"
    from atmem.code.contracts import CodeContextRequest, CodeObservation
    from atmem.code.runtime import CodeRuntime
    from atmem.code.service import CodeIntakeService
    from atmem.code.receipts import CodeReceipts
    env.memory.store.put_code_installation(subject_id="local", project_id=env.project, host="codex", enabled=True)
    intake = CodeIntakeService(env.memory.store, scope=env.scope, host="codex", session_id="session-1", secret=b"x" * 32, enabled=True)
    observation = CodeObservation("event-graph", "session-1", "turn-graph", "codex", "user_turn", "Find the run function.",
                                  "2026-10-14T10:00:00Z", "user:graph", None, env.scope)
    request = CodeContextRequest("request-graph", "session-1", "turn-graph", observation.content, 4096, env.scope)
    context = CodeRuntime(env.memory, intake).on_user_turn(request, observation, intake.sign(observation), repository_root=str(env.root))["context"]
    assert "main.py" in context.content and "run" in context.content
    (env.root / "main.py").write_text("def newer(): pass\n")
    import pytest
    with pytest.raises(PermissionError, match="graph file changed"):
        CodeReceipts(env.memory.store).submitted(request, context, host="codex")
    stale = graph.query(str(env.root), "run")
    assert stale["status"] == "stale" and stale["nodes"] == []
    graph.index(str(env.root))
    assert graph.query(str(env.root), "newer")["status"] == "current"
    subprocess.run(["git", "-C", str(env.root), "checkout", "-b", "different-branch"], check=True, capture_output=True)
    assert graph.query(str(env.root), "newer")["status"] == "stale"
