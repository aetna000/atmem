"""No model calls: exercise the bounded configuration diagnostic transport."""
import os
from pathlib import Path
import sys

import pytest

from benchmarks.code_replay.appserver_probe import ConfigRPC, configuration_command


def rpc_for(code, tmp_path):
    return ConfigRPC([sys.executable, "-u", "-c", code], cwd=tmp_path, env=os.environ.copy())


def test_model_turn_and_billing_methods_are_not_permitted(tmp_path):
    rpc = rpc_for("import time; time.sleep(10)", tmp_path)
    try:
        for method in ("turn/start", "turn/steer", "review/start", "account/login/start"):
            with pytest.raises(ValueError, match="not permitted"):
                rpc.send({"method": method})
        assert not rpc.sent
    finally:
        rpc.close()
    assert rpc.process.returncode is not None


def test_configuration_reply_and_stream_retained(tmp_path):
    rpc = rpc_for('import sys,json\nfor line in sys.stdin:\n m=json.loads(line); print(json.dumps({"id":m["id"],"result":{"ok":True}}),flush=True)', tmp_path)
    try:
        assert rpc.call("config/read", {}) == {"ok": True}
        assert rpc.messages[0]["id"] == 1
        assert b'"ok": true' in rpc.raw["stdout"]
    finally:
        rpc.close()


def test_server_request_never_authorizes_itself(tmp_path):
    rpc = rpc_for('import sys,json\nsys.stdin.readline(); print(json.dumps({"id":99,"method":"item/commandExecution/requestApproval"}),flush=True)', tmp_path)
    try:
        with pytest.raises(PermissionError, match="unexpected server request"):
            rpc.call("initialize", {})
        assert len(rpc.sent) == 1
    finally:
        rpc.close()


def test_eof_is_failure_not_empty_success(tmp_path):
    rpc = rpc_for("import sys; sys.stdin.readline()", tmp_path)
    try:
        with pytest.raises(RuntimeError, match="stream closed"):
            rpc.call("initialize", {})
    finally:
        rpc.close()


def test_timeout_is_bounded_and_child_reaped(tmp_path):
    rpc = rpc_for("import time; time.sleep(10)", tmp_path)
    try:
        with pytest.raises(TimeoutError):
            rpc.call("initialize", {}, timeout=.02)
    finally:
        rpc.close()
    assert rpc.process.returncode is not None


def test_named_permission_and_subscription_model_command(tmp_path):
    from types import SimpleNamespace
    runtime = tmp_path / "atmem-click-runtime"
    interpreter = tmp_path / "cpython-fixture"
    runtime.mkdir()
    interpreter.mkdir()
    command = configuration_command(SimpleNamespace(executable=runtime / "codex"), interpreter)
    assert 'default_permissions="click-replay"' in command
    assert 'approval_policy="never"' in command
    assert 'model="gpt-6-luna"' in command
    assert "--strict-config" in command
    assert not any("api_key" in part for part in command)


def test_interrupted_usage_snapshots_are_not_summed_or_called_complete():
    from benchmarks.code_replay.appserver_usage_probe import usage_evidence
    counters = dict(inputTokens=100, cachedInputTokens=0, outputTokens=5,
                    reasoningOutputTokens=0, totalTokens=105)
    updates = [{"method": "thread/tokenUsage/updated", "params": {
        "threadId": "t", "turnId": "u", "tokenUsage": {"last": counters, "total": counters}}}]
    messages = updates * 2 + [{"method": "turn/completed", "params": {
        "threadId": "t", "turn": {"id": "u", "status": "interrupted"}}}]
    proof = usage_evidence(messages, "t", "u")
    assert len(proof["updates"]) == 2
    assert proof["updates"][-1]["usage"]["total"]["inputTokens"] == 100
    assert proof["full_usage_verified"] is False
    assert proof["historical_usage_backfilled"] is False
    with pytest.raises(ValueError, match="cross-thread"):
        usage_evidence(messages, "other", "u")
    with pytest.raises(ValueError, match="cross-turn"):
        usage_evidence(messages, "t", "other")


def test_usage_probe_allows_only_one_turn(tmp_path):
    from benchmarks.code_replay.appserver_usage_probe import UsageRPC
    rpc = UsageRPC([sys.executable, "-u", "-c", "import time; time.sleep(10)"],
        cwd=tmp_path, env=os.environ.copy())
    try:
        rpc.send({"method": "turn/start", "params": {}})
        with pytest.raises(ValueError, match="one model turn"):
            rpc.send({"method": "turn/start", "params": {}})
    finally:
        rpc.close()
