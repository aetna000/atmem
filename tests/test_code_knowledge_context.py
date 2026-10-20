from hashlib import sha256

import pytest

from atmem.code.contracts import CodeContextRequest, CodeContextPackage
from atmem.code.receipts import CodeReceipts
from atmem.knowledge.projections import CodeKnowledge
from tests.test_knowledge_lifecycle import init_repository, FixtureWorker


def test_rich_context_budget_and_final_source_race(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    context = knowledge.context(str(env.root), "main function", budget=512)
    assert "main.py:1" in context["content"] and "AtMem structure" in context["content"]
    assert len(context["content"].encode()) <= 512
    request = CodeContextRequest("rich-request", "session", "turn", "main function", 512, env.scope)
    package = CodeContextPackage(request.request_id, context["content"], sha256(context["content"].encode()).hexdigest(), ())
    service = CodeReceipts(env.memory.store)
    service.prepare(request, package, host="codex", graph_evidence=context["evidence"], repository_root=str(env.root))
    (env.root / "new_dependency.py").write_text("import main\n")
    with pytest.raises(PermissionError, match="rich structure changed"):
        service.submitted(request, package, host="codex")


def test_rich_context_zero_budget_or_irrelevant_task_stays_empty(code_env):
    env = code_env
    init_repository(env)
    knowledge = CodeKnowledge(env.app, env.scope)
    knowledge.index(str(env.root), FixtureWorker())
    assert knowledge.context(str(env.root), "main", budget=0)["content"] == ""
    assert knowledge.context(str(env.root), "unrelated unusual topic", budget=512)["content"] == ""
