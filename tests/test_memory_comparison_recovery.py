"""Never turn a malformed reply into a pass or repeat a paid request."""
import json

import pytest

from atmem.benchmark.memory_comparison import Ledger, grade_answer
from atmem.benchmark.memory_comparison_recovery import captured_failure


def captured(tmp_path, content, state="complete"):
    ledger = Ledger(tmp_path, {"cases": [{"id": "119"}]})
    messages = [{"role": "system", "content": "fixed"}, {"role": "user", "content": "public question"},
        {"role": "assistant", "content": json.dumps({"action": "QUERY", "content": "SELECT 42"})},
        {"role": "user", "content": json.dumps({"observation": {"columns": ["42"], "rows": [[42]]}})}]
    with ledger.transaction() as (tx, _):
        tx.put("comparison_call", "call", {"trial": "119:original", "state": state,
            "request": {"messages": messages}, "result": {"response": {"choices": [
                {"finish_reason": "stop", "message": {"content": content}}]}}}, expected_revision=0)
    return ledger


def test_malformed_response_is_failed_without_salvaging_answer(tmp_path):
    ledger = captured(tmp_path, '{"action":"ANSWER","content":"42"}\n{"extra":true}')
    output = captured_failure(ledger, "119", "original")
    assert output["answer"] is None
    assert output["queries"] == 1
    assert output["observations"] == [{"query": "SELECT 42", "result": {"columns": ["42"], "rows": [[42]]}}]
    target = {"answer": 42, "answer_type": "integer", "oracle_verified": True, "tolerance": 0}
    assert not grade_answer(output, target).correct


def test_valid_response_cannot_be_reclassified(tmp_path):
    ledger = captured(tmp_path, '{"action":"ANSWER","content":"42"}')
    with pytest.raises(ValueError, match="cannot replace a valid"):
        captured_failure(ledger, "119", "original")


def test_unknown_call_prevents_recovery(tmp_path):
    ledger = captured(tmp_path, 'not JSON', state="unknown")
    with pytest.raises(ValueError, match="settled captured calls"):
        captured_failure(ledger, "119", "original")
