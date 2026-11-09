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


def test_frozen_class_version_groups_include_missing_tasks_and_unassessed_units(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    tasks = ({"outcome_id":"outcome", "episode_id":"one", "answerable":True,
              "task_class":"filing", "versions":{"adapter":"v1", "profile":"p1"}},
             {"outcome_id":"missing", "episode_id":"two", "answerable":True,
              "task_class":"correction", "versions":{"adapter":"v2", "profile":"p1"}})
    f.feedback.schedule(f.owner["token"], f.scope, schedule_id="grouped", tasks=tasks)
    f.feedback.report_outcome(f.session, outcome, idempotency_key="grouped-outcome")
    report = f.feedback.quality(f.session, schedule_id="grouped")
    assert report["verified_full_task_success"] == rate(0, 2)
    assert report["uncertainty"]["verified_full_task_success"]["episodes"] == 2
    assert report["uncertainty"]["wrong_answer_rate"]["estimate"] is None
    for field in ("task_class", "versions"):
        assert len(report["groups"][field]) == 2
        assert sum(group["report"]["verified_full_task_success"]["denominator"] for group in report["groups"][field]) == 2
        assert all(group["status"] == "frozen" for group in report["groups"][field])
        assert all(group["report"]["scope"] == f.scope.to_dict() for group in report["groups"][field])
    missing = report["groups"]["task_class"][1]["report"]
    assert missing["missing_tasks"] == 1 and missing["uncertainty"]["coverage"]["lower"] is None
    legacy = summarize(f.scope, [{"outcome_id":"outcome", "episode_id":"one", "answerable":True}], [(outcome,[])])
    assert legacy["groups"]["versions"][0]["status"] == "unspecified"
    with pytest.raises(FeedbackError, match="conflicting_retry"):
        f.feedback.schedule(f.owner["token"], f.scope, schedule_id="grouped", tasks=(
            {**tasks[0], "versions":{"adapter":"retroactive"}}, tasks[1]))


def test_rate_uncertainty_clusters_units_and_preserves_undefined_denominators():
    from atmem.feedback.metrics import episode_rate_interval
    units = (("one", 20, 20), ("one", 20, 20), ("two", 0, 1))
    result = episode_rate_interval(units)
    assert result == episode_rate_interval(units)
    assert result["episodes"] == 2 and result["units"] == 41
    assert result["estimate"] == 40/41 and result["lower"] == 0 and result["upper"] == 1
    assert episode_rate_interval(())["estimate"] is None
    assert episode_rate_interval((("one", 0, 0),))["episodes"] == 0
    for unit in (("one", True, 1), ("one", 2, 1)):
        with pytest.raises(ValueError):
            episode_rate_interval((unit,))
