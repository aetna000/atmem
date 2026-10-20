"""Host configuration fixtures only, not an actual host or solver result."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from benchmarks.code_replay.progressive import configuration, arguments


def test_configuration_preserves_venv_path_and_exact_tool_allowlist(tmp_path):
    venv = tmp_path / "venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)
    database = tmp_path / "memory.db"
    database.touch()
    dependencies = tmp_path / "site-packages"
    dependencies.mkdir()
    scope = SimpleNamespace(subject_id="owner", project_id="project", profile_id="shared", agent_id="codex")
    config = configuration(venv / "python", [dependencies], database=database, root=tmp_path, scope=scope)
    assert config["command"] == str(venv / "python")
    encoded = arguments(config)[1]
    assert encoded.startswith("mcp_servers.atmem_code={") and "required=true" in encoded
    assert 'enabled_tools=["code_search", "code_explore", "code_source"]' in encoded
    assert arguments(None) == []
    focused = configuration(venv / "python", [dependencies], database=database, root=tmp_path, scope=scope, focused=True)
    assert focused["enabled_tools"] == ["code_context", "code_search", "code_explore", "code_source"]
    assert "code_context" in arguments(focused)[1]
    changed = {**config, "enabled_tools": ["memory_forget"]}
    with pytest.raises(ValueError):
        arguments(changed)


def test_arbitrary_dependency_directory_is_not_an_installed_runtime(tmp_path):
    database = tmp_path / "memory.db"
    database.touch()
    with pytest.raises(ValueError, match="dependency"):
        configuration(sys.executable, [tmp_path], database=database, root=tmp_path, scope=None)


def test_only_exact_notice_is_receipted_as_submitted(code_env):
    from hashlib import sha256
    from atmem.code.contracts import CodeContextRequest, CodeContextPackage
    from atmem.code.receipts import CodeReceipts
    from atmem.knowledge.projections import CodeKnowledge
    from benchmarks.code_replay.progressive import prepare_navigation
    from tests.test_knowledge_lifecycle import init_repository, FixtureWorker
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    source = knowledge.context(str(env.root), "main", budget=2048)
    request = CodeContextRequest("source-pack", "session", "turn", "main", 2048, env.scope)
    package = CodeContextPackage(request.request_id, source["content"], sha256(source["content"].encode()).hexdigest(), ())
    service = CodeReceipts(env.memory.store)
    exposure = service.prepare(request, package, host="codex", graph_evidence=source["evidence"], repository_root=str(env.root))
    lane = SimpleNamespace(knowledge=knowledge, root=env.root, memory=env.memory)
    prepared = prepare_navigation(lane, {"request": request, "package": package, "exposure": exposure, "context_ms": 1})
    assert "no implementation" in prepared["package"].content and "def main" not in prepared["package"].content
    service.submitted(prepared["request"], prepared["package"], host="codex")
    original = env.memory.store.code_document(env.scope.subject_id, env.project, "exposure", request.request_id)
    assert original["state"] == "prepared"
    assert prepared["request"].request_id != request.request_id


def test_actual_mcp_source_observation_requires_exact_frozen_bytes():
    import base64
    import json
    from hashlib import sha256
    from benchmarks.code_replay.progressive import source_observations
    raw = b"def main():\n    return 1\n"
    generation = {"snapshot_id": "a" * 64, "source_bytes": {"main.py": base64.b64encode(raw).decode()}}
    answer = {"status": "current", "snapshot_id": "a" * 64, "path": "main.py",
              "source_sha256": sha256(raw).hexdigest(), "content": "def main():\n    return 1"}
    event = {"type": "item.completed", "item": {"type": "mcp_tool_call", "id": "one", "server": "atmem_code",
             "tool": "code_source", "status": "completed", "arguments": {"path": "main.py", "line_count": 2},
             "result": {"content": [{"type": "text", "text": json.dumps(answer)}]}}}
    assert len(source_observations([event], generation)) == 1
    answer["content"] += " invented"
    event["item"]["result"]["content"][0]["text"] = json.dumps(answer)
    with pytest.raises(ValueError, match="bytes"):
        source_observations([event], generation)
