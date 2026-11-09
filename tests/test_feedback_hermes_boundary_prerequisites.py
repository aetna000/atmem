"""Pin and reproduce upstream blockers before advertising policy enforcement.

These are isolated source-contract probes, NOT an installed host, end-to-end
tool interception, or positive safety qualification. Passing means the documented
upstream behavior was reproduced, including unsafe paths that block Spec 050.
Run: HERMES_SOURCE=/path/to/pinned/checkout python -m pytest -q this_file
"""

from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
import subprocess
import sys
import threading

import pytest

from test_hermes_upstream_contract import function, upstream as pinned_upstream  # noqa: F401


@pytest.fixture
def upstream(pinned_upstream):
    paths = ["agent/tool_executor.py", "hermes_cli/plugins.py", "hermes_cli/plugins_dispatch.py"]
    result = subprocess.run(
        ["git", "-C", str(pinned_upstream), "diff", "--exit-code", "HEAD", "--", *paths],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, "review modified boundary source before probing"
    return pinned_upstream


def _pre_hook(upstream, monkeypatch, dispatcher):
    # Do not import or initialize Hermes: bootstrap can rewrite global launchers.
    plugins = ModuleType("hermes_cli.plugins")
    plugins._dispatch_pre_tool_call_hooks = dispatcher
    parent = ModuleType("hermes_cli")
    parent.__path__ = []
    monkeypatch.setitem(sys.modules, "hermes_cli", parent)
    monkeypatch.setitem(sys.modules, "hermes_cli.plugins", plugins)
    return function(upstream, "agent/tool_executor.py", "_pre_tool_block", {
        "tool_hook_ids": lambda *args: {},
    })


def _dispatch(upstream, monkeypatch, pre_hook):
    terminal = ModuleType("agent.terminal_approval_batch")
    terminal.prepare_current_terminal = lambda ref: None
    parent = ModuleType("agent")
    parent.__path__ = []
    monkeypatch.setitem(sys.modules, "agent", parent)
    monkeypatch.setitem(sys.modules, "agent.terminal_approval_batch", terminal)
    return function(upstream, "agent/tool_executor.py", "_dispatch_authorized_once", {
        "_pre_tool_block": pre_hook,
        "_context_pruned_argument_paths": lambda *args: [],
        "_begin_tool_execution": lambda *args: None,
        "_run_with_activity_heartbeat": lambda agent, name, callback: callback(),
        "_blocked_tool_result": lambda *args, **kw: {"blocked": kw["block_body"]},
    })


def _invoke(dispatch):
    effects = []
    state = SimpleNamespace(args=None, blocked=False)
    ref = SimpleNamespace(name="fixture.write", args={"approved": True},
                          task_id="task", call_id="call", trace=[])
    agent = SimpleNamespace(_tool_guardrails=SimpleNamespace(
        before_call=lambda *args: SimpleNamespace(allows_execution=True)))
    result = dispatch(agent, state, ref, execute=lambda args: effects.append(dict(args)),
                      scope_block=None, display_index=None, begin_execution=None,
                      authorization_gate=None)
    return effects, state, result


def test_normal_block_prevents_synthetic_callback(upstream, monkeypatch):
    pre = _pre_hook(upstream, monkeypatch, lambda *a, **k: ("covered_call_blocked", None))
    effects, state, result = _invoke(_dispatch(upstream, monkeypatch, pre))
    assert effects == []
    assert state.blocked is True
    assert result["blocked"]["error"] == "covered_call_blocked"


def test_hook_dispatch_exception_allows_synthetic_callback(upstream, monkeypatch):
    def unavailable(*args, **kwargs):
        raise PermissionError("policy authority unavailable")

    pre = _pre_hook(upstream, monkeypatch, unavailable)
    effects, state, _ = _invoke(_dispatch(upstream, monkeypatch, pre))
    # A real veto exists, but this error path is fail-open. Do NOT qualify it.
    assert effects == [{"approved": True}]
    assert state.blocked is False


@dataclass
class Directive:
    action: str | None = None
    message: str | None = None
    rule_key: str | None = None
    modified_args: dict | None = None


def test_argument_modification_after_policy_check_reaches_callback(upstream, monkeypatch):
    checked = []
    lifecycle = ModuleType("hermes_cli.lifecycle")

    def invoke_hook(hook, **kwargs):
        # The authority checks the original arguments. Another registered hook
        # proposes a rewrite; Hermes merges it after the hook observations.
        checked.append(dict(kwargs["args"]))
        assert kwargs["args"]["approved"] is True
        return [None, {"action": "modify", "args": {"approved": False}}]

    lifecycle.invoke_hook = invoke_hook
    monkeypatch.setitem(sys.modules, "hermes_cli.lifecycle", lifecycle)
    details = function(upstream, "hermes_cli/plugins.py", "_get_pre_tool_call_directive_details", {
        "_thread_tool_whitelist": threading.local(), "_PreToolCallDirective": Directive,
    })
    resolve = function(upstream, "hermes_cli/plugins.py", "_resolve_block_from_details")
    dispatch_hooks = function(upstream, "hermes_cli/plugins.py", "_dispatch_pre_tool_call_hooks", {
        "_get_pre_tool_call_directive_details": details,
        "_resolve_block_from_details": resolve,
    })
    pre = _pre_hook(upstream, monkeypatch, dispatch_hooks)
    effects, state, _ = _invoke(_dispatch(upstream, monkeypatch, pre))
    assert checked == [{"approved": True}]
    assert effects == [{"approved": False}]
    assert state.blocked is False


def test_existing_veto_wins_over_an_approval_request(upstream, monkeypatch):
    lifecycle = ModuleType("hermes_cli.lifecycle")
    lifecycle.invoke_hook = lambda *a, **k: [
        {"action": "approve", "message": "human confirmation requested"},
        {"action": "block", "message": "existing policy denies"},
    ]
    monkeypatch.setitem(sys.modules, "hermes_cli.lifecycle", lifecycle)
    details = function(upstream, "hermes_cli/plugins.py", "_get_pre_tool_call_directive_details", {
        "_thread_tool_whitelist": threading.local(), "_PreToolCallDirective": Directive,
    })("fixture.write", {})
    assert details.action == "block"
    assert details.message == "existing policy denies"
