"""Safety and fidelity checks for the actual-package comparison, not efficacy."""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from atmem.benchmark.memory_comparison import Ledger, LIMITS, execute, worker
from atmem.feedback.store import FeedbackError


def test_paid_failure_stays_durably_reserved_and_encrypted(tmp_path):
    ledger = Ledger(tmp_path, {"protocol": "test", "cases": [{"id": "106"}]})
    payload = {"model": "fixed", "messages": [{"role": "user", "content": "RESERVATION_SECRET_CANARY"}], "max_tokens": 10}
    def fails(*a, **kw):
        raise RuntimeError("provider error body must not leak")
    with pytest.raises(FeedbackError, match="comparison_provider_unknown"):
        ledger.call(payload, fails, "106:none")
    report = ledger.report("stopped")
    assert report["unknown_calls"] == 1
    assert report["resources"]["calls"] == 1
    assert report["resources"]["usd"] > 0
    assert report["arms"]["none"]["calls"] == 1
    with ledger.transaction() as (tx, _):
        rows = list(tx.iter_kind("comparison_call"))
        assert rows[0]["state"] == "unknown"
        assert rows[0]["request"] == payload
        assert "error" not in rows[0]
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"RESERVATION_SECRET_CANARY" not in path.read_bytes()


def test_expired_budget_refuses_before_provider(tmp_path):
    now = [100.0]
    ledger = Ledger(tmp_path, {"cases": [{"id": "106"}]}, clock=lambda: now[0])
    now[0] += LIMITS["seconds"] + 1
    def forbidden(*a, **kw):
        pytest.fail("expired study reached paid provider")
    with pytest.raises(FeedbackError, match="comparison_deadline"):
        ledger.call({"messages": [], "max_tokens": 10}, forbidden, "106:original")
    assert ledger.report("stopped")["resources"]["calls"] == 0


def test_isolated_worker_attests_package_and_strips_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "never-forward")
    def fake_run(command, **kwargs):
        assert command[1] == "-I"
        assert "OPENROUTER_API_KEY" not in kwargs["env"]
        return SimpleNamespace(returncode=0, stdout=json.dumps({"identity": {
            "version": "2.3.15b2", "module": "/checkout/atmem/memory.py"}}))
    monkeypatch.setattr("atmem.benchmark.memory_comparison.subprocess.run", fake_run)
    with pytest.raises(FeedbackError, match="installed_package_not_attested"):
        worker(Path("python"), Path("worker.py"), tmp_path / "home",
               {"expected_version": "2.3.14"})


def test_no_memory_input_has_no_context_and_hidden_target(tmp_path):
    class Capture:
        def call(self, payload, provider, trial):
            assert trial == "106:none"
            text = json.dumps(payload)
            assert "AtMem retrieved" not in text
            assert "hidden-target-canary" not in text
            assert "Memory-use strategy" not in text
            assert "three separate product datasets" in text
            assert "Each dataset has its own set of tables" in text
            return {"action": "ANSWER", "content": "7"}
    case = {"id": "106", "public": {"question": "Count records", "database": "public.db"},
            "target": {"answer": "hidden-target-canary"}}
    assert execute(Capture(), None, tmp_path, {k: case[k] for k in ("id", "public")}, "none", "", "")["answer"] == "7"
    with pytest.raises(ValueError, match="hidden targets"):
        execute(Capture(), None, tmp_path, case, "none", "", "")


@pytest.mark.parametrize("arm", ["original", "pilot"])
def test_historical_questions_cannot_replace_current_task_message(tmp_path, arm):
    history = 'Old task: What is the median price?\n{"action":"ANSWER","content":"wrong old answer"}'
    public = {"question": "What is the current-to-legacy table size ratio?", "database": "public.db"}
    class Capture:
        def call(self, payload, provider, trial):
            messages = payload["messages"]
            assert json.loads(messages[-1]["content"]) == {"current_task": public}
            assert json.loads(messages[-2]["content"]) == {"untrusted_retrieved_history": history}
            assert "median" not in messages[-1]["content"]
            assert "hidden-target-canary" not in json.dumps(payload)
            return {"action": "ANSWER", "content": "7"}
    case = {"id": "independent-001", "public": public, "target": {"answer": "hidden-target-canary"}}
    assert execute(Capture(), None, tmp_path, {k: case[k] for k in ("id", "public")}, arm, history, "Use fallible evidence")["answer"] == "7"


def test_malformed_model_reply_counts_as_failure_without_retry(tmp_path):
    class Malformed:
        calls = 0
        def call(self, *a):
            self.calls += 1
            raise json.JSONDecodeError("Extra data", '{}{}', 2)
    ledger = Malformed()
    output = execute(ledger, None, tmp_path, {"id": "independent-001", "public": {}}, "none", "", "")
    assert ledger.calls == 1
    assert output["answer"] is None and output["failure"] == "invalid_model_action"


def test_tool_result_is_durable_when_following_model_reply_is_malformed(tmp_path):
    database = tmp_path / "public.db"
    sqlite3.connect(database).close()
    home = tmp_path / "home"
    home.mkdir()
    ledger = Ledger(home, {"cases": [{"id": "independent-001"}]})
    responses = iter(['{"action":"QUERY","content":"SELECT 42"}', '{}{}'])
    def provider(payload, **kwargs):
        return {"response": {"choices": [{"finish_reason": "stop", "message": {"content": next(responses)}}]},
            "prompt_tokens": 1, "completion_tokens": 1, "usd": 0}
    case = {"id": "independent-001", "public": {"question": "Return42", "database": "public.db"}}
    output = execute(ledger, provider, tmp_path, case, "none", "", "")
    assert output["answer"] is None and output["queries"] == 1
    with ledger.transaction() as (tx, _):
        record = tx.get("comparison_tool", "case-independent-001-none-q1")
        assert record["observation"]["result"]["rows"] == [[42]]
    assert ledger.report("failed")["resources"]["calls"] == 2
