import operator
import sqlite3
from typing import Annotated, TypedDict
from urllib.error import HTTPError

import pytest

from test_continuity_http import running
from atmem.continuity.client import ContinuityClient, RecoveryBlocked, Tool
from atmem.continuity.integrations import GovernedToolRunner, RegisteredTool, governed_langgraph_tools
from atmem.evidence import EvidenceRole, EvidenceScope


def coordinator(running):
    client, vault, owner, _ = running
    grant = vault.grant(owner, principal_id="coordinator", role=EvidenceRole.CONTINUITY_COORDINATOR,
        scope=EvidenceScope("local", "local-user", "project"))
    return ContinuityClient(client.url, grant["token"])


def runner(client, effects):
    def execute(arguments, operation_id, key, timeout):
        effects.append(arguments)
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id,
                "effect_id": "effect-" + str(len(effects)), "result": arguments}
    return GovernedToolRunner(client, "test-deployment", {"work": RegisteredTool(Tool(execute))}, enabled=True)


def call(value, *, message="message1", arguments=None):
    return value.run_message(thread_id="thread1", checkpoint_ns="", message_id=message,
        calls=[{"id": "call0", "name": "work", "args": arguments or {"amount": 1}}], durable=True)


def test_dynamic_resume_reuses_receipt_but_distinct_messages_are_distinct_work(running):
    client = coordinator(running)
    effects = []
    first = call(runner(client, effects))
    assert call(runner(client, effects)) == first
    assert effects == [{"amount": 1}]
    call(runner(client, effects), message="message2")
    assert len(effects) == 2
    with pytest.raises(RecoveryBlocked, match="controller_refused_409"):
        call(runner(client, effects), arguments={"amount": True})
    assert len(effects) == 2


def test_coordinator_cannot_override_operator_or_use_other_workflows(running):
    operator_client, _, _, _ = running
    client = coordinator(running)
    effects = []
    call(runner(client, effects))
    workflow = operator_client.request("GET", "/v1/continuity")["workflows"][0]
    operator_client.configure(workflow["workflow_id"], False)
    with pytest.raises(RecoveryBlocked, match="disabled"):
        call(runner(client, effects))
    with pytest.raises(HTTPError) as no_control:
        client.configure(workflow["workflow_id"], True)
    assert no_control.value.code == 403
    with pytest.raises(HTTPError):
        client.request("GET", "/v1/continuity")
    static = operator_client.create("operator-static", [{"name": "work", "tool": "work"}])
    with pytest.raises(HTTPError):
        client.get(static["workflow_id"])
    assert len(effects) == 1


def test_disabled_retired_duplicate_and_unknown_actions_stop_the_host(running):
    client = coordinator(running)
    effects = []
    instance = runner(client, effects)
    instance.enabled = False
    with pytest.raises(RecoveryBlocked):
        call(instance)
    instance.enabled = True
    with pytest.raises(RecoveryBlocked):
        instance.run_message(thread_id="t", checkpoint_ns="", message_id="m", durable=True,
            calls=[{"id": "duplicate", "name": "work", "args": {}}] * 2)
    instance.tools["work"] = RegisteredTool(Tool(lambda *args: None), retired=True)
    with pytest.raises(RecoveryBlocked):
        call(instance)
    assert not effects


def test_actual_langgraph_requires_sync_and_preserves_completed_result(running, tmp_path):
    pytest.importorskip("langgraph")
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.sqlite import SqliteSaver
    class State(TypedDict):
        messages: Annotated[list, operator.add]
    effects = []
    client = coordinator(running)
    with sqlite3.connect(tmp_path / "checkpoints.db", check_same_thread=False) as connection:
        graph = StateGraph(State)
        graph.add_node("tools", governed_langgraph_tools(runner(client, effects)))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        app = graph.compile(checkpointer=SqliteSaver(connection))
        message = {"role": "assistant", "id": "message1", "tool_calls": [{"id": "call0", "name": "work", "args": {"amount": 1}}]}
        with pytest.raises(RecoveryBlocked, match="sync"):
            app.invoke({"messages": [message]}, {"configurable": {"thread_id": "async"}}, durability="async")
        result = app.invoke({"messages": [message]}, {"configurable": {"thread_id": "sync"}}, durability="sync")
        assert result["messages"][-1]["role"] == "tool"
        assert effects == [{"amount": 1}]
        checkpoints = list(app.get_state_history({"configurable": {"thread_id": "sync"}}))
        before_tools = next(checkpoint for checkpoint in checkpoints if checkpoint.next == ("tools",))
        replay = app.invoke(None, before_tools.config, durability="sync")
        assert replay["messages"][-1]["role"] == "tool"
        assert effects == [{"amount": 1}]
        with pytest.raises(RecoveryBlocked, match="assistant"):
            app.invoke({"messages": [{**message, "role": "user"}]}, {"configurable": {"thread_id": "user-injection"}}, durability="sync")


def test_partial_batch_resume_does_not_repeat_completed_first_call(running):
    client = coordinator(running)
    effects = []
    attempts = []
    def first(arguments, operation_id, key, timeout):
        effects.append(operation_id)
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id, "effect_id": "first", "result": 1}
    def second(arguments, operation_id, key, timeout):
        attempts.append(operation_id)
        raise ConnectionError("unknown external outcome")
    def query(arguments, operation_id, key, timeout):
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id, "effect_id": "second", "result": 2}
    instance = GovernedToolRunner(client, "partial-batch", {
        "first": RegisteredTool(Tool(first)), "second": RegisteredTool(Tool(second, query), capability="query")}, enabled=True)
    kwargs = dict(thread_id="thread", checkpoint_ns="root", message_id="message", durable=True,
        calls=[{"id": "c1", "name": "first", "args": {}}, {"id": "c2", "name": "second", "args": {}}])
    with pytest.raises(RecoveryBlocked, match="unavailable"):
        instance.run_message(**kwargs)
    result = instance.run_message(**kwargs)
    assert len(result) == 2
    assert len(effects) == 1
    assert len(attempts) == 1
