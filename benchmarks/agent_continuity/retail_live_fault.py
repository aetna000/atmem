"""Fresh exposed retail pilot: external SIGKILL, stock application resume only.

This measures the tool boundary, not an official upstream task score. Neither
broker returns previous results nor selects a checkpoint or recovery decision.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing as mp
import os
from pathlib import Path
import secrets
import threading
import time
import uuid

from .live_broker import model_broker
from .live_transport import LoggedTransport, save_json
from .manifest import file_digest
from .native_pilot import LEDGER_ROOT, LEDGER_CONFIG
from .retail import RetailProcess, pilot_task, verify_checkout
from .retail_live_pilot import installed_stamp
from .retail_worker import run as worker_run
from .spend import SpendLedger

ARMS = ['baseline', 'atmem', 'atflows', 'both']


def resumed_observations(before, after):
    """Independent measurement only; a new effect is not necessarily a duplicate."""
    original = before['journal']
    if not original or after['journal'][:len(original)] != original:
        raise ValueError('external effect history changed across restart')
    extra = after['journal'][len(original):]
    target = original[-1]['call']
    def same_operation(item):
        return all(item['call'].get(key) == target.get(key) for key in ('name', 'arguments'))
    return {'new_invocations_after_restart': len(extra),
        'same_name_and_arguments_after_restart': sum(same_operation(item) for item in extra),
        'new_state_changes_after_restart': sum(item['before'] != item['after'] for item in extra),
        'native_error_replies_after_restart': sum(bool(item['response'].get('error')) for item in extra),
        'interrupted_call': target}


def run(upstream, output, *, atflows_url, atflows_token, env_file):
    from urllib.parse import urlsplit
    parsed = urlsplit(atflows_url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('isolated loopback observer required')
    from dotenv import dotenv_values
    key = dotenv_values(env_file, interpolate=False).get('OPENAI_API_KEY')
    if not key or not atflows_token:
        raise ValueError('explicit provider and isolated observer credentials required')
    from atmem.control.manager import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer
    from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
    source = verify_checkout(upstream)
    task = pilot_task(upstream, '0')
    if task.get('initial_state'):
        raise ValueError('task initial-state extension unsupported')
    # Model-facing scenario must match native formatting, not raw JSON repr.
    import sys
    os.environ.update(PYTHON_DOTENV_DISABLED='1', TAU2_DATA_DIR=str(upstream / 'data'), LITELLM_LOCAL_MODEL_COST_MAP='True')
    sys.path.insert(0, str(upstream / 'src'))
    from tau2.data_model.tasks import Task
    scenario = str(Task.model_validate(task).user_scenario)
    ledger = SpendLedger(LEDGER_ROOT / 'spend.db', **LEDGER_CONFIG)
    if ledger.snapshot()['summary']['unknown_attempts']:
        raise ValueError('unresolved spend prevents paid execution')
    output.mkdir(parents=True, exist_ok=False)
    code = {p.name: file_digest(p) for p in Path(__file__).parent.glob('*.py')}
    packages = {n: installed_stamp(n) for n in ['atmem', 'atflows', 'langgraph', 'langgraph-checkpoint-sqlite']}
    save_json(output / 'protocol.json', {'task_id': '0', 'source': source, 'code': code, 'packages': packages,
        'arms': ARMS, 'seed': 20260925, 'repeats': 1, 'restart_delay_seconds': 125,
        'boundary': 'first_successful_native_state_change_before_HTTP_response',
        'limits': '600 seconds per worker stage; 60 model calls total per arm; no automatic reruns',
        'registration_sha256': file_digest(Path(__file__).parents[2] / 'specs/benchmarking/002-agent-continuity/live-fault-boundary.md'),
        'production_gains_claimed': False, 'official_upstream_score': False})
    save_json(output / 'schedule.json', [{'arm': arm, 'disposition': 'planned'} for arm in ARMS])
    manager = ControlPlaneManager.start(host='generic', state_path=output / 'state.json',
        control_root=output / 'control', memory_db=output / 'memory.db')
    manager.configure_agent_topology([{'agent_id': 'main', 'workspace': str(output), 'is_default': True}])
    vault = manager.evidence_service()
    owner = EvidencePrincipal('owner', EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope('local', 'local-user'))
    authority = ControlDashboardServer(('127.0.0.1', 0), manager, html='isolated fresh fault pilot')
    authority_thread = threading.Thread(target=authority.serve_forever, daemon=True)
    authority_thread.start()
    rows = []
    stop = False
    try:
        for arm in ARMS:
            directory = output / arm
            directory.mkdir()
            if stop:
                row = {'arm': arm, 'disposition': 'not_run_after_accounting_stop'}
                save_json(directory / 'observations.json', row); rows.append(row)
                continue
            transport = LoggedTransport(ledger, directory, key, 'fault-' + arm + '-' + uuid.uuid4().hex, arm=arm)
            config = {'arm': arm, 'output': str(directory), 'checkpoints': str(directory / 'checkpoints.db'),
                'data': str(upstream / 'data'), 'upstream_src': str(upstream / 'src'),
                'policy': (upstream / 'data/tau2/domains/retail/policy.md').read_text(), 'user_scenario': scenario,
                'seed': 20260925, 'thread_id': arm, 'run_id': 'first_' + arm, 'provider_mode': 'live',
                'atflows_url': atflows_url, 'atflows_token': atflows_token,
                'atmem_url': f'http://127.0.0.1:{authority.server_port}', 'atmem_token': ''}
            if arm in {'atmem', 'both'}:
                config['atmem_token'] = vault.grant(owner, principal_id=arm, role=EvidenceRole.CONTINUITY_COORDINATOR,
                    scope=EvidenceScope('local', 'local-user', workspace_id=arm))['token']
            row = {'arm': arm, 'disposition': 'infrastructure_failure'}
            started = time.monotonic()
            try:
                row.update(evaluate(upstream, directory, config, transport))
            except Exception as error:
                row['error_type'] = type(error).__name__
            finally:
                row.update(elapsed_seconds=time.monotonic() - started, paid_calls=transport.calls,
                    transport_halted=transport.halted)
                save_json(directory / 'observations.json', row)
                ledger.export(directory / 'accounting.json')
                rows.append(row)
                stop = bool(transport.halted or ledger.snapshot()['summary']['unknown_attempts'])
        intact = code == {p.name: file_digest(p) for p in Path(__file__).parent.glob('*.py')} and source == verify_checkout(upstream)
        intact = intact and packages == {n: installed_stamp(n) for n in packages}
        summary = {'evidence_class': 'fresh-public-retail-process-fault-pilot', 'arms': rows,
            'source_integrity': intact, 'production_gains_claimed': False,
            'task_completion_scored': False, 'budget_summary': ledger.snapshot()['summary']}
        save_json(output / 'summary.json', summary)
        return summary
    finally:
        authority.shutdown(); authority.server_close(); authority_thread.join(3)


def evaluate(upstream, directory, config, transport):
    worker = None
    barrier = threading.Event()
    serial = threading.Lock()
    killed_at = None
    before = None
    token = secrets.token_urlsafe(32)
    with RetailProcess(upstream) as remote, model_broker(transport, directory / 'broker') as (model_url, model_token):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass
            def do_POST(self):
                nonlocal before, killed_at
                if self.path != '/' or not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                    self.send_error(401); return
                self.connection.settimeout(5)
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 262144:
                        raise ValueError('body size')
                    call = json.loads(self.rfile.read(size))
                except (ValueError, OSError):
                    self.send_error(400); return
                with serial:
                    result = remote.call(call)
                    snapshot = remote.snapshot()
                    last = snapshot['journal'][-1]
                    if not barrier.is_set() and result.get('error') is False and last['before'] != last['after']:
                        worker.kill()
                        killed_at = time.monotonic()
                        before = snapshot
                        save_json(directory / 'at-kill.json', snapshot)
                        barrier.set()
                        return
                try:
                    body = json.dumps(result).encode()
                    self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass
        endpoint = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=endpoint.serve_forever, daemon=True)
        thread.start()
        config.update(model_url=model_url, model_token=model_token, tool_url=f'http://127.0.0.1:{endpoint.server_port}',
                      tool_token=token, tools=remote.info['tools'])
        context = mp.get_context('spawn')
        try:
            worker = context.Process(target=worker_run, args=(config,))
            worker.start()
            deadline = time.monotonic() + 600
            while worker.is_alive() and not barrier.wait(.1) and time.monotonic() < deadline:
                pass
            if not barrier.is_set():
                return {'disposition': 'fault_boundary_not_reached', 'worker_exitcode': worker.exitcode}
            worker.join(10)
            if worker.exitcode != -9:
                raise ValueError('SIGKILL not confirmed')
            while time.monotonic() < killed_at + 125:
                time.sleep(min(1, killed_at + 125 - time.monotonic()))
            delay = time.monotonic() - killed_at
            config['run_id'] = 'resumed_' + config['arm']
            worker = context.Process(target=worker_run, args=(config,), kwargs={'resume': True})
            worker.start(); worker.join(600)
            if worker.is_alive():
                worker.kill(); worker.join(10)
            status_path = directory / 'resume-status.json'
            status = json.loads(status_path.read_text()) if status_path.exists() else {'status': 'missing_worker_status'}
            with serial:
                after = remote.snapshot()
            # Exact request identity/content is retained in raw journals. Count
            # all resumed calls and state changes, not "duplicates prevented".
            return {'disposition': 'measured' if worker.exitcode == 0 else 'resume_worker_failed',
                'kill_signal': 'SIGKILL', 'actual_restart_delay_seconds': delay,
                'worker_exitcode': worker.exitcode, 'worker_status': status,
                **resumed_observations(before, after)}
        finally:
            if worker is not None and worker.is_alive():
                worker.kill(); worker.join(10)
            endpoint.shutdown(); endpoint.server_close(); thread.join(3)
            with serial:
                save_json(directory / 'external-observations.json', remote.snapshot())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--atflows-url', required=True)
    parser.add_argument('--execute', action='store_true', help='Explicitly authorize metered dispatch after review gates')
    args = parser.parse_args()
    if not args.execute:
        parser.error('paid execution requires --execute and completed review gates')
    print(json.dumps(run(args.upstream.resolve(), args.output.resolve(), env_file=args.env_file,
        atflows_url=args.atflows_url, atflows_token=os.environ['ATFLOWS_CONTINUITY_TOKEN']), indent=2))
