import json
from types import SimpleNamespace

import pytest

from research.retrieval_2310.grading import judge_request, parse_verdict


def test_grader_is_separate_fixed_model_and_has_no_provider_fallback():
    request = judge_request(question='fixture', reference='reference', prediction='prediction', history='source')
    assert request['model'] == 'openai/gpt-5.6-sol'
    assert request['provider'] == {'only': ['Azure'], 'allow_fallbacks': False}
    assert request['reasoning_effort'] == 'medium'


@pytest.mark.parametrize('text', [
    '{"passed":1,"reference_issue":false,"reason":"not boolean"}',
    '{"passed":true,"reference_issue":true,"reason":"contradictory"}',
    '{"passed":true,"reference_issue":false,"reason":"ok","extra":"unknown"}',
    'not JSON',
])
def test_invalid_or_self_contradicting_grades_cannot_pass(text):
    with pytest.raises(ValueError):
        parse_verdict(text)


def test_controls_are_fixed_answer_mutations_not_new_source_observations():
    from research.retrieval_2310.grade_run import controls
    source = {'session_1': [
        {'dia_id': 'D1:29', 'clean_text': 'I study at NYU'},
        {'dia_id': 'D1:32', 'clean_text': "I'm Kate"},
        {'dia_id': 'D1:28', 'clean_text': 'majoring in Economics'},
    ]}
    cases = controls(source)
    assert len(cases) == 6
    assert sum(case['expected'] for case in cases) == 3
    assert {case['source_turn_id'] for case in cases} == {'D1:29', 'D1:32', 'D1:28'}
    assert source['session_1'][0]['clean_text'] == 'I study at NYU'


def test_grading_children_cannot_spend_reserved_final_or_unknown_cost(tmp_path):
    from research.retrieval_2310.grade_run import claim_budget, settle_budget
    from research.retrieval_2310.protocol import CampaignLedger
    path = tmp_path/'ledger.db'
    ledger = CampaignLedger(path)
    ledger.reserve('confidence-and-judging', '40')
    ledger.reserve('final-600-and-comparator', '200')
    ledger.close()
    claim_budget(path, 'one')
    with pytest.raises(ValueError, match='allocation unavailable'):
        claim_budget(path, 'two')
    settle_budget(path, 'one', 700_000)
    claim_budget(path, 'two')
    with pytest.raises(ValueError, match='missing child allocation'):
        settle_budget(path, 'one', 0)


def test_judge_transport_is_arm_blind_and_does_not_override_gateway_route(monkeypatch):
    from research.retrieval_2310.grade_run import call_judge
    calls = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps({'id': 'fixture-response', 'usage': {}, 'choices': [
                {'finish_reason': 'stop', 'message': {'content':
                    '{"passed":true,"reference_issue":false,"reason":"supported"}'}}]}).encode()
    def send(request, timeout):
        calls.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr('urllib.request.urlopen', send)
    gateway = SimpleNamespace(base_url='http://127.0.0.1:1234/v1', local_token='fixture-local-token')
    result = call_judge(gateway, judge_request(question='fixture', reference='supported',
                                            prediction='supported', history='original fixture'))
    assert result['verdict']['passed'] is True
    assert len(calls) == 1
    assert 'provider' not in calls[0]
    assert 'arm' not in json.loads(calls[0]['messages'][1]['content'])
    assert calls[0]['response_format'] == {'type': 'json_object'}


def test_judge_transport_error_is_not_automatically_retried(monkeypatch):
    from research.retrieval_2310.grade_run import call_judge
    calls = []
    def fail(*args, **kwargs):
        calls.append(True)
        raise TimeoutError('fixture')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    gateway = SimpleNamespace(base_url='http://127.0.0.1:1234/v1', local_token='fixture-local-token')
    with pytest.raises(TimeoutError):
        call_judge(gateway, judge_request(question='fixture', reference='supported',
                                         prediction='supported', history='original fixture'))
    assert len(calls) == 1
