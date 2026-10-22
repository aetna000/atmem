import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
export = importlib.import_module('benchmarks.dolphinbench.export')


def test_streamed_tool_arguments_and_usage_are_not_estimated():
    result, usage = export.assistant_response([
        {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'call-1',
            'function': {'name': 'tool_call', 'arguments': '{"calls":'}}]}}]},
        {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0,
            'function': {'arguments': '[]}'}}]}}]},
        {'choices': [], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'cost': 0.001}}])
    assert result['tool_calls'][0]['function'] == {'name': 'tool_call', 'arguments': '{"calls":[]}'}
    assert usage['cost'] == 0.001


def test_stream_without_usage_is_not_zero():
    with pytest.raises(ValueError, match='no API usage'):
        export.assistant_response([{'choices': [{'delta': {'content': 'hello'}}]}])


def test_multiple_response_choices_are_rejected():
    with pytest.raises(ValueError, match='Multiple response'):
        export.assistant_response([{'choices': [{'index': 1, 'delta': {}}]}])


def test_identical_duplicate_argument_keys_are_reversible_not_repaired():
    raw = '{"title":"same","title":"same","missing_name":true}'
    original = {'tool_calls': [{'function': {'name': 'tool_call', 'arguments': raw}}]}
    normalized, changes = export.normalize_identical_argument_keys(original)
    assert original['tool_calls'][0]['function']['arguments'] == raw
    assert changes[0]['original_arguments'] == raw
    assert changes[0]['identical_duplicate_keys'] == ['title']
    assert json.loads(normalized['tool_calls'][0]['function']['arguments']) == {
        'title': 'same', 'missing_name': True}
    assert 'name' not in json.loads(normalized['tool_calls'][0]['function']['arguments'])


@pytest.mark.parametrize('raw', ['{"title":"one","title":"two"}', '{"n":1,"n":true}'])
def test_conflicting_duplicate_argument_keys_are_never_selected(raw):
    with pytest.raises(ValueError, match='Conflicting duplicate'):
        export.normalize_identical_argument_keys({'tool_calls': [{'function': {'arguments': raw}}]})


def witnessed_conflict():
    raw = '{"calls":[{"name":"fixture","arguments":{"n":1},"arguments":{"n":2}}]}'
    call = {'id': 'call-observed', 'function': {'name': 'tool_call', 'arguments': raw}}
    effective = '{"calls":[{"name":"fixture","arguments":{"n":2}}]}'
    messages = [{'role': 'assistant', 'tool_calls': [{'id': call['id'],
        'function': {'name': 'tool_call', 'arguments': effective}}]},
        {'role': 'tool', 'tool_call_id': call['id'], 'content': 'native tool result'}]
    return call, messages, effective


def test_conflicting_keys_require_observed_native_arguments_not_recorder_choice():
    call, messages, effective = witnessed_conflict()
    original = {'tool_calls': [call]}
    result, changes = export.normalize_identical_argument_keys(original,
        observed_next_messages=messages)
    assert result['tool_calls'][0]['function']['arguments'] == effective
    assert original['tool_calls'][0]['function']['arguments'] != effective
    receipt = changes[0]
    assert receipt['original_arguments'] == call['function']['arguments']
    assert receipt['next_request_messages_sha256'] == export.fingerprint(messages)
    assert receipt['conflicting_duplicate_keys'] == ['arguments']
    assert receipt['model_or_tool_replay'] is False
    assert receipt['semantic_repair'] is False


@pytest.mark.parametrize('mutation', ['missing_result', 'wrong_id', 'wrong_name',
    'changed_value', 'duplicate_witness', 'user_message', 'still_duplicate'])
def test_conflicting_keys_reject_unproven_or_changed_native_witness(mutation):
    import copy
    call, messages, effective = witnessed_conflict()
    function = messages[0]['tool_calls'][0]['function']
    if mutation == 'missing_result': messages.pop()
    elif mutation == 'wrong_id': messages[0]['tool_calls'][0]['id'] = 'other'
    elif mutation == 'wrong_name': function['name'] = 'other'
    elif mutation == 'changed_value': function['arguments'] = '{"calls":[]}'
    elif mutation == 'duplicate_witness': messages.insert(0, copy.deepcopy(messages[0]))
    elif mutation == 'user_message': messages[0]['role'] = 'user'
    elif mutation == 'still_duplicate': function['arguments'] = call['function']['arguments']
    with pytest.raises(ValueError):
        export.normalize_identical_argument_keys({'tool_calls': [call]},
            observed_next_messages=messages)


@pytest.fixture
def failed_transport_capture(tmp_path, monkeypatch):
    """Test recording mechanics, not benchmark or training observations."""
    import copy
    from types import ModuleType
    submission = ModuleType('harness.submission')
    submission.SETTINGS_FIELDS = {'model'}
    submission.clean_message = copy.deepcopy
    capture = ModuleType('harness.submission_capture')
    capture.chat_messages = copy.deepcopy
    capture._plain = lambda m: {k: v for k, v in m.items() if k not in {'usage', 'duration_ms'}}
    capture.build_rollout = lambda events: {'settings': events[0]['settings'],
        'messages': events[0]['messages'] + [events[0]['assistant']]}
    monkeypatch.setitem(sys.modules, 'harness.submission', submission)
    monkeypatch.setitem(sys.modules, 'harness.submission_capture', capture)
    messages = [{'role': 'user', 'content': 'fixture request'}]
    answer = {'role': 'assistant', 'content': 'fixture observed answer'}
    for name, body in {
        'a/transport.json': {'started_ns': 1},
        'a/request.json': {'model': 'fixture', 'messages': messages},
        'a/response.json': {'elapsed_seconds': 1, 'response': {'choices': [{'message': answer}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3}}},
        'b/transport.json': {'started_ns': 2},
        'b/request.json': {'model': 'fixture', 'messages': messages + [answer]},
        'b/error.json': {'http_status': 502},
    }.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(body))
    pre = {'event': 'pre_api_request', 'api_request_id': '2',
        'messages_sha256': export.fingerprint(messages + [answer])}
    witnesses = [{'event': 'pre_api_request', 'api_request_id': '1',
        'messages_sha256': export.fingerprint(messages)},
        {'event': 'post_api_request', 'api_request_id': '1'}, pre,
        {'event': 'api_request_error', 'api_request_id': '2'}, pre,
        {'event': 'api_request_error', 'api_request_id': '2'}]
    witness = tmp_path / 'witness.jsonl'
    witness.write_text(''.join(json.dumps(w) + '\n' for w in witnesses))
    return tmp_path, witness


def test_terminal_error_retains_unknown_usage_and_verbatim_runtime_output(failed_transport_capture):
    root, witness = failed_transport_capture
    result = export.export_interaction(root, witness,
        terminal_failure={'exit_code': 1, 'error': 'HTTP 502', 'text': 'verbatim fixture CLI error'})
    assert result['messages'][-1]['content'] == 'verbatim fixture CLI error'
    assert result['messages'][-2]['usage']['prompt_tokens'] == 10
    assert result['failed_transport_attempts'][0]['usage'] is None
    assert result['native_terminal_failure']['model_or_tool_replay'] is False


def test_failed_lifecycle_cannot_be_silently_exported_as_success(failed_transport_capture):
    root, witness = failed_transport_capture
    with pytest.raises(ValueError, match='attempt failed'):
        export.export_interaction(root, witness)


@pytest.fixture
def unforwarded_guard_capture(failed_transport_capture, monkeypatch):
    import hashlib
    from benchmarks.dolphinbench.recording import BudgetLedger
    root, witness = failed_transport_capture
    (root/'b/error.json').unlink()
    payload=json.loads((root/'b/request.json').read_text())
    payload['model']='openai/gpt-5.6-sol'
    (root/'b/request.json').write_text(json.dumps(payload))
    (root/'b/transport.json').write_text(json.dumps({'started_ns':2,'phase':'tests','call_id':'b'}))
    original=root/'qualified-fixture-controller.py'
    original.write_text('# plumbing-only audited control-flow fixture\n')
    monkeypatch.setattr(export,'LEGACY_GUARD_SOURCE_SHA256',hashlib.sha256(original.read_bytes()).hexdigest())
    identity={'test':True}
    book=BudgetLedger(root/'budget.db',cap_usd=1,identity=identity)
    book.close()
    terminal={'exit_code':1,'error':export.UNSENT_GUARD_ERROR,'text':export.UNSENT_GUARD_ERROR}
    proof={'ledger_path':root/'budget.db','campaign_identity':identity,'original_gateway_source':original}
    return root,witness,terminal,proof


def test_unforwarded_guard_requires_exact_ledger_native_and_controller_proof(unforwarded_guard_capture):
    root,witness,terminal,proof=unforwarded_guard_capture
    result=export.export_interaction(root,witness,terminal_failure=terminal,unforwarded_guard=proof)
    attempt=result['failed_transport_attempts'][0]
    assert attempt['usage']=={'prompt_tokens':0,'completion_tokens':0,'cost':0}
    assert attempt['failure_witness']['provider_request_sent'] is False
    assert result['messages'][-1]['usage']=={'prompt_tokens':0,'completion_tokens':0}
    assert result['native_terminal_failure']['model_or_tool_replay'] is False


@pytest.mark.parametrize('mutation',['campaign','reserved','source','call_id','paid','terminal','response_error'])
def test_unforwarded_guard_refuses_absent_or_contradictory_proof(unforwarded_guard_capture,mutation):
    from benchmarks.dolphinbench.recording import BudgetLedger
    root,witness,terminal,proof=unforwarded_guard_capture
    if mutation=='campaign':proof['campaign_identity']={'wrong':True}
    elif mutation=='reserved':
        book=BudgetLedger(root/'budget.db',cap_usd=1,identity=proof['campaign_identity'])
        book.reserve('b',phase='tests',request=json.loads((root/'b/request.json').read_text()),maximum_usd=.1)
        book.close()
    elif mutation=='source':proof['original_gateway_source'].write_text('# changed controller')
    elif mutation=='call_id':(root/'b/transport.json').write_text(json.dumps({'started_ns':2,'phase':'tests','call_id':'other'}))
    elif mutation=='paid':
        request_body=json.loads((root/'b/request.json').read_text());request_body['provider']={'only':['azure']}
        (root/'b/request.json').write_text(json.dumps(request_body))
    elif mutation=='terminal':terminal['error']='other failure'
    elif mutation=='response_error':(root/'b/subscription-failure.json').write_text('{}')
    with pytest.raises(ValueError):
        export.export_interaction(root,witness,terminal_failure=terminal,unforwarded_guard=proof)


@pytest.fixture
def sdk_retry_capture(failed_transport_capture):
    root,_=failed_transport_capture
    root=root/'sdk';root.mkdir()
    messages=[{'role':'user','content':'unchanged fixture question'}]
    request={'model':'fixture','messages':messages,'tools':[],'reasoning_effort':'high'}
    response={'elapsed_seconds':1,'response':{
        'choices':[{'message':{'role':'assistant','content':'actual observed response'}}],
        'usage':{'prompt_tokens':10,'completion_tokens':3}}}
    files={'a/transport.json':{'started_ns':1},
        'a/request.json':{**request,'stream':True,'stream_options':{'include_usage':True}},
        'a/error.json':{'http_status':502},'b/transport.json':{'started_ns':2},
        'b/request.json':request,'b/response.json':response}
    for name,value in files.items():
        path=root/name;path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(value))
    witness=root/'witness.jsonl'
    witness.write_text('\n'.join(json.dumps(value) for value in [
        {'event':'pre_api_request','api_request_id':'native-1','messages_sha256':export.fingerprint(messages)},
        {'event':'post_api_request','api_request_id':'native-1'}])+'\n')
    return root,witness


def test_sdk_streaming_fallback_is_retained_without_rerunning_or_inventing_usage(sdk_retry_capture):
    root,witness=sdk_retry_capture
    result=export.export_interaction(root,witness)
    failed=result['failed_transport_attempts']
    assert len(failed)==1 and failed[0]['usage'] is None
    assert failed[0]['failure_witness']['native_request_id']=='native-1'
    assert failed[0]['failure_witness']['framing_changes']['stream']=={'failed':True,'successful':None}
    assert failed[0]['failure_witness']['model_or_tool_replay'] is False
    assert result['messages'][-1]['content']=='actual observed response'


@pytest.mark.parametrize('mutation',['semantic_change','ambiguous','missing_error','nonretryable','auxiliary','unwitnessed','stream_option'])
def test_sdk_retry_refuses_unwitnessed_or_semantically_changed_requests(sdk_retry_capture,mutation):
    root,witness=sdk_retry_capture
    path=root/'b/request.json';request=json.loads(path.read_text())
    if mutation=='semantic_change':
        request['reasoning_effort']='medium';path.write_text(json.dumps(request))
    elif mutation=='ambiguous':
        (root/'c').mkdir()
        for name in ('request.json','response.json'):(root/'c'/name).write_bytes((root/'b'/name).read_bytes())
        (root/'c/transport.json').write_text(json.dumps({'started_ns':3}))
    elif mutation=='missing_error':(root/'a/error.json').unlink()
    elif mutation=='nonretryable':(root/'a/error.json').write_text(json.dumps({'http_status':400}))
    elif mutation=='stream_option':
        request['stream_options']={'unsupported_option':True};path.write_text(json.dumps(request))
    else:
        events=[json.loads(line) for line in witness.read_text().splitlines()]
        if mutation=='auxiliary':
            events[0]['event']='pre_auxiliary_call';events[1]['event']='post_auxiliary_call'
        else:events[0]['messages_sha256']='0'*64
        witness.write_text('\n'.join(json.dumps(e) for e in events)+'\n')
    with pytest.raises(ValueError,match='Unreconciled missing'):export.export_interaction(root,witness)


def test_unknown_missing_response_needs_actual_error_receipt(failed_transport_capture):
    root, witness = failed_transport_capture
    (root / 'b/error.json').unlink()
    with pytest.raises(ValueError, match='Unreconciled missing'):
        export.export_interaction(root, witness,
            terminal_failure={'exit_code': 1, 'error': 'HTTP 502', 'text': 'native failure'})
