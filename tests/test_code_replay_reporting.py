"""Reporting arithmetic only; rows below are explicitly test fixtures."""
from benchmarks.code_replay.report import summarize, markdown


def row(arm, repetition=1, order=1, status="passed", delivered=0):
    return {"run": {"arm": arm, "repetition": repetition, "task_id": "fixture-task"}, "task_order": order,
            "result": {"status": status, "memory_ids": ["fixture-record"] * delivered, "context_sha256": "a" * 64,
                "measurements": {"input_tokens": 100, "cached_tokens": 20, "output_tokens": 5, "elapsed_ms": 1200,
                                 "context_bytes": 200},
                "stage_ms": {"setup": 100, "index": 100, "retrieval": 20, "capture": 5, "solver": 975, "grading": 10}},
            "formation": {"candidates": 1 if arm == "D" else 0, "admitted": 1 if arm == "D" else 0},
            "applicability": []}


def test_missing_rows_remain_in_planned_denominator_and_cost_unknown():
    rows = [row("C"), row("D", status="failed")]
    summary = summarize(rows)
    assert summary["C"]["expected"] == 10
    assert summary["C"]["completed"] == 1 and summary["C"]["missing"] == 9
    assert summary["D"]["failed"] == 1 and summary["D"]["passed"] == 0
    assert summary["D"]["billing_cost"] is None
    assert summary["D"]["input_tokens"] == 100  # cache is a subset
    rendered = markdown(rows, summary, "a" * 64)
    assert "cannot be attributed" in rendered
    assert "unknown" in rendered and "missing" in rendered
    assert "complete independently observed" in rendered


def test_delivered_count_is_actual_record_exposure_not_admission():
    rows = [row("D", order=1), row("D", order=2, delivered=1)]
    result = summarize(rows)["D"]
    assert result["admitted"] == 2 and result["memory_deliveries"] == 1
    assert result["end_to_end_total_ms"] == 2400
    assert summarize([])["C"]["input_tokens"] is None
