"""External process fault and independent observations; no recovery implementation.

The fixed sixth public tool request in exposed task 0 changes the native store.
Kill after that tool finishes, before HTTP reply. Restart uses stock LangGraph.
Recorded replies qualify the boundary only; divergent requests stop the cassette.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import importlib.metadata
import multiprocessing as mp
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time

from .manifest import digest, file_digest
from .retail import RetailProcess, pilot_task, verify_checkout
from .retail_worker import run as worker_run


def run(upstream, native, output, *, atflows_url, atflows_token):
    from atmem.control.manager import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer
    from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
    stamp = verify_checkout(upstream)
    raw_task = pilot_task(upstream, '0')
    os.environ.update(PYTHON_DOTENV_DISABLED='1', TAU2_DATA_DIR=str(upstream / 'data'),
        LITELLM_LOCAL_MODEL_COST_MAP='True', LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false')
    sys.path.insert(0, str(upstream / 'src'))
    from loguru import logger
    logger.remove()
    from tau2.data_model.tasks import Task
    task = Task.model_validate(raw_task)
    trajectory = json.loads((native / 'trajectory.json').read_text())['messages']
    tool_batches = [entry['tool_calls'] for entry in trajectory if entry.get('tool_calls')]
    if len(tool_batches[-1]) != 1 or sum(map(len, tool_batches)) != 6 or tool_batches[-1][0]['name'] != 'exchange_delivered_order_items':
        raise ValueError('fault must be sixth invocation and the only call in its superstep')
    output.mkdir(parents=True, exist_ok=False)
    source_files = ['retail_fault_qualification.py', 'retail_worker.py', 'retail_graph.py', 'retail_graph_qualification.py', 'retail.py', 'manifest.py']
    source_hashes = {name: file_digest(Path(__file__).with_name(name)) for name in source_files}
    (output / 'protocol.json').write_text(json.dumps({'source': stamp, 'code': source_hashes,
        'task_id': '0', 'tool_ordinal': 6, 'restart_delay_seconds': 125, 'paid_calls': 0,
        'arms': ['baseline', 'atmem', 'atflows', 'both'], 'primary_measure': 'new_invocations_after_restart',
        'cassette_manifest_sha256': file_digest(native / 'SHA256SUMS.json'),
        'trajectory_sha256': file_digest(native / 'trajectory.json'),
        'packages': {name: {'version': importlib.metadata.version(name),
            'record_sha256': sha256(importlib.metadata.distribution(name).read_text('RECORD').encode()).hexdigest()}
            for name in ['atmem', 'atflows', 'langgraph', 'langgraph-checkpoint-sqlite']}}, indent=2))
    manager = ControlPlaneManager.start(host='generic', state_path=output / 'state.json',
        control_root=output / 'control', memory_db=output / 'memory.db')
    manager.configure_agent_topology([{'agent_id': 'main', 'workspace': str(output), 'is_default': True}])
    vault = manager.evidence_service()
    owner = EvidencePrincipal('owner', EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope('local', 'local-user'))
    server = ControlDashboardServer(('127.0.0.1', 0), manager, html='isolated fault qualification')
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    configurations = {}
    for arm in ['baseline', 'atmem', 'atflows', 'both']:
        directory = output / arm
        directory.mkdir()
        credential = vault.grant(owner, principal_id=arm, role=EvidenceRole.CONTINUITY_COORDINATOR,
            scope=EvidenceScope('local', 'local-user', workspace_id=arm)) if arm in {'atmem', 'both'} else None
        configurations[arm] = {'arm': arm, 'output': str(directory), 'checkpoints': str(directory / 'checkpoints.db'),
            'data': str(upstream / 'data'), 'upstream_src': str(upstream / 'src'), 'cassette': str(native),
            'policy': (upstream / 'data/tau2/domains/retail/policy.md').read_text(),
            'user_scenario': str(task.user_scenario), 'seed': 20260925,
            'thread_id': arm, 'run_id': 'first_' + arm, 'atflows_url': atflows_url,
            'atflows_token': atflows_token, 'atmem_url': f'http://127.0.0.1:{server.server_port}',
            'atmem_token': credential['token'] if credential else ''}

    def evaluate(config):
        directory = Path(config['output'])
        token = secrets.token_urlsafe(32)
        barrier = threading.Event()
        counter = 0
        call_lock = threading.Lock()
        killed_at = None
        worker = None
        with RetailProcess(upstream) as remote:
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *unused):
                    pass
                def do_POST(self):
                    nonlocal counter, killed_at
                    if self.headers.get('Authorization') != 'Bearer ' + token:
                        self.send_error(401); return
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 262144:
                        self.send_error(413); return
                    call = json.loads(self.rfile.read(size))
                    with call_lock:
                        if counter == 5 and call['name'] != 'exchange_delivered_order_items':
                            self.send_error(409, 'fixed fault target mismatch'); return
                        result = remote.call(call)
                        counter += 1
                        if counter == 6:
                            worker.kill()
                            killed_at = time.monotonic()
                            barrier.set()
                            return
                    body = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            endpoint = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            endpoint_thread = threading.Thread(target=endpoint.serve_forever, daemon=True)
            endpoint_thread.start()
            try:
                config.update(tool_url=f'http://127.0.0.1:{endpoint.server_port}', tool_token=token, tools=remote.info['tools'])
                context = mp.get_context('spawn')
                worker = context.Process(target=worker_run, args=(config,))
                worker.start()
                deadline = time.monotonic() + 60
                while not barrier.wait(.1):
                    if not worker.is_alive() or time.monotonic() >= deadline:
                        raise RuntimeError('worker did not reach fixed fault boundary')
                worker.join(10)
                if worker.exitcode != -9:
                    raise ValueError('worker was not killed with SIGKILL')
                before = remote.snapshot()
                last = before['journal'][-1]
                if len(before['journal']) != 6 or last['response'].get('error') is not False or last['before'] == last['after']:
                    raise ValueError('fault did not follow a confirmed native store change')
                # Read-only evaluator inspection, never passed to the worker.
                with sqlite3.connect(f'file:{directory / "checkpoints.db"}?mode=ro', uri=True) as connection:
                    pending = connection.execute('SELECT checkpoint_id,task_id,idx,channel,type,length(value) FROM writes').fetchall()
                time.sleep(max(0, killed_at + 125 - time.monotonic()))
                waited = time.monotonic() - killed_at
                config['run_id'] = 'resumed_' + config['arm']
                worker = context.Process(target=worker_run, args=(config,), kwargs={'resume': True})
                worker.start(); worker.join(60)
                if worker.is_alive() or worker.exitcode != 0:
                    raise RuntimeError('resumed worker failed unexpectedly')
                after = remote.snapshot()
                status = json.loads((directory / 'resume-status.json').read_text())
                before_count = len(before['journal'])
                extra = after['journal'][before_count:]
                result = {'arm': config['arm'], 'fault': 'sixth_tool_committed_before_http_response',
                    'kill_signal': 'SIGKILL', 'single_call_superstep': True, 'native_store_changed_before_kill': True,
                    'actual_restart_delay_seconds': waited,
                    'new_invocations_after_restart': len(extra),
                    'new_state_changes_after_restart': sum(item['before'] != item['after'] for item in extra),
                    'native_error_replies_after_restart': sum(bool(item['response'].get('error')) for item in extra),
                    'worker_status': status, 'pending_write_metadata_at_kill': pending,
                    'before': before, 'after': after,
                    'topology': json.loads((directory / 'start-topology.json').read_text())}
                if result['topology'] != json.loads((directory / 'resume-topology.json').read_text()):
                    raise ValueError('graph topology changed on restart')
                (directory / 'observations.json').write_text(json.dumps(result, indent=2))
                return {key: value for key, value in result.items() if key not in {'before', 'after', 'pending_write_metadata_at_kill', 'topology'}}
            finally:
                if worker is not None and worker.is_alive():
                    worker.kill(); worker.join(10)
                endpoint.shutdown(); endpoint.server_close(); endpoint_thread.join(3)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(evaluate, configurations.values()))
        if source_hashes != {name: file_digest(Path(__file__).with_name(name)) for name in source_files}:
            raise ValueError('qualification code changed during run')
        topologies = [json.loads((output / arm / 'start-topology.json').read_text()) for arm in configurations]
        if any(topology != topologies[0] for topology in topologies):
            raise ValueError('graph topology differs across arms')
        summary = {'evidence_class': 'public-retail-recorded-response-fault-qualification', 'source': stamp,
            'paid_calls': 0, 'arms': rows, 'graph_topology_equal': True,
            'primary_measure': 'public HTTP tool invocations after restart',
            'completion_comparison_allowed': False, 'production_gains_claimed': False,
            'limitations': 'One exposed public task, recorded native model replies. Native store may reject repeats. Not fresh autonomous or held-out performance.'}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2))
        return summary
    except BaseException as error:
        (output / 'failure.json').write_text(json.dumps({'disposition': 'qualification_failed',
            'error_type': type(error).__name__, 'paid_calls': 0}, indent=2))
        raise
    finally:
        server.shutdown(); server.server_close(); server_thread.join(3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--atflows-url', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.upstream.resolve(), args.native.resolve(), args.output.resolve(),
        atflows_url=args.atflows_url, atflows_token=os.environ['ATFLOWS_CONTINUITY_TOKEN']), indent=2))
