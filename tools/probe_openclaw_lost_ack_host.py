#!/usr/bin/env python3
"""Exercise lost-ack recovery in real OpenClaw using a deterministic local model endpoint."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bridge', type=Path, required=True)
    p.add_argument('--gateway', action='store_true')
    p.add_argument('--no-fault', action='store_true')
    args = p.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    if args.no_fault:
        (root / 'no-fault').touch()
    repo = Path(__file__).resolve().parents[1]
    fact = 'User prefers cobalt blue notebooks.'
    requests = []

    class Model(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            n = len(requests)
            (root / f'model-request-{n:02d}.json').write_text(json.dumps(body, indent=2))
            time.sleep(0.6)  # allow bridge idle close after timed-out request
            call = None
            if n <= 2:
                call = {'id': f'write-{n:03d}', 'type': 'function',
                        'function': {'name': 'memory_remember', 'arguments': json.dumps(
                            {'fact': fact, 'factKey': 'notebook_preference'})}}
            elif n == 3:
                import re
                ids = re.findall(r'rec_[a-f0-9]+', json.dumps(body['messages']))
                if ids:
                    call = {'id': 'read-001', 'type': 'function', 'function': {
                        'name': 'memory_get', 'arguments': json.dumps({'path': 'atmem://record/' + ids[-1]})}}
            message = {'role': 'assistant', 'content': None if call else 'Deterministic fault probe finished; inspect the recorded tool results.'}
            if call:
                message['tool_calls'] = [call]
            finish = 'tool_calls' if call else 'stop'
            self.send_response(200)
            if body.get('stream'):
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                delta = dict(message)
                if call:
                    delta['tool_calls'] = [dict(call, index=0)]
                for d, reason in [(delta, None), ({}, finish)]:
                    chunk = {'id': f'probe-{n}', 'object': 'chat.completion.chunk',
                             'created': int(time.time()), 'model': 'fault-probe',
                             'choices': [{'index': 0, 'delta': d, 'finish_reason': reason}]}
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
            else:
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'id': f'probe-{n}', 'object': 'chat.completion',
                    'created': int(time.time()), 'model': 'fault-probe',
                    'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                    'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}).encode())

    server = ThreadingHTTPServer(('127.0.0.1', 0), Model)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    bridge = root / 'plugin'
    shutil.copytree(args.bridge, bridge / 'dist')
    shutil.copy(repo / 'integrations/openclaw/openclaw.plugin.json', bridge)
    package = json.loads((repo / 'integrations/openclaw/package.json').read_text())
    (bridge / 'package.json').write_text(json.dumps(package))
    workspace = root / 'workspace'
    workspace.mkdir()
    state = root / 'state'
    state.mkdir(mode=0o700)
    config = {'gateway': {'mode': 'local'}, 'skills': {'allowBundled': []},
      'agents': {'defaults': {'workspace': str(workspace), 'model': {'primary': 'local-probe/fault-probe'},
                              'skipBootstrap': True}},
      'models': {'mode': 'merge', 'providers': {'local-probe': {
        'baseUrl': f'http://127.0.0.1:{server.server_port}/v1', 'apiKey': 'synthetic-local-only',
        'api': 'openai-completions', 'models': [{'id': 'fault-probe', 'name': 'Deterministic fault probe',
          'reasoning': False, 'input': ['text'], 'contextWindow': 128000, 'maxTokens': 4096,
          'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}}]}}},
      'plugins': {'allow': ['memory-atmem'], 'load': {'paths': [str(bridge)]},
        'slots': {'memory': 'memory-atmem'}, 'entries': {'memory-atmem': {'enabled': True,
          'hooks': {'allowConversationAccess': True, 'allowPromptInjection': True},
          'config': {'command': sys.executable,
            'commandArgs': [str(repo / 'tools/probe_openclaw_lost_ack.py'), '--proxy', '--output', str(root)],
            'dbPath': str(root / 'memory.db'), 'subject': 'lost-ack-test', 'takeoverActive': True,
            'recall': {'enabled': False, 'timeoutMs': 2000}, 'capture': {'enabled': False},
            'persona': {'enabled': False}, 'tools': {'enabled': True},
            'controlPlane': {'enabled': False, 'blackboxEnabled': False}}}}}}
    if args.gateway:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            gateway_port = sock.getsockname()[1]
        config['gateway'].update(port=gateway_port, bind='loopback', auth={'mode': 'token', 'token': uuid.uuid4().hex})
        config['discovery'] = {'mdns': {'mode': 'off'}}
        config['browser'] = {'enabled': False}
        config['cron'] = {'enabled': False}
    (root / 'openclaw.json').write_text(json.dumps(config, indent=2))
    env = dict(os.environ, PYTHONPATH=str(repo), OPENCLAW_STATE_DIR=str(state),
               OPENCLAW_CONFIG_PATH=str(root / 'openclaw.json'))
    command = ['openclaw', 'agent', '--local', '--agent', 'main', '--session-id', str(uuid.uuid4()),
               '--session-key', 'agent:main:lost-ack-probe',
               '--message', 'Remember that I prefer cobalt blue notebooks. If the save times out, retry the same fact, then read it back.',
               '--timeout', '60', '--json']
    gateway = None
    if args.gateway:
        command.remove('--local')
        gateway_log = (root / 'gateway.log').open('w')
        gateway = subprocess.Popen(['openclaw', 'gateway', 'run', '--port', str(gateway_port)],
                                   env=env, cwd=workspace, stdout=gateway_log, stderr=gateway_log)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', gateway_port), timeout=0.2):
                    break
            except OSError:
                if gateway.poll() is not None:
                    raise RuntimeError('Isolated gateway exited; inspect gateway.log')
                time.sleep(0.2)
    try:
        with (root / 'host.stdout').open('w') as out, (root / 'host.stderr').open('w') as err:
            done = subprocess.run(command, env=env, cwd=workspace, stdout=out, stderr=err, timeout=90)
        from atmem import Memory
        memory = Memory(root / 'memory.db')
        records = memory.list('lost-ack-test', include_inactive=True)
        verification = memory.verify('lost-ack-test')
        audit = memory.audit('lost-ack-test')
        import sqlite3
        with sqlite3.connect(root / 'memory.db') as db:
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_key_errors = db.execute('PRAGMA foreign_key_check').fetchall()
        tool_results = [m for m in requests[-1]['messages'] if m['role'] == 'tool'] if requests else []
        evidence = {'host_exit': done.returncode, 'model_requests': len(requests),
                    'records': records, 'verification': verification,
                    'audit': audit, 'sqlite_integrity': integrity, 'foreign_key_errors': foreign_key_errors,
                    'tool_results': tool_results, 'no_fault_control': args.no_fault,
                    'fault_injected': (root / 'dropped.json').exists(),
                    'driver': 'deterministic local OpenAI-compatible endpoint; no paid inference'}
        try:
            assert done.returncode == 0
            assert len(requests) == 4 and len(tool_results) == 3
            assert evidence['fault_injected'] != args.no_fault
            assert len(records) == 1 and records[0]['content'] == fact and records[0]['status'] == 'active'
            first, retry, read = [json.loads(m['content']) for m in tool_results]
            if args.no_fault:
                assert first['stored'] and first['record_id'] == records[0]['id']
            else:
                assert 'timed out' in first['error']
                dropped = json.loads((root / 'dropped.json').read_text())
                committed = json.loads(dropped['reply']['result']['content'][0]['text'])['records'][0]
                assert committed['id'] == records[0]['id']
            assert retry['stored'] and retry['status'] == 'already_stored' and retry['record_id'] == records[0]['id']
            assert read['text'] == fact
            assert verification['valid'] and audit['audit_chain_valid']
            assert sum(e['event_type'] == 'memory.record_created' for e in audit['audit_log']) == 1
            assert integrity == 'ok' and not foreign_key_errors
            evidence['assertions_passed'] = True
        except (AssertionError, KeyError) as exc:
            evidence['assertions_passed'] = False
            evidence['assertion_error'] = repr(exc)
        (root / 'summary.json').write_text(json.dumps(evidence, indent=2, default=str))
        print(json.dumps({k: evidence[k] for k in ['host_exit','model_requests','fault_injected','assertions_passed']}))
        if not evidence['assertions_passed']:
            raise RuntimeError('Probe assertions failed; see summary.json')
    finally:
        if gateway:
            gateway.terminate()
            gateway.wait(timeout=15)
            gateway_log.close()
        server.shutdown()


if __name__ == '__main__':
    main()
