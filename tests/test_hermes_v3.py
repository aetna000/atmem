"""Product V3 binding qualification; fixture facts are not benchmark scores."""
from dataclasses import replace

import pytest

from atmem.adapters.hermes.client import HermesRPCClient
from atmem.adapters.hermes.service import HermesService
from atmem.control import ControlPlaneManager
from atmem.memory import Memory
from atmem.service import APIError, APIPrincipal


def test_public_memory_discovery_keeps_encrypted_authority_and_revocation(v3):
    from atmem.context_engine.contracts import ContextRequestV3
    from atmem.context_engine.navigator import NavigationBudget
    service,admin,grant=v3
    observe(v3)
    service.freeze_memory(admin,grant['binding']['binding_id'])
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    binding=service._binding(service._authenticate(grant['credential']))
    enabled=[True]
    with binding.v3().memory() as (memory,scope):
        generation=memory.context_generation(scope)
        request=ContextRequestV3(context_id='investigation',request_id='request',scope=scope,
            query='deployment channel',profile_id='context-fast',generation=generation['canonical_generation'],
            turn_id='turn',mode='active')
        session=memory.open_evidence_discovery(request,authorize=lambda r:enabled[0],
            budget=NavigationBudget(4,20000,10000))
        value=session.search('deployment channel')
        assert value['evidence'] and '#engineering' in str(value)
        assert value['sufficiency']=='not_assessed'
        enabled[0]=False
        with pytest.raises(PermissionError):session.inspect(value['evidence'][0]['unit_id'])
    service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)


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


def _initial_interpretation_fixture(evidence):
    return {'format':'atbot-source-state-assessment-v1',
        'rows':[{'unit_id':evidence[0]['unit_id'],'quote':evidence[0]['text'],
                 'applicability':'current_at_query','stage':'standing_rule'}],
        'unresolved_needs':[], 'assurance':'model_interpreted',
        'canonical_storage':False,'authority_decision':None,
        'provider':'fixture','model':'fixture','input_tokens':1,'output_tokens':1}


def test_initial_assessment_is_explicit_uses_initial_sources_and_keeps_checkpoint(v3):
    service,admin,grant=v3
    observe(v3)
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    original=recall(v3)
    calls=[]
    def assessor(query,evidence):
        calls.append((query,evidence));return _initial_interpretation_fixture(evidence)
    with pytest.raises(ValueError,match='explicit egress'):
        HermesService(service.manager,initial_state_assessor=assessor)
    selected=HermesService(service.manager,initial_state_assessor=assessor,
                          allow_remote_initial_assessment=True)
    value=recall((selected,admin,grant))
    assert len(calls)==1 and value['context'].endswith(original['context'])
    assert all('source_id' in row['source_range'] for row in calls[0][1])
    assert value['context_receipt_id'].startswith('prepare:initial-source-state:')
    assert value['profile'].endswith('-initial-source-state-v1')
    selected.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)
    assert recall(v3)['context']==original['context']


def test_initial_assessment_revoke_during_provider_returns_no_context(v3):
    service,admin,grant=v3
    observe(v3);service.freeze_memory(admin,grant['binding']['binding_id'])
    def assessor(query,evidence):
        service.configure(admin,grant['binding']['binding_id'],enabled=False)
        return _initial_interpretation_fixture(evidence)
    selected=HermesService(service.manager,initial_state_assessor=assessor,
                          allow_remote_initial_assessment=True)
    try:
        value=recall((selected,admin,grant))
    except APIError:
        pass
    else:
        assert not value['context']


def test_source_dossier_profile_uses_product_receipts_and_preserves_originals(v3):
    service,admin,grant=v3
    observe(v3)
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    supplied=[]
    def assessor(query,evidence):
        supplied.extend(evidence)
        return {'format':'atbot-source-dossier-v1','needs':[{
            'need':'Deployment channel','quotes':[{'unit_id':evidence[0]['unit_id'],
                                                 'quote':evidence[0]['text']}]}],
            'unresolved_needs':[],'assurance':'model_selected_source_quotes',
            'canonical_storage':False,'authority_decision':None,
            'provider':'fixture','model':'fixture','input_tokens':1,'output_tokens':1}
    selected=HermesService(service.manager,initial_state_assessor=assessor,
        allow_remote_initial_assessment=True,initial_state_presentation='dossier')
    value=recall((selected,admin,grant))
    assert value['reason']=='authorized' and value['profile']=='authorized-source-dossier-v1'
    assert list(value['candidate_ids'])==[supplied[0]['unit_id']]
    assert '#engineering' in value['context'] and 'not_assessed' in value['context']
    assert len(value['context'].encode())<=16000
    selected.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)
    assert '#engineering' in recall(v3)['context']


def test_v3_source_identity_conflicts_and_secret_screening(v3):
    service, admin, grant = v3
    observe(v3)
    with pytest.raises(APIError, match='inspect the observation'):
        observe(v3, 'A different message using the same identity.')
    result = observe(v3, 'password: fixture-secret-not-for-retention', 'secret')
    assert not result['captured'] and not result['memory_mutated']
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    assert checkpoint['canonical']['context_engine']['tables']['context_source_episodes']['rows'] == 1


def test_explicit_engine_uses_same_memory_authority_and_preserves_default(v3):
    from atmem.context_engine.contracts import ContextRequestV3
    from atmem.context_engine.service import StoredContextEngine
    service, admin, grant = v3
    observe(v3)
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    binding = service._binding(service._load(grant['binding']['binding_id']))
    with binding.v3().memory() as (memory, scope):
        generation = memory.context_generation(scope)
        calls = []
        class Explicit(StoredContextEngine):
            def select(self, request, manifest):
                calls.append(manifest)
                return super().select(request, manifest)
        request = ContextRequestV3(context_id='ctx', request_id='req', scope=scope,
            query='What is the deployment channel?', profile_id='context-fast',
            generation=generation['canonical_generation'], turn_id='turn', mode='active')
        default = memory.prepare_context_v3(request)
        selected = memory.prepare_context_v3(request,
            engine=Explicit(memory.store, generation_id=generation['generation_id']))
        assert default.context == selected.context
        assert calls[0].scope == scope
    service.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)


@pytest.mark.parametrize('table,column,value', [
    ('context_semantic_indexes_v1', 'config', 'tampered'),
    ('context_semantic_buckets_v1', 'bucket', 123456),
])
def test_optional_semantic_metadata_is_scoped_exported_and_checkpointed(v3, tmp_path, table, column, value):
    import json
    from atmem.context_engine.semantic import SemanticIndex
    service, admin, grant = v3
    formation = observe(v3)['formation']
    binding = service._binding(service._load(grant['binding']['binding_id']))
    with binding.v3().memory() as (memory, _):
        generation = formation['generation_id']
        identity = memory.store._conn.execute(
            'SELECT unit_id FROM context_evidence_units WHERE generation_id=? LIMIT 1',
            (generation,)).fetchone()[0]
        index = SemanticIndex(memory.store, generation_id=generation,
            model_identity={'model': 'fixture', 'revision': 'fixed'}, dimensions=3)
        index.build([(identity, [1, 0, 0])], allowed_unit_ids=frozenset([identity]))
    checkpoint = service.freeze_memory(admin, grant['binding']['binding_id'])
    context = checkpoint['canonical']['context_engine']
    assert context['format'] == 'atmem-hermes-context-v3-checkpoint-v2'
    assert context['tables']['context_semantic_indexes_v1']['rows'] == 1
    assert context['tables']['context_semantic_buckets_v1']['rows'] == 8
    destination = tmp_path/'authorized-export.jsonl'
    receipt = binding.v3().export(destination, actor='operator')
    assert receipt['format'] == 'atmem-context-v3-export-receipt-v2'
    exported = [json.loads(line) for line in destination.read_text().splitlines()]
    assert exported[0]['format'] == 'atmem-context-v3-export-v2'
    assert sum(row.get('table') == 'context_semantic_indexes_v1' for row in exported) == 1
    assert sum(row.get('table') == 'context_semantic_buckets_v1' for row in exported) == 8
    with binding.v3().memory() as (memory, _):
        memory.store._conn.execute(f'UPDATE {table} SET {column}=?', (value,))
    with pytest.raises(ValueError, match='mismatch'):
        service.verify_memory_checkpoint(admin, grant['binding']['binding_id'], checkpoint)


def test_optional_semantic_incomplete_schema_fails_closed(v3):
    service, admin, grant = v3
    observe(v3)
    binding = service._binding(service._load(grant['binding']['binding_id']))
    with binding.v3().memory() as (memory, _):
        memory.store._conn.execute('CREATE TABLE context_semantic_indexes_v1(unused TEXT)')
    with pytest.raises(ValueError, match='incomplete semantic metadata'):
        service.freeze_memory(admin, grant['binding']['binding_id'])


def test_application_engine_factory_reaches_native_recall_without_client_override(v3):
    from atmem.context_engine.service import balanced_context_engine
    service,admin,grant=v3
    observe(v3)
    service.freeze_memory(admin,grant['binding']['binding_id'])
    calls=[]
    def factory(store,generation_id):
        calls.append(generation_id)
        return balanced_context_engine(store,generation_id)
    configured=HermesService(service.manager,context_engine_factory=factory)
    response=configured.dispatch(grant['credential'],'recall',{
        'query':'What is the deployment channel?','session_id':'s','turn_id':'t'})
    assert calls
    assert response['reason']=='authorized'
    assert '#engineering' in response['context']
    with pytest.raises(ValueError):
        configured.dispatch(grant['credential'],'recall',{
            'query':'q','session_id':'s','turn_id':'t','context_engine_factory':'client-supplied'})


def test_source_coherent_cache_is_encrypted_scope_bound_and_does_not_mutate_source(v3,tmp_path):
    pytest.importorskip('sqlite_vec')
    from atmem.context_engine.contracts import ContextRequestV3
    from atmem.context_engine.part_semantic import SourcePartSemanticIndex
    from atmem.context_engine.service import stored_manifest
    service,admin,grant=v3
    observe(v3)
    checkpoint=service.freeze_memory(admin,grant['binding']['binding_id'])
    binding=service._binding(service._load(grant['binding']['binding_id']))
    documents=[]
    class LocalFixtureEmbedder:
        identity={'model':'fixture','revision':'pinned','endpoint':'http://127.0.0.1:11434','truncate':False}
        def verify_identity(self): pass
        def embed_documents(self,texts):
            documents.extend(texts)
            return [[1.,0.,0.] for _ in texts]
        def embed_query(self,text):return [1.,0.,0.]
    embedder=LocalFixtureEmbedder()
    with binding.v3().memory() as (memory,scope):
        gen=memory.context_generation(scope)
        path=tmp_path/(gen['generation_id']+'.db')
        request=ContextRequestV3(context_id='c',request_id='r',scope=scope,query='fixture',
            profile_id='context-fast',mode='active',generation=gen['canonical_generation'],turn_id='t')
        manifest=stored_manifest(memory.store,request,generation_id=gen['generation_id'])
        index=SourcePartSemanticIndex(memory.store,generation_id=gen['generation_id'],
            manifest=manifest,path=path,model_identity=embedder.identity)
        try:
            assert index.build(embedder)['vectors']>0
            assert '#engineering' in ''.join(documents)
            hits=index.nominate([1,0,0],allowed_unit_ids=frozenset(manifest.authorized_unit_ids))
            assert hits and {h.unit_id for h in hits} <= set(manifest.authorized_unit_ids)
            with pytest.raises(ValueError,match='authorization'):
                index.nominate([1,0,0],allowed_unit_ids=frozenset())
        finally:index.close()
        from atmem.context_engine.part_semantic import SourceCoherentHybridFactory
        request=replace(request,query='What is the deployment channel?')
        factory=SourceCoherentHybridFactory(directory=tmp_path,embedder=embedder)
        result=memory.prepare_context_v3(request,engine=factory(memory.store,gen['generation_id']))
        assert result.status=='sufficient'
        assert '#engineering' in result.context
    assert path.read_bytes()[:16]!=b'SQLite format 3\x00'
    assert b'#engineering' not in path.read_bytes()
    service.verify_memory_checkpoint(admin,grant['binding']['binding_id'],checkpoint)


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
    ('authorized-source-dossier-v1', '文' * 5333, True),
    ('authorized-source-dossier-v1', '文' * 5334, False),
    ('authorized-at-recall-context-v3-initial-source-state-v1', '文' * 13_333, True),
    ('authorized-at-recall-context-v3-initial-source-state-v1', '文' * 13_334, False),
    ('authorized-at-recall-context-v3', '文' * 10_000, True),
    ('authorized-at-recall-context-v3', '文' * 10_667, False),
    ('authorized-at-recall-v1', 'x' * 4097, False),
    ('unknown-profile', 'x' * 5000, False),
],ids=lambda value: f'{len(value.encode())}-utf8-bytes' if isinstance(value,str) and len(value)>120 else None)
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
