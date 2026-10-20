"""Installed Codex app-server + local provider, not subscription efficacy."""
import json
import os
from pathlib import Path
import runpy
import shutil
import time

import pytest


@pytest.mark.skipif(os.name == 'nt' or not shutil.which('codex') or
                   os.environ.get('ATMEM_CODE_SKIP_HOST_PROBES') == '1',
                   reason='separately qualified installed Codex app-server required')
def test_installed_codex_dynamic_discovery_is_authorized_and_returned(tmp_path, monkeypatch):
    from tests.fixtures.discovery_project import project, navigation_plan
    from tests.fixtures.discovery_codex_rpc import DiscoveryRPC
    from atmem.code.discovery import Discovery
    from atmem.knowledge.code.mcp import CodeKnowledgeMCP
    fixtures = Path(__file__).parent / 'fixtures'
    endpoint_type = runpy.run_path(str(fixtures / 'responses_endpoint.py'))['ResponsesEndpoint']
    helpers = runpy.run_path(str(fixtures / 'host_process.py'))
    env = project(tmp_path, monkeypatch, 'codex')
    rpc = None
    try:
        service = Discovery(env.app, env.scope, str(env.root))
        definition = CodeKnowledgeMCP._tool_definitions(type('Profile', (), {'tool_profile': 'navigation'})())[0]
        prepared_calls = {}
        def callback(arguments):
            prepared = service.prepare(arguments)
            final = service.for_delivery(prepared)
            prepared_calls[arguments['request_id']] = prepared
            return final
        def written(params, final, wire):
            service.written(prepared_calls.pop(params['arguments']['request_id']), final, wire=wire)
        home = tmp_path / 'codex-home'
        home.mkdir()
        with endpoint_type(tool_plan=lambda value, index: navigation_plan(value, index, native_root=env.root)) as endpoint:
            environment = helpers['offline_environment']()
            environment.update(CODEX_HOME=str(home), ATMEM_HOME=str(env.home))
            command = [shutil.which('codex'), 'app-server', '--listen', 'stdio://',
                '-c', 'model="gpt-5.4"', '-c', 'model_provider="atmem_probe"',
                '-c', 'model_providers.atmem_probe.name="AtMem local fixture"',
                '-c', 'model_providers.atmem_probe.wire_api="responses"',
                '-c', 'model_providers.atmem_probe.requires_openai_auth=false',
                '-c', 'model_providers.atmem_probe.base_url=' + json.dumps(endpoint.url),
                '-c', 'web_search="disabled"']
            rpc = DiscoveryRPC(command, cwd=env.root, env=environment, callback=callback, on_written=written)
            rpc.call('initialize', {'clientInfo': {'name': 'atmem-local-discovery-probe', 'version': '1.0.0'},
                'capabilities': {'experimentalApi': True}})
            rpc.send({'method': 'initialized'})
            thread = rpc.call('thread/start', {'model': 'gpt-5.4', 'ephemeral': True,
                'cwd': str(env.root), 'approvalPolicy': 'never', 'sandbox': 'workspace-write',
                'dynamicTools': [{'type': 'function', 'name': definition['name'],
                    'description': definition['description'], 'inputSchema': definition['inputSchema']}]})
            thread_id = thread['thread']['id']
            rpc.call('turn/start', {'threadId': thread_id,
                'input': [{'type': 'text', 'text': 'Run the local discovery protocol fixture.'}]})
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if any(m.get('method') == 'turn/completed' for m in rpc.messages):
                    break
                rpc.pump(.1)
            assert any(m.get('method') == 'turn/completed' for m in rpc.messages), bytes(rpc.raw['stderr'])[-1500:]
        assert len(rpc.calls) == 2, json.dumps(endpoint.requests[0].get('tools', []))[:1800]
        records = env.app.store.code_documents('local', env.project, 'curation-exposure')
        assert len(records) == 1 and records[0]['navigation_delivered']['items']
        assert len(endpoint.requests) >= 6
        wire = json.dumps(endpoint.requests)
        assert 'atmem-repository-discovery-response-v1' in wire
        assert 'non_exhaustive' in wire and 'discovery request refused' in wire
        assert 'return 2' in (env.root / 'main.py').read_text()
        assert 'discovery-native-test-ok' in wire
    finally:
        if rpc is not None:
            rpc.close()
        env.memory.close()
