"""No-cost behavioral probes of reviewed, pinned Hermes source functions.

Run with HERMES_SOURCE set to the pinned checkout. These are isolated source
contract tests, NOT an installed Hermes run or an action-accuracy benchmark.
Only named function bodies are loaded; Hermes's agent/model runtime is not run.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest


HERMES_COMMIT = "d0288be5b3330d2442e3907185b8e9d0958297bb"


@pytest.fixture
def upstream():
    location = os.environ.get("HERMES_SOURCE")
    if not location:
        pytest.skip("set HERMES_SOURCE to the reviewed Hermes checkout")
    root = Path(location).resolve()
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.strip() == HERMES_COMMIT, "review a changed host before qualification"
    for path in ("agent/turn_api_request.py", "agent/turn_context.py", "agent/memory_manager.py", "hermes_cli/middleware.py"):
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--exit-code", "HEAD", "--", path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"upstream source was modified: {path}"
    return root


def function(root, relative, name, namespace=None):
    """Execute just the reviewed function, with explicit dependency doubles."""
    tree = ast.parse((root / relative).read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    isolated = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    ast.fix_missing_locations(isolated)
    values = dict(namespace or {})
    exec(compile(isolated, str(root / relative), "exec"), values)
    return values[name]


def test_pre_request_observer_cannot_veto_on_error(upstream, monkeypatch):
    calls = []
    lifecycle = ModuleType("hermes_cli.lifecycle")
    lifecycle.has_hook = lambda name: True

    def deny(*args, **kwargs):
        calls.append(kwargs["api_request_id"])
        raise PermissionError("AtMem authorization was revoked")

    lifecycle.invoke_hook = deny
    conversation = ModuleType("agent.conversation_loop")
    conversation._system_prompt_for_hooks = lambda *args: "system"
    monkeypatch.setitem(sys.modules, "hermes_cli.lifecycle", lifecycle)
    monkeypatch.setitem(sys.modules, "agent.conversation_loop", conversation)
    hook = function(upstream, "agent/turn_api_request.py", "_fire_pre_api_request_hook")
    messages = [{"role": "user", "content": "previously authorized memory"}]
    agent = SimpleNamespace(session_id="s", platform="cli", model="no-network",
                            provider="test", base_url="", api_mode="chat_completions",
                            tools=[], max_tokens=1, _api_request_payload_for_hook=lambda x: x)
    result = hook(agent, {"messages": messages}, messages, [], messages=messages,
                  original_user_message="test", approx_tokens=1, total_chars=1,
                  retry_count=0, api_call_count=1, api_request_id="request-1",
                  api_start_time=0, effective_task_id="task", turn_id="turn")
    assert calls == ["request-1"]
    assert result is None  # Host swallowed the authorization failure.
    assert messages[0]["content"] == "previously authorized memory"


def test_prefetch_is_embedded_in_replayable_user_content(upstream):
    compose = function(
        upstream, "agent/turn_context.py", "compose_user_api_content",
        {"compose_multimodal_context_part": lambda memory, plugin: memory or None},
    )
    old = compose("original user input", "approved memory at time A", "")
    assert old == "original user input\n\napproved memory at time A"
    # A subsequent empty recall does not itself rewrite an earlier host message.
    assert compose("next user input", "", "") is None
    assert "approved memory at time A" in old


def test_prefetch_contract_is_turn_scoped_not_request_scoped(upstream):
    tree = ast.parse((upstream / "agent/turn_context.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_memory_turn_start_and_prefetch")
    calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "prefetch_all"]
    assert len(calls) == 1
    assert "once" in ast.get_docstring(node)
    assert "before the tool loop" in ast.get_docstring(node)


def test_request_middleware_has_fail_open_exception_path(upstream):
    tree = ast.parse((upstream / "agent/turn_api_request.py").read_text())
    matching = [node for node in ast.walk(tree) if isinstance(node, ast.Try)
                and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                        and child.func.id == "apply_llm_request_middleware"
                        for statement in node.body for child in ast.walk(statement))]
    assert len(matching) == 1
    handler = matching[0].handlers[0]
    assert isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
    assert not any(isinstance(n, (ast.Raise, ast.Return)) for n in ast.walk(handler))


def test_prefetch_uses_host_spill_path(upstream):
    tree = ast.parse((upstream / "agent/memory_manager.py").read_text())
    manager = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MemoryManager")
    method = next(n for n in manager.body if isinstance(n, ast.FunctionDef) and n.name == "_prefetch_provider")
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "spill_if_oversized" for n in ast.walk(method))


def test_execution_middleware_denial_still_calls_downstream(upstream, monkeypatch):
    downstream = []
    warnings = []

    def deny(**kwargs):
        raise PermissionError("AtMem unavailable; context must be withheld")

    manager = SimpleNamespace(_middleware={"llm_execution": [deny]},
                              _report_hook_failure=lambda *a, **kw: warnings.append(True))
    plugins = ModuleType("hermes_cli.plugins")
    plugins._delivery_manager = lambda: manager
    monkeypatch.setitem(sys.modules, "hermes_cli.plugins", plugins)

    class DownstreamError(Exception):
        def __init__(self, original):
            self.original = original

    run = function(upstream, "hermes_cli/middleware.py", "_run_execution_chain",
                   {"middleware_payload": lambda **kw: kw,
                    "_DownstreamExecutionError": DownstreamError})

    def terminal(payload):
        downstream.append(payload)
        return "provider called"

    request = {"messages": [{"role": "user", "content": "retained memory"}]}
    assert run("llm_execution", terminal, request=request) == "provider called"
    assert downstream == [request]
    assert warnings == [True]
