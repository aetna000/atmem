"""Contract fixtures only, not token-saving or coding-quality evidence."""
import argparse
from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
import os
import shutil
import sys

import pytest

from atmem.code.curation import Curation, encoded, fit
from atmem.code.history import mask_observations
from atmem.knowledge.code.mcp import CodeKnowledgeMCP
from tests.test_knowledge_lifecycle import init_repository, FixtureWorker
from atmem.knowledge.projections import CodeKnowledge
from tests.test_code_product_workflow import execute


@pytest.fixture
def curated(code_env):
    init_repository(code_env)
    code_env.memory._allow_insecure_typed_development = True
    CodeKnowledge(code_env.app, code_env.scope).index(str(code_env.root), FixtureWorker())
    return code_env, CodeKnowledgeMCP(code_env.app, code_env.scope, str(code_env.root),
                                    experience=True, tool_profile='curated')


def call(server, operation, args=None, *, write=True):
    reply = server._call_tool(1, 'code_query', {'operation': operation, 'arguments': args or {}})
    assert not reply['result']['isError'], reply
    if write:
        stream = StringIO()
        server._write(stream, reply)
        reply = json.loads(stream.getvalue())
    return json.loads(reply['result']['content'][0]['text'])


def test_discovery_fetch_exact_and_goal_omissions(curated):
    env, instance = curated
    result = call(instance, 'discover', {'query': 'main behavior', 'kind': 'code'})
    assert result['items'] and all('content' not in item for item in result['items'])
    identity = result['items'][0]['id']
    detail = call(instance, 'fetch', {'ids': [identity], 'goal': 'return value'})
    item = detail['items'][0]
    assert item['content'] == 'def main():\n    return 1'
    assert item['source_sha256'] and not item['omitted']
    assert detail['estimator'] == 'utf8-byte-upper-bound-v1'
    assert call(instance, 'discover', {'query': 'zzzznomatch', 'kind': 'code'})['items'] == []


def test_experience_index_never_contains_observation_or_output(curated):
    env, instance = curated
    attempt = execute(env)
    index = call(instance, 'discover', {'kind': 'experience', 'query': 'main behavior'})
    item = index['items'][0]
    assert item['applicability'] == 'unchecked'
    assert 'observation' not in item and 'anchors' not in item
    assert 'bounded command result' not in str(index) and 'execution_evidence' not in str(index)
    assert call(instance, 'fetch', {'ids': [item['id']]})['items'][0]['applicability'] == 'applicable'
    assert 'stdout' not in str(call(instance, 'fetch', {'ids': [item['id']]}))
    private = Curation(env.app, replace(env.scope, profile_id='private', agent_id='claude'), str(env.root))
    assert private.prepare('fetch', {'ids': [item['id']]})['items'][0]['status'] == 'missing'
    env.app.forget(env.project, attempt['formation']['record_ids'][0])
    assert call(instance, 'fetch', {'ids': [item['id']]})['items'][0]['status'] == 'missing'


@pytest.mark.parametrize('change', ['edit', 'forget'])
def test_experience_changed_before_delivery_is_withheld(curated, change):
    env, instance = curated
    attempt = execute(env)
    identity = 'exp:' + attempt['formation']['record_ids'][0]
    reply = instance._call_tool(1, 'code_query', {'operation': 'fetch', 'arguments': {'ids': [identity]}})
    if change == 'edit':
        (env.root / 'main.py').write_text('def changed(): pass\n')
    else:
        env.app.forget(env.project, identity[4:])
    stream = StringIO()
    instance._write(stream, reply)
    answer = json.loads(json.loads(stream.getvalue())['result']['content'][0]['text'])
    assert answer['status'] == 'withheld' and answer['items'] == []


def test_code_changed_after_preparation_cannot_escape_stream(curated):
    env, instance = curated
    identity = call(instance, 'discover', {'kind': 'code', 'query': 'main'})['items'][0]['id']
    reply = instance._call_tool(1, 'code_query', {'operation': 'fetch', 'arguments': {'ids': [identity]}})
    (env.root / 'main.py').write_text('def changed(): return 3\n')
    stream = StringIO()
    instance._write(stream, reply)
    assert 'return 1' not in stream.getvalue()
    assert 'evidence_changed_before_delivery' in stream.getvalue()


@pytest.mark.parametrize('corruption', ['scope', 'source'])
def test_projection_rows_cannot_bypass_authority_or_source_integrity(curated, monkeypatch, corruption):
    env, instance = curated
    generation = instance.knowledge.current(str(env.root))
    changed = deepcopy(generation)
    identity = 'code:' + changed['objects'][0]['object_id']
    if corruption == 'scope':
        changed['objects'][0]['scope']['subject_id'] = 'foreign'
    else:
        import base64
        changed['source_bytes']['main.py'] = base64.b64encode(b'not the admitted source').decode()
    monkeypatch.setattr(instance.curation.knowledge, 'current', lambda root: changed)
    response = call(instance, 'fetch', {'ids': [identity]})
    assert response['items'][0]['status'] == 'withheld'
    assert 'not the admitted source' not in str(response)


def test_references_require_stream_delivery_session_epoch_and_explicit_opt_in(curated):
    env, instance = curated
    identity = call(instance, 'discover', {'kind': 'code', 'query': 'main'})['items'][0]['id']
    args = {'ids': [identity], 'session': 'session1', 'epoch': 'epoch1'}
    prepared = call(instance, 'fetch', args, write=False)
    known = [{'id': identity, 'version': prepared['items'][0]['version']}]
    refs = {**args, 'references': True, 'known': known}
    # Prepared-only evidence is not delivered.
    assert 'content' in call(instance, 'fetch', refs)['items'][0]
    assert call(instance, 'fetch', refs)['items'][0]['status'] == 'reference'
    assert 'content' in call(instance, 'fetch', args)['items'][0]
    for field in ['session', 'epoch']:
        assert 'content' in call(instance, 'fetch', {**refs, field: 'new'})['items'][0]
    fresh = CodeKnowledgeMCP(env.app, env.scope, str(env.root), experience=True, tool_profile='curated')
    assert 'content' in call(fresh, 'fetch', refs)['items'][0]
    assert call(instance, 'changes', refs)['items'][0]['status'] == 'reference'


@pytest.mark.parametrize('operation,args', [
    ('discover', {'root': '/other'}), ('discover', {'limit': True}),
    ('discover', {'kind': 'all'}), ('discover', {'budget': 255}),
    ('discover', {'query': '中' * 1334}), ('fetch', {'ids': []}),
    ('fetch', {'ids': ['code:x'], 'references': True}),
    ('fetch', {'ids': ['code:x'], 'known': [{'id': 'code:x', 'version': 'not-a-hash'}]}),
    ('fetch', {'ids': ['code:x', 'code:x']}), ('capabilities', {'root': 'other'}),
    ([], {}), ('run', {}),
])
def test_closed_contract_rejects_bad_inputs(curated, operation, args):
    _, instance = curated
    assert instance._call_tool(1, 'code_query', {'operation': operation, 'arguments': args})['result']['isError']


@pytest.mark.parametrize('budget', [256, 512, 1024])
def test_multibyte_response_fitting(budget):
    response = fit([{'title': '中文' * 100, 'id': str(i)} for i in range(8)], budget)
    assert len(encoded(response)) <= budget
    assert response.get('truncated') or response['status'] == 'withheld'


def test_capabilities_and_existing_profiles(curated):
    env, instance = curated
    result = call(instance, 'capabilities')
    assert result['learned_pruning'] is False and result['native_history_masking'] is False
    assert result['prompt_owner_masking_helper']
    assert [row['name'] for row in instance._tool_definitions()] == ['code_query']
    denied = CodeKnowledgeMCP(env.app, env.scope, str(env.root), experience=False, tool_profile='curated')
    execute(env)
    assert call(denied, 'discover', {'kind': 'experience'})['items'] == []
    from atmem.code.cli import add_commands
    parser = argparse.ArgumentParser()
    add_commands(parser, default_db='memory.db')
    assert parser.parse_args(['mcp-config', '--tool-profile', 'curated']).tool_profile == 'curated'
    assert parser.parse_args(['discover', 'main', '--kind', 'code']).kind == 'code'


def test_curated_discovery_cost_accounts_for_response_metadata(curated):
    _, instance = curated
    index = call(instance, 'discover', {'kind': 'code', 'query': 'main'})
    item = index['items'][0]
    detail = call(instance, 'fetch', {'ids': [item['id']]})
    assert item['estimated_detail_tokens'] >= len(encoded(detail))


def test_encrypted_metadata_is_screened_before_experience_index(curated):
    env, instance = curated
    result = execute(env)
    identity = result['experience_id']
    value = env.memory.store.code_document('local', env.project, 'code-experience', identity)
    assert value is not None
    secret = 'sk-proj-' + 'abcd1234' * 12
    value['proposal']['intent'] += ' API key: ' + secret
    env.memory.store.put_code_document('local', env.project, 'code-experience', identity, value)
    index = call(instance, 'discover', {'kind': 'experience'})
    assert index['items'] == [] and secret not in str(index)


def test_delivery_ledger_is_bounded_and_versions_are_not_authority():
    from atmem.code.evidence_ledger import EvidenceLedger
    ledger = EvidenceLedger(sessions=1, entries=1)
    ledger.delivered('session', 'epoch', [{'id': 'a', 'version': 'v1'}, {'id': 'b', 'version': 'v2'}])
    assert not ledger.has('session', 'epoch', 'a', 'v1')
    assert ledger.has('session', 'epoch', 'b', 'v2')
    ledger.delivered('other', 'epoch', [{'id': 'c', 'version': 'v3'}])
    assert not ledger.has('session', 'epoch', 'b', 'v2')


def test_dashboard_discovery_uses_same_scope_and_role_boundary(curated, monkeypatch):
    from atmem.code.dashboard import execute as dashboard
    from tests.test_code_dashboard import session
    from types import SimpleNamespace
    env, _ = curated
    class BorrowedMemory:
        def __getattr__(self, name):
            return getattr(env.memory, name)
        def close(self):
            pass
    monkeypatch.setattr('atmem.code.dashboard.Memory', lambda *a, **k: BorrowedMemory())
    manager = SimpleNamespace(state=lambda: None, _generic_memory_db=lambda state: ':memory:')
    body = {'action': 'discover', 'project_id': env.project, 'root': str(env.root),
            'arguments': {'kind': 'code', 'query': 'main'}}
    assert dashboard(manager, session('investigator'), body, read_only=True)['items']
    with pytest.raises(PermissionError):
        dashboard(manager, session('viewer'), body, read_only=True)
    with pytest.raises(PermissionError):
        dashboard(manager, session('investigator'), {**body, 'subject_id': 'other'}, read_only=True)
    with pytest.raises(PermissionError):
        dashboard(manager, session('investigator'), {'action': 'config', 'changes': {'context_mode': 'index'}})


def test_application_dispatch_and_retained_exact_response(curated):
    env, _ = curated
    args = {'kind': 'code', 'query': 'main'}
    result = env.app.dispatch('discover', {'project_id': env.project, 'root': str(env.root), 'arguments': args})
    assert result['items']
    evidence = env.memory.store.code_documents('local', env.project, 'curation-exposure')[-1]
    assert evidence['response'] == result and evidence['arguments'] == args
    assert evidence['assurance'] == 'prepared_only'


def test_equal_responses_do_not_mix_delivery_sessions(curated):
    _, instance = curated
    identity = call(instance, 'discover', {'kind': 'code', 'query': 'main'})['items'][0]['id']
    pending = []
    for session in ['first', 'second']:
        args = {'ids': [identity], 'session': session, 'epoch': 'epoch1'}
        pending.append(instance._call_tool(session, 'code_query', {'operation': 'fetch', 'arguments': args}))
    answers = [json.loads(reply['result']['content'][0]['text']) for reply in pending]
    assert answers[0]['items'] == answers[1]['items']
    assert answers[0]['receipt_id'] != answers[1]['receipt_id']
    instance._write(StringIO(), pending[0])
    known = [{key: answers[1]['items'][0][key] for key in ('id', 'version')}]
    args = {'ids': [identity], 'session': 'second', 'epoch': 'epoch1', 'known': known, 'references': True}
    # The second session has only prepared output, not a delivered response.
    assert 'content' in call(instance, 'fetch', args, write=False)['items'][0]


def test_masking_preserves_originals_instructions_pairs_and_errors():
    history = [{'role': 'system', 'content': 'policy'}, {'role': 'user', 'content': 'task'}]
    for i in range(4):
        history += [{'role': 'assistant', 'tool_calls': [{'id': str(i)}]},
                    {'role': 'tool', 'tool_call_id': str(i), 'content': 'output' + str(i)}]
    history[5]['unresolved_error'] = True
    original = deepcopy(history)
    retained = []
    def retain(row):
        retained.append(row)
        return 'evidence-' + row['tool_call_id']
    result = mask_observations(history, retain=retain, keep_last=1)
    assert history == original and retained[0]['content'] == 'output0'
    assert result['messages'][:2] == original[:2]
    assert result['messages'][5] == original[5] and result['messages'][-1] == original[-1]
    assert [row.get('tool_call_id') for row in result['messages']] == [row.get('tool_call_id') for row in original]
    assert len(result['masked']) == 2


def test_masking_retention_failure_preserves_original():
    history = [{'role': 'assistant', 'tool_calls': [{'id': str(i)}]} for i in range(2)]
    history += [{'role': 'tool', 'tool_call_id': str(i), 'content': 'exact'} for i in range(2)]
    before = deepcopy(history)
    with pytest.raises(ValueError):
        mask_observations(history, retain=lambda row: None, keep_last=1)
    assert history == before


@pytest.mark.parametrize('legacy', ['none', 'settings', 'installation'])
def test_fresh_setup_and_legacy_settings_are_not_silently_migrated(code_env, monkeypatch, legacy):
    from atmem.code.install import CodeInstall
    env = code_env
    if legacy == 'settings':
        env.app.settings(env.project, {'auto_recall': False})
    elif legacy == 'installation':
        env.memory.store.put_code_installation(subject_id='local', project_id=env.project, host='claude', enabled=False)
    monkeypatch.setattr(CodeInstall, 'doctor', lambda self, host: {'host': host})
    result = CodeInstall(env.memory.store).setup(env.root, subject_id='local', profile_id='shared', agent_id='codex', host='codex', apply=True)
    assert result['enabled'] is False
    settings = env.app.settings(env.project)
    assert settings['context_mode'] == ('index' if legacy == 'none' else 'content')
    if legacy == 'settings':
        assert settings['auto_recall'] is False


def test_index_turn_excludes_details_graph_and_delegated_provider(curated, monkeypatch):
    from atmem.code.contracts import CodeObservation, CodeContextRequest
    from atmem.code.runtime import CodeRuntime
    from atmem.code.service import CodeIntakeService
    from atmem.code.receipts import CodeReceipts
    env, _ = curated
    execute(env)
    env.app.settings(env.project, {'context_mode': 'index', 'auto_capture': False, 'context_tags': ['docs']})
    env.memory.store.put_code_installation(subject_id='local', project_id=env.project, host='codex', enabled=True)
    intake = CodeIntakeService(env.memory.store, scope=env.scope, host='codex', session_id='session1', secret=b'x' * 32, enabled=True)
    event = CodeObservation('turn-event', 'session1', 'turn1', 'codex', 'user_turn', 'main behavior',
                            '2026-10-19T10:00:00Z', 'test:user', None, env.scope)
    request = CodeContextRequest('index-request', 'session1', 'turn1', 'main behavior', 4096, env.scope)
    monkeypatch.setattr('atmem.code.providers.CodeRouter.prepare', lambda *a, **k: pytest.fail('index mode delegated automatic content'))
    result = CodeRuntime(env.memory, intake).on_user_turn(request, event, intake.sign(event), repository_root=str(env.root))
    text = result['context'].content
    assert 'unchecked' in text and 'observation' not in json.loads(text)['items'][0]
    assert 'bounded command result' not in text and 'def main' not in text
    assert len(text.encode()) <= 1024
    # Index metadata is historical; source changes do not falsely claim currency.
    (env.root / 'main.py').write_text('def changed(): pass\n')
    receipt = CodeReceipts(env.memory.store).submitted(request, result['context'], host='codex')
    assert receipt['presentation'] == 'unchecked_experience_index'
    env.memory.store.set_code_installation_enabled(subject_id='local', project_id=env.project, host='codex', enabled=False)
    paused = CodeRuntime(env.memory, intake).on_user_turn(replace(request, request_id='paused'), event, intake.sign(event), repository_root=str(env.root))
    assert paused['context'].content == '' and paused['formation'] == []


def test_goal_selects_exact_later_source_lines_without_neural_model(curated):
    env, instance = curated
    lines = ['def main():'] + ['    value = ' + str(i) for i in range(80)] + ['    return value  # final_result']
    (env.root / 'main.py').write_text('\n'.join(lines) + '\n')
    CodeKnowledge(env.app, env.scope).index(str(env.root), FixtureWorker())
    identity = call(instance, 'discover', {'query': 'main', 'kind': 'code'})['items'][0]['id']
    detail = call(instance, 'fetch', {'ids': [identity], 'goal': 'final_result'})['items'][0]
    assert 'final_result' in detail['content'] and detail['omitted']
    assert detail['content'] == '\n'.join(lines[detail['start_line'] - 1:detail['end_line']])


def test_qualification_has_no_model_and_keeps_original_responses(curated):
    from tools.qualify_code_curation import qualify
    env, instance = curated
    result = qualify(instance, 'main')
    assert result['status'] == 'passed' and result['model_calls'] == 0
    assert len(result['measurements']) == 5
    receipts = env.memory.store.code_documents('local', env.project, 'curation-exposure')
    assert len(receipts) == 5 and all('delivered_response' in row for row in receipts)
    for row in receipts:
        envelope = json.loads(row['delivered_wire'])
        assert json.loads(envelope['result']['content'][0]['text']) == row['delivered_response']


def test_v3_bundle_preserves_curation_evidence_and_no_delivery_cache(curated, tmp_path):
    from atmem.code.portable import CodePortable, FORMAT_V3
    from atmem.code.application import CodeApplication
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
    from atmem.memory import Memory
    env, instance = curated
    call(instance, 'discover', {'query': 'main', 'kind': 'code'})
    env.app.settings(env.project, {'context_mode': 'index'})
    public, secret = generate_recipient_keypair()
    signer, signing_secret = generate_signing_keypair()
    portable = CodePortable(env.app)
    sealed = portable.export(env.project, recipient_public_key=public, signing_public_key=signer, signing_secret_key=signing_secret)
    opened = portable.open(sealed, recipient_secret_key=secret, trusted_signing_public_key=signer)
    assert opened['manifest']['format'] == FORMAT_V3
    assert opened['state']['documents']['curation-exposure'][0]['value']['delivered_response']['items']
    target = Memory(':memory:', auto_vectors=False)
    try:
        new = CodePortable(CodeApplication(target, subject_id='local'))
        root = tmp_path / 'clone'
        root.mkdir()
        preview = new.preview(opened, root=str(root))
        assert new.restore(opened, root=str(root), preview_token=preview['preview_token'])['imported']
        assert target.store.code_documents('local', env.project, 'curation-exposure') == env.memory.store.code_documents('local', env.project, 'curation-exposure')
    finally:
        target.close()


@pytest.mark.skipif(os.name == 'nt' or os.environ.get('ATMEM_CODE_SKIP_HOST_PROBES') == '1',
                   reason='actual Claude hook qualification is separate from portable core; Windows automatic hook is unsupported')
def test_installed_claude_receives_experience_index_without_detail(tmp_path):
    """Actual host + local fixture endpoint, not a paid/model efficacy run."""
    if not shutil.which('claude'):
        pytest.skip('Claude CLI not installed')
    from atmem.code.application import CodeApplication
    from atmem.code.identity import CodeIdentity
    from atmem.code.install import CodeInstall
    from atmem.code.adapters.claude import ClaudeAdapter
    from atmem.code.adapters.probe import claude_probe
    from atmem.code.execution import run_command
    from atmem.evidence.crypto import load_existing_key
    from atmem.memory import Memory
    from atmem.service.household import HouseholdApplication
    from types import SimpleNamespace
    import shlex
    database = tmp_path / 'memory.db'
    HouseholdApplication.initialize(database, encrypted=True)
    root = tmp_path / 'repo'
    root.mkdir()
    memory = Memory(database, auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(root, subject_id='local', profile_id='shared', agent_id='claude')
        app = CodeApplication(memory, subject_id='local')
        env = SimpleNamespace(memory=memory, root=root, app=app, scope=scope, project=scope.project_id)
        init_repository(env)
        run_command(app, scope, str(root), [sys.executable, '-c', 'print("private detail not for automatic context")'],
                    intent='Check main behavior', anchors=['main.py'])
        app.settings(scope.project_id, {'context_mode': 'index'})
        installer = CodeInstall(memory.store)
        installer.setup(root, subject_id='local', profile_id='shared', agent_id='claude', host='claude', apply=True)
        active = installer.enable(project=root, subject_id='local', host='claude')
        assert active['enabled']
        command = json.loads((root / '.claude/settings.local.json').read_text())['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']
        argv = shlex.split(command)
        probe = claude_probe(store=memory.store, subject='local', project=scope.project_id, root=root,
            credential=load_existing_key(argv[argv.index('--credential-file') + 1]),
            initial=ClaudeAdapter(root, command).probe(), command=command, canary_mode=False,
            prompt_override='How does main behavior work?', expected_context='unchecked')
        assert probe.automatic and probe.assurance == 'model_input_observed'
        contexts = memory.store.code_documents('local', scope.project_id, 'exposure')
        bodies = [row['package']['content'] for row in contexts if row.get('presentation') == 'unchecked_experience_index']
        assert any('Check main behavior' in body for body in bodies)
        assert all('private detail not for automatic context' not in body for body in bodies)
    finally:
        memory.close()
