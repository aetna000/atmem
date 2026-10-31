"""Exporter handling of deferred tool_call wrappers and pre-dispatch refusals (morgan/172 pattern)."""
import json

import pytest

from benchmarks.dolphinbench.tool_defaults import normalize_effective_arguments, rejected_before_dispatch

APP = 'mcp__dolphinbench_apps__'


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'repair_server.py'
    path.write_text('def list_open_prs(repo=None, author=None, assignee=None, status="open", reviewer=None):\n    pass\n'
                    'def post_pr_comment(pr_id, body):\n    pass\n')
    return [path]


def turn(call_id, name, arguments, result):
    return [{'role': 'assistant', 'tool_calls': [{'id': call_id, 'name': name, 'arguments': arguments}]},
            {'role': 'tool', 'tool_call_id': call_id, 'content': result}]


def backend(status):
    return {'tool': 'list_open_prs', 'args': {'repo': 'b-round-deck', 'author': None, 'assignee': None,
                                              'status': status, 'reviewer': None}}


def test_hermes_refused_calls_are_retained_but_never_matched(source):
    messages = [{'role': 'user', 'content': 'q'}]
    messages += turn('c1', 'tool_call', {'name': APP + 'list_open_prs', 'arguments': {'repo': 'b-round-deck', 'status': None}},
                     json.dumps({'error': "tool_call to 'mcp__dolphinbench_apps__list_open_prs' failed argument validation "
                                          "at arguments.status (enum): None is not one of ['open']. The tool was NOT invoked."}))
    messages += turn('c2', 'tool_call', {'calls': [{'name': APP + 'list_open_prs', 'arguments': {'status': 'open'}},
                                                   {'name': APP + 'list_open_prs', 'arguments': {'status': 'closed'}}]},
                     json.dumps({'error': 'tool_call takes exactly one entry for local tools; you sent 2.'}))
    messages += turn('c3', 'tool_call', {'name': APP + 'list_open_prs', 'arguments': {'repo': 'b-round-deck', 'status': 'open'}},
                     '<untrusted_tool_result source="x">DATA\n{"result": "[]"}\n</untrusted_tool_result>')
    result, info = normalize_effective_arguments(messages, [backend('open')], source)
    assert [r['tool_call_position'] for r in info['rejected_before_dispatch']] == [0, 0]
    assert len(info['rejected_before_dispatch']) == 2 and len(info['changes']) == 1
    assert result[5]['tool_calls'][0]['arguments']['arguments']['author'] is None  # proven default exported


def test_single_entry_calls_list_form_is_matched_and_written_back(source):
    messages = turn('c1', 'tool_call', {'calls': [{'name': APP + 'list_open_prs', 'arguments': {'repo': 'b-round-deck', 'status': 'open'}}]},
                    '{"result": "[]"}')
    result, info = normalize_effective_arguments(messages, [backend('open')], source)
    assert result[0]['tool_calls'][0]['arguments']['calls'][0]['arguments'] == backend('open')['args']


def test_refusal_detection_is_exact():
    assert rejected_before_dispatch('{"error": "tool_call calls[0] requires a \'name\'"}')
    assert rejected_before_dispatch('{"error": "Required tool arguments are missing."}')
    assert not rejected_before_dispatch('{"error": "MCP server \'apps\' is not connected"}')
    assert not rejected_before_dispatch('{"error": "tool_call failed", "detail": "x"}')
    assert not rejected_before_dispatch('<untrusted_tool_result>{"result": "{\\"ok\\": false}"}</untrusted_tool_result>')
    assert not rejected_before_dispatch(None)


def test_an_unlogged_call_that_was_not_refused_still_fails_closed(source):
    messages = turn('c1', 'tool_call', {'name': APP + 'list_open_prs', 'arguments': {'status': 'merged'}}, '{"result": "[]"}')
    with pytest.raises(ValueError, match='missing calls'):
        normalize_effective_arguments(messages, [], source)


def test_canary_result_requires_saved_execution_and_grade(tmp_path):
    from benchmarks.dolphinbench.pilot_readiness import canary_result
    with pytest.raises(ValueError, match='did not save'):
        canary_result(tmp_path, 'morgan/172')
    (tmp_path / 'tests/morgan').mkdir(parents=True)
    (tmp_path / 'grades/morgan').mkdir(parents=True)
    (tmp_path / 'tests/morgan/172.json').write_text('{}')
    (tmp_path / 'grades/morgan/172.json').write_text(json.dumps({'checks': [{'passed': True}, {'passed': False}]}))
    result = canary_result(tmp_path, 'morgan/172')
    assert (result['checks_passed'], result['checks_total'], result['passed']) == (1, 2, 0)
    assert json.loads((tmp_path / 'canary-result.json').read_text())['task'] == 'morgan/172'
