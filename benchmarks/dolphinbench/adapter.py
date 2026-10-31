"""Private, disclosed AtMem adapter for installed Hermes on macOS.

No custom extraction or retrieval: the installed AtMem memory provider handles
both. The upstream runner controls order, app resets and grading boundaries.
"""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import time

from .app_bridge import bridge, stage_client, short_socket
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
        self.memory_engine = options.get('memory_engine', 'control')
        self.ingestion_mode = options.get('ingestion_mode', 'native-agent')
        if options.get('app_python'):
            self.app_python = options['app_python']
            self.app_native_dependency = Path(self.app_python).parent.parent / 'lib/python3.12/site-packages/pydantic_core/_pydantic_core.cpython-312-darwin.so'
        if self.ingestion_mode == 'source-episode' and self.memory_engine != 'context-v3':
            raise ValueError('Episode ingestion requires the qualified V3 product binding')
        self.hosts = {}
        self.runtime = NativeRuntime(options.get('runtime_root', '/Volumes/AtMemDolphin/runtime-home'),
            source='/Users/javadtaghia/.hermes/hermes-agent',
            python='/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3',
            dependency_facts='/Users/javadtaghia/.hermes/installs/7f16443560343fb8/facts.json')
        self.runtime_identity = self.runtime.stage()
        self.native_inventory = self.runtime.verify_native_dependencies()
        self.observer = self.runtime.root / 'observers/observe_native.py'
        if self.observer.read_bytes() != Path(__file__).with_name('observe_native.py').read_bytes():
            raise ValueError('Native observer differs from the qualified runtime')
        self.campaign_identity = options['campaign_identity']
        self.reader_model=self.campaign_identity.get('agent',{}).get('model','openai/gpt-5.6-luna')
        from .subscription_service import subscription_reader_model
        subscription_reader_model(self.reader_model)
        self.cap_usd = self.campaign_identity['cap_usd']
        self.ledger = self.work / 'budget.db'

    def identity(self):
        return {'runtime': self.runtime_identity, 'campaign': self.campaign_identity,
                'integration': {'memory_engine': self.memory_engine, 'ingestion_mode': self.ingestion_mode,
                    'memory_delivery': self.options.get('memory_delivery', 'native-prefetch'),
                    'frozen_baseline_root': self.options.get('baseline_memory_root'),
                    'provider': 'installed AtMem', 'freeze': 'product-owned monotonic freeze'},
                'boundary': 'macOS sandbox-exec, not upstream Docker runner',
                'transport': 'Hermes Codex OAuth compatibility bridge' if self.options.get('subscription_endpoint') else 'OpenRouter Azure-only, official acceptance unconfirmed',
                'app_pydantic_core_version': '2.50.1',
                'app_python': self.app_python,
                'app_pydantic_core_sha256': self.app_native_sha256,
                'native_dependency_sha256': self.native_inventory,
                'adapter_source': {p.name: fingerprint(p.read_text()) for p in Path(__file__).parent.glob('*.py')}}

    def host(self, persona):
        if persona not in self.hosts:
            factory = None
            variant = self.options.get('context_engine_variant')
            if variant is not None:
                if variant == 'balanced-pools-v1':
                    from atmem.context_engine.service import balanced_context_engine
                    factory = balanced_context_engine
                elif variant == 'source-coherent-v1':
                    from atmem.context_engine.part_semantic import SourceCoherentHybridFactory
                    from atmem.semantic.providers import OllamaEmbedder
                    factory = SourceCoherentHybridFactory(
                        directory=self.options['context_index_directory'],
                        embedder=OllamaEmbedder('nomic-embed-text:latest',
                            model_version='sha256:0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f',
                            truncate=False))
                else:
                    raise ValueError('unknown explicit product engine variant')
            self.hosts[persona] = AtMemHost(self.options.get('baseline_memory_root', self.work / 'memory'),
                                          persona, memory_engine=self.memory_engine,context_engine_factory=factory,
                                          state_assessor=self.options.get('state_assessor'),
                                          initial_state_assessor=self.options.get('initial_state_assessor'),
                                          initial_state_presentation=self.options.get('initial_state_presentation','annotated-source'),
                                          source_time_frames=self.options.get('source_time_frames',False),
                                          source_bundles=self.options.get('source_bundles',False),
                                          native_soul=self.options.get('native_souls',{}).get(persona))
        return self.hosts[persona]

    def run_interaction(self, request):
        if request.phase == 'tests':
            from .readiness import require_options
            require_options(self.options, request=request)
        if request.phase == 'ingestion' and self.ingestion_mode != 'source-episode':
            raise ValueError('Native model ingestion is disabled; baseline history import must remain local')
        from harness.adapter import InteractionRecord
        from scripts.openrouter_azure_sol import load_key
        if request.phase == 'ingestion' and self.ingestion_mode == 'source-episode':
            started = time.monotonic()
            host = self.host(request.persona)
            capture = host.service.dispatch(host.credential, 'observe', {
                'text': request.dated_message, 'session_id': request.interaction_id,
                'observation_id': request.interaction_id})
            directory = self.work / 'native' / request.phase / request.persona / request.interaction_id
            save_new(directory / 'product-observe.json', capture)
            if capture.get('captured') and not capture['formation']['processing_complete']:
                raise RuntimeError('Product episode processing did not complete; preserve the receipt')
            return InteractionRecord(settings={'model': 'atmem-local-history-ingestion'},
                messages=[{'role': 'user', 'content': request.dated_message},
                    {'role': 'assistant', 'content': 'History recorded.' if capture.get('captured') else
                        'History observation refused by source policy.',
                     'usage': {'input_tokens': 0, 'output_tokens': 0}}],
                duration_ms=(time.monotonic() - started) * 1000,
                attempts=[{'cost_usd': 0.0, 'provider_calls': 0, 'product_receipt': capture}], app_calls=[])
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
        governed_context = '' if self.options.get('memory_delivery') in {'native-ephemeral-system', 'native-product-api'} else None
        if self.memory_engine == 'context-v3' and request.phase == 'tests' and self.options.get('pre_action_gate', True):
            if governed_context is not None:
                ruling, governed_context = host.prepare_native_context(request.dated_message,
                    home=home, session_id='gate-' + request.interaction_id, native_source=self.runtime.source,
                    in_process=self.options.get('memory_delivery') == 'native-product-api',
                    reader_model=self.reader_model)
            else:
                ruling = host.service.dispatch(host.credential, 'recall', {'query': request.dated_message,
                    'session_id': 'gate-' + request.interaction_id, 'turn_id': request.interaction_id})
            save_new(directory / 'pre-action-ruling.json', ruling)
            from atmem.adapters.hermes.task_guidance import RECOVERABLE_CONTEXT_STATUSES
            recoverable=(self.options.get('read_only_discovery') is True
                         and ruling['reason'] in RECOVERABLE_CONTEXT_STATUSES)
            if ruling['reason'] != 'authorized' and not recoverable:
                return InteractionRecord(settings={'model': self.reader_model},
                    messages=[{'role': 'user', 'content': request.dated_message},
                        {'role': 'assistant', 'content': 'Blocked before model invocation: ' + ruling['reason'],
                         'usage': {'input_tokens': 0, 'output_tokens': 0}}],
                    duration_ms=(time.monotonic() - started) * 1000,
                    attempts=[{'cost_usd': 0.0, 'provider_calls': 0, 'gate_blocked': True}], app_calls=[])
        if self.runtime.verify_native_dependencies() != self.native_inventory:
            raise RuntimeError('Native dependency inventory changed after qualification')
        subscription = self.options.get('subscription_endpoint')
        gateway_options = ({'endpoint': subscription, 'provider_name': 'OpenAI-Subscription',
            'upstream_timeout': 36000} if subscription else {})
        from .safe_runner import InteractionJournal
        journal = InteractionJournal(directory / 'app-evidence', request.apps)
        gateway = Gateway(key=os.environ['ATMEM_SUBSCRIPTION_PROXY_TOKEN'] if subscription else load_key(self.options['env_file']), output=directory / 'calls',
            ledger_path=self.ledger, campaign_identity=self.campaign_identity, cap_usd=self.cap_usd,
            phase=request.phase, model=self.reader_model,
            input_per_million=5 if self.reader_model.endswith('-sol') else 1,
            output_per_million=30 if self.reader_model.endswith('-sol') else 5,
            required_tool_catalog='mcp__dolphinbench_apps__',
            required_instruction_text=getattr(host,'native_soul',None),
            execution_profile=self.options.get('execution_profile'),
            readiness_options=self.options if request.phase == 'tests' else None, **gateway_options).start()
        completed = False
        try:
            with short_socket() as socket, bridge(request.apps, socket):
                client = home / 'app_client.py'
                stage_client(self.options.get('upstream_root', '/Volumes/AtMemDolphin/upstream'), client, socket)
                reader = self.campaign_identity.get('agent', {'reasoning': 'medium', 'max_turns': 20})
                host.configure_profile(home, base_url=gateway.base_url, local_token=gateway.local_token,
                    mcp={'command': str(self.runtime.python), 'args': ['-I', str(client)]},
                    governed_context=governed_context,
                    reader_model=self.reader_model,
                    reader_reasoning=reader['reasoning'], reader_max_turns=reader['max_turns'],
                    reader_context_length=reader.get('context_length', 1000000),
                    **({'discovery_query':request.dated_message,
                        'discovery_python':str(self.runtime.python)}
                       if self.options.get('read_only_discovery') else {}),
                    application_workflow=self.options.get('application_workflow',False),
                    strict_application_contracts=self.options.get('strict_application_contracts',False),
                    initial_status=ruling['reason'] if 'ruling' in locals() else 'authorized')
                if self.options.get('execution_profile'):
                    from .execution_profile import apply_profile
                    config = json.loads((home / 'config.yaml').read_text())
                    tool_config = Path(request.apps['env']['DOLPHINBENCH_TOOL_CONFIG_PATH'])
                    app_tools = json.loads(tool_config.read_text()).get('active_tools', []) if tool_config.exists() else []
                    config = apply_profile(self.options['execution_profile'], config, home=home,
                        request=request.dated_message, app_tools=app_tools, persona=request.persona,
                        skill_roots=(self.runtime.source / 'skills',
                        Path.home() / '.hermes/skills', self.runtime.root / 'skills'))
                    from .driver import private_json
                    private_json(home / 'config.yaml', config)
                if subscription:
                    from .driver import private_json
                    config = json.loads((home / 'config.yaml').read_text())
                    config['providers']['custom'].update(request_timeout_seconds=36000, stale_timeout_seconds=36000)
                    config['agent']['api_max_retries'] = 0
                    private_json(home / 'config.yaml', config)
                witness = home / 'shutdown-witness.jsonl'
                process = self.runtime.invoke(profile,
                    ['chat', '-q', request.dated_message, '-Q', '--yolo', '--format', 'stream-json',
                     '--max-turns', str(reader['max_turns'])],
                    ports=[gateway.server_port, host.server.server_port], sockets=[socket], timeout=43200 if subscription else 600,
                    environment={'CUSTOM_API_KEY': gateway.local_token,
                        'ATMEM_BENCH_OBSERVER': str(self.observer), 'ATMEM_BENCH_WITNESS': str(witness)})
            save_new(directory / 'process.json', {'exit_code': process.returncode,
                'stdout': process.stdout, 'stderr': process.stderr})
            terminal_failure = None
            if process.returncode != 0:
                results = [json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
                results = [r for r in results if r.get('type') == 'result' and r.get('exit_code') == 1]
                if (not subscription or len(results) != 1 or not results[0].get('error')
                        or 'HTTP 502' not in results[0]['error']):
                    raise RuntimeError('Native interaction failed; no automatic paid replay')
                terminal_failure = results[0]
            if governed_context is None and not witness.exists():
                raise RuntimeError('Native provider shutdown witness is missing')
            shutdown = [json.loads(line) for line in witness.read_text().splitlines()] if witness.exists() else []
            providers = [p for event in shutdown for p in event['providers']]
            if governed_context is not None:
                if providers:
                    raise RuntimeError('One-shot API context must not also load a native memory provider')
                save_new(directory / 'context-delivery.json', {
                    'mode': 'installed AtMem API to native ephemeral_system_prompt',
                    'native_memory_provider': 'disabled, so no provider shutdown hook applies',
                    'actual_native_process_exit_code': process.returncode,
                    'product_context_sha256': hashlib.sha256(governed_context.encode()).hexdigest()})
            elif not providers or any(p['name'] != 'atmem' or p['pending_writes'] != 0 or p['write_errors'] != 0 for p in providers):
                raise RuntimeError('Native memory provider did not drain cleanly')
            from graders.mechanical import load_tool_calls
            app_calls = load_tool_calls(Path(request.apps['env']['DOLPHINBENCH_LOG_PATH']))
            export = export_interaction(directory / 'calls', home / 'api-witness.jsonl',
                app_calls=app_calls,
                default_source_paths=(Path(self.options['upstream_root']) / 'mock_mcp').glob('repair*.py'),
                terminal_failure=terminal_failure)
            if governed_context is not None:
                if [m.get('content') for m in export['messages'] if m.get('role') == 'user'] != [request.dated_message]:
                    raise RuntimeError('Native system-context mode changed the original user boundary')
                if governed_context and not any(governed_context in str(m.get('content', ''))
                    for m in export['messages'] if m.get('role') in {'system', 'developer'}):
                    raise RuntimeError('Product context is missing from the actual native system/developer input')
            save_new(directory / 'export.json', export)
            for name in ('api-witness.jsonl', 'shutdown-witness.jsonl', 'app_client.provenance.json'):
                if name == 'shutdown-witness.jsonl' and governed_context is not None and not (home / name).exists():
                    continue
                shutil.copyfile(home / name, directory / name)
            save_new(directory / 'profile.json', {'profile_name': profile,
                'campaign_root': str(self.work), 'ephemeral': True})
            completed = True
            return InteractionRecord(settings=export['settings'], messages=export['messages'],
                duration_ms=(time.monotonic() - started) * 1000,
                attempts=[{'auxiliary_calls': export['auxiliary_calls']}])
        finally:
            try:
                journal.snapshot(completed=completed)
            finally:
                gateway.stop()

    def freeze(self, persona):
        return self.host(persona).freeze()

    def verify_checkpoint(self, persona, checkpoint):
        self.host(persona).verify_checkpoint(checkpoint)

    def total_cost_usd(self, phase):
        if phase not in {'ingestion','tests'}:
            raise ValueError('Upstream cost phases are ingestion or tests')
        included=({'tests','state-assessment','initial-state-assessment','action-review'}
                  if phase=='tests' else {'ingestion'})
        book = BudgetLedger(self.ledger, cap_usd=self.cap_usd, identity=self.campaign_identity)
        try:
            totals = book.totals()
            uncertain = (sum(totals.get(name,{}).get('reserved_usd',0) for name in included)
                         if self.memory_engine == 'context-v3' else
                         sum(row['reserved_usd'] for row in totals.values()))
            if uncertain:
                raise ValueError('Unreconciled API cost reservations')
            return sum(totals.get(name,{}).get('actual_usd',0) for name in included)
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
