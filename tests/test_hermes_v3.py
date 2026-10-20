"""Product V3 binding qualification; fixture facts are not benchmark scores."""
from dataclasses import replace

import pytest

from atmem.adapters.hermes.client import HermesRPCClient
from atmem.adapters.hermes.service import HermesService
from atmem.control import ControlPlaneManager
from atmem.memory import Memory
from atmem.service import APIError, APIPrincipal


@pytest.fixture
def v3(tmp_path, monkeypatch):
    pytest.importorskip('sqlcipher3', reason='V3 history import requires encrypted household support')
    from atmem.service.household import HouseholdApplication
    HouseholdApplication.initialize(tmp_path / 'memory.db', encrypted=True, backend='file')
    manager = ControlPlaneManager.start(host='generic', state_path=tmp_path / 'state.json',
        control_root=tmp_path / 'control', memory_db=tmp_path / 'memory.db')
    workspace = manager.agent_topology()['workspaces'][0]
    admin = APIPrincipal('operator', 'admin', workspace['subject_id'])
    service = HermesService(manager)
    grant = service.provision(admin, profile_id='v3-fixture', agent_id='main',
        workspace_id=workspace['workspace_id'], accept_reduced_capture=True,
        memory_engine='context-v3', authorize_history_import=True)
    service.configure(admin, grant['binding']['binding_id'], enabled=True)
    manager.activate()
    def no_legacy(*args, **kwargs):
        raise AssertionError('V3 must not consult legacy capture/prepare')
    monkeypatch.setattr(manager, 'capture', no_legacy)
    monkeypatch.setattr(manager, 'prepare', no_legacy)
    return service, admin, grant


def observe(state, text='The deployment channel is #engineering.', observation='one'):
    service, _, grant = state
    return service.dispatch(grant['credential'], 'observe',
        {'text': text, 'session_id': 'session', 'observation_id': observation})


def recall(state, query='What is the deployment channel?'):
    service, _, grant = state
    return service.dispatch(grant['credential'], 'recall',
        {'query': query, 'session_id': 'new-session', 'turn_id': 'turn'})


def test_v3_requires_explicit_scoped_administrator_authority(v3):
    service, admin, grant = v3
    arguments = dict(profile_id='other', agent_id='main', workspace_id='other',
                     accept_reduced_capture=True, memory_engine='context-v3')
    with pytest.raises(PermissionError, match='explicit administrator'):
        service.provision(admin, **arguments)
    with pytest.raises(APIError):
        service.provision(replace(admin, role='agent'), **arguments,
                          authorize_history_import=True)
    with pytest.raises(ValueError):
        service.dispatch(grant['credential'], 'observe',
            {'text': 'x', 'session_id': 's', 'observation_id': 'o', 'memory_engine': 'context-v3'})


def test_v3_source_formation_and_frozen_recall_use_public_core(v3, monkeypatch):
    service, admin, grant = v3
    assert recall(v3)['reason'] == 'history_not_frozen'
    first = observe(v3)
    assert first['formation']['representation_complete']
    assert first['formation']['units_created'] > 0
    observe(v3)  # Same stable source is retry-safe.
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    tables = checkpoint['canonical']['context_engine']['tables']
    assert tables['context_source_episodes']['rows'] == 1
    assert tables['context_evidence_units']['rows'] > 0
    calls = []
    original = Memory.prepare_context_v3
    def prepare(memory, request):
        calls.append(request)
        return original(memory, request)
    monkeypatch.setattr(Memory, 'prepare_context_v3', prepare)
    result = recall(v3)
    assert '#engineering' in result['context']
    assert result['profile'] == 'authorized-at-recall-context-v3'
    assert calls[0].profile_id == 'context-fast'
    assert calls[0].budget.total_candidates == 200
    assert calls[0].budget.context_bytes == 32000
    assert observe(v3, 'The deployment channel is #elsewhere.', 'two')['reason'] == 'memory_frozen'
    service.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)
    restarted = HermesService(ControlPlaneManager(service.manager.state_path))
    restarted.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)
    assert restarted.dispatch(grant['credential'], 'status', {})['memory_engine'] == 'context-v3'


def test_v3_source_identity_conflicts_and_secret_screening(v3):
    service, admin, grant = v3
    observe(v3)
    with pytest.raises(APIError, match='inspect the observation'):
        observe(v3, 'A different message using the same identity.')
    result = observe(v3, 'password: fixture-secret-not-for-retention', 'secret')
    assert not result['captured'] and not result['memory_mutated']
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    assert checkpoint['canonical']['context_engine']['tables']['context_source_episodes']['rows'] == 1


@pytest.mark.parametrize('table,column,value', [
    ('context_source_parts', 'content_bytes', b'tampered fixture source'),
    ('context_evidence_units', 'compact_json', '{"tampered":true}'),
    ('context_evidence_units', 'lifecycle', 'deleted'),
    ('context_view_generations', 'configuration_sha256', 'tampered'),
])
def test_v3_checkpoint_detects_out_of_band_evidence_changes(v3, table, column, value):
    service, admin, grant = v3
    observe(v3)
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    binding = service._binding(service._load(grant['binding']['binding_id']))
    with binding.v3().memory() as (memory, _):
        # Only fixed fixture identifiers above reach this SQL, not user input.
        memory.store._conn.execute(f'UPDATE {table} SET {column}=?', (value,))
    with pytest.raises(ValueError, match='mismatch'):
        service.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)


@pytest.mark.parametrize('profile,context,accepted', [
    ('authorized-at-recall-context-v3', '文' * 10_000, True),
    ('authorized-at-recall-context-v3', '文' * 10_667, False),
    ('authorized-at-recall-v1', 'x' * 4097, False),
    ('unknown-profile', 'x' * 5000, False),
])
def test_rpc_v3_budget_is_explicit_utf8_and_never_truncated(monkeypatch, profile, context, accepted):
    client = HermesRPCClient('http://127.0.0.1:8768', 'hermes_test.value', profile_id='fixture')
    monkeypatch.setattr(client, '_call', lambda *a, **k: {
        'context': context, 'candidate_ids': [], 'reason': 'authorized', 'profile': profile})
    for result in (client.recall('q', session_id='s', turn_id='t'),
        client.prepare_turn('q', session_id='s', turn_id='t', model='fixture',
                            platform='cli', prompt_sha256='a'*64, prompt_chars=1)):
        assert result.context == (context if accepted else '')


def test_v3_shadow_and_control_mode_do_not_disclose_context(v3):
    service, admin, grant = v3
    observe(v3)
    service.freeze_memory(admin, grant['binding']['binding_id'])
    service.configure_mode(admin, grant['binding']['binding_id'], mode='shadow')
    assert recall(v3)['context'] == ''
    service.configure_mode(admin, grant['binding']['binding_id'], mode='active')
    service.manager.deactivate()
    assert recall(v3)['context'] == ''


def test_v3_export_preserves_actual_source_and_requires_admin(v3, tmp_path):
    import base64
    import json
    service, admin, grant = v3
    text = 'The deployment channel is #engineering.'
    observe(v3, text)
    destination = tmp_path / 'history.jsonl'
    with pytest.raises(APIError):
        service.export_context_memory(replace(admin, role='agent'), grant['binding']['binding_id'], destination)
    assert not destination.exists()
    receipt = service.export_context_memory(admin, grant['binding']['binding_id'], destination)
    rows = [json.loads(line) for line in destination.read_text().splitlines()]
    parts = [row['row'] for row in rows[1:] if row['table'] == 'context_source_parts']
    assert len(parts) == 1
    assert base64.b64decode(parts[0]['content_bytes']['base64']).decode() == text
    assert receipt['rows'] == len(rows) - 1
    assert grant['credential'] not in destination.read_text()
