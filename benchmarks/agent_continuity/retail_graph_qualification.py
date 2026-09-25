"""No-fault public-pilot replay qualification, not fresh autonomous results.

Runs native model replies against the real pinned retail environment. The only
recovery code in the AtMem arm is the installed governed node. Zero paid calls.
"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
from urllib.request import Request, build_opener, ProxyHandler

from .manifest import digest, file_digest
from .retail import RetailProcess, pilot_task, verify_checkout
from .retail_graph import build_graph, initial_state


@contextmanager
def endpoint(remote):
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            if self.headers.get('Authorization') != 'Bearer ' + token:
                self.send_error(401)
                return
            count = int(self.headers.get('Content-Length', '0'))
            if not 0 < count <= 262144:
                self.send_error(413)
                return
            reply = remote.call(json.loads(self.rfile.read(count)))
            body = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}'
    opener = build_opener(ProxyHandler({}))
    def public_call(value):
        request = Request(url, data=json.dumps(value).encode(), headers={'Authorization': 'Bearer ' + token})
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    try:
        yield url, token, public_call
    finally:
        server.shutdown(); server.server_close(); worker.join(3)


class NativeCassette:
    def __init__(self, directory):
        self.matches = []
        self.records = {}
        checksums = json.loads((directory / 'SHA256SUMS.json').read_text())
        required = {'trajectory.json'}
        for request_file in directory.glob('*.request.json'):
            required.update({request_file.name, request_file.name.replace('.request.', '.response.')})
        if not required <= checksums.keys():
            raise ValueError('native checksum manifest omits loaded evidence')
        for name, expected in checksums.items():
            if file_digest(directory / name) != expected:
                raise ValueError('native evidence checksum mismatch')
        for request_file in directory.glob('*.request.json'):
            request = json.loads(request_file.read_text())['request']
            response = json.loads(request_file.with_name(request_file.name.replace('.request.', '.response.')).read_text())['response']
            key = digest(request)
            if key in self.records and self.records[key] != response:
                raise ValueError('ambiguous duplicate native request')
            self.records[key] = response
    def completion(self, **kwargs):
        from litellm import ModelResponse
        allowed = {'model', 'messages', 'tools', 'tool_choice', 'temperature', 'num_retries', 'seed', 'max_tokens'}
        if set(kwargs) - allowed or kwargs.get('model') != 'gpt-4.1-2025-04-14' or kwargs.get('temperature', 0) != 0 or kwargs.get('num_retries', 0) != 0 or kwargs.get('max_tokens', 2048) != 2048:
            raise ValueError('native request options changed')
        body = {key: value for key, value in kwargs.items() if key in {'messages', 'tools', 'tool_choice', 'seed'} and value is not None}
        body.update(model=kwargs['model'], temperature=0, max_completion_tokens=2048, n=1,
                    stream=False, service_tier='default', store=False)
        key = digest(body)
        if key not in self.records:
            raise ValueError('request differs from preserved native public run; parity failed')
        self.matches.append(key)
        return ModelResponse(**{k: v for k, v in self.records[key].items() if not k.startswith('_benchmark')})


def semantic_messages(messages):
    fields = {'role', 'content', 'tool_calls', 'requestor', 'error', 'id'}
    return [{key: value for key, value in item.items() if key in fields} for item in messages]


def run(upstream, native, output, *, atflows_url, atflows_token):
    from atmem.continuity.client import ContinuityClient, AtFlowsObserver
    from atmem.continuity.integrations import GovernedToolRunner, RegisteredTool, governed_langgraph_tools
    from atmem.continuity.tools import JsonResponseTool
    from atmem.control.manager import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer
    from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
    from atflows.continuity import ContinuityObserver
    from langgraph.checkpoint.sqlite import SqliteSaver

    stamp = verify_checkout(upstream)
    task = pilot_task(upstream, '0')
    if task.get('initial_state'):
        raise ValueError('this qualification does not support custom initial state')
    output.mkdir(parents=True, exist_ok=False)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', TAU2_DATA_DIR=str(upstream / 'data'),
        LITELLM_LOCAL_MODEL_COST_MAP='True', LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false')
    sys.path.insert(0, str(upstream / 'src'))
    from tau2.agent.llm_agent import LLMAgent
    from tau2.user.user_simulator import UserSimulator
    from tau2.domains.retail.environment import get_environment
    from tau2.data_model.tasks import Task
    from tau2.utils import llm_utils
    from loguru import logger
    logger.remove()
    task = Task.model_validate(task)
    native_trajectory = json.loads((native / 'trajectory.json').read_text())['messages']
    manager = ControlPlaneManager.start(host='generic', state_path=output / 'state.json',
        control_root=output / 'control', memory_db=output / 'memory.db')
    manager.configure_agent_topology([{'agent_id': 'main', 'workspace': str(output), 'is_default': True}])
    vault = manager.evidence_service()
    owner = EvidencePrincipal('owner', EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope('local', 'local-user'))
    server = ControlDashboardServer(('127.0.0.1', 0), manager, html='isolated qualification')
    evaluator_grant = vault.grant(owner, principal_id='evaluator', role=owner.role, scope=owner.scope)
    evaluator = ContinuityClient(f'http://127.0.0.1:{server.server_port}', evaluator_grant['token'])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows = []
    topology = None
    original_completion = llm_utils.completion
    try:
        for arm in ['baseline', 'atmem', 'atflows', 'both']:
            cassette = NativeCassette(native)
            llm_utils.completion = cassette.completion
            environment = get_environment()
            kwargs = {'temperature': 0, 'num_retries': 0, 'max_tokens': 2048}
            agent = LLMAgent(environment.get_tools(), environment.get_policy(), 'gpt-4.1-2025-04-14', kwargs)
            user = UserSimulator(llm='gpt-4.1-2025-04-14', instructions=str(task.user_scenario), tools=None, llm_args=kwargs)
            agent.set_seed(20260925); user.set_seed(20260925)
            governed = None
            observed = ContinuityObserver(atflows_url, atflows_token) if arm == 'atflows' else None
            with RetailProcess(upstream) as remote, endpoint(remote) as (url, token, public_call), sqlite3.connect(output / (arm + '-checkpoints.db'), check_same_thread=False) as connection:
                if arm in {'atmem', 'both'}:
                    grant = vault.grant(owner, principal_id=arm, role=EvidenceRole.CONTINUITY_COORDINATOR,
                        scope=EvidenceScope('local', 'local-user', workspace_id=arm))
                    client = ContinuityClient(f'http://127.0.0.1:{server.server_port}', grant['token'],
                        observer=AtFlowsObserver(atflows_url, atflows_token) if arm == 'both' else None)
                    registry = {schema['function']['name']: RegisteredTool(JsonResponseTool(url, token).tool()) for schema in remote.info['tools']}
                    governed = governed_langgraph_tools(GovernedToolRunner(client, 'retail-qualification', registry, enabled=True))
                graph = build_graph(agent, user, checkpointer=SqliteSaver(connection), public_call=public_call, governed_node=governed, observer=observed)
                current_topology = graph.get_graph().to_json()
                if topology is None:
                    topology = current_topology
                elif current_topology != topology:
                    raise ValueError('graph topology differs across arms')
                result = graph.invoke(initial_state(agent, user), {'configurable': {'thread_id': arm, 'run_id': 'run_' + arm}, 'recursion_limit': 70}, durability='sync')
                external = remote.snapshot()
                parity = semantic_messages(result['trajectory']) == semantic_messages(native_trajectory)
                if not parity:
                    raise ValueError('native trajectory differs in ' + arm)
                errors = client.observation_errors if arm == 'both' else observed.errors if observed else []
                if errors:
                    raise ValueError('product telemetry delivery failed')
                governed_count = 0
                if arm in {'atmem', 'both'}:
                    actual = [value for value in evaluator.request('GET', '/v1/continuity')['workflows'] if value['creator_id'] == arm]
                    governed_count = sum(len(value['operations']) for value in actual)
                    if governed_count != len(external['journal']) or governed_count == 0:
                        raise ValueError('native tool calls do not match authoritative product operations')
                row = {'arm': arm, 'native_request_matches': len(cassette.matches), 'trajectory_matches': parity,
                    'termination': result['termination'], 'tool_calls': len(external['journal']),
                    'final_state_sha256': digest(external['final']), 'trajectory': result['trajectory'],
                    'external_observations': external, 'observer_errors': errors,
                    'graph': current_topology, 'governed_operation_count': governed_count}
                (output / (arm + '.json')).write_text(json.dumps(row, indent=2) + '\n')
                rows.append({key: value for key, value in row.items() if key not in {'trajectory', 'external_observations', 'graph'}})
        if len({row['final_state_sha256'] for row in rows}) != 1:
            raise ValueError('four-arm final retail states differ')
        summary = {'evidence_class': 'public-native-cassette-four-arm-no-fault-qualification', 'paid_calls': 0,
            'production_gains_claimed': False, 'source': stamp, 'arms': rows,
            'packages': {name: importlib.metadata.version(name) for name in ['atmem', 'atflows', 'langgraph', 'langgraph-checkpoint-sqlite']},
            'limits': 'Preserved real agent replies replayed to verify native prompt/tool parity. No fresh agent score, faults or held-out results.'}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        (output / 'SHA256SUMS.json').write_text(json.dumps({p.name: file_digest(p) for p in output.glob('*.json')}, indent=2) + '\n')
        return summary
    finally:
        llm_utils.completion = original_completion
        server.shutdown(); server.server_close(); thread.join(3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--atflows-url', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.upstream.resolve(), args.native.resolve(), args.output.resolve(),
        atflows_url=args.atflows_url, atflows_token=os.environ['ATFLOWS_CONTINUITY_TOKEN']), indent=2))
