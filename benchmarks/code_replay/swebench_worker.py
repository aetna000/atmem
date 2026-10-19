"""Trusted WSL controller. Never exposed as a model-selectable Python tool.

Programs execute only inside fresh named, offline Docker containers. Evaluator
material is supplied only to separate grading containers, never solver ones.
"""
import base64
from hashlib import sha256
import io
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import time
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path('/home/user/atmem-swebench-20261019')
LABEL = 'atmem.benchmark=swebench-lite-20261019'
PREFIX = 'atmem-swe-lite-'


def resolution_value(value):
    value = getattr(value, 'value', value)
    if value not in {'RESOLVED_NO', 'RESOLVED_PARTIAL', 'RESOLVED_FULL'}:
        raise ValueError('unknown upstream resolution')
    return value


def materialize_source(raw, source):
    """Preserve tracked repository links, without following them during writes."""
    with tarfile.open(fileobj=io.BytesIO(raw)) as stream:
        for member in stream.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or member.islnk():
                raise ValueError('regular bounded source archive required')
            target = source / member.name
            if any(p.is_symlink() for p in target.parents if p != source.parent):
                raise ValueError('archive cannot write through a source symlink')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym():
                link = PurePosixPath(member.linkname)
                normalized = posixpath.normpath(str(path.parent / link))
                if link.is_absolute() or normalized == '..' or normalized.startswith('../'):
                    raise ValueError('source symlink escapes repository')
                target.symlink_to(member.linkname)
                continue
            if not member.isfile() or member.size > 8_000_000:
                raise ValueError('unsupported source member')
            target.write_bytes(stream.extractfile(member).read())


def run(argv, *, data=None, timeout=120, check=True):
    result = subprocess.run(argv, input=data, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(json.dumps({'command': argv[:5], 'exit': result.returncode,
                                      'stderr': result.stderr.decode(errors='replace')[-3000:]}))
    return result


def guard():
    if min(shutil.disk_usage('/mnt/c').free, shutil.disk_usage('/').free) < 48 * 1024 ** 3:
        raise RuntimeError('backing_disk_below_48GiB; no owner files or images deleted')


def image(task):
    guard()
    tag = task['image']
    if not re.fullmatch(r'swebench/sweb\.eval\.x86_64\.[a-z0-9_.-]+:latest', tag):
        raise ValueError('upstream instance image required')
    found = run(['docker', 'image', 'inspect', tag], check=False)
    if found.returncode:
        run(['docker', 'pull', '--platform', 'linux/amd64', tag], timeout=360)
        found = run(['docker', 'image', 'inspect', tag])
    guard()
    inspected = json.loads(found.stdout)[0]
    if inspected['Architecture'] != 'amd64':
        raise ValueError('x86_64 executor required')
    return {k: inspected[k] for k in ('Id', 'RepoDigests', 'Architecture', 'Size')}


def name():
    return PREFIX + uuid4().hex


def checked_name(value):
    if not re.fullmatch(PREFIX + '[a-f0-9]{32}', value):
        raise ValueError('owned exact container name required')
    inspected = json.loads(run(['docker', 'inspect', value]).stdout)[0]
    if inspected['Config']['Labels'].get('atmem.benchmark') != 'swebench-lite-20261019':
        raise PermissionError('container ownership label differs')
    return value


def start(image_id):
    if not re.fullmatch('sha256:[a-f0-9]{64}', image_id):
        raise ValueError('immutable local image identity required')
    guard()
    container = name()
    run(['docker', 'run', '-d', '--name', container, '--label', LABEL, '--network', 'none',
         '--security-opt', 'no-new-privileges', '--memory', '6g',
         '--cpus', '4', '--pids-limit', '512', '--entrypoint', '/bin/sleep', image_id, 'infinity'])
    return container


def stop(container):
    checked_name(container)
    run(['docker', 'rm', '-f', container], timeout=30)


def execute(container, argv, *, data=None, user='root', timeout=120):
    checked_name(container)
    return run(['docker', 'exec', '-i', '--user', user, '-w', '/testbed', container, *argv],
               data=data, timeout=timeout, check=False)


def reset(container, base):
    if not re.fullmatch('[0-9a-f]{40}', base):
        raise ValueError('exact upstream base required')
    # Upstream images contain prepared runtime/configuration changes. The
    # official evaluator DOES NOT reset/clean them away. Verify the image's
    # original revision and keep that identical prepared state in both arms.
    result = execute(container, ['git', '-c', 'safe.directory=/testbed', 'rev-parse', 'HEAD'])
    if result.returncode:
        raise RuntimeError('prepared upstream image base does not match selected revision')
    head = result.stdout.decode().strip()
    if head != base:
        # Official task images commit their setup changes as one SWE-bench
        # commit on top of the selected repository base. It is not a future
        # issue solution. Bind both revisions and preserve its exact changes.
        parent = execute(container, ['git', '-c', 'safe.directory=/testbed', 'rev-parse', 'HEAD^'])
        if parent.returncode or parent.stdout.decode().strip() != base:
            raise RuntimeError('prepared upstream image base does not match selected revision')
    delta = execute(container, ['git', '-c', 'safe.directory=/testbed', '-c', 'core.fileMode=false', 'diff', '--binary', base])
    if delta.returncode or len(delta.stdout) > 4_000_000:
        raise RuntimeError('prepared image setup delta cannot be bound')
    return {'base_commit': base, 'prepared_head': head,
            'setup_delta_base64': base64.b64encode(delta.stdout).decode()}


def grade(task, image_id, patch):
    """Run the upstream eval script and its unmodified official grading code."""
    container = start(image_id)
    try:
        prepared = reset(container, task['base_commit'])
        if patch.strip():
            applied = execute(container, ['git', 'apply', '--whitespace=nowarn', '-'], data=patch.encode())
            if applied.returncode:
                return {'valid': False, 'reason': 'patch_did_not_apply',
                        'stderr': applied.stderr.decode(errors='replace')}
        script = task['eval_script']
        # The script embeds upstream hidden tests. Only the separate evaluator
        # container ever receives these bytes.
        # Match upstream run_instance: materialize /eval.sh, then use its own
        # ordered, multiplexed Docker stream reader. Feeding bash via stdin and
        # concatenating stderr afterward changes markers/pytest log semantics.
        import docker
        from swebench.harness.docker_utils import exec_run_with_timeout
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as tar:
            data = script.encode()
            member = tarfile.TarInfo('eval.sh'); member.size = len(data); member.mode = 0o700
            tar.addfile(member, io.BytesIO(data))
        client = docker.from_env()
        target = client.containers.get(container)
        if not target.put_archive('/', stream.getvalue()):
            raise RuntimeError('upstream eval script staging failed')
        text, timed_out, elapsed = exec_run_with_timeout(target, '/bin/bash /eval.sh', 180)
        raw = text.encode()
        from swebench.harness.grading import get_logs_eval, get_eval_tests_report, get_resolution_status, _resolve_case
        from swebench.harness.constants import EvalType
        import tempfile
        with tempfile.NamedTemporaryFile(dir='/dev/shm') as log:
            log.write(raw); log.flush()
            spec = SimpleNamespace(log_parser=task['log_parser'], repo=task['repo'],
                                   version=task['version'], instance_id=task['instance_id'])
            statuses, found = get_logs_eval(spec, log.name)
        expected = {key: (json.loads(task[key]) if isinstance(task[key], str) else task[key])
                    for key in ('FAIL_TO_PASS', 'PASS_TO_PASS')}
        report = get_eval_tests_report(statuses, expected, eval_type=EvalType.PASS_AND_FAIL)
        return {'valid': bool(found) and not timed_out, 'resolution': resolution_value(get_resolution_status(report)),
                'report': report, 'elapsed_s': elapsed, 'timed_out': timed_out,
                'prepared_runtime': prepared,
                'log_encoding': 'upstream UTF-8 decoded with replacement',
                'log_base64': base64.b64encode(raw).decode(),
                'observed_f2p_failures': sum(statuses.get(_resolve_case(k, statuses)) in ('FAILED', 'ERROR')
                                             for k in expected['FAIL_TO_PASS'])}
    finally:
        stop(container)


def solver(task, image_id):
    container = start(image_id)
    try:
        prepared = reset(container, task['base_commit'])
        # Replace full upstream history by an identical single-commit source
        # snapshot. Future/target Git objects are not accessible to the solver.
        result = execute(container, ['/bin/bash', '-c',
            'git ls-files -z > /tmp/benchmark-tracked-paths && '
            'rm -rf /testbed/.git && git init -q && '
            'git add -f --pathspec-from-file=/tmp/benchmark-tracked-paths --pathspec-file-nul && '
            'git -c user.name=Benchmark -c user.email=benchmark@localhost commit -qm baseline && '
            'chmod -R a+rX /testbed && chmod -R a+rw /testbed && chmod -R a-w /testbed/.git && '
            'mkdir -p /tmp/solver-home && chmod 777 /tmp/solver-home'])
        if result.returncode:
            raise RuntimeError('single-commit source stage failed: ' + result.stderr.decode(errors='replace'))
        # Runtime variables only; no credentials or evaluator material.
        result = execute(container, ['/bin/bash', '-c',
            'find / -maxdepth 2 -type f \\( -name "gold.patch" -o -name "test.patch" '
            '-o -name "eval.sh" -o -name "problem_statement.txt" \\) 2>/dev/null'], user='1000:1000')
        if result.stdout.strip():
            raise RuntimeError('evaluator-like image artifacts accessible; source barrier not qualified')
        archive = execute(container, ['git', '-c', 'safe.directory=/testbed', 'archive', 'HEAD'])
        if archive.returncode or len(archive.stdout) > 100_000_000:
            raise RuntimeError('bounded base archive required')
        source = ROOT / 'sources' / container
        source.mkdir(parents=True, exist_ok=False)
        materialize_source(archive.stdout, source)
        for command in (['git', 'init', '-q', str(source)], ['git', '-C', str(source), 'add', '.'],
            ['git', '-C', str(source), '-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@localhost',
             'commit', '-qm', 'baseline']):
            run(command)
        head = execute(container, ['git', '-c', 'safe.directory=/testbed', 'rev-parse', 'HEAD'])
        tree = execute(container, ['git', '-c', 'safe.directory=/testbed', 'rev-parse', 'HEAD^{tree}'])
        return {'container': container, 'source': str(source), 'baseline_head': head.stdout.decode().strip(),
                'source_tree': tree.stdout.decode().strip(),
                'prepared_runtime': prepared,
                'source_archive_sha256': sha256(archive.stdout).hexdigest()}
    except BaseException:
        stop(container)
        raise


def command(container, value):
    if not isinstance(value, str) or not 1 <= len(value) <= 20000:
        raise ValueError('bounded shell command required')
    tick = time.monotonic()
    result = execute(container, ['/usr/bin/timeout', '--signal=KILL', '40', '/bin/bash', '-c',
        'export HOME=/tmp/solver-home; export PYTHONDONTWRITEBYTECODE=1; '
        'export PATH=/opt/miniconda3/envs/testbed/bin:/usr/local/bin:/usr/bin:/bin; '
        'export GIT_CONFIG_COUNT=1; export GIT_CONFIG_KEY_0=safe.directory; '
        'export GIT_CONFIG_VALUE_0=/testbed; cd /testbed; ' + value], user='1000:1000', timeout=50)
    raw = result.stdout + result.stderr
    return {'exit_code': result.returncode, 'elapsed_s': time.monotonic() - tick,
            'output': raw[:24000].decode(errors='replace'), 'output_truncated': len(raw) > 24000}


def dispatch(action, payload):
    if action == 'cognee_graph':
        namespace = {'__name__': 'trusted_cognee_provider'}
        exec(compile(payload['provider_source'], '<frozen-cognee-provider>', 'exec'), namespace)
        return namespace['prepare'](payload, payload['cognee_runtime'], payload['image_id'])
    if action == 'image':
        return image(payload['task'])
    if action == 'grade':
        return grade(payload['task'], payload['image_id'], payload['patch'])
    if action == 'solver':
        return solver(payload['task'], payload['image_id'])
    if action == 'command':
        return command(payload['container'], payload['command'])
    if action == 'patch':
        head = execute(payload['container'], ['git', '-c', 'safe.directory=/testbed', 'rev-parse', 'HEAD'])
        result = execute(payload['container'], ['git', '-c', 'safe.directory=/testbed', 'diff', '--no-ext-diff', '--no-textconv', '--binary', 'HEAD'])
        extra = execute(payload['container'], ['git', '-c', 'safe.directory=/testbed', 'ls-files', '--others', '--exclude-standard'])
        names = execute(payload['container'], ['git', '-c', 'safe.directory=/testbed', 'diff', '--name-only', '-z', 'HEAD'])
        return {'patch': result.stdout.decode(), 'untracked': extra.stdout.decode().splitlines(),
                'changed_paths': [p for p in names.stdout.decode().split('\0') if p],
                'head': head.stdout.decode().strip(), 'exit_code': result.returncode}
    if action == 'stop':
        stop(payload['container']); return {'stopped': True}
    if action == 'graph':
        # Source is a single-commit copy of the same initial public tree. The
        # graph is withheld by the tool boundary once solver source diverges.
        source = Path(payload['source'])
        if source.parent != ROOT / 'sources' or not source.is_dir():
            raise ValueError('owned staged source required')
        runtime = payload.get('product_runtime')
        if runtime:
            import atmem
            import sys
            import zipfile
            wheel_path = Path(runtime['wheel_path'])
            if (not wheel_path.is_relative_to(ROOT) or sha256(wheel_path.read_bytes()).hexdigest() != runtime['wheel_sha256']
                    or sys.executable != runtime['python']):
                raise ValueError('pinned installed product runtime mismatch')
            package = Path(atmem.__file__).parent
            if not package.is_relative_to(Path(sys.executable).parent.parent):
                raise ValueError('product must be installed in the pinned isolated runtime')
            with zipfile.ZipFile(wheel_path) as archive:
                for member in archive.namelist():
                    if member.startswith('atmem/') and not member.endswith('/'):
                        if package.joinpath(*PurePosixPath(member).parts[1:]).read_bytes() != archive.read(member):
                            raise ValueError('installed product differs from pinned wheel')
        state = ROOT / 'memory' / source.name
        state.mkdir(parents=True, exist_ok=False)
        os.environ['ATMEM_HOME'] = str(state / 'home')
        from atmem.service.household import HouseholdApplication
        from atmem.memory import Memory
        from atmem.code.identity import CodeIdentity
        from atmem.code.application import CodeApplication
        from atmem.code.knowledge_setup import configure, mcp_configuration
        db = state / 'memory.db'
        HouseholdApplication.initialize(db, encrypted=True)
        memory = Memory(db, auto_vectors=False)
        try:
            scope = CodeIdentity(memory.store).resolve(source, subject_id='swebench-pilot',
                profile_id='shared', agent_id='claude')
            app = CodeApplication(memory, subject_id=scope.subject_id)
            app.settings(scope.project_id, {'graph_enabled': True})
            image_id = runtime['worker_image_id'] if runtime else 'sha256:62e15650d96e24eb4c5adce548ee711425e4a91f1a87ab9f9a8772a78ed724f3'
            configure(app, scope, str(source), image_id=image_id)
            tick = time.monotonic()
            graph = app.dispatch('knowledge-index', {'project_id': scope.project_id,
                'root': str(source), 'agent': scope.agent_id})
            config = mcp_configuration(app, scope, str(source), tool_profile=payload.get('tool_profile', 'expanded'))
            server = config['configuration']['mcpServers']['atmem_code']
            return {'index_seconds': time.monotonic() - tick, 'graph': graph,
                    'server': server, 'home': str(state / 'home'), 'db': str(db)}
        finally:
            memory.close()
    raise ValueError('unrecognized trusted controller action')
