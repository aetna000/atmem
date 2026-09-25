"""External fault rig for the installed, ordinary document-publishing example.

Run with an isolated interpreter (-I), outside the source checkout. The proxy
only withholds an HTTP response and kills the worker. It makes no resume decision.
"""
import argparse
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

import atmem
from atmem.continuity.client import ContinuityClient
from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--host', choices=['direct', 'langgraph'], default='direct')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.output.resolve()
    package = Path(atmem.__file__).resolve()
    assert 'site-packages' in str(package), package
    assert not any('benchmarks' in name for name in sys.modules)
    manager = ControlPlaneManager.start(host='generic', state_path=root / 'state.json',
        control_root=root / 'control', memory_db=root / 'memory.db')
    manager.configure_agent_topology([{'agent_id': 'main', 'workspace': str(root), 'is_default': True}])
    vault = manager.evidence_service()
    owner = EvidencePrincipal('owner', EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope('local', 'local-user'))
    grant = vault.grant(owner, principal_id='operator', role=owner.role, scope=owner.scope)
    server = ControlDashboardServer(('127.0.0.1', 0), manager, html='isolated acceptance')
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    client = ContinuityClient(base, grant['token'])
    observations = []
    fault = {'mode': None, 'hit': threading.Event(), 'worker': None}

    class Barrier(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def relay(self):
            data = self.rfile.read(int(self.headers.get('Content-Length', '0'))) if self.command == 'POST' else None
            is_outcome = self.path.endswith('/outcome') and fault['mode'] is not None
            # This is the sole injected failure; no product state is read or changed.
            if is_outcome and fault['mode'] == 'before_receipt':
                fault['hit'].set()
                while fault['worker'] is None:
                    time.sleep(.01)
                fault['worker'].kill()
                return
            request = Request(base + self.path, data=data, method=self.command,
                headers={'Authorization': self.headers.get('Authorization', ''), 'Content-Type': 'application/json'})
            with urlopen(request, timeout=20) as response:
                body, status = response.read(), response.status
            if is_outcome:
                fault['hit'].set()
                while fault['worker'] is None:
                    time.sleep(.01)
                fault['worker'].kill()
                return
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = relay
        do_POST = relay

    proxy = ThreadingHTTPServer(('127.0.0.1', 0), Barrier)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    document = args.document.read_text(encoding='utf-8')
    try:
        for mode in ['after_receipt', 'before_receipt']:
            destination = root / mode / 'published'
            if args.host == 'direct':
                workflow = client.create('installed-' + mode, [{'name': 'publish', 'tool': 'publish_document',
                    'arguments': {'text': document, 'destination': str(destination)},
                    'capability': 'query', 'timeout_seconds': 30}])
                workflow_id = workflow['workflow_id']
                client.configure(workflow_id, True)
                worker_grant = vault.grant(owner, principal_id='worker-' + mode, role=EvidenceRole.CONTINUITY_HOST,
                    scope=EvidenceScope('local', 'local-user', run_id=workflow_id))
                command = [sys.executable, '-I', '-m', 'atmem.continuity.example', 'run',
                    '--workflow-id', workflow_id, '--output', str(destination)]
            else:
                worker_grant = vault.grant(owner, principal_id='worker-' + mode, role=EvidenceRole.CONTINUITY_COORDINATOR,
                    scope=EvidenceScope('local', 'local-user', workspace_id=mode))
                command = [sys.executable, '-I', '-m', 'atmem.continuity.langgraph_example', 'start',
                    '--thread', mode, '--checkpoints', str(root / mode / 'checkpoints.db'),
                    '--output', str(destination), '--document', str(args.document.resolve()), '--enabled']
            env = {**os.environ, 'ATMEM_EVIDENCE_TOKEN': worker_grant['token'], 'PYTHON_DOTENV_DISABLED': '1'}
            env.pop('PYTHONPATH', None)
            fault.update(mode=mode, worker=None)
            fault['hit'].clear()
            worker = subprocess.Popen(command + ['--url', f'http://127.0.0.1:{proxy.server_port}'],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            fault['worker'] = worker
            assert fault['hit'].wait(25), 'worker never reached external receipt barrier'
            stdout, stderr = worker.communicate(timeout=10)
            assert worker.returncode != 0
            if args.host == 'langgraph':
                workflows = client.request('GET', '/v1/continuity')['workflows']
                matching = [value for value in workflows if value['creator_id'] == 'worker-' + mode]
                assert len(matching) == 1
                workflow_id = matching[0]['workflow_id']
                command[4] = 'resume'
            before = client.get(workflow_id)
            effects_before = list(destination.glob('*.md'))
            assert len(effects_before) == 1
            assert effects_before[0].read_text(encoding='utf-8') == document
            fault['mode'] = None
            # Wait actual persisted lease time; no clock/state mutation by the rig.
            wait_seconds = max(0, before['operations'][0].get('lease_until', 0) - time.time() + .1)
            if mode == 'before_receipt':
                time.sleep(wait_seconds)
            resumed = subprocess.run(command + ['--url', base], cwd=root, env=env,
                text=True, capture_output=True, timeout=30)
            assert resumed.returncode == 0, resumed.stderr
            after = client.get(workflow_id)
            assert after['operations'][0]['status'] == 'completed'
            assert len(list(destination.glob('*.md'))) == 1
            status = subprocess.run([sys.executable, '-I', '-m', 'atmem.cli', 'continuity', 'show', workflow_id, '--url', base],
                cwd=root, env=env, text=True, capture_output=True, timeout=30)
            assert status.returncode == 0, status.stderr
            assert json.loads(status.stdout)['operations'][0]['status'] == 'completed'
            observations.append({'fault': mode, 'barrier_reached': True, 'killed_returncode': worker.returncode,
                'before': before, 'after': after, 'resume_stdout': json.loads(resumed.stdout),
                'external_effects': 1, 'document_sha256': sha256(document.encode()).hexdigest(),
                'actual_wait_seconds': wait_seconds if mode == 'before_receipt' else 0})
        report = {'format': 'installed-continuity-acceptance-v1', 'atmem_version': importlib.metadata.version('atmem'),
            'host': args.host,
            'atmem_module': str(package), 'source_imports': False, 'benchmark_recovery_code': False,
            'case_count': len(observations), 'cases': observations,
            'claim': 'Installed document publisher survives these two actual process-kill receipt windows. Not a retail agent score.'}
        (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'passed': len(observations), 'report': str(root / 'report.json')}))
    finally:
        if fault['worker'] is not None and fault['worker'].poll() is None:
            fault['worker'].kill()
            fault['worker'].wait(10)
        proxy.shutdown(); proxy.server_close(); proxy_thread.join(3)
        server.shutdown(); server.server_close(); server_thread.join(3)


if __name__ == '__main__':
    main()
