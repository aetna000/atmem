"""Product-boundary fixtures, not task-quality or benchmark evidence."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

from atmem.code.execution import run_command
from atmem.code.experience_view import experiences
from atmem.code.knowledge_setup import configure, worker_context
from tests.test_knowledge_lifecycle import init_repository, FixtureWorker


def execute(env, command=None, **kwargs):
    return run_command(env.app, env.scope, str(env.root),
        command or [sys.executable, '-c', 'print("bounded command result")'],
        intent='Check main function behavior', anchors=['main.py'], **kwargs)


@pytest.fixture
def ready(code_env):
    init_repository(code_env)
    code_env.memory._allow_insecure_typed_development = True
    return code_env


def test_real_command_forms_source_bound_experience_and_cross_agent_recall(ready):
    from atmem.code.context import build_context
    from atmem.code.contracts import CodeContextRequest
    env = ready
    result = execute(env)
    assert result['exit_code'] == 0 and result['formation']['formed'], result
    assert result['outcome'] == 'observed_pass'
    assert result['stdout'] == 'bounded command result\n'
    other = replace(env.scope, agent_id='claude')
    listed = experiences(env.app, other, str(env.root))
    assert listed['items'][0]['applicability']['status'] == 'applicable'
    assert listed['items'][0]['execution_evidence'][0]['exit_code'] == 0
    assert 'stdout' not in str(listed)
    evidence = env.app.dispatch('experience-evidence', {'project_id': env.project,
        'record_id': result['formation']['record_ids'][0], 'receipt_id': result['experience_id']})
    assert evidence['stdout'] == 'bounded command result\n'
    assert evidence['result']['source_stable']
    with pytest.raises(PermissionError):
        env.app.dispatch('experience-evidence', {'project_id': env.project,
            'record_id': result['formation']['record_ids'][0], 'receipt_id': 'unrelated'})
    context = build_context(env.memory, CodeContextRequest('later', 'session2', 'turn2',
        'main function behavior', 4096, other), repository_root=str(env.root))
    assert result['formation']['record_ids'][0] in context.memory_ids
    (env.root / 'unrelated.py').write_text('value = 2\n')
    assert experiences(env.app, other, str(env.root))['items'][0]['applicability']['status'] == 'applicable'
    (env.root / 'main.py').write_text('def main(): return 3\n')
    changed = experiences(env.app, other, str(env.root))['items'][0]
    assert 'ANCHOR_CHANGED_OR_MISSING' in changed['applicability']['reason_codes']
    assert build_context(env.memory, replace(CodeContextRequest('changed', 'session3', 'turn3',
        'main function', 4096, other)), repository_root=str(env.root)).memory_ids == ()


def test_failure_unknown_and_pause_are_not_successes(ready):
    env = ready
    failed = execute(env, [sys.executable, '-c', 'print("failure observed"); raise SystemExit(3)'])
    assert failed['exit_code'] == 3 and failed['outcome'] == 'observed_failure'
    changed = execute(env, [sys.executable, '-c', 'from pathlib import Path; Path("main.py").write_text("def main(): return 5\\n")'])
    assert changed['outcome'] == 'unknown' and not changed['source_stable']
    env.app.settings(env.project, {'auto_capture': False})
    paused = execute(env)
    assert paused['exit_code'] == 0 and not paused['formation']['formed']
    assert paused['capture']['reason'] == 'auto_capture_disabled'


def test_secret_output_is_not_persisted_or_returned(ready, monkeypatch):
    token = 'sk-proj-' + 'abcd1234' * 12
    monkeypatch.setenv('ATMEM_WORKFLOW_TEST_SECRET', token)
    result = execute(ready, [sys.executable, '-c', 'import os; print(os.environ["ATMEM_WORKFLOW_TEST_SECRET"])'])
    assert result['reason'] == 'secret_output' and not result['formation']['formed']
    assert token not in str(result)
    assert ready.memory.store.code_documents('local', ready.project, 'execution-receipt') == []


def test_timeout_and_output_limit_keep_unknown_outcome(ready):
    slow = execute(ready, [sys.executable, '-c', 'import time; time.sleep(5)'], timeout=1)
    assert slow['stop_reason'] == 'timeout' and slow['outcome'] == 'unknown'
    noisy = execute(ready, [sys.executable, '-c', 'print("x" * 50000)'], max_output=1024)
    assert noisy['stop_reason'] == 'output_limit' and noisy['outcome'] == 'unknown'


def test_unknown_anchor_and_secret_metadata_refuse_before_execution(ready):
    with pytest.raises(ValueError, match='anchor'):
        run_command(ready.app, ready.scope, str(ready.root), [sys.executable, '-c', 'print(1)'],
            intent='main function', anchors=['missing.py'])
    with pytest.raises(ValueError):
        execute(ready, [sys.executable], timeout=True)
    with pytest.raises(ValueError):
        configure(ready.app, ready.scope, str(ready.root), image_id='latest')


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX signal-denial branch')
def test_signal_denial_falls_back_only_to_direct_child(ready, monkeypatch):
    import atmem.code.execution as module
    def denied(*args):
        raise PermissionError('group signalling denied')
    monkeypatch.setattr(module.os, 'killpg', denied)
    result = execute(ready, [sys.executable, '-c', 'import time; time.sleep(5)'], timeout=1)
    assert result['stop_reason'] == 'timeout' and result['outcome'] == 'unknown'


def test_extractor_configuration_and_bundled_context(ready, tmp_path):
    configured = configure(ready.app, ready.scope, str(ready.root), image_id='sha256:' + 'a' * 64)
    assert configured['configured'] and not configured['automatic_download']
    assert configure(ready.app, ready.scope, str(ready.root)) == configured
    target = tmp_path / 'worker'
    result = worker_context(target)
    assert result['runtime_network'] == 'none'
    source = Path(__file__).parents[1] / 'tools/code-extractor'
    for name in ('Dockerfile', 'entrypoint.py'):
        assert (target / name).read_bytes() == (source / name).read_bytes()
    with pytest.raises(ValueError):
        worker_context(target)


def test_experience_mcp_is_explicit_read_only_and_scope_bound(ready):
    from atmem.knowledge.code.mcp import CodeKnowledgeMCP
    env = ready
    execute(env)
    normal = CodeKnowledgeMCP(env.app, env.scope, str(env.root))
    assert 'code_experience' not in {d['name'] for d in normal._tool_definitions()}
    instance = CodeKnowledgeMCP(env.app, env.scope, str(env.root), experience=True)
    assert len(instance.query('code_experience', {})['items']) == 1
    assert instance._call_tool(1, 'code_experience', {'root': '/other'})['result']['isError']
    assert instance._call_tool(1, 'run', {'command': 'echo bad'}).get('error')
    private = replace(env.scope, profile_id='private', agent_id='claude')
    assert experiences(env.app, private, str(env.root))['items'] == []


def test_graph_only_replay_withholds_stale_context(ready):
    from atmem.code.contracts import CodeContextRequest, CodeObservation
    from atmem.code.runtime import CodeRuntime
    from atmem.code.service import CodeIntakeService
    from atmem.knowledge.projections import CodeKnowledge
    env = ready
    env.app.settings(env.project, {'auto_capture': False})
    env.memory.store.put_code_installation(subject_id='local', project_id=env.project, host='codex', enabled=True)
    intake = CodeIntakeService(env.memory.store, scope=env.scope, host='codex', session_id='session', secret=b'x' * 32, enabled=True)
    runtime = CodeRuntime(env.memory, intake)
    CodeKnowledge(env.app, env.scope).index(str(env.root), FixtureWorker())
    request = CodeContextRequest('replay', 'session', 'turn', 'main function', 4096, env.scope)
    observation = CodeObservation('event', 'session', 'turn', 'codex', 'user_turn', 'main function',
        '2026-10-19T10:00:00Z', 'test:user', None, env.scope)
    first = runtime.on_user_turn(request, observation, intake.sign(observation), repository_root=str(env.root))
    assert first['context'].content and not first['context'].memory_ids
    (env.root / 'main.py').write_text('def changed(): return 2\n')
    replay = runtime.on_user_turn(request, observation, intake.sign(observation), repository_root=str(env.root))
    assert replay['context'].content == '' and replay['exposure']['state'] == 'withheld'


@pytest.mark.parametrize('change', ['forget', 'edit'])
def test_experience_transport_revalidates_before_writing(ready, change):
    import io
    import json
    from atmem.knowledge.code.mcp import CodeKnowledgeMCP
    result = execute(ready)
    instance = CodeKnowledgeMCP(ready.app, ready.scope, str(ready.root), experience=True)
    prepared = instance._call_tool(1, 'code_experience', {})
    if change == 'forget':
        ready.app.forget(ready.project, result['formation']['record_ids'][0])
    else:
        (ready.root / 'main.py').write_text('def changed(): return 3\n')
    stream = io.StringIO()
    instance._write(stream, prepared)
    answer = json.loads(json.loads(stream.getvalue())['result']['content'][0]['text'])
    assert answer['status'] == 'withheld' and answer['items'] == []
