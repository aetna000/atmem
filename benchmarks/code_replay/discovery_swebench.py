"""One pinned Verified qualification task, offline Windows graders/local agents.

This is a diagnostic resource/transport pilot, not the complete 500-task score.
No rental, copied sign-in, target feedback to memory, or score-guided retries.
"""
import argparse
import base64
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay import discovery_click as click
from benchmarks.code_replay.discovery_study import Comparator, definitions
from benchmarks.code_replay.discovery_metrics import events, usage, summarize_tools

SOCKET = '/private/tmp/atmem-discovery-044-win.sock'
REMOTE = '/home/user/atmem-discovery-044-20261020'
HARNESS = '/home/user/atmem-swebench-20261019/venv/bin/python'
PILOT = 'psf__requests-6028'


def worker_source():
    source = Path(__file__).with_name('swebench_worker.py').read_text()
    changes = {
        "ROOT = Path('/home/user/atmem-swebench-20261019')": 'ROOT = Path(' + repr(REMOTE) + ')',
        "LABEL = 'atmem.benchmark=swebench-lite-20261019'": "LABEL = 'atmem.benchmark=discovery-044-20261020'",
        "PREFIX = 'atmem-swe-lite-'": "PREFIX = 'atmem-discovery-044-'",
        "!= 'swebench-lite-20261019'": "!= 'discovery-044-20261020'",
    }
    for before, after in changes.items():
        if source.count(before) != 1:
            raise ValueError('review changed controller before adaptation')
        source = source.replace(before, after)
    return source


def remote(action, payload, timeout=420):
    # Existing documented native SSH sign-in stays local. The solver cannot
    # select this controller action, container, source root, or interpreter.
    source = worker_source()
    if action == 'export':
        program = source + '\np=Path(job["payload"]["source"]); assert p.parent==ROOT/"sources"; print(json.dumps({"tar_base64":base64.b64encode(run(["git","-C",str(p),"archive","HEAD"]).stdout).decode()}))'
    else:
        program = source + '\nROOT.mkdir(parents=True,exist_ok=True)\nprint(json.dumps(dispatch(' + repr(action) + ',job["payload"])))'
    loader = 'import json,sys,os;job=json.loads(sys.stdin.readline());fd=os.open(os.devnull,os.O_RDONLY);os.dup2(fd,0);os.close(fd);exec(job["program"])'
    command = ['ssh', '-S', SOCKET, '-o', 'BatchMode=yes', '-T', 'user@192.168.0.87',
        'wsl -d Ubuntu -u root -- ' + HARNESS + ' -I -c "' + loader.replace('"', '\\"') + '"']
    result = subprocess.run(command, input=json.dumps({'program': program, 'payload': payload}) + '\n',
        capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('owned SWE controller failed: ' + result.stderr[-2000:] + result.stdout[-1000:])
    return json.loads(result.stdout)


def evidence(root):
    scope = EvidenceScope('benchmark', 'local-operator', 'discovery-044')
    principal = EvidencePrincipal('discovery-044-operator', EvidenceRole.ADMINISTRATOR, scope)
    return ReplayEvidence(Path(root) / 'vault', vault_id='discovery-044', scope=scope), principal


def serve(config):
    from atmem.code.curation import encoded
    from atmem.code.discovery import DiscoveryRequest, RESPONSE
    vault, principal = evidence(config['evidence_root'])
    comparator = Comparator(config)
    count = 0
    try:
        for line in sys.stdin:
            if len(line.encode()) > 100_000:
                raise ValueError('bounded MCP message required')
            request = json.loads(line)
            if 'id' not in request:
                continue
            tick = time.monotonic()
            try:
                method, params = request['method'], request.get('params', {})
                if method == 'initialize':
                    result = {'protocolVersion': params['protocolVersion'], 'capabilities': {'tools': {}},
                        'serverInfo': {'name': 'controlled-verified-discovery', 'version': '1'}}
                elif method == 'tools/list':
                    tools = definitions()
                    tools[1]['description'] = ('Run an offline shell command in the pinned task container at /testbed. '
                        'Original reads, exact searches, edits and public tests. Testbed Python is on PATH. '
                        '40 second command cap, 24000 byte returned-output cap. No host access or network.')
                    result = {'tools': tools}
                elif method == 'ping':
                    result = {}
                elif method == 'tools/call':
                    count += 1
                    if count > 30:
                        raise ValueError('tool-call cap')
                    arguments = params.get('arguments', {})
                    if params['name'] == 'workspace_command' and set(arguments) == {'command'}:
                        value = remote('command', {'container': config['container'], 'command': arguments['command']}, timeout=65)
                    elif params['name'] == 'repository_discover':
                        typed = DiscoveryRequest.from_dict(arguments)
                        current = remote('patch', {'container': config['container']}, timeout=30)
                        if current['patch'] or current['exit_code'] or current['head'] != config['baseline_head']:
                            value = {'format': RESPONSE, 'request_id': typed.request_id, 'turn_id': typed.turn_id,
                                'backend': config['backend'], 'status': 'withheld', 'items': [], 'reason': 'solver_source_changed'}
                        else:
                            value = comparator.discover(arguments)
                    else:
                        raise ValueError('unknown tool or fields')
                    result = {'content': [{'type': 'text', 'text': encoded(value).decode()}], 'isError': False}
                else:
                    raise ValueError('unknown MCP method')
                response = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
            except (ValueError, PermissionError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                response = {'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32602, 'message': type(exc).__name__ + ': unavailable'}}
            payload = {'request': request, 'response': response, 'backend': config['backend'],
                'elapsed_ms': int((time.monotonic()-tick)*1000), 'assurance': 'prepared_before_write'}
            vault.capture(run_id=config['run_id'], kind='discovery.tool_prepared', payload=payload, principal=principal)
            sys.stdout.write(json.dumps(response) + '\n'); sys.stdout.flush()
            vault.capture(run_id=config['run_id'], kind='discovery.tool_written',
                payload={**payload, 'assurance': 'stream_written_not_model_ack'}, principal=principal)
    finally:
        comparator.close()


def solve(args):
    """Frozen six-cell requested-consultation pilot after official controls."""
    if args.root.exists():
        raise ValueError('new solver campaign required; no scored retries')
    previous, access = evidence(args.qualified_resource)
    retained = previous.inspect(access, 'campaign')
    frozen = next(e['envelope']['payload'] for e in retained if e['envelope']['event_type'] == 'discovery.verified_pilot_frozen')
    proof = [e['envelope']['payload'] for e in retained if e['envelope']['event_type'] == 'discovery.verified_resource_qualified']
    if len(proof) != 1 or {r['control']: (r['valid'], r['resolution']) for r in proof[0]['controls']} != {
            'base': (True, 'RESOLVED_NO'), 'reference': (True, 'RESOLVED_FULL')}:
        raise ValueError('passing official base/reference controls required')
    task, image = frozen['task_evaluator_only'], proof[0]['image']
    if task['instance_id'] != PILOT:
        raise ValueError('only frozen qualification identity allowed')
    args.root.mkdir(parents=True, mode=0o700)
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    from atmem.core import keys
    keys.DEFAULT_KEY_PATH = args.root / 'home/identity/keys/db.key'
    click.installed_matches(click.WHEEL, click.WHEEL_SHA)
    vault, principal = evidence(args.root)
    def save(run, kind, payload):
        vault.capture(run_id=run, kind=kind, payload=payload, principal=principal)
    qualified, access = evidence(args.qualification_evidence)
    terminals = [e['envelope']['payload'] for e in qualified.inspect(access, 'campaign') if e['envelope']['event_type'] == 'discovery.completed']
    passed = {r['host'] for t in terminals if t.get('qualification_only') for r in t['rows'] if r.get('qualified') is True}
    if not {'claude', 'codex'} <= passed:
        raise ValueError('both native subscription/tool/usage preflights required')
    save('campaign', 'discovery.swe_preparation', {'instance_id': PILOT, 'resource_proof': proof[0],
        'task_evaluator_only': task, 'classification': 'one_verified_qualification_task_requested_consultation',
        'source_code': Path(__file__).read_text(), 'wheel_sha256': click.WHEEL_SHA,
        'rental_spend_usd': 0, 'copilot': 'blocked_by_account_policy_no_bypass'})
    containers, memories, cases, rows = [], [], [], []
    try:
        for h, host in enumerate(('claude', 'codex')):
            order = ['native', 'cognee', 'atmem']
            for backend in order[h:] + order[:h]:
                run = host + '-' + backend
                root = args.root / run
                root.mkdir()
                print(json.dumps({'state': 'preparing_solver', 'run': run, 'instance_id': PILOT}), flush=True)
                start = time.monotonic()
                stage = remote('solver', {'task': task, 'image_id': image['Id']})
                containers.append(stage['container'])
                save(run, 'discovery.swe_solver_staged', stage)
                exported = remote('export', {'source': stage['source']})
                raw = base64.b64decode(exported['tar_base64'], validate=True)
                if len(raw) > 40_000_000:
                    raise ValueError('source archive exceeds bound')
                save(run, 'discovery.swe_source_archive', exported)
                files = {}
                with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                    for member in archive.getmembers():
                        if member.isdir():
                            continue
                        from atmem.knowledge.contracts import source_path
                        source_path(member.name)
                        if not member.isfile() or member.size > 8_000_000:
                            raise ValueError('review unsupported source member before indexing')
                        files[member.name] = archive.extractfile(member).read()
                workspace = root / 'source'
                workspace.mkdir()
                from benchmarks.code_replay.grade import write_new_tree
                write_new_tree(workspace, files)
                env = {'PATH': os.environ['PATH'], 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
                for command in (['git', 'init', str(workspace)], ['git', '-C', str(workspace), 'add', '.'],
                        ['git', '-C', str(workspace), '-c', 'user.name=Replay', '-c', 'user.email=replay@localhost', 'commit', '-m', 'Permitted source snapshot']):
                    subprocess.run(command, env=env, capture_output=True, check=True)
                config = {'backend': backend, 'workspace': str(workspace),
                    'source_files': {n: sha256(b).hexdigest() for n,b in files.items()},
                    'provider': None, 'evidence_root': str(args.root), 'run_id': run,
                    'atmem_home': os.environ['ATMEM_HOME'], 'container': stage['container'],
                    'baseline_head': stage['baseline_head']}
                index_ms = 0
                if backend == 'cognee':
                    state = root / 'cognee-state'; state.mkdir()
                    from benchmarks.code_replay.cognee_click import worker_environment
                    provider_env = worker_environment(state, click.COGNEE)
                    worker = Path(__file__).with_name('cognee_click.py').read_text()
                    boot = 'import sys;sys.argv=["worker",*sys.argv[1:]];exec(compile(' + repr(worker) + ',"<actual-upstream-CODE>","exec"))'
                    tick = time.monotonic()
                    indexed = subprocess.run([str(click.COGNEE), '-I', '-u', '-c', boot, 'index', '--root', str(workspace)],
                        cwd=state, env=provider_env, capture_output=True, timeout=300)
                    index_ms = int((time.monotonic()-tick)*1000)
                    save(run, 'discovery.swe_cognee_index', {'exit_code': indexed.returncode,
                        'stdout_base64': base64.b64encode(indexed.stdout).decode(), 'stderr_base64': base64.b64encode(indexed.stderr).decode(),
                        'index_ms': index_ms, 'revision': click.COGNEE_REVISION})
                    if indexed.returncode:
                        raise RuntimeError('actual upstream extraction failed')
                    config['provider'] = {'command': [str(click.COGNEE), '-I', '-u', '-c', boot, 'serve'],
                        'cwd': str(state), 'environment': provider_env}
                elif backend == 'atmem':
                    from atmem.memory import Memory
                    from atmem.service.household import HouseholdApplication
                    from atmem.code.application import CodeApplication
                    from atmem.code.identity import CodeIdentity
                    from atmem.knowledge.projections import CodeKnowledge
                    from atmem.knowledge.worker import ExtractionWorker
                    db = root / 'memory.db'; HouseholdApplication.initialize(db, encrypted=True)
                    memory = Memory(db, auto_vectors=False); memories.append(memory)
                    identity = CodeIdentity(memory.store).resolve(workspace, subject_id='benchmark-operator', profile_id='shared', agent_id=host)
                    app = CodeApplication(memory, subject_id=identity.subject_id)
                    app.settings(identity.project_id, {'graph_enabled': True, 'auto_capture': False, 'auto_recall': False})
                    package = json.loads(click.PACKAGE.read_bytes())
                    tick = time.monotonic()
                    indexed = CodeKnowledge(app, identity).index(str(workspace), ExtractionWorker(package['image_id']))
                    index_ms = int((time.monotonic()-tick)*1000)
                    save(run, 'discovery.swe_atmem_index', {'index': indexed, 'index_ms': index_ms})
                    config['provider'] = {'command': [str(click.PYTHON), '-I', '-u', '-m', 'atmem.knowledge.code.mcp',
                        '--db', str(db), '--root', str(workspace), '--subject', identity.subject_id,
                        '--project-id', identity.project_id, '--profile', 'shared', '--agent', host, '--tool-profile', 'navigation'],
                        'cwd': str(root), 'environment': {'PATH': os.environ['PATH'], 'HOME': os.environ['HOME'], 'ATMEM_HOME': config['atmem_home']}}
                comparator = Comparator(config)
                try:
                    found = comparator.discover({'format': 'atmem-repository-discovery-request-v1', 'request_id': 'preflight',
                        'turn_id': 'preflight', 'query': 'CaseInsensitiveDict', 'limit': 3, 'budget': 4096})
                    save(run, 'discovery.swe_provider_qualified', found)
                    if not found['items']:
                        raise RuntimeError('common API canary not available through comparator')
                finally:
                    comparator.close()
                prompt = ('Implement the issue below in the offline repository at /testbed. Begin repository navigation '
                    'with repository_discover, choosing your own task-relevant query. It returns ranked locations, not source. '
                    'Use workspace_command to read exact original source, search, edit and run available public tests. '
                    'All three backends receive this same instruction. No command is gated on consultation. '
                    'No network, host files, reference solution or future history is available. Do not alter tests, '
                    'dependency configuration or Git history. Python/testbed dependencies are on PATH. '
                    'You have 240 seconds and 30 tool calls. End with a concise summary of actual changes and observed tests.\n\n'
                    + task['problem_statement'])
                command, child_env = click.command_for(host, config, prompt)
                before = 'from benchmarks.code_replay.discovery_study import serve'
                if sum(arg.count(before) for arg in command) != 1:
                    raise ValueError('review changed shared host launcher')
                command = [arg.replace(before, 'from benchmarks.code_replay.discovery_swebench import serve') for arg in command]
                boot = ('import atmem,sys,json;sys.path.insert(0,' + repr(str(click.REPO)) +
                    ');from benchmarks.code_replay.discovery_swebench import serve;serve(json.loads(sys.argv[1]))')
                requests = [
                    {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'id': 3, 'method': 'ping'}]
                checked = subprocess.run([str(click.PYTHON), '-I', '-u', '-c', boot, json.dumps(config)],
                    input='\n'.join(map(json.dumps, requests)) + '\n', capture_output=True, text=True, timeout=60,
                    env={**click.environment(), 'ATMEM_HOME': config['atmem_home']})
                replies = [json.loads(line) for line in checked.stdout.splitlines()]
                save(run, 'discovery.swe_transport_qualified', {'requests': requests, 'responses': replies,
                    'stderr': checked.stderr, 'exit_code': checked.returncode, 'model_dispatches': 0})
                if checked.returncode or len(replies) != 3 or any('error' in r for r in replies) or [
                        t['name'] for t in replies[1]['result']['tools']] != ['repository_discover', 'workspace_command']:
                    raise RuntimeError('real SWE MCP transport preflight failed; no solver dispatch')
                cases.append({'run': run, 'host': host, 'backend': backend, 'workspace': workspace,
                    'stage': stage, 'config': config, 'command': command, 'environment': child_env,
                    'index_ms': index_ms, 'setup_ms': int((time.monotonic()-start)*1000)})
        save('campaign', 'discovery.swe_frozen', {'cases': [{k: str(v) if isinstance(v, Path) else v for k,v in c.items() if k != 'environment'} for c in cases],
            'classification': 'one_qualification_task_requested_consultation_not_full_or_heldout',
            'full_target_cells': 4500, 'planned_pilot_cells': 9, 'qualified_pilot_cells': 6,
            'copilot_missing': 'third_party_mcp_disabled_by_account_policy', 'resource_proof': proof[0]})
        for case in cases:
            print(json.dumps({'state': 'solver_started', 'run': case['run'], 'instance_id': PILOT}), flush=True)
            save(case['run'], 'discovery.trial_started', {'command': case['command']})
            observed = click.bounded(case['command'], cwd=case['workspace'], env=case['environment'])
            save(case['run'], 'discovery.attempt', {k: base64.b64encode(v).decode() if isinstance(v, bytes) else v for k,v in observed.items()})
            patch = remote('patch', {'container': case['stage']['container']}, timeout=30)
            save(case['run'], 'discovery.swe_patch', patch)
            forbidden = [p for p in patch['changed_paths'] if p.startswith(('tests/', '.git/', '.github/')) or
                p in {'setup.py', 'setup.cfg', 'tox.ini', 'pyproject.toml', 'requirements.txt'}]
            case.update(observed=observed, patch=patch,
                violations=forbidden or patch['untracked'] or patch['head'] != case['stage']['baseline_head'])
            row = {'run': case['run'], 'host': case['host'], 'backend': case['backend'], 'instance_id': PILOT,
                'usage': usage(case['host'], events(observed['stdout'])), 'solver_ms': observed['elapsed_ms'],
                'exit_code': observed['exit_code'], 'stop': observed['stop'], 'index_ms': case['index_ms'],
                'setup_ms': case['setup_ms'], **summarize_tools(vault.inspect(principal, case['run']))}
            case['row'] = row; rows.append(row)
            save(case['run'], 'discovery.solver_terminal', row)
            print(json.dumps({'state': 'solver_terminal', **row}), flush=True)
        for case in cases:
            grade = remote('grade', {'task': task, 'image_id': image['Id'], 'patch': case['patch']['patch']})
            case['row'].update(functional_pass=bool(grade.get('valid') and grade.get('resolution') == 'RESOLVED_FULL' and not case['violations']),
                grade_valid=grade.get('valid', False), resolution=grade.get('resolution'), grader_seconds=grade.get('elapsed_s'),
                patch_violations=case['violations'])
            save(case['run'], 'discovery.swe_graded', {'row': case['row'], 'grade': grade})
            print(json.dumps({'state': 'graded', **case['row']}), flush=True)
        save('campaign', 'discovery.completed', {'rows': rows, 'instance_id': PILOT, 'full_target_cells': 4500,
            'executed': len(rows), 'qualification_only': False, 'rental_spend_usd': 0,
            'classification': 'single_qualification_task_requested_consultation'})
        print(json.dumps({'state': 'completed', 'rows': rows, 'rental_spend_usd': 0}), flush=True)
    except BaseException as exc:
        save('campaign', 'discovery.interrupted', {'type': type(exc).__name__, 'message': str(exc), 'terminal_solvers': len(rows)})
        raise
    finally:
        for memory in memories:
            memory.close()
        for container in containers:
            result = remote('stop', {'container': container}, timeout=45)
            save('campaign', 'discovery.container_stopped', {'container': container, 'result': result})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest-evidence', type=Path, required=True)
    parser.add_argument('--resource-only', action='store_true')
    parser.add_argument('--qualified-resource', type=Path)
    parser.add_argument('--qualification-evidence', type=Path)
    args = parser.parse_args()
    if args.qualified_resource:
        if args.resource_only or not args.qualification_evidence:
            raise ValueError('solver mode requires explicit real-host qualification and separate resource proof')
        return solve(args)
    if not args.resource_only:
        raise ValueError('select resource-only or supply retained qualification proofs')
    if args.root.exists():
        raise ValueError('new campaign root required')
    args.root.mkdir(parents=True, mode=0o700)
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    from atmem.core import keys
    keys.DEFAULT_KEY_PATH = args.root / 'home/identity/keys/db.key'
    click.installed_matches(click.WHEEL, click.WHEEL_SHA)
    vault, principal = evidence(args.root)
    def save(run, kind, payload):
        vault.capture(run_id=run, kind=kind, payload=payload, principal=principal)
    upstream, access = evidence(args.manifest_evidence)
    saved = upstream.inspect(access, 'verified-manifest')
    chunks = [e['envelope']['payload'] for e in saved if e['envelope']['event_type'] == 'discovery.evaluator_parquet_chunk']
    chunks.sort(key=lambda c: c['index'])
    raw = b''.join(base64.b64decode(c['data_base64'], validate=True) for c in chunks)
    manifest = next(e['envelope']['payload'] for e in saved if e['envelope']['event_type'] == 'discovery.verified_manifest')
    if sha256(raw).hexdigest() != manifest['parquet_sha256']:
        raise ValueError('evaluator parquet identity mismatch')
    import pyarrow.parquet as pq
    table = pq.read_table(io.BytesIO(raw))
    task = next(row for row in table.to_pylist() if row['instance_id'] == PILOT)
    if next(row for row in manifest['rows'] if row['instance_id'] == PILOT)['partition'] != 'qualification':
        raise ValueError('only the predeclared qualification task is permitted')
    save('campaign', 'discovery.verified_pilot_frozen', {'instance_id': PILOT,
        'manifest_revision': manifest['revision'], 'parquet_sha256': manifest['parquet_sha256'],
        'task_evaluator_only': task, 'worker_source': worker_source(), 'resource_only': args.resource_only,
        'rental_cap_usd': 6, 'rentals_started': 0, 'full_target_cells': 4500,
        'classification': 'single_qualification_task_not_confirmation_or_full_score'})
    print(json.dumps({'state': 'image_qualification_started', 'instance_id': PILOT}), flush=True)
    tick = time.monotonic()
    image = remote('image', {'task': task})
    save('campaign', 'discovery.verified_image', {'image': image, 'elapsed_ms': int((time.monotonic()-tick)*1000)})
    controls = []
    for label, patch in [('base', ''), ('reference', task['patch'])]:
        print(json.dumps({'state': 'grader_control_started', 'control': label}), flush=True)
        result = remote('grade', {'task': task, 'image_id': image['Id'], 'patch': patch})
        save('campaign', 'discovery.verified_control', {'control': label, 'result': result})
        public = {k: result[k] for k in ('valid', 'resolution', 'elapsed_s', 'timed_out') if k in result}
        controls.append({'control': label, **public})
        print(json.dumps({'state': 'grader_control_completed', 'control': label, **public}), flush=True)
        if not result.get('valid') or (label == 'base' and result['resolution'] == 'RESOLVED_FULL') or (label == 'reference' and result['resolution'] != 'RESOLVED_FULL'):
            raise RuntimeError('official base/reference grader control failed; no solver dispatch')
    save('campaign', 'discovery.verified_resource_qualified', {'controls': controls, 'image': image,
        'solver_dispatches': 0, 'rental_spend_usd': 0, 'next': 'freeze a separate actual-consultation solver matrix before model dispatch'})
    print(json.dumps({'state': 'resource_qualified', 'controls': controls, 'solver_dispatches': 0, 'rental_spend_usd': 0}), flush=True)


if __name__ == '__main__':
    main()
