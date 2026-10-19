import io
import json
import os
import select
import subprocess
import sys
import pytest
from tools.qualify_swebench_warm_queries import PROBE, main


def test_persistent_probe_reuses_one_isolated_process_and_cleans_its_group(monkeypatch, capsys):
    reply = {'content': [{'type': 'text', 'text': json.dumps({'status': 'current'})}], 'isError': False}
    class Process:
        pid = 123456
        stdin = io.StringIO()
        stdout = io.StringIO('\n'.join(json.dumps({'jsonrpc': '2.0', 'id': i, 'result': reply}) for i in range(1, 6)) + '\n')
        def poll(self):
            return None
        def wait(self, timeout):
            return 0
    process, launches, signals = Process(), [], []
    def launch(*args, **kwargs):
        launches.append(kwargs)
        return process
    monkeypatch.setattr(subprocess, 'Popen', launch)
    monkeypatch.setattr(subprocess, 'check_output', lambda _: b'')
    monkeypatch.setattr(select, 'select', lambda *args: ([process.stdout], [], []))
    monkeypatch.setattr(os, 'killpg', lambda pid, sig: signals.append(pid))
    monkeypatch.setenv('UNRELATED_OWNER_CREDENTIAL', 'not-forwarded')
    config = {'arm': 'atmem_structure', 'graph': {'home': '/benchmark/home',
              'server': {'command': '/benchmark/venv/bin/python', 'args': ['-I', 'serve']}},
              'stage': {'source_tree': 'a' * 40}}
    exec(compile(PROBE, '<warm-control>', 'exec'), {'job': {'payload': config}})
    result = json.loads(capsys.readouterr().out)
    requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
    assert len(launches) == 1 and launches[0]['start_new_session'] is True
    assert 'UNRELATED_OWNER_CREDENTIAL' not in launches[0]['env']
    assert [r['id'] for r in requests if r['method'] == 'tools/call'] == [3, 4, 5]
    assert result['result_stable_across_queries'] and len(result['queries']) == 3
    assert signals == [process.pid]


def test_live_confirmation_guard_runs_before_creating_a_control_root(tmp_path, monkeypatch):
    ongoing = tmp_path / 'ongoing'
    ongoing.mkdir()
    (ongoing / 'results.json').write_text(json.dumps({'status': 'running'}))
    target = tmp_path / 'new-control'
    monkeypatch.setattr(sys, 'argv', ['probe', '--source', str(tmp_path / 'not-opened'),
                                    '--root', str(target), '--after', str(ongoing)])
    with pytest.raises(ValueError, match='finish scored confirmation'):
        main()
    assert not target.exists()
