import json

import pytest

from research.retrieval_2310.reader_report import summarize


def fixture_run(tmp_path, *, usage=None, provider='OpenAI-Subscription'):
    (tmp_path/'results').mkdir()
    (tmp_path/'manifest.json').write_text(json.dumps({
        'authentication': 'existing-Hermes-ChatGPT-subscription', 'paid_fallback': False,
        'reader': 'gpt-5.6-luna', 'cases': [['baseline', 1], ['baseline', 2]],
    }))
    (tmp_path/'results'/'baseline-1.json').write_text(json.dumps({
        'arm': 'baseline', 'qa_index': 1, 'duration_ms': 2., 'error': None,
        'response': {'provider': provider, 'model': 'openai/gpt-5.6-luna', 'usage': usage},
    }))
    return tmp_path


def test_partial_unknown_usage_is_not_free_complete_or_quality_evidence(tmp_path):
    report = summarize(fixture_run(tmp_path))
    assert report['all_cases_attempted'] is False
    assert report['ready_for_600'] is False
    arm = report['arms']['baseline']
    assert arm['cases_with_unknown_token_usage'] == 1
    assert arm['cases_with_confirmed_zero_incremental_api_charge'] == 0
    assert arm['fully_correct_answers'] is None


def test_explicit_subscription_cash_receipt_preserves_usage(tmp_path):
    report = summarize(fixture_run(tmp_path, usage={
        'prompt_tokens': 9, 'completion_tokens': 5, 'cost': 0.,
        'cost_basis': 'incremental_api_charge_zero_subscription_usage_not_free_or_unlimited',
    }))
    arm = report['arms']['baseline']
    assert arm['known_prompt_tokens'] == 9
    assert arm['known_completion_tokens'] == 5
    assert arm['cases_with_confirmed_zero_incremental_api_charge'] == 1


def test_paid_provider_cannot_be_reported_as_subscription(tmp_path):
    with pytest.raises(ValueError, match='model/provider'):
        summarize(fixture_run(tmp_path, provider='Azure'))
