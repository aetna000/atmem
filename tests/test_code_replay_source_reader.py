"""Bounded read-tool transport tests; no model or paid service is used."""
from io import StringIO
import json

import pytest

from benchmarks.code_replay import claude_click_tools as tools


def run(monkeypatch, tmp_path, arguments, reader=None):
    seen = []
    monkeypatch.setattr(tools, 'shell', lambda c, command: seen.append(command) or {
        'exit_code': 0, 'timed_out': False, 'output_truncated': False, 'output': 'def example():\n    return 1\n'})
    requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                 'params': {'name': 'read_source', 'arguments': arguments}}]
    monkeypatch.setattr(tools.sys, 'stdin', StringIO('\n'.join(map(json.dumps, requests))))
    output = StringIO()
    monkeypatch.setattr(tools.sys, 'stdout', output)
    tools.serve({'provider_log': str(tmp_path / 'provider'), 'audit': str(tmp_path / 'audit'),
                 'source_reader': reader or {}})
    return [json.loads(line) for line in output.getvalue().splitlines()], seen


def test_full_source_reader(monkeypatch, tmp_path):
    replies, seen = run(monkeypatch, tmp_path, {'path': 'src/click/core.py', 'start': 2, 'end': 4, 'goal': 'read implementation'})
    assert 'read_source' in {t['name'] for t in replies[0]['result']['tools']}
    result = json.loads(replies[1]['result']['content'][0]['text'])
    assert result['code'] == 'def example():\n    return 1\n'
    assert result['omitted'] is False and len(result['source_window_sha256']) == 64
    assert seen == ['sed -n 2,4p src/click/core.py']


@pytest.mark.parametrize('patch', [{'path': '/etc/passwd'}, {'path': 'src/../secret.py'},
    {'path': 'tests/private.py'}, {'start': True}, {'start': 0}, {'end': 401},
    {'end': 0}, {'goal': 'x' * 1001}, {'extra': 'unknown'}])
def test_invalid_read_never_runs_shell(monkeypatch, tmp_path, patch):
    args = {'path': 'src/click/core.py', 'start': 1, 'end': 10, 'goal': 'inspect'} | patch
    replies, seen = run(monkeypatch, tmp_path, args)
    assert 'error' in replies[1] and not seen


def test_pruned_source_is_not_duplicated_in_metadata(monkeypatch, tmp_path):
    import sys
    fixture = '''import json,sys
print(json.dumps({'status':'ready'}),flush=True)
for line in sys.stdin:
 request=json.loads(line)
 print(json.dumps({'pruned_code':'def example(): ...','origin_token_cnt':10,'left_token_cnt':4,'seconds':0.01}),flush=True)
'''
    replies, seen = run(monkeypatch, tmp_path,
        {'path': 'src/click/core.py', 'start': 1, 'end': 5, 'goal': 'inspect'},
        {'command': [sys.executable, '-u', '-c', fixture]})
    value = json.loads(replies[1]['result']['content'][0]['text'])
    assert value['code'] == 'def example(): ...' and value['omitted']
    assert 'pruned_code' not in value['pruning']
    assert value['input_window_bytes'] == len('def example():\n    return 1\n'.encode())
    assert seen


def test_source_consult_gate_is_shared_and_opens_after_read(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(tools, 'shell', lambda c, command: seen.append(command) or {
        'exit_code': 0, 'timed_out': False, 'output_truncated': False, 'output': 'def example(): pass\n'})
    requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
        'name': 'workspace_command', 'arguments': {'command': 'before'}}},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'read_source',
        'arguments': {'path': 'src/example.py', 'start': 1, 'end': 3, 'goal': 'inspect'}}},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
        'name': 'workspace_command', 'arguments': {'command': 'after'}}}]
    monkeypatch.setattr(tools.sys, 'stdin', StringIO('\n'.join(map(json.dumps, requests))))
    output = StringIO();monkeypatch.setattr(tools.sys, 'stdout', output)
    tools.serve({'provider_log': str(tmp_path / 'log'), 'audit': str(tmp_path / 'audit'),
                 'source_reader': {}, 'require_source_consult': True})
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert 'error' in replies[0] and 'error' not in replies[1] and 'error' not in replies[2]
    assert seen == ['sed -n 1,3p src/example.py', 'after']
