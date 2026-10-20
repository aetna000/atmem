"""Installed Claude against a local protocol fixture, not an efficacy trial."""
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.skipif(os.name == 'nt' or not shutil.which('claude') or
                   os.environ.get('ATMEM_CODE_SKIP_HOST_PROBES') == '1',
                   reason='separately qualified installed Claude boundary required')
def test_installed_claude_navigation_and_native_tools(tmp_path, monkeypatch):
    from atmem.code.application import CodeApplication
    from atmem.code.identity import CodeIdentity
    from atmem.knowledge.projections import CodeKnowledge
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    from tests.test_knowledge_lifecycle import init_repository, FixtureWorker
    fixtures = Path(__file__).parent / 'fixtures'
    helpers = runpy.run_path(str(fixtures / 'host_process.py'))
    endpoint_type = runpy.run_path(str(fixtures / 'discovery_anthropic_endpoint.py'))['DiscoveryAnthropicEndpoint']
    home = tmp_path / 'atmem-home'
    monkeypatch.setenv('ATMEM_HOME', str(home))
    # Earlier test imports may have bound the parent's file-key location. Create
    # a NEW fixture key at the same location a fresh MCP process will resolve;
    # never copy a key from the owner's home or another benchmark environment.
    from atmem.core import keys
    monkeypatch.setattr(keys, 'DEFAULT_KEY_PATH', home / 'identity/keys/db.key')
    database = tmp_path / 'memory.db'
    HouseholdApplication.initialize(database, encrypted=True)
    root = tmp_path / 'repo'
    root.mkdir()
    memory = Memory(database, auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(root, subject_id='local', profile_id='shared', agent_id='claude')
        app = CodeApplication(memory, subject_id='local')
        env = SimpleNamespace(memory=memory, root=root, scope=scope, app=app, project=scope.project_id)
        init_repository(env)
        CodeKnowledge(app, scope).index(str(root), FixtureWorker())
        # Use the source preview explicitly, not a stale wheel on this test runner.
        source = 'import sys;sys.path.insert(0,' + repr(str(Path(__file__).resolve().parents[1])) + ');from atmem.knowledge.code.mcp import main;main()'
        config = {'mcpServers': {'nav': {'command': sys.executable,
            'args': ['-I', '-c', source, '--db', str(database), '--root', str(root),
                     '--subject', 'local', '--project-id', scope.project_id, '--agent', 'claude',
                     '--tool-profile', 'navigation'], 'env': {'ATMEM_HOME': str(home)}}}}
        with endpoint_type(root / 'main.py') as endpoint:
            environment = helpers['offline_environment']()
            environment.update(ANTHROPIC_BASE_URL=endpoint.url, ANTHROPIC_API_KEY='offline-local-probe',
                CLAUDE_CONFIG_DIR=str(tmp_path / 'claude-home'), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                MAX_THINKING_TOKENS='0', ATMEM_HOME=str(home))
            result = helpers['run_owned_cli']([shutil.which('claude'), '-p', 'Run the local boundary probe.',
                '--max-turns', '8', '--tools', 'Read,Edit,Bash', '--allowedTools',
                'Read,Edit,Bash,mcp__nav__repository_discover', '--strict-mcp-config', '--mcp-config', json.dumps(config),
                '--permission-mode', 'dontAsk', '--setting-sources', '', '--no-session-persistence',
                '--output-format', 'stream-json', '--verbose'], cwd=root, env=environment, timeout=75)
        assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-2000:]
        assert len(endpoint.requests) >= 6, result.stdout[-3000:]
        results = []
        for req in endpoint.requests:
            for message in req.get('messages', []):
                for part in message.get('content', []) if isinstance(message.get('content'), list) else []:
                    if part.get('type') == 'tool_result':
                        results.append(part)
        navigation = next(p for p in results if p.get('tool_use_id') == 'probe-tool-0')
        text = json.dumps(navigation)
        assert 'main.py' in text and 'non_exhaustive' in text and 'return 1' not in text
        assert any(p.get('tool_use_id') == 'probe-tool-1' and p.get('is_error') for p in results)
        assert 'return 2' in (root / 'main.py').read_text()
        assert any('discovery-native-test-ok' in json.dumps(p) for p in results)
        exposures = memory.store.code_documents('local', scope.project_id, 'curation-exposure')
        assert len(exposures) == 1 and exposures[0]['navigation_delivered']['items']
    finally:
        memory.close()
