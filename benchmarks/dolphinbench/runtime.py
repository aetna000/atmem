"""Stage installed Hermes dependencies externally and invoke its ordinary CLI.

Only dependency/runtime metadata is copied from the user's installation. No
personal config, memories, OAuth state, profiles or provider keys are copied.
"""
import hashlib
import base64
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess

from .gateway import save_new
from .sandbox import policy, run


class NativeRuntime:
    def __init__(self, root, *, source, python, dependency_facts):
        self.root = Path(root).resolve()
        self.source = Path(source).resolve()
        self.python = Path(python).resolve()
        self.dependency_facts = Path(dependency_facts).resolve()
        self.install_key = hashlib.sha256(str(self.source).encode()).hexdigest()[:16]

    def verify_native_dependencies(self):
        """Reject corrupt staged binaries before a model request is possible."""
        facts = json.loads((self.root / 'installs' / self.install_key / 'facts.json').read_text())
        environment = Path(facts['packages']['venv']['environment'])
        sites = list((environment / 'lib').glob('python*/site-packages'))
        if len(sites) != 1:
            raise ValueError('Cannot unambiguously locate the staged dependency inventory')
        result = {}
        for record in sites[0].glob('*.dist-info/RECORD'):
            with record.open() as source:
                for relative, expected, _size in csv.reader(source):
                    if not relative.endswith('.so') or not expected.startswith('sha256='):
                        continue
                    path = (sites[0] / relative).resolve()
                    path.relative_to(sites[0].resolve())
                    digest = hashlib.sha256(path.read_bytes()).digest()
                    if base64.urlsafe_b64encode(digest).decode().rstrip('=') != expected[7:]:
                        raise RuntimeError('Staged native dependency differs from its wheel RECORD; refusing inference')
                    result[relative] = digest.hex()
        if not result:
            raise ValueError('Native dependency integrity inventory is empty')
        return result

    def stage(self):
        marker = self.root / 'runtime-identity.json'
        source_revision = subprocess.check_output(['git', '-C', str(self.source), 'rev-parse', 'HEAD'], text=True).strip()
        facts = json.loads(self.dependency_facts.read_text())
        original = Path(facts['packages']['venv']['environment']).parent
        identity = {'hermes_source': str(self.source), 'hermes_commit': source_revision,
                    'dependency_facts_sha256': hashlib.sha256(self.dependency_facts.read_bytes()).hexdigest(),
                    'python': str(self.python)}
        if marker.exists():
            if json.loads(marker.read_text()) != identity:
                raise ValueError('Hermes runtime identity changed; cannot resume')
            return identity
        state = self.root / 'installs' / self.install_key
        generation = state / 'environments' / original.name
        if generation.exists():
            raise ValueError('Interrupted runtime staging requires inspection')
        generation.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(original, generation, symlinks=True)
        facts['packages']['venv']['environment'] = str(generation / 'venv')
        facts['packages']['venv']['resolved_lock'] = str(generation / 'workspace' / 'uv.lock')
        save_new(state / 'facts.json', facts)
        original_inputs = self.dependency_facts.parent / 'inputs'
        if original_inputs.is_dir():
            shutil.copytree(original_inputs, state / 'inputs', symlinks=False)
        (generation / '.leases').mkdir(exist_ok=True)
        (self.root / 'profiles').mkdir(exist_ok=True)
        (self.root / 'scratch').mkdir(exist_ok=True)
        save_new(marker, identity)
        return identity

    def command(self, arguments):
        # The installed launcher performs this same source/bootstrap/main sequence.
        # No agent loop, model selection, prompt or tool execution is implemented here.
        script = ("import sys;sys.dont_write_bytecode=True;"
                  "sys.path.insert(0,sys.argv.pop(1));import hermes_bootstrap;"
                  "import os,runpy;observer=os.environ.get('ATMEM_BENCH_OBSERVER');"
                  "observer and runpy.run_path(observer,run_name='atmem_benchmark_observer');"
                  "from hermes_cli.main import main;sys.argv[0]='hermes';raise SystemExit(main())")
        return [str(self.python), '-I', '-c', script, str(self.source), *arguments]

    def invoke(self, profile_name, arguments, *, ports=(), sockets=(), environment=None, timeout=300):
        home = self.root / 'profiles' / profile_name
        if not home.is_dir():
            raise ValueError('Agent profile must be staged before invocation')
        facts = json.loads((self.root / 'installs' / self.install_key / 'facts.json').read_text())
        generation = Path(facts['packages']['venv']['environment']).parent
        scratch = home / 'cache' / 'scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        work = home / 'workspace'
        work.mkdir(exist_ok=True)
        writable = [home, generation / '.leases', self.root / 'scratch']
        # PM's lock file is the only shared mutable control file the agent needs.
        lock = self.root / 'installs' / self.install_key / '.install.lock'
        lock.touch(exist_ok=True)
        boundary = policy(readable=[self.source, self.python.parent.parent,
                                    self.root / 'installs', self.root / 'observers'], writable=writable,
                          ports=ports, sockets=sockets)
        boundary += '(allow file-read* (literal ' + json.dumps(str(self.root / 'profiles')) + '))\n'
        boundary += '(allow file-read* file-write* (literal ' + json.dumps(str(lock)) + '))\n'
        for name in ('.env', 'auth.json', 'credentials.json', '.git'):
            boundary += '(deny file-read* (subpath ' + json.dumps(str(self.source / name)) + '))\n'
        env = {'PATH': str(generation / 'venv' / 'bin') + ':/usr/bin:/bin:/usr/sbin:/sbin',
               'HOME': str(home / 'home'), 'HERMES_HOME': str(self.root),
               'TMPDIR': str(scratch), 'PYTHONDONTWRITEBYTECODE': '1',
               'HERMES_ENABLE_PROJECT_PLUGINS': '0', 'HERMES_MAX_TOKENS': '4096',
               'HERMES_EXIT_WATCHDOG_S': '30', 'LANG': 'en_US.UTF-8',
               **(environment or {})}
        return run(self.command(['-p', profile_name, *arguments]), profile=boundary,
                   environment=env, cwd=work, timeout=timeout)
