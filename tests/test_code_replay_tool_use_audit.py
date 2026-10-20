import base64
import json

import pytest

from benchmarks.code_replay.tool_use_audit import audit_trial


def retained(messages):
    raw = b"\n".join(json.dumps(m).encode() for m in messages)
    return [{"envelope": {"event_type": kind, "payload": payload}} for kind, payload in [
        ("agent.attempt", {"stdout_base64": base64.b64encode(raw).decode()}),
        ("trial.completed", {"result": {"run_id": "test", "arm": "C", "functional_pass": False,
                                        "tokens": {"input_tokens": None}}})]]


def item(identity, kind, **kwargs):
    return {"type": "item.completed", "item": {"id": identity, "type": kind, **kwargs}}


def test_counts_observed_calls_without_inventing_token_saving():
    proof = audit_trial(retained([item("1", "command_execution", aggregated_output="東京"),
        item("2", "command_execution", aggregated_output="東京"),
        item("3", "mcp_tool_call", server="atmem_code", tool="code_context")]))
    assert proof["observed_native_output_bytes"] == 12
    assert proof["exact_nonempty_output_repeats"] == 1
    assert proof["atmem_tool_counts"] == {"code_context": 1}
    assert proof["recorded_input_tokens"] is None
    assert not proof["tokens_attributed_to_outputs"] and not proof["complete_tool_trace_claimed"]


def test_repeated_event_is_not_a_second_call():
    event = item("1", "command_execution", aggregated_output="abc")
    assert audit_trial(retained([event, event]))["completed_native_commands"] == 1


def test_started_but_unfinished_call_not_marked_complete():
    event = {"type": "item.started", "item": {"id": "1", "type": "mcp_tool_call"}}
    proof = audit_trial(retained([event]))
    assert proof["started_mcp_calls"] == 1 and proof["completed_mcp_calls"] == 0


def test_conflicting_event_rejected():
    with pytest.raises(ValueError, match="conflicting"):
        audit_trial(retained([item("1", "command_execution"), item("1", "mcp_tool_call")]))
