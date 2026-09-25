"""Ordinary retail application process; stock checkpoint resume, no repair logic.

Only public tool HTTP and model requests cross this worker boundary. The parent
does not pass task grading criteria, native DB access or an oracle connection.
"""
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from urllib.request import Request, build_opener, ProxyHandler


def run(config, *, resume=False):
    if config['arm'] not in {'baseline', 'atmem', 'atflows', 'both'}:
        raise ValueError('unknown comparison arm')
    keep = {key: value for key, value in os.environ.items() if key in {'PATH', 'TMPDIR', 'LANG', 'SYSTEMROOT', 'WINDIR'}}
    os.environ.clear()
    os.environ.update(keep)
    def local_network_only(event, arguments):
        if event == 'socket.connect' and isinstance(arguments[1], tuple) and arguments[1][0] not in {'127.0.0.1', '::1'}:
            raise PermissionError('recorded-response qualification permits loopback only')
        if event == 'socket.getaddrinfo' and arguments[0] not in {'127.0.0.1', '::1', 'localhost'}:
            raise PermissionError('recorded-response qualification permits loopback only')
    sys.addaudithook(local_network_only)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', TAU2_DATA_DIR=config['data'],
        LITELLM_LOCAL_MODEL_COST_MAP='True', LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false')
    sys.path.insert(0, config['upstream_src'])
    from loguru import logger
    logger.remove()
    from tau2.agent.llm_agent import LLMAgent
    from tau2.user.user_simulator import UserSimulator
    from tau2.utils import llm_utils
    from langgraph.checkpoint.sqlite import SqliteSaver
    from atmem.continuity.client import ContinuityClient, AtFlowsObserver, RecoveryBlocked
    from atmem.continuity.integrations import GovernedToolRunner, RegisteredTool, governed_langgraph_tools
    from atmem.continuity.tools import JsonResponseTool
    from atflows.continuity import ContinuityObserver
    from .retail_graph import build_graph, initial_state
    from .retail_graph_qualification import NativeCassette

    # Native agent only needs public schema and policy, never the evaluator's task.
    tools = [SimpleNamespace(name=value['function']['name'], openai_schema=value) for value in config['tools']]
    options = {'temperature': 0, 'num_retries': 0, 'max_tokens': 2048}
    agent = LLMAgent(tools, config['policy'], 'gpt-4.1-2025-04-14', options)
    user = UserSimulator(llm='gpt-4.1-2025-04-14', instructions=config['user_scenario'], tools=None, llm_args=options)
    agent.set_seed(config['seed']); user.set_seed(config['seed'])
    opener = build_opener(ProxyHandler({}))
    cassette = None
    mode = config.get('provider_mode', 'recorded')
    if mode == 'recorded':
        cassette = NativeCassette(Path(config['cassette']))
        llm_utils.completion = cassette.completion
    elif mode == 'live':
        from litellm import ModelResponse
        role = [None]
        def completion(**kwargs):
            if role[0] not in {'agent', 'simulator'}:
                raise ValueError('unidentified model caller')
            request = Request(config['model_url'], data=json.dumps({'role': role[0], 'request': kwargs}).encode(),
                headers={'Authorization': 'Bearer ' + config['model_token'], 'Content-Type': 'application/json'})
            with opener.open(request, timeout=100) as response:
                return ModelResponse(**json.load(response))
        llm_utils.completion = completion
        for participant, label in [(agent, 'agent'), (user, 'simulator')]:
            generate = participant.generate_next_message
            def wrapped(*args, _generate=generate, _label=label, **kwargs):
                role[0] = _label
                try:
                    return _generate(*args, **kwargs)
                finally:
                    role[0] = None
            participant.generate_next_message = wrapped
    else:
        raise ValueError('unsupported provider mode')
    def public_call(value):
        request = Request(config['tool_url'], data=json.dumps(value).encode(),
            headers={'Authorization': 'Bearer ' + config['tool_token'], 'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    governed = None
    observer = ContinuityObserver(config['atflows_url'], config['atflows_token']) if config['arm'] == 'atflows' else None
    if config['arm'] in {'atmem', 'both'}:
        client = ContinuityClient(config['atmem_url'], config['atmem_token'],
            observer=AtFlowsObserver(config['atflows_url'], config['atflows_token']) if config['arm'] == 'both' else None)
        registry = {tool.name: RegisteredTool(JsonResponseTool(config['tool_url'], config['tool_token']).tool()) for tool in tools}
        governed = governed_langgraph_tools(GovernedToolRunner(client, 'retail-fault-qualification', registry, enabled=True))
    output = Path(config['output'])
    stage = 'resume' if resume else 'start'
    with sqlite3.connect(config['checkpoints'], check_same_thread=False) as connection:
        graph = build_graph(agent, user, checkpointer=SqliteSaver(connection), public_call=public_call,
                            governed_node=governed, observer=observer)
        graph_config = {'configurable': {'thread_id': config['thread_id'], 'run_id': config['run_id']}, 'recursion_limit': 70}
        (output / (stage + '-topology.json')).write_text(json.dumps(graph.get_graph().to_json(), indent=2))
        try:
            result = graph.invoke(None if resume else initial_state(agent, user), graph_config, durability='sync')
            disposition = {'status': 'conversation_returned', 'termination': result['termination']}
            (output / (stage + '-trajectory.json')).write_text(json.dumps(result['trajectory'], indent=2))
        except RecoveryBlocked as error:
            disposition = {'status': 'product_refused_before_dispatch', 'reason': str(error)}
        except ValueError as error:
            if 'request differs from preserved native' not in str(error):
                raise
            disposition = {'status': 'cassette_miss', 'reason': 'changed request has no recorded model response'}
        disposition.update(native_request_matches=len(cassette.matches) if cassette is not None else None,
            packages={name: importlib.metadata.version(name) for name in ['atmem', 'atflows', 'langgraph']})
        (output / (stage + '-status.json')).write_text(json.dumps(disposition, indent=2))
