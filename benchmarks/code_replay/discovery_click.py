"""Spec 044 real subscription diagnostic; no credential reads/copies or rental.

Invoke from the installed product environment with repository benchmark helpers.
All solvers use the same two tools and an offline confined source-command tool.
This is controlled discovery, not an unmodified native CLI comparison.
"""
import argparse
import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.claude_click_tools import shell
from benchmarks.code_replay.cognee_click import worker_environment
from benchmarks.code_replay.control import prompt_for
from benchmarks.code_replay.discovery_metrics import events, usage, summarize_tools
from benchmarks.code_replay.frozen import digest_files, grader_tree, solution_tree
from benchmarks.code_replay.grade import tree_files, write_new_tree, grade_files
from benchmarks.code_replay.pilot import stage_workspace, collect_patch, summary_counts, installed_matches
from benchmarks.code_replay.sandbox import permission_arguments

REPO = Path(__file__).resolve().parents[2]
PACKAGE = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/efficiency-p11c1-frozen.json')
CHECKOUT = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/upstream/click')
PYTHON = Path('/private/tmp/atmem-discovery-044-installed-20261020/bin/python')
COGNEE = Path('/private/tmp/atmem-click-cognee-upstream-20261018/bin/python')
WHEEL = Path('/private/tmp/atmem-discovery-044-wheel-final-20261020/atmem-2.3.8-py3-none-any.whl')
WHEEL_SHA = '77a67773e33adcfe2c8a60d5a1da29326f0bc2dfe27663fc5f14297d0e272d92'
COGNEE_REVISION = 'f154b32a9e544dac73e7ddf2010327cf9988edcd'
MODELS = {'claude': 'claude-opus-5-5', 'codex': 'gpt-6-luna', 'copilot': 'gpt-5.4'}


@dataclass(frozen=True)
class Session:
    root: Path
    workspace: Path


def environment():
    # Native hosts find their existing sign-in themselves. No copied OAuth,
    # environment API key, endpoint override, config override or token scraping.
    return {k: v for k, v in os.environ.items() if k in {
        'HOME', 'PATH', 'TMPDIR', 'LANG', 'SHELL', 'USER', 'LOGNAME', '__CF_USER_TEXT_ENCODING'}}


def source_environment(workspace, binaries):
    # Keep the launcher's denied :tmpdir outside the permitted workspace.
    # shell() exports the actual workspace-local scratch TMPDIR INSIDE the
    # confined child; passing it to the launcher would deny our scratch too.
    return {'PATH': str(binaries) + ':/usr/bin:/bin', 'HOME': str(workspace / '.solver-tmp'),
        'LANG': 'en_US.UTF-8', 'TMPDIR': '/tmp',
        'PYTHONPATH': str(workspace / 'src') + ':' + str(workspace / '.solver-metadata'),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}


def bootstrap(module):
    # Import the installed AtMem FIRST, then expose benchmark-only helpers.
    return 'import atmem,sys;sys.path.insert(0,' + repr(str(REPO)) + ');from ' + module + ' import main;main()'


def bounded(command, *, cwd, env, timeout=240):
    p = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    selector = selectors.DefaultSelector()
    for stream, name in ((p.stdout, 'stdout'), (p.stderr, 'stderr')):
        selector.register(stream, selectors.EVENT_READ, name)
    captured = {'stdout': bytearray(), 'stderr': bytearray()}
    started = time.monotonic()
    stop, killed = None, None
    try:
        while selector.get_map():
            if time.monotonic() - started > timeout:
                stop = 'wall_cap'
            if sum(map(len, captured.values())) > 8_000_000:
                stop = 'output_cap'
            if stop and killed is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                killed = time.monotonic()
            if killed is not None and time.monotonic() - killed > 2:
                break
            for key, _ in selector.select(.2):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    captured[key.data].extend(chunk)
        p.wait(timeout=5)
        return {'exit_code': p.returncode, 'stop': stop,
            'elapsed_ms': int((time.monotonic() - started) * 1000),
            **{k: bytes(v) for k, v in captured.items()}}
    finally:
        selector.close()
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(timeout=5)


def command_for(host, config, prompt):
    source = 'import atmem,sys;sys.path.insert(0,' + repr(str(REPO)) + ');from benchmarks.code_replay.discovery_study import serve;import json;serve(json.loads(sys.argv[1]))'
    server = {'command': str(PYTHON), 'args': ['-I', '-u', '-c', source, json.dumps(config)],
        'env': {'ATMEM_HOME': config['atmem_home'], 'PATH': os.environ['PATH']}}
    env = environment()
    if host == 'claude':
        env.update(CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', CLAUDE_CODE_DISABLE_AUTO_MEMORY='1',
            DISABLE_AUTOUPDATER='1', MAX_THINKING_TOKENS='0')
        command = ['claude', '-p', prompt, '--model', MODELS[host], '--effort', 'medium',
            '--tools', '', '--disable-slash-commands', '--setting-sources', '',
            '--settings', json.dumps({'disableAllHooks': True, 'autoMemoryEnabled': False, 'claudeMdExcludes': ['**']}),
            '--strict-mcp-config', '--mcp-config', json.dumps({'mcpServers': {'benchmark': server}}),
            '--allowedTools', 'mcp__benchmark__*', '--permission-mode', 'dontAsk', '--no-session-persistence',
            '--output-format', 'stream-json', '--verbose', '--max-turns', '30']
    elif host == 'codex':
        # These installed native flags preserve managed sign-in but skip owner
        # tools/instructions. Every real source command uses the shared sandbox.
        packet = {'command': server['command'], 'args': server['args'], 'env': server['env'],
            'enabled_tools': ['repository_discover', 'workspace_command'], 'required': True,
            'startup_timeout_sec': 60, 'tool_timeout_sec': 45, 'default_tools_approval_mode': 'approve'}
        toml = ','.join(k + '=' + (json.dumps(v) if not isinstance(v, dict) else
            '{' + ','.join(a + '=' + json.dumps(b) for a, b in v.items()) + '}') for k, v in packet.items())
        command = ['codex', 'exec', '--ignore-user-config', '--ignore-rules', '--strict-config', '--ephemeral',
            '--json', '-m', MODELS[host], '--skip-git-repo-check', '-c', 'model_reasoning_effort="low"',
            '-c', 'web_search="disabled"', '-c', 'features.shell_tool=false', '-c', 'features.apply_patch_freeform=false',
            '-c', 'mcp_servers.benchmark={' + toml + '}', prompt]
    elif host == 'copilot':
        server.update(type='local', tools=['*'])
        command = ['copilot', '-p', prompt, '--model', MODELS[host], '--reasoning-effort', 'low',
            '--additional-mcp-config', json.dumps({'mcpServers': {'benchmark': server}}),
            '--available-tools', 'benchmark', '--allow-tool', 'benchmark', '--disable-builtin-mcps',
            '--no-auto-update', '--no-custom-instructions', '--no-ask-user', '--no-remote', '--no-remote-export',
            '--max-ai-credits', '30', '--output-format', 'json', '--silent']
    else:
        raise ValueError('unqualified scoring host')
    return command, env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--hosts', nargs='+', choices=tuple(MODELS), default=list(MODELS))
    parser.add_argument('--backends', nargs='+', choices=('native', 'cognee', 'atmem'), default=['native', 'cognee', 'atmem'])
    parser.add_argument('--tasks', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--qualification-only', action='store_true')
    parser.add_argument('--qualification-evidence', type=Path)
    parser.add_argument('--consultation', choices=('optional', 'requested'), default='optional')
    args = parser.parse_args()
    if not args.qualification_only:
        if args.qualification_evidence is None or not (args.qualification_evidence / 'vault').is_dir():
            raise ValueError('retained real-host qualification required before scored dispatch')
        qscope = EvidenceScope('benchmark', 'local-operator', 'discovery-044')
        qprincipal = EvidencePrincipal('discovery-044-operator', EvidenceRole.ADMINISTRATOR, qscope)
        qvault = ReplayEvidence(args.qualification_evidence / 'vault', vault_id='discovery-044', scope=qscope)
        terminals = [e['envelope']['payload'] for e in qvault.inspect(qprincipal, 'campaign')
            if e['envelope']['event_type'] == 'discovery.completed']
        qualified = {row['host'] for t in terminals if t.get('qualification_only')
            for row in t['rows'] if row.get('qualified') is True}
        if not set(args.hosts) <= qualified:
            raise ValueError('a requested host has no passing real subscription/tool/usage qualification')
    if args.root.exists():
        raise ValueError('new run root required; never overwrite or retry a scored cell')
    args.root.mkdir(mode=0o700, parents=True)
    os.environ['ATMEM_HOME'] = str(args.root / 'atmem-home')
    from atmem.core import keys
    keys.DEFAULT_KEY_PATH = args.root / 'atmem-home/identity/keys/db.key'
    installed_matches(WHEEL, WHEEL_SHA)
    scope = EvidenceScope('benchmark', 'local-operator', 'discovery-044')
    principal = EvidencePrincipal('discovery-044-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.root / 'vault', vault_id='discovery-044', scope=scope)
    def save(run, kind, payload):
        vault.capture(run_id=run, kind=kind, payload=payload, principal=principal)
    package = json.loads(PACKAGE.read_bytes())
    python = Path(package['environment']['python'])
    interpreter = Path(package['environment']['interpreter'])
    cognee_source = (REPO / 'benchmarks/code_replay/cognee_click.py').read_text()
    cognee_boot = 'import sys;sys.argv=["worker",*sys.argv[1:]];exec(compile(' + repr(cognee_source) + ',"<upstream-cognee-transport>","exec"))'
    cases, memories, blocked = [], [], {}
    try:
        tasks = package['tasks'][:args.tasks]
        save('campaign', 'discovery.preparation', {'tasks': tasks, 'host_models': MODELS,
            'rental_cap_usd': 6, 'rentals_started': 0, 'protocol': 'controlled_optional_navigation_v1',
            'source_code': {name: (REPO / name).read_text() for name in (
                'benchmarks/code_replay/discovery_study.py', 'benchmarks/code_replay/discovery_metrics.py',
                'benchmarks/code_replay/discovery_click.py')}, 'wheel_sha256': WHEEL_SHA})
        for task in tasks:
            original = tree_files(CHECKOUT, task['parent_commit'])
            grader = grader_tree(CHECKOUT, task)
            if digest_files(original) != task['manifest']['source_sha256'] or digest_files(grader) != task['manifest']['grader_sha256']:
                raise ValueError('historical task manifest differs')
            for h, host in enumerate(args.hosts):
                order = args.backends
                offset = (tasks.index(task) + h) % len(order)
                for backend in order[offset:] + order[:offset]:
                    run = task['short'] + '-' + host + '-' + backend
                    root = args.root / run
                    root.mkdir()
                    workspace = root / 'atmem-click-source'
                    print(json.dumps({'run': run, 'state': 'preparing'}), flush=True)
                    tick = time.monotonic()
                    stage_workspace(Session(root, workspace), workspace, original, python)
                    binaries = workspace / '.solver-tmp/bin'
                    binaries.mkdir()
                    native_git = subprocess.check_output(['/usr/bin/xcrun', '--find', 'git'], text=True).strip()
                    shutil.copy2(native_git, binaries / 'git')
                    shutil.copy2(shutil.which('rg'), binaries / 'rg')
                    env = source_environment(workspace, binaries)
                    config = {'backend': backend, 'workspace': str(workspace), 'codex': shutil.which('codex'),
                        'permissions': permission_arguments((python.parent.parent, interpreter)),
                        'shell_environment': env, 'source_files': {n: sha256(b).hexdigest() for n, b in original.items()},
                        'evidence': str(args.root / 'vault'), 'run_id': run,
                        'atmem_home': os.environ['ATMEM_HOME'], 'provider': None}
                    probe = shell(config, str(python) + ' -c ' + __import__('shlex').quote(
                        'import pathlib,socket; assert "from __future__" in pathlib.Path("src/click/core.py").read_text(); '
                        'p=pathlib.Path(".solver-tmp/probe");p.write_text("ok");assert p.read_text()=="ok"; '
                        'paths=' + repr([str(PACKAGE), str(CHECKOUT / '.git/config'), str(args.root / 'vault')]) +
                        ';\nfor p in paths:\n try: open(p,"rb").read(1)\n except (PermissionError,IsADirectoryError): pass\n else: raise RuntimeError("barrier failed")\n'
                        's=socket.socket();\ntry: s.connect(("1.1.1.1",443))\nexcept OSError: print("ISOLATION_OK")\nelse: raise RuntimeError("network permitted")'))
                    save(run, 'discovery.shell_qualified', probe)
                    if probe['exit_code'] or 'ISOLATION_OK' not in probe['output']:
                        raise RuntimeError('offline source barrier qualification failed')
                    index_ms = 0
                    if backend == 'cognee':
                        state = root / 'cognee-state'
                        state.mkdir()
                        provider_env = worker_environment(state, COGNEE)
                        source_root = root / 'index-input'
                        source_root.mkdir()
                        write_new_tree(source_root, original)
                        start = time.monotonic()
                        indexed = subprocess.run([str(COGNEE), '-I', '-u', '-c', cognee_boot, 'index', '--root', str(source_root)],
                            cwd=state, env=provider_env, capture_output=True, timeout=300)
                        index_ms = int((time.monotonic() - start) * 1000)
                        save(run, 'discovery.cognee_index', {'exit_code': indexed.returncode,
                            'stdout': indexed.stdout.decode(errors='replace'), 'stderr': indexed.stderr.decode(errors='replace'),
                            'index_ms': index_ms, 'revision': COGNEE_REVISION})
                        if indexed.returncode or b'get_help_option' not in indexed.stdout:
                            raise RuntimeError('real upstream CODE extraction qualification failed')
                        config['provider'] = {'command': [str(COGNEE), '-I', '-u', '-c', cognee_boot, 'serve'],
                            'cwd': str(state), 'environment': provider_env}
                    elif backend == 'atmem':
                        from atmem.memory import Memory
                        from atmem.service.household import HouseholdApplication
                        from atmem.code.application import CodeApplication
                        from atmem.code.identity import CodeIdentity
                        from atmem.knowledge.projections import CodeKnowledge
                        from atmem.knowledge.worker import ExtractionWorker
                        db = root / 'memory.db'
                        HouseholdApplication.initialize(db, encrypted=True)
                        memory = Memory(db, auto_vectors=False)
                        memories.append(memory)
                        identity = CodeIdentity(memory.store).resolve(workspace, subject_id='benchmark-operator', profile_id='shared', agent_id=host)
                        app = CodeApplication(memory, subject_id=identity.subject_id)
                        app.settings(identity.project_id, {'graph_enabled': True, 'auto_capture': False, 'auto_recall': False})
                        start = time.monotonic()
                        index = CodeKnowledge(app, identity).index(str(workspace), ExtractionWorker(package['image_id']))
                        index_ms = int((time.monotonic() - start) * 1000)
                        save(run, 'discovery.atmem_index', {'index': index, 'index_ms': index_ms, 'scope': identity.to_dict()})
                        config['provider'] = {'command': [str(PYTHON), '-I', '-u', '-m', 'atmem.knowledge.code.mcp',
                            '--db', str(db), '--root', str(workspace), '--subject', identity.subject_id,
                            '--project-id', identity.project_id, '--profile', 'shared', '--agent', host, '--tool-profile', 'navigation'],
                            'cwd': str(root), 'environment': {'PATH': os.environ['PATH'], 'HOME': os.environ['HOME'], 'ATMEM_HOME': config['atmem_home']}}
                    from benchmarks.code_replay.discovery_study import Comparator
                    comparator = Comparator(config)
                    try:
                        request = {'format': 'atmem-repository-discovery-request-v1', 'request_id': 'preflight',
                            'turn_id': 'preflight', 'query': 'get_help_option', 'limit': 5, 'budget': 4096}
                        found = comparator.discover(request)
                        save(run, 'discovery.provider_qualified', {'request': request, 'response': found})
                        if not found['items']:
                            raise RuntimeError('provider has no indexed canary symbol')
                    finally:
                        comparator.close()
                    prompt = prompt_for(task, python,
                        'A ranked, non-exhaustive navigation tool repository_discover is available on demand. '
                        'Use short identifiers or relevant query words when useful to replace repeated exploration. '
                        'It returns locations, not code. Read original source with workspace_command. '
                        'Exact search, edits and tests also use workspace_command. No experience or source pack is supplied. '
                        'Do not call navigation when the implementation is already known. Discovery is optional in every arm.')
                    prompt += '\nYou have 240 seconds and 30 tool calls. Use only the supplied two MCP tools.\n'
                    if args.consultation == 'requested':
                        prompt += ('\nThis separately named controlled consultation condition asks you to begin '
                            'repository navigation with repository_discover, choosing your own task-relevant query. '
                            'Then use workspace_command to verify original source, edit and test. This applies '
                            'identically to all three discovery backends. No command is gated on consultation.\n')
                    command, child_env = command_for(host, config, prompt)
                    cases.append({'run': run, 'host': host, 'backend': backend, 'task': task, 'original': original,
                        'grader': grader, 'workspace': workspace, 'config': config, 'command': command,
                        'environment': child_env, 'index_ms': index_ms, 'setup_ms': int((time.monotonic()-tick)*1000)})
        save('campaign', 'discovery.frozen', {'classification': 'exposed_click_controlled_' + args.consultation + '_discovery_diagnostic',
            'consultation': args.consultation,
            'cases': [{k: str(v) if isinstance(v, Path) else v for k, v in c.items() if k not in {'original', 'grader', 'environment'}} for c in cases],
            'qualification_only': args.qualification_only, 'planned_click_cells': 45, 'frozen_cells': len(cases),
            'qualification_evidence': str(args.qualification_evidence) if args.qualification_evidence else None,
            'upstream_cognee_revision': COGNEE_REVISION, 'experience': False, 'pruning': False,
            'automatic_injection': False, 'credential_copies': False, 'rentals_started': 0})
        rows = []
        for case in cases:
            if case['host'] in blocked:
                save(case['run'], 'discovery.cell_blocked', {'reason': blocked[case['host']]})
                continue
            prompt = case['command']
            if args.qualification_only:
                instruction = ('This is a protocol qualification, not a Click task. Call repository_discover once with '
                    'format=atmem-repository-discovery-request-v1, request_id=probe, turn_id=probe, '
                    'query=get_help_option, limit=3, budget=4096. Then use workspace_command to read the first line of '
                    'src/click/core.py, write the text ok into .solver-tmp/native-probe, and run Python to assert that '
                    'file contains ok. Finally report success. Do not solve or change Click source.')
                prompt, _ = command_for(case['host'], case['config'], instruction)
            save(case['run'], 'discovery.trial_started', {'command': prompt, 'qualification_only': args.qualification_only})
            print(json.dumps({'run': case['run'], 'state': 'solver_started'}), flush=True)
            observed = bounded(prompt, cwd=case['workspace'], env=case['environment'], timeout=120 if args.qualification_only else 240)
            parsed = events(observed['stdout'])
            tokens = usage(case['host'], parsed)
            save(case['run'], 'discovery.attempt', {k: base64.b64encode(v).decode() if isinstance(v, bytes) else v for k,v in observed.items()})
            paths, sources, changes, violations = collect_patch(case['workspace'], case['original'])
            save(case['run'], 'discovery.patch', {'paths': paths, 'source_bytes_base64': changes, 'violations': violations})
            metrics = summarize_tools(vault.inspect(principal, case['run']))
            row = {'run': case['run'], 'host': case['host'], 'backend': case['backend'], 'task': case['task']['short'],
                'usage': tokens, 'solver_ms': observed['elapsed_ms'], 'exit_code': observed['exit_code'],
                'stop': observed['stop'], 'index_ms': case['index_ms'], 'setup_ms': case['setup_ms'], **metrics}
            case.update(observed=observed, sources=sources, violations=violations, row=row)
            if args.qualification_only:
                row['native_probe'] = (case['workspace'] / '.solver-tmp/native-probe').read_text() == 'ok' if (case['workspace'] / '.solver-tmp/native-probe').exists() else False
                row['qualified'] = bool(observed['exit_code'] == 0 and not observed['stop'] and metrics['discovery_calls'] and row['native_probe'] and tokens['complete'])
                if not row['qualified']:
                    blocked[case['host']] = 'live_protocol_or_usage_qualification_failed_no_scored_dispatch'
            rows.append(row)
            save(case['run'], 'discovery.solver_terminal', row)
            print(json.dumps({'state': 'solver_terminal', **row}), flush=True)
        if not args.qualification_only:
            for case in cases:
                if 'row' not in case:
                    continue
                graded = grade_files(solution_tree(case['grader'], case['sources']), python=python,
                    interpreter_root=interpreter, test_paths=('tests/',))
                case['row'].update(functional_pass=graded.exit_code == 0 and not graded.environment_error and not case['violations'],
                    grade=graded.summary(), grade_counts=summary_counts(graded.output))
                save(case['run'], 'discovery.graded', {'row': case['row'], 'output_base64': base64.b64encode(graded.output).decode()})
                print(json.dumps({'state': 'graded', **case['row']}), flush=True)
        save('campaign', 'discovery.completed', {'rows': rows, 'blocked': blocked, 'planned': 45,
            'executed': len(rows), 'qualification_only': args.qualification_only, 'rental_spend_usd': 0})
        print(json.dumps({'state': 'completed', 'rows': rows, 'blocked': blocked, 'rental_spend_usd': 0}), flush=True)
    except BaseException as exc:
        save('campaign', 'discovery.interrupted', {'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        for memory in memories:
            memory.close()


if __name__ == '__main__':
    main()
