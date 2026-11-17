"""Safety and fidelity checks for the actual-package comparison, not efficacy."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from atmem.benchmark.memory_comparison import Ledger, LIMITS, execute, worker
from atmem.feedback.store import FeedbackError


def test_paid_failure_stays_durably_reserved_and_encrypted(tmp_path):
    ledger = Ledger(tmp_path, {"protocol": "test"})
    payload = {"model": "fixed", "messages": [{"role": "user", "content": "RESERVATION_SECRET_CANARY"}], "max_tokens": 10}
    def fails(*a, **kw):
        raise RuntimeError("provider error body must not leak")
    with pytest.raises(FeedbackError, match="comparison_provider_unknown"):
        ledger.call(payload, fails, "106:none")
    report = ledger.report("stopped")
    assert report["unknown_calls"] == 1
    assert report["resources"]["calls"] == 1
    assert report["resources"]["usd"] > 0
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
    ledger = Ledger(tmp_path, {}, clock=lambda: now[0])
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
            return {"action": "ANSWER", "content": "7"}
    case = {"id": "106", "public": {"question": "Count records", "database": "public.db"},
            "target": {"answer": "hidden-target-canary"}}
    assert execute(Capture(), None, tmp_path, case, "none", "", "")["answer"] == "7"
