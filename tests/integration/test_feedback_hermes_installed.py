"""Actual imported Hermes candidate dispatch with real AtMem encrypted storage.

Run in the candidate's own Python environment, with PYTHONPATH pointing to this
AtMem checkout and its tests, ATMEM_HERMES_CANDIDATE=/reviewed/source. No Hermes
CLI/bootstrap, model, global launcher, owner Home or production effect is used.
Trusted-store synthetic qualifications test consumers, never prove efficacy.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def installed(tmp_path, monkeypatch):
    root = os.environ.get("ATMEM_HERMES_CANDIDATE")
    if not root:
        pytest.skip("explicit pinned Hermes candidate environment required")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path/"hermes-home"))
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(tmp_path/"hermes-runtime"))
    monkeypatch.syspath_prepend(root)
    from atmem.adapters.hermes.feedback_guard import HermesFeedbackGuard
    from atmem.mcp.guarded import GuardedDispatcher
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    f, memory, rule, lifecycle = reviewed_shadow(tmp_path/"atmem")
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
                           operations=("read", "execute"), expires_at=1_700_010_000)
    qualification = seed_trusted_test_receipt(f, rule)
    lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="active", expected_generation=1,
                         qualification_id=qualification, versions=VERSIONS)
    dispatcher = GuardedDispatcher(f.feedback, versions=VERSIONS)
    binding = HermesFeedbackGuard(dispatcher, host_root=root, session_resolver=lambda **ids:f.session)
    schema = {"type":"object", "properties":{"target":{"type":"string"}}, "required":["target"], "additionalProperties":False}
    binding.register_tool(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=schema,
                          native_guard=lambda args:args["target"] != "native-denied")
    from hermes_cli import plugins
    from tools.registry import registry
    manager = plugins.PluginManager()
    manager._discovered = True
    monkeypatch.setattr(plugins, "get_plugin_manager", lambda:manager)
    context = plugins.PluginContext(plugins.PluginManifest(name="atmem-feedback-test", version="1"), manager)
    from atmem.adapters.hermes.action_guard_plugin import register
    register(context, feedback_guard=binding)
    effect = tmp_path/"real-effect.jsonl"
    def write(args, **kwargs):
        with effect.open("a") as stream:
            stream.write(json.dumps(args)+"\n")
        return json.dumps({"ok":True})
    registry.register("fixture.write", "atmem-feedback-test",
        {"name":"fixture.write", "parameters":schema}, write)
    ids = {"session_id":"session", "task_id":"task", "turn_id":"turn", "tool_call_id":"call"}
    try:
        yield SimpleNamespace(f=f, memory=memory, binding=binding, dispatcher=dispatcher, context=context,
                              ids=ids, effect=effect, write=write)
    finally:
        memory.close()


def invoke(fixture, args, *, path="direct", **ids):
    identities = {**fixture.ids, **ids}
    if path == "direct":
        from model_tools import handle_function_call
        return handle_function_call("fixture.write", args, **identities)
    from agent.tool_executor import _run_agent_tool_execution_middleware
    agent = SimpleNamespace(session_id=identities["session_id"], _current_turn_id=identities["turn_id"],
        _current_api_request_id="request", _tool_guardrails=SimpleNamespace(
            before_call=lambda *args:SimpleNamespace(allows_execution=True)),
        verbose_logging=False, quiet_mode=True, tool_progress_callback=None, tool_start_callback=None,
        _touch_activity=lambda *args:None, _checkpoint_mgr=SimpleNamespace(enabled=False))
    return _run_agent_tool_execution_middleware(agent, function_name="fixture.write", function_args=args,
        effective_task_id=identities["task_id"], tool_call_id=identities["tool_call_id"], execute=fixture.write).result


@pytest.mark.parametrize("path", ["direct", "agent"])
def test_real_registered_dispatch_blocks_forbidden_and_runs_legitimate_once(installed, path):
    assert "error" in json.loads(invoke(installed, {"target":"production"}, path=path))
    assert not installed.effect.exists()
    allowed = invoke(installed, {"target":"staging"}, path=path, tool_call_id="allowed")
    assert json.loads(allowed) == {"ok":True}
    assert installed.effect.read_text().splitlines() == [json.dumps({"target":"staging"})]
    assert invoke(installed, {"target":"staging"}, path=path, tool_call_id="allowed") == allowed
    assert len(installed.effect.read_text().splitlines()) == 1
    assert "error" in json.loads(invoke(installed, {"target":"production"}, path=path, tool_call_id="allowed"))


@pytest.mark.parametrize("mode", ["late_rewrite", "native_veto", "revoked", "missing_identity", "source_deleted", "unavailable"])
def test_actual_host_has_no_effect_for_rewrite_veto_revocation_missing_identity_or_outage(installed, mode):
    ids = {}
    if mode == "late_rewrite":
        installed.context.register_middleware("tool_execution", lambda args, next_call, **kw:next_call({"target":"production"}))
    elif mode == "native_veto":
        installed.context.register_hook("authorize_tool_call", lambda **kw:{"action":"block", "message":"Existing native policy denies"})
    elif mode == "revoked":
        installed.f.feedback.revoke_agent(installed.f.owner["token"], installed.f.scope,
                                          principal_id=installed.f.user["principal_id"])
    elif mode == "missing_identity":
        ids["turn_id"] = ""
    elif mode == "source_deleted":
        with installed.f.feedback.store.transaction(installed.f.scope) as tx:
            source = tx.get("rule_proposal", "rule")["candidate"]["sources"][0]["source_id"]
        installed.memory.forget_record("alice", source)
    else:
        def unavailable(**ids):
            raise RuntimeError("PRIVATE-CREDENTIAL-TEXT")
        installed.binding.session_resolver = unavailable
    result = invoke(installed, {"target":"staging"}, **ids)
    assert "error" in json.loads(result) and "PRIVATE-CREDENTIAL-TEXT" not in result
    assert not installed.effect.exists()


def test_pure_final_hook_cannot_dispatch_or_consume_approval_and_unregistered_tool_is_blocked(installed):
    from agent.tool_authorization import authorize_tool_call
    block, args = authorize_tool_call("fixture.write", {"target":"staging"}, **installed.ids)
    assert block and not installed.effect.exists()
    assert installed.binding.tool_execution("unregistered", {}, lambda args:installed.write(args), **installed.ids)
    assert not installed.effect.exists()


def test_actual_host_consumes_exact_approval_once_at_execution_not_final_check(installed):
    from agent.tool_authorization import authorize_tool_call
    from atmem.contracts.feedback import MCPInvocation
    f = installed.f
    schema = {"type":"object", "properties":{"target":{"type":"string"}}, "required":["target"], "additionalProperties":False}
    installed.binding.register_tool(f.owner['token'], f.scope, tool='fixture.write', schema_version='v1',
        schema=schema, native_guard=lambda args:True, requires_approval=True)
    invocation = installed.binding.invocation(f.session, tool_name='fixture.write', args={'target':'staging'}, **installed.ids)
    approval = installed.dispatcher.approve(f.owner['token'], f.scope, principal_id=f.user['principal_id'],
        invocation=invocation, expires_at=int(f.feedback.clock())+60)
    installed.binding.approval_resolver = lambda *args:approval
    for _ in range(2):
        assert authorize_tool_call('fixture.write', {'target':'staging'}, **installed.ids)[0]
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.get('call_approval', approval)['used'] is False
    assert json.loads(invoke(installed, {'target':'staging'})) == {'ok':True}
    assert json.loads(invoke(installed, {'target':'staging'})) == {'ok':True}
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.get('call_approval', approval)['used'] is True
    assert 'error' in json.loads(invoke(installed, {'target':'staging'}, tool_call_id='different-call'))
    assert len(installed.effect.read_text().splitlines()) == 1


def test_real_unknown_batch_and_skipped_middleware_cannot_bypass_final_boundary(installed):
    from model_tools import handle_function_call
    from tools.registry import registry
    called = []
    def batch(args, **kw):
        called.append(True)
        return installed.write(args)
    registry.register('fixture.batch', 'atmem-feedback-test',
        {'name':'fixture.batch', 'parameters':{'type':'object'}}, batch)
    result = handle_function_call('fixture.batch', {'target':'staging'}, **installed.ids)
    assert 'error' in json.loads(result) and not called and not installed.effect.exists()
    result = handle_function_call('fixture.write', {'target':'staging'}, skip_tool_execution_middleware=True, **installed.ids)
    assert 'error' in json.loads(result) and not installed.effect.exists()
    assert installed.binding.capabilities(installed.f.session)['qualification'] == 'not_established'
