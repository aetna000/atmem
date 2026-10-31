"""Installed Copilot + local fixture provider: no subscription/efficacy claim."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('copilot') or os.environ.get('ATMEM_CODE_SKIP_HOST_PROBES') == '1',
                   reason='separately qualified installed Copilot boundary required')
def test_installed_copilot_discovery_tool_reaches_local_model_input(tmp_path, monkeypatch):
    from atmem.code.adapters.copilot import copilot_cli_argv, copilot_offline_remote_flags
    from tests.fixtures.discovery_project import project, mcp_server, navigation_plan
    fixtures = Path(__file__).parent / 'fixtures'
    helpers = runpy.run_path(str(fixtures / 'host_process.py'))
    endpoint_type = runpy.run_path(str(fixtures / 'responses_endpoint.py'))['ResponsesEndpoint']
    env = project(tmp_path, monkeypatch, 'copilot')
    try:
        home = tmp_path / 'copilot-home'
        home.mkdir()
        (home / 'config.json').write_text(json.dumps({'trustedFolders': [str(env.root.resolve())]}))
        with endpoint_type(tool_plan=lambda value, index: navigation_plan(value, index, native_root=env.root)) as endpoint:
            environment = helpers['offline_environment']()
            environment.update(COPILOT_HOME=str(home), COPILOT_OFFLINE='true',
                COPILOT_PROVIDER_BASE_URL=endpoint.url, COPILOT_PROVIDER_TYPE='openai',
                COPILOT_PROVIDER_WIRE_API='responses', COPILOT_MODEL='gpt-5.4', ATMEM_HOME=str(env.home))
            binary = copilot_cli_argv()
            version = subprocess.run([*binary, '--version'], capture_output=True, text=True, timeout=5, check=False)
            result = helpers['run_owned_cli']([*binary, '-p', 'Run the local discovery boundary probe.',
                '--additional-mcp-config', json.dumps({'mcpServers': {'nav': mcp_server(env)}}),
                '--allow-tool', 'nav(repository_discover)', '--disable-builtin-mcps', '--no-auto-update',
                '--allow-tool', 'write', '--allow-tool', 'shell(python3:*)',
                '--allow-tool', 'shell',
                '--no-custom-instructions', '--no-ask-user', *copilot_offline_remote_flags(version.stdout or version.stderr),
                '--output-format', 'json', '--silent'], cwd=env.root, env=environment, timeout=75)
        (tmp_path/'provider-observations.json').write_text(json.dumps({
            'requests':endpoint.requests,'stdout':result.stdout,'stderr':result.stderr},
            ensure_ascii=False),encoding='utf-8')
        assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-2000:]
        assert len(endpoint.requests) >= 6, json.dumps(endpoint.requests[0].get('tools', []))[:1500]
        wire = json.dumps(endpoint.requests)
        assert 'atmem-repository-discovery-response-v1' in wire and 'non_exhaustive' in wire
        assert 'main.py' in wire
        records = env.app.store.code_documents('local', env.project, 'curation-exposure')
        assert len(records) == 1 and records[0]['navigation_delivered']['items']
        assert 'return 1' not in json.dumps(records[0]['navigation_delivered'])
        assert any('refused' in json.dumps(r).lower() for r in endpoint.requests[2:])
        assert 'return 2' in (env.root / 'main.py').read_text()
        assert 'discovery-native-test-ok' in wire
    finally:
        env.memory.close()
