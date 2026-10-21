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


def test_unknown_missing_response_needs_actual_error_receipt(failed_transport_capture):
    root, witness = failed_transport_capture
    (root / 'b/error.json').unlink()
    with pytest.raises(ValueError, match='Unreconciled missing'):
        export.export_interaction(root, witness,
            terminal_failure={'exit_code': 1, 'error': 'HTTP 502', 'text': 'native failure'})
