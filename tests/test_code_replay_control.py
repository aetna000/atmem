"""No inference: follow-up control invariants and summary parsing."""
import pytest
from benchmarks.code_replay.control import SCHEDULE, prompt_for, validate
from benchmarks.code_replay.pilot import summary_counts
from benchmarks.code_replay.control_report import summarize, terminal_rows


def test_native_control_has_no_supplied_knowledge():
    task = {"requirements": "Fix the documented behavior."}
    native = prompt_for(task, "/qualified/python", "")
    structured = prompt_for(task, "/qualified/python", "SOURCE-BOUND-KNOWLEDGE")
    assert structured.replace("SOURCE-BOUND-KNOWLEDGE", "") == native
    assert "SOURCE-BOUND-KNOWLEDGE" not in native
    assert len(SCHEDULE) == 5
    assert all(sorted(pair) == ["A", "C"] for pair in SCHEDULE)


def test_control_rejects_wrong_binding():
    with pytest.raises(ValueError, match="binding"):
        validate({}, "0" * 64)


def test_pytest_ansi_does_not_corrupt_counts():
    assert summary_counts(b"\x1b[32m1200 passed\x1b[0m, \x1b[33m1 deselected\x1b[0m in 3.4s") == {"passed": 1200, "deselected": 1}


def test_report_distinguishes_functional_and_budget_pass_unknown_usage():
    rows = [{"arm": arm, "task_order": order, "passed": arm == "C", "functional_pass": True,
             "infra_invalid": False, "stage_ms": {"setup": 1, "index": 2, "retrieval": 3, "solver": 1000, "grading": 10},
             "tool_calls": 10, "context_bytes": 0 if arm == "A" else 123,
             "tokens": {"input_tokens": None if arm == "A" else 10, "output_tokens": None if arm == "A" else 1,
                        "cached_tokens": None if arm == "A" else 5}}
            for order in range(1, 6) for arm in "AC"]
    summary = summarize(rows)
    assert summary["A"]["passed"] == 0 and summary["A"]["functional_pass"] == 5
    assert summary["A"]["input_tokens"] is None and summary["A"]["usage_receipts"] == 0
    assert summary["C"]["passed"] == 5 and summary["C"]["input_tokens"] == 50
    with pytest.raises(ValueError):
        summarize(rows[:-1])
    with pytest.raises(ValueError):
        terminal_rows({"click-ac-v3q-a-t1": []})
