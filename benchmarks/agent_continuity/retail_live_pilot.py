"""Fresh four-arm public retail no-fault pilot. No benchmark recovery logic."""
import argparse
import base64
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import traceback
import uuid
from urllib.parse import urlsplit

from .live_transport import LoggedTransport, MODEL, PRICE, save_json
from .manifest import digest, file_digest
from .native_pilot import LEDGER_ROOT, LEDGER_CONFIG
from .retail import RetailProcess, pilot_task, verify_checkout, dependency_versions
from .retail_graph import build_graph, initial_state
from .retail_graph_qualification import endpoint
from .spend import SpendLedger


def installed_stamp(name):
    distribution = importlib.metadata.distribution(name)
    direct = json.loads(distribution.read_text('direct_url.json') or '{}')
    if direct.get('dir_info', {}).get('editable'):
        raise ValueError('paid qualification requires installed artifacts, not editable source')
    hashes = {}
    for entry in distribution.files or []:
        if entry.hash is None:
            continue
        actual = sha256(distribution.locate_file(entry).read_bytes()).digest()
        if entry.hash.mode != 'sha256' or base64.urlsafe_b64encode(actual).decode().rstrip('=') != entry.hash.value:
            raise ValueError('installed artifact differs from its RECORD')
        hashes[str(entry)] = actual.hex()
    if not hashes:
        raise ValueError('installed artifact has no verified files')
    return {'version': distribution.version, 'files_sha256': digest(hashes), 'verified_files': len(hashes)}


def run(upstream, output, *, atflows_url, atflows_token, env_file=None, execute=False):
    parsed = urlsplit(atflows_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', '::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('qualification requires an isolated loopback AtFlows endpoint')
    if execute and not atflows_token:
        raise ValueError('isolated AtFlows producer credential is required')
    key = None
    if execute:
        from dotenv import dotenv_values
        key = dotenv_values(env_file, interpolate=False).get('OPENAI_API_KEY') if env_file else os.environ.get('OPENAI_API_KEY')
        if not key:
            raise ValueError('explicit OpenAI credential unavailable')
    source = verify_checkout(upstream)
    task_data = pilot_task(upstream, '0')
    if task_data.get('initial_state'):
        raise ValueError('this pilot does not support a task-specific initial state')
    output.mkdir(parents=True, exist_ok=False)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', TAU2_DATA_DIR=str(upstream / 'data'),
        LITELLM_LOCAL_MODEL_COST_MAP='True', LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false')
    sys.path.insert(0, str(upstream / 'src'))
    from loguru import logger
    logger.remove()
    from tau2.agent.llm_agent import LLMAgent
    from tau2.user.user_simulator import UserSimulator
    from tau2.domains.retail.environment import get_environment
    from tau2.data_model.tasks import Task
    from tau2.data_model.message import AssistantMessage, UserMessage, ToolMessage
    from tau2.evaluator.evaluator_env import EnvironmentEvaluator
    from tau2.evaluator import evaluator_nl_assertions as nl
    from tau2.utils import llm_utils
    from litellm import ModelResponse
    from langgraph.checkpoint.sqlite import SqliteSaver
    from atmem.continuity.client import ContinuityClient, AtFlowsObserver, RecoveryBlocked
    from atmem.continuity.integrations import GovernedToolRunner, RegisteredTool, governed_langgraph_tools
    from atmem.continuity.tools import JsonResponseTool
    from atmem.control.manager import ControlPlaneManager
    from atmem.control.web import ControlDashboardServer
    from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
    from atflows.continuity import ContinuityObserver
    task = Task.model_validate(task_data)
    if {str(value.value) for value in task.evaluation_criteria.reward_basis} != {'DB', 'NL_ASSERTION'} or nl.DEFAULT_LLM_NL_ASSERTIONS != MODEL:
        raise ValueError('unsupported native grading contract')
    environment = get_environment()
    options = {'temperature': 0, 'num_retries': 0, 'max_tokens': 2048}
    sample_agent = LLMAgent(environment.get_tools(), environment.get_policy(), MODEL, options)
    sample_user = UserSimulator(llm=MODEL, instructions=str(task.user_scenario), tools=None, llm_args=options)
    code = {path.name: file_digest(path) for path in Path(__file__).parent.glob('*.py')}
    manifest = {'evidence_class': 'fresh-public-retail-engineering-pilot', 'source': source,
        'task_id': '0', 'task_sha256': digest(task_data), 'tool_schemas': [tool.openai_schema for tool in environment.get_tools()],
        'initial_db_sha256': digest(environment.tools.db.model_dump(mode='json')),
        'agent_prompt': sample_agent.system_prompt, 'simulator_prompt': sample_user.system_prompt,
        'arms': ['baseline', 'atmem', 'atflows', 'both'], 'model': MODEL, 'options': options, 'seed': 20260925,
        'price': PRICE, 'budget': LEDGER_CONFIG, 'code': code,
        'upstream_dependency_versions': dependency_versions(upstream),
        'registration_sha256': file_digest(Path(__file__).parents[2] / 'specs/benchmarking/002-agent-continuity/fresh-pilot-protocol.md'),
        'packages': {name: installed_stamp(name) for name in ['atmem', 'atflows', 'langgraph', 'langgraph-checkpoint-sqlite']},
        'grader_options': options, 'arm_order': 'fixed registered baseline, atmem, atflows, both; descriptive only',
        'production_gains_claimed': False, 'faults': None, 'repeats': 1,
        'limits': 'Exposed task0 only. No automatic reruns. Fresh no-fault engineering pilot, not held-out accuracy or recovery evidence.'}
    manifest['manifest_sha256'] = digest(manifest)
    save_json(output / 'manifest.json', manifest)
    save_json(output / 'schedule.json', [{'arm': arm, 'initial_disposition': 'planned'} for arm in manifest['arms']])
    if not execute:
        return {'disposition': 'dry_run', 'manifest_sha256': manifest['manifest_sha256'], 'paid_calls': 0}
    ledger = SpendLedger(LEDGER_ROOT / 'spend.db', **LEDGER_CONFIG)
    if ledger.snapshot()['summary']['unknown_attempts']:
        raise ValueError('unresolved prior spend prevents new paid work')
    if LEDGER_CONFIG['cap_micro_usd'] - ledger.snapshot()['summary']['budget_exposure_micro_usd'] < 4 * PRICE['upper_reserve_micro_usd']:
        raise ValueError('insufficient headroom for four conservative single-call reservations')
    manager = ControlPlaneManager.start(host='generic', state_path=output / 'state.json',
        control_root=output / 'control', memory_db=output / 'memory.db')
    manager.configure_agent_topology([{'agent_id': 'main', 'workspace': str(output), 'is_default': True}])
    vault = manager.evidence_service()
    owner = EvidencePrincipal('owner', EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope('local', 'local-user'))
    server = ControlDashboardServer(('127.0.0.1', 0), manager, html='isolated live pilot')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows, stop = [], False
    original = llm_utils.completion
    original_grader_options = nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS
    nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = options
    try:
        for arm in manifest['arms']:
            directory = output / arm
            directory.mkdir()
            if stop:
                row = {'arm': arm, 'disposition': 'not_run_after_safety_stop', 'paid_calls': 0}
                save_json(directory / 'status.json', row); rows.append(row)
                continue
            trial_id = 'fresh-' + arm + '-' + uuid.uuid4().hex
            transport = LoggedTransport(ledger, directory, key, trial_id, arm=arm)
            started = time.monotonic()
            grading_started = None
            def completion(**kwargs):
                if time.monotonic() - (grading_started if transport.role == 'grader' and grading_started is not None else started) > 600:
                    raise TimeoutError('trial deadline reached before provider dispatch')
                return ModelResponse(**transport.complete(**kwargs))
            llm_utils.completion = completion
            agent = LLMAgent(environment.get_tools(), environment.get_policy(), MODEL, options)
            user = UserSimulator(llm=MODEL, instructions=str(task.user_scenario), tools=None, llm_args=options)
            agent.set_seed(20260925); user.set_seed(20260925)
            for participant, role in [(agent, 'agent'), (user, 'simulator')]:
                generate = participant.generate_next_message
                def wrapped(*args, _generate=generate, _role=role, **kwargs):
                    transport.role = _role
                    try:
                        return _generate(*args, **kwargs)
                    finally:
                        transport.role = None
                participant.generate_next_message = wrapped
            row = {'arm': arm, 'trial_id': trial_id, 'disposition': 'infrastructure_failure'}
            observed = ContinuityObserver(atflows_url, atflows_token) if arm == 'atflows' else None
            governed, client = None, None
            try:
                with RetailProcess(upstream) as remote, endpoint(remote) as (url, token, public_call), sqlite3.connect(directory / 'checkpoints.db', check_same_thread=False) as connection:
                    if digest(remote.snapshot()['initial']) != manifest['initial_db_sha256']:
                        raise ValueError('native tool process initial state differs from registration')
                    if arm in {'atmem', 'both'}:
                        grant = vault.grant(owner, principal_id=arm, role=EvidenceRole.CONTINUITY_COORDINATOR,
                            scope=EvidenceScope('local', 'local-user', workspace_id=arm))
                        client = ContinuityClient(f'http://127.0.0.1:{server.server_port}', grant['token'],
                            observer=AtFlowsObserver(atflows_url, atflows_token) if arm == 'both' else None)
                        registry = {value['function']['name']: RegisteredTool(JsonResponseTool(url, token).tool()) for value in remote.info['tools']}
                        governed = governed_langgraph_tools(GovernedToolRunner(client, 'retail-fresh-pilot', registry, enabled=True))
                    graph = build_graph(agent, user, checkpointer=SqliteSaver(connection), public_call=public_call, governed_node=governed, observer=observed)
                    save_json(directory / 'topology.json', graph.get_graph().to_json())
                    graph_config = {'configurable': {'thread_id': arm, 'run_id': trial_id}, 'recursion_limit': 70}
                    try:
                        result = graph.invoke(initial_state(agent, user), graph_config, durability='sync')
                    finally:
                        save_json(directory / 'external-observations.json', remote.snapshot())
                        save_json(directory / 'checkpoint-observation.json', graph.get_state(graph_config).values)
                    save_json(directory / 'trajectory.json', result['trajectory'])
                    normal = result['termination'] in {'user_stop', 'agent_stop'}
                    row.update(disposition='completed' if normal else 'premature_termination', termination=result['termination'])
                    messages = [{'assistant': AssistantMessage, 'user': UserMessage, 'tool': ToolMessage}[value['role']].model_validate(value) for value in result['trajectory']]
                    if transport.halted or ledger.snapshot()['summary']['unknown_attempts']:
                        raise RuntimeError('accounting halted before grading')
                    db = EnvironmentEvaluator.calculate_reward(get_environment, task, messages)
                    transport.role = 'grader'
                    grading_started = time.monotonic()
                    grade = nl.NLAssertionsEvaluator.calculate_reward(task, messages)
                    if sorted(item.nl_assertion for item in grade.nl_assertions or []) != sorted(task.evaluation_criteria.nl_assertions or []):
                        raise ValueError('incomplete native assertion grading')
                    row.update(db_score=db.model_dump(mode='json'), nl_score=grade.model_dump(mode='json'),
                        local_task_reward=db.reward * grade.reward if normal else 0,
                        observer_errors=client.observation_errors if arm == 'both' else observed.errors if observed else [])
            except RecoveryBlocked as error:
                reason = str(error)
                row.update(disposition='product_refused', reason=reason if reason in {'needs_confirmation', 'workflow_disabled', 'lease_active', 'controller_unavailable'} else 'controller_refused')
            except Exception as error:
                if row['disposition'] in {'completed', 'premature_termination'}:
                    row['grading_status'] = 'failed'
                else:
                    row['disposition'] = 'infrastructure_failure'
                row.update(error_type=type(error).__name__, error_frames=[{'file': Path(frame.filename).name,
                    'line': frame.lineno, 'function': frame.name} for frame in traceback.extract_tb(error.__traceback__)])
            finally:
                row.update(elapsed_seconds=time.monotonic() - started, paid_calls=transport.calls, transport_halted=transport.halted)
                save_json(directory / 'status.json', row)
                ledger.export(directory / 'accounting.json')
                save_json(directory / 'SHA256SUMS.json', {path.name: file_digest(path) for path in directory.glob('*.json')})
                rows.append(row)
            stop = bool(transport.halted or ledger.snapshot()['summary']['unknown_attempts'])
        try:
            intact = verify_checkout(upstream) == source and code == {path.name: file_digest(path) for path in Path(__file__).parent.glob('*.py')} and manifest['packages'] == {name: installed_stamp(name) for name in manifest['packages']}
        except Exception:
            intact = False
        report = {'evidence_class': manifest['evidence_class'], 'manifest_sha256': manifest['manifest_sha256'],
            'arms': rows, 'source_integrity': intact, 'production_gains_claimed': False, 'budget_summary': ledger.snapshot()['summary']}
        report['comparison_eligible'] = intact and len(rows) == 4 and all(row['disposition'] == 'completed' and 'local_task_reward' in row and not row.get('observer_errors') for row in rows)
        save_json(output / 'summary.json', report)
        return report
    finally:
        llm_utils.completion = original
        nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = original_grader_options
        server.shutdown(); server.server_close(); thread.join(3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--atflows-url', required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.upstream.resolve(), args.output.resolve(), atflows_url=args.atflows_url,
        atflows_token=os.environ.get('ATFLOWS_CONTINUITY_TOKEN', ''), env_file=args.env_file, execute=args.execute), indent=2))
