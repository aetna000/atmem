"""Claude's only task tools: offline container commands and optional AtMem MCP.

Trusted configuration is recovered through the protected evidence boundary.
No arbitrary SSH, host path, database, container ID or Python argument is
accepted from the model. Audit content never goes to a plaintext log file.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from benchmarks.code_replay.swebench_pilot import SOCKET, vault, worker


def serve(root, identity, arm, mode='model'):
    if mode not in {'model', 'preparation'}:
        raise ValueError('operator-selected transport mode required')
    root = Path(root)
    os.environ['ATMEM_HOME'] = str(root / 'home')
    evidence, principal = vault(root)
    events = evidence.inspect(principal, identity)
    config = next(e['envelope']['payload'] for e in reversed(events)
                  if e['envelope']['event_type'] == 'trial.configured' and e['envelope']['payload']['arm'] == arm)
    provider = None
    count = 0
    graph_tools = []
    guidance = None
    if arm in {'atmem_structure', 'cognee_structure'} and (config.get('model_graph_tools', True) or mode == 'preparation'):
        graph = config['graph']
        server = graph['server']
        args = [a for a in server['args'] if a != '--experience']
        import shlex
        if arm == 'cognee_structure':
            remote_command = 'wsl -d Ubuntu -u root -- env -i ' + shlex.join(
                [key + '=' + value for key, value in graph['environment'].items()]) + ' ' + shlex.join([server['command'], *args])
        else:
            remote_command = 'wsl -d Ubuntu -u root -- env ATMEM_HOME=' + graph['home'] + ' ' + shlex.join([server['command'], *args])
        # These pinned benchmark paths contain no spaces or shell quotes.
        provider = subprocess.Popen(['ssh', '-S', SOCKET, '-o', 'BatchMode=yes', '-T',
            'user@192.168.0.87', remote_command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def rpc(method, params=None):
        provider.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 90, 'method': method, 'params': params or {}}) + '\n')
        provider.stdin.flush()
        while True:
            line = provider.stdout.readline()
            if not line:
                raise RuntimeError('AtMem MCP transport terminated')
            reply = json.loads(line)
            if reply.get('id') == 90:
                if 'error' in reply:
                    raise RuntimeError('AtMem MCP error: ' + json.dumps(reply['error']))
                return reply['result']

    try:
        if provider:
            initialized = rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                'clientInfo': {'name': 'swebench-pilot', 'version': '1'}})
            guidance = initialized.get('instructions')
            provider.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            provider.stdin.flush()
            graph_tools = rpc('tools/list')['tools']
        tools = [{'name': 'workspace_command', 'description':
            'Execute a shell command in the offline repository task container. Read, search, edit and run '
            'existing public tests here. The testbed Python environment is on PATH. No network, host '
            'files or future Git history are available. 40-second command limit, 24000-byte returned '
            'output limit. Work in /testbed. Do not modify tests, Git history or dependency configuration.',
            'inputSchema': {'type': 'object', 'additionalProperties': False,
                'properties': {'command': {'type': 'string', 'minLength': 1, 'maxLength': 20000}},
                'required': ['command']}}, *graph_tools]
        for line in sys.stdin:
            request = json.loads(line)
            if 'id' not in request:
                continue
            tick = time.monotonic()
            try:
                method, params = request['method'], request.get('params', {})
                if method == 'initialize':
                    result = {'protocolVersion': params['protocolVersion'], 'capabilities': {'tools': {}},
                              'serverInfo': {'name': 'swebench-pilot', 'version': '1'}}
                    if guidance:
                        result['instructions'] = guidance
                elif method == 'tools/list':
                    result = {'tools': tools}
                elif method == 'ping':
                    result = {}
                elif method == 'tools/call':
                    count += 1
                    if count > 30:
                        raise ValueError('30-call budget exhausted')
                    name = params['name']
                    if name == 'workspace_command':
                        arguments = params.get('arguments', {})
                        if set(arguments) != {'command'}:
                            raise ValueError('exact command argument required')
                        value = worker('command', {'container': config['stage']['container'],
                                                   'command': arguments['command']}, timeout=65)
                        result = {'content': [{'type': 'text', 'text': json.dumps(value)}], 'isError': False}
                    elif name in {tool['name'] for tool in graph_tools}:
                        changes = worker('patch', {'container': config['stage']['container']}, timeout=30)
                        if changes['patch']:
                            result = {'content': [{'type': 'text', 'text': json.dumps({'status': 'withheld',
                                'reason': 'solver_source_changed_since_graph_snapshot',
                                'guidance': 'Use current workspace source.'})}], 'isError': False}
                        else:
                            result = rpc(method, params)
                    else:
                        raise ValueError('unknown tool')
                else:
                    raise ValueError('unsupported MCP method')
                reply = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
            except Exception as exc:
                reply = {'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32000, 'message': str(exc)}}
            evidence.capture(run_id=identity, kind='tool.exchange', principal=principal,
                payload={'arm': arm, 'request': request, 'response': reply, 'elapsed_s': time.monotonic() - tick})
            print(json.dumps(reply), flush=True)
    finally:
        if provider:
            provider.terminate()
            try:
                provider.wait(timeout=5)
            except subprocess.TimeoutExpired:
                provider.kill(); provider.wait()


if __name__ == '__main__':
    serve(*sys.argv[1:])
