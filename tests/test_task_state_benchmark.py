"""Release-gate coverage for the governed task-state benchmark."""

from atmem.benchmark import run_task_state_benchmark


def test_task_state_benchmark_covers_the_spec_007_risk_set() -> None:
    report = run_task_state_benchmark()

    assert report["format"] == "atmem-task-state-benchmark-report-v1"
    assert report["passed"] is True
    assert report["passed_cases"] == 10
    assert {row["case_id"] for row in report["case_results"]} == {
        "completed",
        "remaining",
        "blocked",
        "skipped",
        "failed",
        "repeated-action",
        "premature-finish",
        "expired",
        "overflow",
        "instruction-shaped",
    }
    assert report["report_sha256"].startswith("sha256:")
