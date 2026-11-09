from dataclasses import replace

import pytest

from atmem.feedback.metrics import paired_episode_interval, rate, summarize
from atmem.feedback.store import FeedbackError
from test_feedback_actions import actions_fixture


def test_missing_unknown_and_abstain_all_never_imply_good_quality(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    schedule = [{"outcome_id": "outcome", "episode_id": "episode", "answerable": True},
                {"outcome_id": "missing", "episode_id": "episode-2", "answerable": True}]
    report = summarize(f.scope, schedule, [(outcome, [])])
    assert report["verified_full_task_success"] == rate(0, 2)
    assert report["coverage"] == rate(0, 2)
    assert report["unknown_tasks"] == 2 and report["missing_tasks"] == 1
    for metric in ("wrong_answer_rate", "evidence_precision", "false_denial_rate", "required_fact_write_failure"):
        assert report[metric]["value"] is None
    assert rate(0, 0)["status"] == "insufficient_evidence"
    with pytest.raises(ValueError):
        rate(True, 1)


def test_independent_assessment_denominators_conflicts_and_scope(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    schedule = [{"outcome_id": "outcome", "episode_id": "episode", "answerable": True}]
    assessments = [dict(outcome_id="outcome", metric="wrong_answer_rate", unit_id="answer", positive=True),
                   dict(outcome_id="outcome", metric="wrong_answer_rate", unit_id="unassessed", positive=None),
                   dict(outcome_id="outcome", metric="required_fact_write_failure", unit_id="write", positive=True)]
    report = summarize(f.scope, schedule, [(outcome, [])], assessments=assessments)
    assert report["wrong_answer_rate"] == rate(1, 1)
    assert report["unassessed_units"]["wrong_answer_rate"] == 1
    assert report["required_fact_write_failure"] == rate(1, 1)
    assessments.append({**assessments[0], "positive": False})
    report = summarize(f.scope, schedule, [(outcome, [])], assessments=assessments)
    assert report["wrong_answer_rate"] == rate(0, 0)
    assert report["disputed_units"]["wrong_answer_rate"] == 1
    with pytest.raises(ValueError):
        summarize(replace(f.scope, subject_id="bob"), schedule, [(outcome, [])])


def test_service_uses_owner_frozen_schedule_and_current_scoped_evidence(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    tasks = ({"outcome_id": "outcome", "episode_id": "episode", "answerable": True},)
    with pytest.raises(FeedbackError, match="denied"):
        f.feedback.schedule(f.user["token"], f.scope, schedule_id="schedule", tasks=tasks)
    f.feedback.schedule(f.owner["token"], f.scope, schedule_id="schedule", tasks=tasks)
    assert f.feedback.quality(f.session, schedule_id="schedule")["missing_tasks"] == 1
    f.feedback.report_outcome(f.session, outcome, idempotency_key="observation")
    assert f.feedback.quality(f.session, schedule_id="schedule")["missing_tasks"] == 0
    with pytest.raises(FeedbackError, match="schedule_after_observation"):
        f.feedback.schedule(f.owner["token"], f.scope, schedule_id="late", tasks=tasks)


def test_episode_uncertainty_does_not_treat_correlated_tasks_as_independent():
    one = paired_episode_interval(tuple(("one", False, True) for _ in range(10)))
    assert one["status"] == "inconclusive" and one["lower"] is None
    pairs = (("one", False, True), ("two", True, False))
    result = paired_episode_interval(pairs)
    assert result == paired_episode_interval(pairs)
    assert result["estimate"] == 0 and result["lower"] == -1 and result["upper"] == 1
    assert result["claim"] == "diagnostic_only"
