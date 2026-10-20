"""Inert installed AtMem/Hermes wiring; product services own all memory behavior."""
import json
import os
from pathlib import Path
import sys
import threading
import time

from atmem.adapters.hermes.service import HermesService
from atmem.control import ControlPlaneManager
from atmem.control.web import ControlDashboardServer
from atmem.hermes_install import install
from atmem.service import APIPrincipal


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.preparing')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, ensure_ascii=False)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


class AtMemHost:
    def __init__(self, root, persona, *, memory_engine="control"):
        self.root = Path(root).resolve() / persona
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        state_path = self.root / 'state.json'
        if memory_engine == 'context-v3' and not state_path.exists():
            from atmem.service.household import HouseholdApplication
            database = self.root / 'memory.db'
            if database.exists():
                raise ValueError('Refusing to replace an existing unconfigured memory database')
            HouseholdApplication.initialize(database, encrypted=True, backend='file')
        self.manager = ControlPlaneManager(state_path) if state_path.exists() else ControlPlaneManager.start(
            host='generic', state_path=state_path, control_root=self.root / 'control',
            memory_db=self.root / 'memory.db', subject_id='dolphin-' + persona)
        workspace = self.manager.agent_topology()['workspaces'][0]
        self.admin = APIPrincipal('benchmark-operator', 'admin', workspace['subject_id'])
        self.service = HermesService(self.manager)
        grants = self.service.list_bindings(self.admin)
        if grants:
            if len(grants) != 1 or grants[0]['profile_id'] != 'dolphin-' + persona:
                raise ValueError('Unexpected prior Hermes bindings')
            self.binding = grants[0]
            if self.binding.get('memory_engine', 'control') != memory_engine:
                raise ValueError('Memory engine changed; create a fresh condition, not a migrated run')
            self.credential = (self.root / 'scoped-credential').read_text().strip()
        else:
            grant = self.service.provision(self.admin, profile_id='dolphin-' + persona,
                agent_id='main', workspace_id=workspace['workspace_id'], accept_reduced_capture=True,
                memory_engine=memory_engine, authorize_history_import=memory_engine == 'context-v3')
            self.binding, self.credential = grant['binding'], grant['credential']
            fd = os.open(self.root / 'scoped-credential', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as output:
                output.write(self.credential)
                output.flush()
                os.fsync(output.fileno())
            self.service.configure(self.admin, self.binding['binding_id'], enabled=True)
            self.manager.activate()
        self.server = ControlDashboardServer(('127.0.0.1', 0), self.manager, html='Isolated benchmark RPC')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def prepare_native_context(self, query, *, home, session_id, native_source, in_process=False):
        """Use the installed product provider's RPC, authorization and renderer.

        Observe the returned ruling, without changing it or implementing a
        second retrieval/renderer in the benchmark. Only its delivery channel
        differs from Hermes's normal user-message attachment.
        """
        if str(native_source) not in sys.path:
            sys.path.insert(0, str(native_source))
        from atmem.adapters.hermes.client import HermesRPCClient
        from atmem.adapters.hermes.provider import create_provider

        class ObservedClient(HermesRPCClient):
            prepared = None
            def _call(client_self, operation, payload, *, timeout=None):
                if in_process and operation == 'prepare-turn':
                    # Same authenticated product endpoint, schema, governance,
                    # retrieval and lifecycle. Avoid only the desktop RPC's
                    # ten-second network deadline in this bulk-history study.
                    return self.service.dispatch(self.credential, operation, payload)
                return super()._call(operation, payload, timeout=timeout)

            def prepare_turn(self, *args, **kwargs):
                self.prepared = super().prepare_turn(*args, **kwargs)
                return self.prepared

        client = ObservedClient(f'http://127.0.0.1:{self.server.server_port}', self.credential,
            profile_id=self.binding['profile_id'], timeout=10)
        provider = create_provider(client, hermes_home=str(home))
        try:
            provider.initialize(session_id, hermes_home=str(home), platform='cli')
            provider.on_turn_start(1, query, model='openai/gpt-5.6-luna')
            rendered = provider.prefetch(query, session_id=session_id)
            if client.prepared is None:
                raise RuntimeError('Installed native provider did not prepare a context')
            return vars(client.prepared), rendered
        finally:
            provider.shutdown()

    def configure_profile(self, home, *, base_url, local_token, mcp=None, governed_context=None):
        home = Path(home).resolve()
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        home.chmod(0o700)
        install(home, apply=True)
        private = home / '.atmem'
        private.mkdir(exist_ok=True, mode=0o700)
        private.chmod(0o700)
        private_json(private / 'connection.json', {
            'format': 'atmem-hermes-connection-v1', 'hermes_home': str(home),
            'endpoint': f'http://127.0.0.1:{self.server.server_port}',
            'profile_id': self.binding['profile_id']})
        credential_path = private / 'credential'
        if credential_path.exists():
            if credential_path.read_text().strip() != self.credential:
                raise ValueError('Profile credential changed')
        else:
            fd = os.open(credential_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as output:
                output.write(self.credential)
        toolsets = ['hermes-cli', 'memory', 'session_search']
        if mcp:
            toolsets.append('dolphinbench-apps')
        config = {
            'model': {'provider': 'custom', 'default': 'openai/gpt-5.6-luna',
                      'base_url': base_url, 'api_mode': 'chat_completions',
                      'context_length': 1000000, 'max_tokens': 4096},
            'memory': {'provider': 'atmem', 'memory_enabled': True, 'user_profile_enabled': True},
            'toolsets': toolsets, 'platform_toolsets': {'cli': toolsets},
            'agent': {'api_max_retries': 2, 'retry_rate_limits_until_success': False,
                      'reasoning_effort': 'medium', 'max_turns': 20},
            # Ordinary supported Hermes setting: retain derived titles without
            # spawning an unrelated, lossy background title-generation request.
            'auxiliary': {'title_generation': {'model_upgrade_enabled': False},
                          'background_review': {'enabled': False}},
            'mcp_servers': {'dolphinbench-apps': mcp} if mcp else {},
            'providers': {'custom': {'api': base_url, 'api_key': local_token}},
        }
        if self.binding.get('memory_engine') == 'context-v3':
            # Supported host setting: the product already bounds V3 at 32,000
            # bytes. A second 10k-char spill would change the delivered context.
            config['hooks'] = {'output_spill': {'enabled': True, 'max_chars': 33_000}}
        if governed_context is not None:
            # A fresh one-shot native session: preserve the original user bytes
            # and forward the product-rendered context through Hermes's supported
            # ephemeral system prompt. Do not also run native user-side prefetch.
            config['memory'] = {'provider': '', 'memory_enabled': False, 'user_profile_enabled': False}
            toolsets.remove('memory')
            config['agent']['system_prompt'] = governed_context
            # The submission format is one conversation, not a graph of child
            # agents. Keep native session search and app tools, not delegation.
            config['agent']['disabled_toolsets'] = ['memory', 'delegation']
        private_json(home / 'config.yaml', config)  # JSON is valid YAML.

    def freeze(self):
        self.service.flush_evidence()
        return self.service.freeze_memory(self.admin, self.binding['binding_id'])

    def verify_checkpoint(self, checkpoint):
        self.service.verify_memory_checkpoint(self.admin, self.binding['binding_id'], checkpoint)

    def portable_export(self, destination):
        if self.binding.get('memory_engine') == 'context-v3':
            destination = Path(destination)
            # Incremental checkpoints preserve the previously verified export.
            destination = destination.with_name(destination.stem + '-' + str(time.time_ns()) + destination.suffix)
            return self.service.export_context_memory(self.admin, self.binding['binding_id'], destination)
        from atmem.memory import Memory
        from atmem.interchange import ScopeMap, export_archive
        scope, path = self.manager._memory_authority_scope(self.manager.state(),
            subject_id=self.admin.subject_id, agent_id='main')
        memory = Memory(path, retain_query_text=False)
        try:
            return export_archive(memory, ScopeMap(scope.subject_id, scope.workspace_id,
                scope.agent_id, self.admin.tenant_id), destination, include_inactive=True)
        finally:
            memory.close()

    def stop(self):
        self.service.flush_evidence()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(10)
