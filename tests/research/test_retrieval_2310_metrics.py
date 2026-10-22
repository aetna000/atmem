"""Unit-level arithmetic checks, not benchmark efficacy evidence."""
import pytest

from research.retrieval_2310.evaluate import Outcome, paired_summary, readiness, wilson


def outcome(i, passed, tokens=10, cluster=None):
    return Outcome(str(i), cluster or str(i), passed, float(i+1), tokens, 2)


def test_exact_pairs_and_failures_remain_denominator():
    base = [outcome(i, False) for i in range(10)]
    candidate = [outcome(i, i < 9) for i in range(10)]
    result = paired_summary(base, candidate)
    assert result['candidate']['accuracy'] == .9
    assert result['candidate']['tasks'] == 10
    assert result['paired_wins'] == 9
    assert result['ready_for_600'] is False
    assert result['accuracy_delta'] == .9


def test_unknown_usage_does_not_become_zero_claim():
    result = paired_summary([outcome(0, False)], [outcome(0, True, tokens=None)])
    assert result['candidate']['tasks_with_unknown_usage'] == 1
    assert result['cluster_bootstrap_95_delta_interval'] is None
    assert readiness(result, pillars_accepted=4, transfer_accepted=True,
                     review_passed=True, guardrails_passed=True,
                     matched_mem0=True, powered_confirmation=True)['ready_for_600'] is False


def test_missing_and_duplicate_results_refused():
    with pytest.raises(ValueError, match='identical complete'):
        paired_summary([outcome(1, False)], [])
    with pytest.raises(ValueError, match='identical complete'):
        paired_summary([outcome(1, False)]*2, [outcome(1, True)])


def test_ninety_percent_alone_is_not_readiness():
    result = paired_summary([outcome(i, True) for i in range(10)],
                            [outcome(i, True) for i in range(10)])
    gate = readiness(result, pillars_accepted=4, transfer_accepted=True,
                     review_passed=True, guardrails_passed=True,
                     matched_mem0=True, powered_confirmation=True)
    assert gate['ready_for_600'] is False
    assert gate['conditions']['positive_cluster_lower_bound'] is False


def test_wilson_and_single_cluster_warning():
    low, high = wilson(90, 100)
    assert .82 < low < .84 and .94 < high < .95
    result = paired_summary([outcome(i, False, cluster='same') for i in range(10)],
                            [outcome(i, True, cluster='same') for i in range(10)])
    assert result['cluster_bootstrap_95_delta_interval'] is None
    assert result['cluster_inference_warning']
