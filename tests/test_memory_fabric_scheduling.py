import pytest

from research.memory_fabric.scheduling import Scheduler, Work
from research.memory_fabric.homa_experiment import run_trial, workload


def test_service_debt_picks_oldest_large_job_despite_stream_of_small_jobs():
    scheduler = Scheduler("homa", {"write": .100, "recall": .001})
    old = Work(0, 0, "write", 100)
    queue = [old, Work(1, .001, "recall", 10)]
    selected, _ = scheduler.pick(queue, .001)
    assert selected == 1
    scheduler.finish(queue.pop(selected), .001)
    queue.append(Work(2, .002, "recall", 10))
    selected, reason = scheduler.pick(queue, .002)
    assert queue[selected] == old
    assert reason == "oldest_service_debt"


def test_one_large_task_cannot_bank_unbounded_credit():
    scheduler = Scheduler("homa", {"write": .1, "recall": .001})
    scheduler.oldest_debt = .001
    old = Work(0, 0, "write", 100)
    queue = [old, Work(1, 0, "recall", 1)]
    scheduler.pick(queue, 0)
    scheduler.finish(old, 10)
    assert scheduler.oldest_debt == -.005
    # Accrual uses actual service, so 5ms of credit takes 100ms of short
    # service to repay, not an arbitrary number of completed jobs.
    remaining = Work(2, 0, "write", 100)
    elapsed = 0
    for i in range(3, 110):
        queue = [remaining, Work(i, elapsed + .001, "recall", 1)]
        selected, _ = scheduler.pick(queue, elapsed)
        if selected == 0:
            assert elapsed <= .103
            break
        scheduler.finish(queue[selected], .001)
        elapsed += .001
    else:
        pytest.fail("oldest job starved")


def test_size_order_is_not_hidden_behind_nonurgent_deadline():
    scheduler = Scheduler("homa", {"write": .010, "recall": .020})
    jobs = [Work(0, 0, "recall", 1, 10), Work(1, .01, "write", 1)]
    assert scheduler.pick(jobs, .1)[0] == 1


def test_fair_bulk_debt_precedes_urgent_deadline():
    scheduler = Scheduler("fair", {"write": .02, "recall": .01})
    scheduler.bulk_debt = .01
    jobs = [Work(0, 0, "recall", 1, .001), Work(1, 0, "write", 1)]
    assert scheduler.pick(jobs, .002) == (1, "bulk_service_debt")


def test_invalid_duplicate_and_mismatched_completions_rejected():
    scheduler = Scheduler("homa", {"recall": .01})
    job = Work(1, 0, "recall", 1)
    scheduler.pick([job], 0)
    with pytest.raises(ValueError):
        scheduler.pick([job], 0)
    with pytest.raises(ValueError):
        scheduler.finish(Work(2, 0, "recall", 1), .01)
    with pytest.raises(ValueError):
        scheduler.finish(job, float("nan"))
    scheduler.finish(job, .01)
    with pytest.raises(ValueError):
        scheduler.finish(job, .01)


def test_idle_classes_do_not_bank_service():
    scheduler = Scheduler("fair", {"recall": .01})
    scheduler.oldest_debt = scheduler.bulk_debt = 5
    job = Work(1, 0, "recall", 1)
    scheduler.pick([job], 0)
    scheduler.finish(job, 2)
    assert scheduler.oldest_debt == scheduler.bulk_debt == 0


def test_workloads_are_seeded_and_not_fixed_operation_cycles():
    media = [("image/png", b"fixture")]
    first = workload(101, 100, 40, "mixed", media)
    assert first == workload(101, 100, 40, "mixed", media)
    assert first != workload(103, 100, 40, "mixed", media)
    assert sum(job.kind == "write" for job in first) == 15


def test_real_trial_checks_exact_context_and_encrypted_evidence():
    report = run_trial(policy="homa", count=20, rate=15)
    assert report["summary"]["all"]["completed"] == 20
    assert report["quality"]["exact_read_digest_failures"] == 0
    assert report["quality"]["exact_read_digest_matches"] == report["summary"]["recall"]["completed"]
    assert report["quality"]["reconstructed_events"] == 20
    assert report["quality"]["recovered_artifacts"] == report["summary"]["artifact"]["completed"]


def test_legacy_bulk_job_count_can_starve_an_old_large_bulk_task():
    from research.memory_fabric.simulation import adversarial_report
    result = adversarial_report()["results"]
    assert result["legacy"]["oldest_write_start_s"] >= .49
    assert result["homa"]["oldest_write_start_s"] <= .002
    assert {row["completed"] for row in result.values()} == {501}
    assert max(row["makespan_s"] for row in result.values()) == pytest.approx(.55)


def test_bounded_admission_retains_refusals_and_unattainable_offered_percentile():
    report = run_trial(policy="homa", count=20, rate=100000, max_outstanding=1)
    summary = report["summary"]["all"]
    assert summary["completed"] + summary["refused"] + summary["error"] == 20
    assert summary["refused"] > 1
    assert summary["all_offered_p95_attainable"] is False
    assert summary["all_offered_p95_completion_bound_s"] is None
    assert report["quality"]["reconstructed_events"] == summary["completed"]


def test_analysis_never_turns_missing_or_zero_throughput_into_a_win():
    from research.memory_fabric.analyze_fairness import interval
    assert interval([1, None])["bootstrap_95"] == [None, None]
    assert interval([1, 0])["geometric_mean_ratio"] is None
