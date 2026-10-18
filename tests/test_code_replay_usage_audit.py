import base64
import json

import pytest

from benchmarks.code_replay.usage_audit import audit_trial


def retained(stream, *, reason="tool_budget", exit_code=-9, missing=True):
    tokens = dict.fromkeys(("input_tokens", "output_tokens", "cached_tokens"), None if missing else 1)
    return [{"envelope": {"event_type": kind, "payload": payload}} for kind, payload in [
        ("agent.attempt", {"stdout_base64": base64.b64encode(stream).decode()}),
        ("trial.completed", {"result": {"run_id": "test", "tokens": tokens,
         "reason": reason, "solver_exit_code": exit_code, "tool_calls": 25}})]]


def test_killed_stream_does_not_invent_usage():
    result = audit_trial(retained(b'{"type":"turn.started"}\n'))
    assert result["diagnosis"] == "harness_killed_before_terminal_usage"
    assert result["usage_missing"] and result["tokens_imputed"] is False


def test_terminal_without_newline_is_audited_not_discarded():
    stream = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}).encode()
    result = audit_trial(retained(stream, reason="checks_failed", exit_code=0))
    assert result["diagnosis"] == "completed_turn_requires_usage_schema_review"
    assert result["top_level_usage_events"] == 1


def test_unexplained_provider_exit_is_not_blamed_on_harness():
    assert audit_trial(retained(b'', reason="checks_failed", exit_code=1))["diagnosis"] == "no_terminal_usage_unresolved"


def test_invalid_stream_is_distinct():
    assert audit_trial(retained(b'{broken\n'))["diagnosis"] == "invalid_retained_stream"


def test_known_usage_remains_recorded():
    assert audit_trial(retained(b'', reason="passed", exit_code=0, missing=False))["diagnosis"] == "receipt_recorded"


def test_interrupted_attempt_cannot_be_mistaken_for_terminal_trial():
    with pytest.raises(ValueError, match="terminal trial"):
        audit_trial([])
