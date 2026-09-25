"""Native upstream control flow with fake model replies; never uses an API key."""
import json
import os
from pathlib import Path

import pytest

from benchmarks.agent_continuity import native_pilot
from benchmarks.agent_continuity.live_transport import LoggedTransport, MODEL


@pytest.mark.skipif(not os.environ.get("CONTINUITY_TAU_ROOT"), reason="pinned optional upstream required")
def test_native_pilot_retains_failed_task_and_grading(tmp_path, monkeypatch):
    root = Path(os.environ["CONTINUITY_TAU_ROOT"])
    monkeypatch.setattr(native_pilot, "LEDGER_ROOT", tmp_path / "budget")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-only")
    native_pilot.initialize_budget()
    task = native_pilot.pilot_task(root, "0")
    # Task 0 has an empty NL list despite NL_ASSERTION in its reward basis.
    # Plant one ONLY in this offline fixture to exercise the grader transport.
    task["evaluation_criteria"]["nl_assertions"] = ["The customer request was completed."]
    monkeypatch.setattr(native_pilot, "pilot_task", lambda *_: task)
    assertions = task["evaluation_criteria"]["nl_assertions"]
    calls = []
    def sender(body, key):
        assert key == "fake-test-only"
        calls.append(body)
        canned = ["Hello, I need help.", "Sorry, I cannot help.", "###STOP###"]
        content = canned[len(calls)-1] if len(calls) <= 3 else json.dumps({"results": [
            {"expectedOutcome": assertion, "metExpectation": False, "reasoning": "fake incomplete conversation"}
            for assertion in assertions]})
        return {"id": f"fake-{len(calls)}", "object": "chat.completion", "created": 1,
            "service_tier": "default", "system_fingerprint": "fp_fixture",
            "model": MODEL, "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110,
            "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 0}}}
    class FakeTransport(LoggedTransport):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, sender=sender)
    monkeypatch.setattr(native_pilot, "LoggedTransport", FakeTransport)
    output = tmp_path / "run"
    result = native_pilot.run(root, output, "0", execute=True)
    assert result["disposition"] == "completed"
    assert result["local_task_reward"] == 0  # Completed conversation != task success.
    assert result["dispatched_attempts"] == len(calls) == 4  # Fake dispatch accounting only.
    accounting = json.loads((output / "accounting.json").read_text())
    assert set(accounting["summary"]["by_role"]) == {"agent", "simulator", "grader"}
    assert (output / "step-0001.json").exists()
    assert (output / "SHA256SUMS.json").exists()
    assert "fake-test-only" not in "".join(p.read_text() for p in output.glob("*.json"))
