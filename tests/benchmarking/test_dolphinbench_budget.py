import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).parents[2] / 'benchmarks/dolphinbench/recording.py'
spec = importlib.util.spec_from_file_location('dolphin_budget', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BudgetLedger = module.BudgetLedger


def ledger(tmp_path, **kwargs):
    return BudgetLedger(tmp_path / 'ledger.sqlite', cap_usd=kwargs.get('cap', 1), identity={'test': 1})


def reserve(book, name, cost=0.6, phase='judge'):
    book.reserve(name, phase=phase, request={'input': name}, maximum_usd=cost)


def test_inflight_counted_before_network_and_across_restart(tmp_path):
    first = ledger(tmp_path)
    reserve(first, 'one')
    first.close()
    second = ledger(tmp_path)
    with pytest.raises(PermissionError):
        reserve(second, 'two')
    assert second.totals()['judge']['reserved_usd'] == 0.6


def test_replay_and_changed_configuration_denied(tmp_path):
    book = ledger(tmp_path)
    reserve(book, 'one')
    with pytest.raises(ValueError):
        reserve(book, 'one', 0.1)
    with pytest.raises(ValueError):
        ledger(tmp_path, cap=2)


def test_real_usage_settles_once_and_keeps_phases_separate(tmp_path):
    book = ledger(tmp_path)
    reserve(book, 'one')
    book.complete('one', actual_usd=0.000396, usage={'prompt_tokens': 24, 'completion_tokens': 15}, response={'id': '1'})
    reserve(book, 'two', 0.5, 'tests')
    assert book.totals()['judge']['actual_usd'] == 0.000396
    assert book.totals()['tests']['reserved_usd'] == 0.5
    with pytest.raises(ValueError):
        book.complete('one', actual_usd=0, usage={'prompt_tokens': 0, 'completion_tokens': 0}, response={})


def test_unknown_usage_and_uncertain_failure_remain_reserved(tmp_path):
    book = ledger(tmp_path)
    reserve(book, 'one')
    with pytest.raises(ValueError):
        book.complete('one', actual_usd=0, usage={}, response={})
    with pytest.raises(PermissionError):
        book.cancel_unsent('one')
    assert book.totals()['judge']['reserved_usd'] == 0.6
    book.cancel_unsent('one', proven_unsent=True)
    assert book.totals()['judge']['reserved_usd'] == 0


def test_concurrent_ledgers_share_reservations(tmp_path):
    first, second = ledger(tmp_path), ledger(tmp_path)
    reserve(first, 'one')
    with pytest.raises(PermissionError):
        reserve(second, 'two')


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True])
def test_bad_prices_denied(value):
    with pytest.raises(ValueError):
        module.micros(value)


def test_provider_overrun_retained_and_stops_future_calls(tmp_path):
    book = ledger(tmp_path)
    reserve(book, 'one', 0.1)
    with pytest.raises(RuntimeError):
        book.complete('one', actual_usd=1.1, usage={'prompt_tokens': 20, 'completion_tokens': 10}, response={})
    assert book.totals()['judge']['actual_usd'] == 1.1
    with pytest.raises(PermissionError):
        reserve(book, 'two', 0.01)


@pytest.mark.parametrize('reader_model',['openai/gpt-5.6-luna','openai/gpt-5.6-sol'])
def test_subscription_failure_is_not_a_completed_zero_token_answer(tmp_path,reader_model):
    import json
    book = ledger(tmp_path)
    request = {'model':reader_model, 'messages': []}
    book.reserve('sub', phase='tests', request=request, maximum_usd=0.2)
    proof = {'provider': 'OpenAI-Subscription', 'response_delivered': False}
    book.settle_subscription_failure('sub', request=request, failure_receipt=proof)
    state, bound, actual, usage = book.connection.execute(
        'SELECT state,reserved,actual,usage_json FROM calls').fetchone()
    assert state == 'subscription_failure_usage_unknown' and bound == 200000 and actual == 0
    assert json.loads(usage)['token_usage'] is None
    assert book.totals()['tests']['reserved_usd'] == 0
    with pytest.raises(ValueError):
        book.settle_subscription_failure('sub', request=request, failure_receipt=proof)


def test_subscription_failure_cannot_release_paid_api_reservation(tmp_path):
    book = ledger(tmp_path)
    reserve(book, 'paid', 0.2)
    with pytest.raises(ValueError):
        book.settle_subscription_failure('paid', request={'model': 'openai/gpt-5.6-sol'},
            failure_receipt={'provider': 'Azure', 'response_delivered': False})
    assert book.totals()['judge']['reserved_usd'] == 0.2


def test_subscription_cash_zero_still_requires_actual_token_usage(tmp_path):
    book = ledger(tmp_path, cap=0.001)
    request = {'model': 'openai/gpt-5.6-sol', 'messages': []}
    book.reserve_subscription('sub', phase='tests', request=request)
    with pytest.raises(ValueError, match='unknown is not zero'):
        book.complete('sub', actual_usd=0, usage={}, response={})
    book.complete('sub', actual_usd=0,
                  usage={'prompt_tokens': 25000, 'completion_tokens': 900}, response={'id': 'sub'})
    row = book.connection.execute('SELECT reserved,actual,state,usage_json FROM calls').fetchone()
    assert row[:3] == (0, 0, 'completed')
    assert '25000' in row[3]
    with pytest.raises(ValueError):
        book.reserve('paid', phase='tests', request=request, maximum_usd=0)


def test_subscription_unexpected_cash_is_retained_as_overrun(tmp_path):
    book = ledger(tmp_path)
    request = {'model': 'openai/gpt-5.6-sol'}
    book.reserve_subscription('sub', phase='tests', request=request)
    with pytest.raises(RuntimeError, match='exceeded reservation'):
        book.complete('sub', actual_usd=0.01,
                      usage={'prompt_tokens': 12, 'completion_tokens': 5}, response={})
    assert book.totals()['tests']['actual_usd'] == 0.01
    with pytest.raises(PermissionError):
        book.reserve_subscription('next', phase='tests', request=request)


@pytest.mark.parametrize('payload', [
    {'model': 'unknown'}, {'model': 'openai/gpt-5.6-sol', 'provider': {}},
])
def test_subscription_does_not_accept_paid_routing_or_unknown_model(tmp_path, payload):
    with pytest.raises(ValueError):
        ledger(tmp_path).reserve_subscription('sub', phase='tests', request=payload)
