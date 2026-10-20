"""Benchmark-only transport for the full, pinned upstream Cognee CODE SDK.

This is not shipped in AtMem and does not substitute AtMem's graph algorithms.
Public, screened source and Enola artifacts stay in an isolated benchmark state.
"""
import argparse
import asyncio
from contextlib import redirect_stdout
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path('/home/user/atmem-swebench-20261019')
OPERATIONS = ('query_facts', 'explore', 'traverse', 'find_path', 'impact_analysis',
              'insights', 'architecture', 'delta')


def environment(state, python):
    state = Path(state)
    if (state.parent != ROOT / 'cognee-states' or state.is_symlink()
            or not state.name.startswith('atmem-swe-lite-')):
        raise ValueError('dedicated benchmark Cognee state required')
    return {'PATH': str(Path(python).parent) + ':/usr/bin:/bin', 'HOME': str(state),
        'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'TELEMETRY_DISABLED': '1',
        'COGNEE_TRACING_ENABLED': 'false', 'AUTO_FEEDBACK': 'false',
        'CACHING': 'true', 'ENABLE_BACKEND_ACCESS_CONTROL': 'true',
        'DATA_ROOT_DIRECTORY': str(state / 'data'),
        'SYSTEM_ROOT_DIRECTORY': str(state / 'system'),
        'CACHE_ROOT_DIRECTORY': str(state / 'cache'),
        'COGNEE_LOGS_DIR': str(state / 'logs'), 'COGNEE_REPOS_DIR': str(state / 'repos'),
        'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'ENOLA_NO_UPDATE_CHECK': '1',
        'ENOLA_NO_PROMPTS': '1'}


def tool_definition():
    return {'name': 'code_search',
        'description': "Search Cognee's indexed pre-change code graph. query_facts finds names; "
            'explore inspects a fact; traverse/find_path/impact_analysis/insights/architecture/delta '
            'inspect relationships. Current workspace source takes precedence after edits.',
        'inputSchema': {'type': 'object', 'additionalProperties': False,
            'properties': {'operation': {'type': 'string', 'enum': list(OPERATIONS)},
                'arguments': {'type': 'object'}, 'query': {'type': 'string', 'maxLength': 1000},
                'top_k': {'type': 'integer', 'minimum': 1, 'maximum': 100}},
            'required': ['operation']}}


async def query(arguments):
    if (not isinstance(arguments, dict) or set(arguments) - {'operation', 'arguments', 'query', 'top_k'}
            or arguments.get('operation') not in OPERATIONS):
        raise ValueError('invalid code-search request')
    fields = arguments.get('arguments', {})
    text, k = arguments.get('query', ''), arguments.get('top_k', 15)
    if (not isinstance(fields, dict) or 'operation' in fields or not isinstance(text, str)
            or len(text) > 1000 or type(k) is not int or not 1 <= k <= 100):
        raise ValueError('invalid bounded query')
    import cognee
    from cognee import SearchType
    return await cognee.search(query_type=SearchType.CODE, query_text=text,
        datasets=['swebench_structure'], top_k=k,
        code_query={'operation': arguments['operation'], **fields})


async def serve():
    output = sys.stdout
    for line in sys.stdin:
        if len(line.encode()) > 100_000:
            raise ValueError('MCP request too large')
        request = json.loads(line)
        if 'id' not in request:
            continue
        try:
            method, params = request['method'], request.get('params', {})
            if method == 'initialize':
                result = {'protocolVersion': params['protocolVersion'], 'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'upstream-cognee-code', 'version': '1.6.4'}}
            elif method == 'tools/list':
                result = {'tools': [tool_definition()]}
            elif method == 'ping':
                result = {}
            elif method == 'tools/call' and params.get('name') == 'code_search':
                with redirect_stdout(sys.stderr):
                    value = await query(params.get('arguments', {}))
                raw = json.dumps(value, default=str)
                if len(raw.encode()) > 1_000_000:
                    raise ValueError('upstream response exceeds transport budget; request a smaller result')
                result = {'content': [{'type': 'text', 'text': raw}], 'isError': False}
            else:
                raise ValueError('unsupported read-only method')
            reply = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
        except Exception as exc:
            reply = {'jsonrpc': '2.0', 'id': request['id'],
                     'error': {'code': -32602, 'message': str(exc)}}
        output.write(json.dumps(reply) + '\n')
        output.flush()


async def index(state):
    import cognee
    from cognee.tasks.code_graph import get_code_graph_tasks
    tick = time.monotonic()
    await cognee.run_custom_pipeline(tasks=get_code_graph_tasks(str(state / 'source'),
        snapshot_dir=str(state / 'artifacts'), index_vectors=False), data=str(state / 'source'),
        dataset='swebench_structure', pipeline_name='swebench_structure', skip_connection_test=True)
    return {'status': 'indexed', 'load_seconds': time.monotonic() - tick}


def prepare(stage, runtime, image_id):
    """Called by the trusted installed AtMem worker, never by the solver."""
    import subprocess
    import zipfile
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    from atmem.code.identity import CodeIdentity
    from atmem.code.application import CodeApplication
    from atmem.knowledge.projections import CodeKnowledge, INDEX_SOURCE_BYTES
    from atmem.knowledge.worker import ExtractionWorker
    from atmem.knowledge.code.source_policy import SOURCE_POLICY
    from atmem.knowledge.contracts import stable_digest
    source = Path(stage['source'])
    if source.parent != ROOT / 'sources' or source.is_symlink():
        raise ValueError('owned source required')
    state = ROOT / 'cognee-states' / source.name
    state.mkdir(mode=0o700, parents=True, exist_ok=False)
    wheel = Path(runtime['wheel_path'])
    if sha256(wheel.read_bytes()).hexdigest() != runtime['wheel_sha256']:
        raise ValueError('Cognee wheel digest differs')
    # Verify the package in its own interpreter before executing its SDK.
    audit = """import pathlib,zipfile,cognee
p=pathlib.Path(cognee.__file__).parent
with zipfile.ZipFile(%r) as z:
 for n in z.namelist():
  if n.startswith('cognee/') and n.endswith('.py'):
   if p.joinpath(*pathlib.PurePosixPath(n).parts[1:]).read_bytes()!=z.read(n):raise ValueError('upstream package differs')
""" % str(wheel)
    env = environment(state, runtime['python'])
    subprocess.run([runtime['python'], '-I', '-c', audit], env=env,
                   check=True, capture_output=True, timeout=90)
    os.environ['ATMEM_HOME'] = str(state / 'capture-home')
    HouseholdApplication.initialize(state / 'capture.db', encrypted=True)
    memory = Memory(state / 'capture.db', auto_vectors=False)
    tick = time.monotonic()
    try:
        scope = CodeIdentity(memory.store).resolve(source, subject_id='swebench-pilot',
            profile_id='shared', agent_id='claude')
        app = CodeApplication(memory, subject_id=scope.subject_id)
        app.settings(scope.project_id, {'graph_enabled': True})
        knowledge = CodeKnowledge(app, scope)
        config = stable_digest({'worker_image': image_id, 'source_policy': SOURCE_POLICY})
        snapshot, files, omissions = knowledge.capture(str(source), config,
            max_source_bytes=INDEX_SOURCE_BYTES, omit_oversized_files=True, omit_invalid_text=True)
        artifacts = ExtractionWorker(image_id).extract(snapshot, files, authorize=knowledge.authorize)
        (state / 'source').mkdir()
        for name, raw in files.items():
            target = state / 'source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (state / 'artifacts').mkdir()
        for name, raw in [('facts.jsonl', artifacts.facts_jsonl), ('receipt.json', artifacts.receipt_json),
                          ('insights.json', artifacts.insights_json)]:
            (state / 'artifacts' / name).write_bytes(raw)
        (state / 'source-manifest.json').write_text(json.dumps({
            'files': dict(snapshot.files), 'omissions': omissions, 'image_id': image_id}))
    finally:
        memory.close()
    extractor_s = time.monotonic() - tick
    server = Path(runtime['server_path'])
    if sha256(server.read_bytes()).hexdigest() != runtime['server_sha256']:
        raise ValueError('Cognee transport differs')
    indexed = subprocess.run([runtime['python'], '-I', str(server), 'index', '--state', str(state)],
        env=env, capture_output=True, text=True, timeout=600)
    (state / 'index-stderr.log').write_text(indexed.stderr)
    if indexed.returncode:
        raise RuntimeError('upstream Cognee indexing failed; retained benchmark diagnostics')
    loaded = json.loads(indexed.stdout)
    return {'provider': 'actual_upstream_cognee', 'index_seconds': extractor_s + loaded['load_seconds'],
        'extraction_seconds': extractor_s, 'upstream_load_seconds': loaded['load_seconds'],
        'admitted_files_digest': stable_digest(dict(snapshot.files)),
        'server': {'command': runtime['python'], 'args': ['-I', str(server), 'serve', '--state', str(state)]},
        'environment': env, 'server_sha256': runtime['server_sha256']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['index', 'serve'])
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    # All SDK calls run with credentials and owner configuration excluded.
    env = environment(args.state, sys.executable)
    os.environ.clear()
    os.environ.update(env)
    if args.mode == 'index':
        with redirect_stdout(sys.stderr):
            value = asyncio.run(index(args.state))
        print(json.dumps(value), flush=True)
    else:
        asyncio.run(serve())


if __name__ == '__main__':
    main()
