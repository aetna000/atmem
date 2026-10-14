import pytest


def test_receipt_retains_bytes_and_requires_independent_delivery_evidence(code_env):
    from atmem.code.context import build_context
    from atmem.code.contracts import CodeContextRequest
    from atmem.code.receipts import CodeReceipts
    env = code_env
    env.seed()
    request = CodeContextRequest("request-1", "session-1", "turn-1", "formatter", 2048, env.scope)
    package = build_context(env.memory, request)
    receipts = CodeReceipts(env.memory.store)
    prepared = receipts.prepare(request, package, host="codex")
    assert prepared["assurance"] is None
    assert prepared["package"]["content"] == package.content
    assert receipts.submitted(request, package, host="codex")["assurance"] == "submitted"
    with pytest.raises(PermissionError):
        receipts.acknowledge(request, host="codex", content_sha256=package.content_sha256,
                             observation={"reported": True}, verify=lambda _: False)
    with pytest.raises(PermissionError):
        receipts.observe_model_input(request, model_input=package.content, observation={}, verify=lambda *_: False)


def test_deletion_between_preparation_and_submission_withholds_context(code_env):
    from atmem.code.context import build_context
    from atmem.code.contracts import CodeContextRequest
    from atmem.code.receipts import CodeReceipts
    env = code_env
    record = env.seed()
    request = CodeContextRequest("request-1", "session-1", "turn-1", "formatter", 2048, env.scope)
    package = build_context(env.memory, request)
    receipts = CodeReceipts(env.memory.store)
    receipts.prepare(request, package, host="codex")
    env.app.forget(env.project, record)
    with pytest.raises(PermissionError):
        receipts.submitted(request, package, host="codex")
