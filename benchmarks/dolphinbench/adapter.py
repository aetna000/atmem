"""Private, disclosed AtMem adapter for installed Hermes on macOS.

No custom extraction or retrieval: the installed AtMem memory provider handles
both. The upstream runner controls order, app resets and grading boundaries.
"""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import time

from .app_bridge import bridge, stage_client
from .driver import AtMemHost
from .export import export_interaction
from .gateway import Gateway, save_new
from .recording import BudgetLedger, fingerprint
from .runtime import NativeRuntime


class AtMemAdapter:
    app_python = '/Volumes/AtMemDolphin/venv/bin/python'
    app_native_dependency = Path('/Volumes/AtMemDolphin/venv/lib/python3.12/site-packages/pydantic_core/_pydantic_core.cpython-312-darwin.so')
    app_native_sha256 = 'f80019557d114dbaba3ab7aa53debd7d0d717659eee1a3aad48f760a6f8f8e80'

    def __init__(self, options, work_dir):
        self.options, self.work = options, Path(work_dir)
        self.hosts = {}
        self.runtime = NativeRuntime('/Volumes/AtMemDolphin/runtime-home',
            source='/Users/javadtaghia/.hermes/hermes-agent',
            python='/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3',
            dependency_facts='/Users/javadtaghia/.hermes/installs/7f16443560343fb8/facts.json')
        self.runtime_identity = self.runtime.stage()
        self.observer = self.runtime.root / 'observers/observe_native.py'
        if self.observer.read_bytes() != Path(__file__).with_name('observe_native.py').read_bytes():
            raise ValueError('Native observer differs from the qualified runtime')
        self.campaign_identity = options['campaign_identity']
        self.cap_usd = self.campaign_identity['cap_usd']
        self.ledger = self.work / 'budget.db'

    def identity(self):
        return {'runtime': self.runtime_identity, 'campaign': self.campaign_identity,
                'integration': 'installed AtMem provider; patched product freeze',
                'boundary': 'macOS sandbox-exec, not upstream Docker runner',
                'transport': 'OpenRouter Azure-only, official acceptance unconfirmed',
                'app_pydantic_core_version': '2.50.1',
                'app_pydantic_core_sha256': self.app_native_sha256,
                'adapter_source': {p.name: fingerprint(p.read_text()) for p in Path(__file__).parent.glob('*.py')}}

    def host(self, persona):
        if persona not in self.hosts:
            self.hosts[persona] = AtMemHost(self.work / 'memory', persona)
        return self.hosts[persona]

    def run_interaction(self, request):
        from harness.adapter import InteractionRecord
        from scripts.openrouter_azure_sol import load_key
        if hashlib.sha256(self.app_native_dependency.read_bytes()).hexdigest() != self.app_native_sha256:
            raise RuntimeError('Simulated app dependency integrity changed; refusing new paid work')
        started = time.monotonic()
        directory = self.work / 'native' / request.phase / request.persona / request.interaction_id
        if directory.exists():
            raise ValueError('Native interaction already started; reconcile evidence before replay')
        directory.mkdir(parents=True, mode=0o700)
        profile = 'db-' + fingerprint({'run': str(self.work), 'persona': request.persona,
                                      'phase': request.phase, 'id': request.interaction_id})[:24]
        home = self.runtime.root / 'profiles' / profile
        home.mkdir(mode=0o700)
        host = self.host(request.persona)
        gateway = Gateway(key=load_key(self.options['env_file']), output=directory / 'calls',
            ledger_path=self.ledger, campaign_identity=self.campaign_identity, cap_usd=self.cap_usd,
            phase=request.phase, model='openai/gpt-5.6-luna', input_per_million=1,
            output_per_million=5, required_tool_catalog='mcp__dolphinbench_apps__').start()
        try:
            socket = directory / 'apps.sock'
            # Unix socket paths have a strict OS length bound. Keep the actual
            # socket under the external root, without exposing controller files.
            socket = self.runtime.root / 'scratch' / (profile + '.sock')
            with bridge(request.apps, socket):
                client = home / 'app_client.py'
                stage_client('/Volumes/AtMemDolphin/upstream', client, socket)
                host.configure_profile(home, base_url=gateway.base_url, local_token=gateway.local_token,
                    mcp={'command': str(self.runtime.python), 'args': ['-I', str(client)]})
                witness = home / 'shutdown-witness.jsonl'
                process = self.runtime.invoke(profile,
                    ['chat', '-q', request.dated_message, '-Q', '--yolo', '--format', 'stream-json', '--max-turns', '20'],
                    ports=[gateway.server_port, host.server.server_port], sockets=[socket], timeout=600,
                    environment={'CUSTOM_API_KEY': gateway.local_token,
                        'ATMEM_BENCH_OBSERVER': str(self.observer), 'ATMEM_BENCH_WITNESS': str(witness)})
            save_new(directory / 'process.json', {'exit_code': process.returncode,
                'stdout': process.stdout, 'stderr': process.stderr})
            if process.returncode != 0:
                raise RuntimeError('Native interaction failed; no automatic paid replay')
            shutdown = [json.loads(line) for line in witness.read_text().splitlines()]
            providers = [p for event in shutdown for p in event['providers']]
            if not providers or any(p['name'] != 'atmem' or p['pending_writes'] != 0 or p['write_errors'] != 0 for p in providers):
                raise RuntimeError('Native memory provider did not drain cleanly')
            export = export_interaction(directory / 'calls', home / 'api-witness.jsonl')
            save_new(directory / 'export.json', export)
            for name in ('api-witness.jsonl', 'shutdown-witness.jsonl', 'app_client.provenance.json'):
                shutil.copyfile(home / name, directory / name)
            save_new(directory / 'profile.json', {'profile_name': profile,
                'campaign_root': str(self.work), 'ephemeral': True})
            return InteractionRecord(settings=export['settings'], messages=export['messages'],
                duration_ms=(time.monotonic() - started) * 1000,
                attempts=[{'auxiliary_calls': export['auxiliary_calls']}])
        finally:
            gateway.stop()

    def freeze(self, persona):
        return self.host(persona).freeze()

    def verify_checkpoint(self, persona, checkpoint):
        self.host(persona).verify_checkpoint(checkpoint)

    def total_cost_usd(self, phase):
        book = BudgetLedger(self.ledger, cap_usd=self.cap_usd, identity=self.campaign_identity)
        try:
            totals = book.totals()
            if any(row['reserved_usd'] for row in totals.values()):
                raise ValueError('Unreconciled API cost reservations')
            return totals.get(phase, {}).get('actual_usd', 0)
        finally:
            book.close()

    def stop(self):
        for host in self.hosts.values():
            host.stop()

    def archive(self):
        directory = self.work / 'portable-memory'
        directory.mkdir(exist_ok=True)
        for persona, host in self.hosts.items():
            host.service.flush_evidence()
            receipt = host.portable_export(directory / f'{persona}.jsonl')
            from .driver import private_json
            private_json(directory / f'{persona}.json', receipt)
        script = ('import sys;sys.path.append(' + repr(str(Path(__file__).parents[2])) + ');'
                  'from benchmarks.dolphinbench.archive import main;main()')
        result = subprocess.run(['/private/tmp/atmem-archive-validation-20261020/bin/python', '-I', '-c', script,
            '--root', str(self.work), '--env-file', self.options['env_file']],
            capture_output=True, text=True, timeout=1200)
        if result.returncode:
            raise RuntimeError('Cloud checkpoint failed; staged evidence preserved: ' + result.stderr[-1000:])
        print(result.stdout.strip(), flush=True)
        # Only remove this campaign's generated disposable profiles, after the
        # evidence archive independently round-trips. Persistent AtMem databases,
        # credentials and source files are not targets of this cleanup.
        parent = (self.runtime.root / 'profiles').resolve()
        for marker in (self.work / 'native').rglob('profile.json'):
            metadata = json.loads(marker.read_text())
            name = metadata['profile_name']
            if (metadata.get('campaign_root') != str(self.work) or not metadata.get('ephemeral')
                    or len(name) != 27 or not name.startswith('db-')
                    or any(c not in '0123456789abcdef' for c in name[3:])):
                raise ValueError('Invalid generated profile cleanup target')
            target = parent / name
            if target.is_symlink() or target.resolve().parent != parent:
                raise ValueError('Refusing profile cleanup outside the generated namespace')
            if target.exists():
                shutil.rmtree(target)
