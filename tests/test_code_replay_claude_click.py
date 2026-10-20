from benchmarks.code_replay.claude_click_study import parse_usage


def test_missing_usage_is_unknown():
    assert parse_usage([])['total_input_tokens'] is None


def test_terminal_aggregate_counts_cache_once():
    event = {'type': 'result', 'subtype': 'success', 'is_error': False,
             'usage': {'input_tokens': 10, 'cache_creation_input_tokens': 20,
                       'cache_read_input_tokens': 30, 'output_tokens': 5}}
    result = parse_usage([{'type': 'assistant', 'usage': event['usage']}, event])
    assert result['total_input_tokens'] == 60
    assert result['output_tokens'] == 5
    assert result['complete']
    assert not parse_usage([event, event])['complete']


def test_error_receipt_not_success():
    event = {'type': 'result', 'subtype': 'error_max_turns', 'is_error': True,
             'usage': {'input_tokens': 10, 'cache_creation_input_tokens': 0,
                       'cache_read_input_tokens': 0, 'output_tokens': 5}}
    assert not parse_usage([event])['complete']
    assert parse_usage([event])['total_input_tokens'] == 10


def test_explicit_consult_gate_requires_successful_graph(tmp_path, monkeypatch, capsys):
    import io
    import json
    from types import SimpleNamespace
    from benchmarks.code_replay import claude_click_tools as tools
    child = SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO('\n'.join(json.dumps(
        {'id': 100, 'result': result}) for result in (
            {}, {'tools': [{'name': 'code_search'}]},
            {'content': [{'type': 'text', 'text': 'public source fact'}], 'isError': False})) + '\n'),
        terminate=lambda: None, wait=lambda timeout: None)
    monkeypatch.setattr(tools.subprocess, 'Popen', lambda *a, **kw: child)
    calls = []
    monkeypatch.setattr(tools, 'shell', lambda c, s: calls.append(s) or {'output': 'ok'})
    requests = [{'jsonrpc': '2.0', 'id': i, 'method': 'tools/call', 'params': params}
        for i, params in enumerate(({'name': 'workspace_command', 'arguments': {'command': 'before'}},
            {'name': 'code_search', 'arguments': {}},
            {'name': 'workspace_command', 'arguments': {'command': 'after'}}), 1)]
    monkeypatch.setattr(tools.sys, 'stdin', io.StringIO('\n'.join(map(json.dumps, requests))))
    tools.serve({'provider_log': str(tmp_path / 'provider.log'), 'audit': str(tmp_path / 'audit.jsonl'),
        'provider': {'command': [], 'cwd': str(tmp_path), 'environment': {}}, 'require_graph_consult': True})
    replies = list(map(json.loads, capsys.readouterr().out.splitlines()))
    assert 'error' in replies[0]
    assert 'result' in replies[1] and 'result' in replies[2]
    assert calls == ['after']


def test_command_child_never_inherits_mcp_stdin_and_exports_runtime(monkeypatch):
    from types import SimpleNamespace
    from benchmarks.code_replay import claude_click_tools as tools
    seen = {}
    def launch(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return SimpleNamespace(returncode=0, communicate=lambda timeout: (b'ok', b''))
    monkeypatch.setattr(tools.subprocess, 'Popen', launch)
    config = {'codex': '/bin/codex', 'workspace': '/source', 'permissions': [],
        'shell_environment': {'PATH': '/source/.solver-tmp/bin:/usr/bin:/bin', 'PYTHONPATH': '/source/src'}}
    result = tools.shell(config, 'cat > /dev/null')
    assert seen['stdin'] == tools.subprocess.DEVNULL
    assert 'export PATH=' in seen['argv'][-1]
    assert 'export PYTHONPATH=/source/src' in seen['argv'][-1]
    assert 'export TMPDIR=/source/.solver-tmp' in seen['argv'][-1]
    assert result['exit_code'] == 0 and not result['timed_out']
