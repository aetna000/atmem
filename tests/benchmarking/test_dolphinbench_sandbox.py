import importlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
sandbox = importlib.import_module('benchmarks.dolphinbench.sandbox')
pytestmark = pytest.mark.skipif(platform.system() != 'Darwin', reason='macOS sandbox qualification')


def test_forbids_broad_home_and_root_access(tmp_path):
    for path in ('/', '/Users', '/Volumes', str(Path.home())):
        with pytest.raises(ValueError):
            sandbox.policy(readable=[path], writable=[tmp_path], ports=[])


def test_actual_process_denies_sibling_evidence_and_writes(tmp_path):
    agent = tmp_path / 'agent'
    agent.mkdir()
    hidden = tmp_path / 'sealed-evidence.txt'
    hidden.write_text('not-visible-to-agent')
    profile = sandbox.policy(readable=[Path(sys.base_prefix), Path(sys.prefix)], writable=[agent], ports=[])
    program = '''
import json,pathlib,sys
own=pathlib.Path(sys.argv[1]); hidden=pathlib.Path(sys.argv[2])
(own/'allowed.txt').write_text('local')
for action in (lambda:hidden.read_text(),lambda:hidden.write_text('bad')):
    try: action()
    except PermissionError: pass
    else: raise RuntimeError('Sandbox leaked sibling evidence')
print(json.dumps({'isolated':True}))
'''
    result = sandbox.run([sys.executable, '-I', '-c', program, str(agent), str(hidden)],
        profile=profile, environment={'PATH': '/usr/bin:/bin', 'TMPDIR': str(agent)}, cwd=agent, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['isolated']
    assert hidden.read_text() == 'not-visible-to-agent'


def test_network_denied_except_declared_local_port(tmp_path):
    permitted = socket.socket()
    permitted.bind(('127.0.0.1', 0))
    permitted.listen()
    disallowed = socket.socket()
    disallowed.bind(('127.0.0.1', 0))
    disallowed.listen()
    profile = sandbox.policy(readable=[Path(sys.base_prefix), Path(sys.prefix)], writable=[tmp_path],
                             ports=[permitted.getsockname()[1]])
    program = '''
import socket,sys
s=socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=2);s.close()
try: socket.create_connection(('127.0.0.1',int(sys.argv[2])),timeout=2)
except PermissionError: pass
else: raise RuntimeError('Undeclared local service was reachable')
print('isolated')
'''
    try:
        result = sandbox.run([sys.executable, '-I', '-c', program,
            str(permitted.getsockname()[1]), str(disallowed.getsockname()[1])],
            profile=profile, environment={'PATH': '/usr/bin:/bin', 'TMPDIR': str(tmp_path)}, cwd=tmp_path, timeout=20)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == 'isolated'
    finally:
        permitted.close()
        disallowed.close()
