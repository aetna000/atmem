"""Navigation contract/authority fixtures, not coding-efficacy evidence."""
from copy import deepcopy
import json
from io import StringIO
from dataclasses import replace

import pytest

from atmem.code.discovery import Discovery, DiscoveryRequest, REQUEST, ITEM_FIELDS
from atmem.code.curation import encoded
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.code.mcp import CodeKnowledgeMCP
from tests.test_knowledge_lifecycle import init_repository, FixtureWorker


def request(**updates):
    return {'format': REQUEST, 'request_id': 'request-01', 'turn_id': 'turn-01',
            'query': 'main implementation', 'limit': 5, 'budget': 4096, **updates}


@pytest.fixture
def discovery(code_env):
    init_repository(code_env)
    code_env.memory._allow_insecure_typed_development = True
    CodeKnowledge(code_env.app, code_env.scope).index(str(code_env.root), FixtureWorker())
    return code_env, Discovery(code_env.app, code_env.scope, str(code_env.root))


@pytest.mark.parametrize('updates', [
    {'format': 'unknown'}, {'root': '/etc'}, {'backend': 'remote'}, {'query': ''},
    {'query': '中' * 1400}, {'limit': True}, {'limit': 0}, {'limit': 9},
    {'budget': False}, {'budget': 511}, {'budget': 8193}, {'budget': float('nan')},
    {'request_id': '../escape'}, {'turn_id': None}, {'operation': 'exact_search'},
])
def test_invalid_input_never_invokes_backend(discovery, monkeypatch, updates):
    _, service = discovery
    seen = []
    monkeypatch.setattr(service.curation, 'prepare', lambda *a: seen.append(a))
    with pytest.raises((ValueError, PermissionError)):
        service.prepare(request(**updates))
    assert seen == []


def test_request_roundtrip_and_closed_contract():
    assert DiscoveryRequest.from_dict(request()).to_dict() == request()
    with pytest.raises(ValueError):
        DiscoveryRequest.from_dict({k: v for k, v in request().items() if k != 'turn_id'})


def test_one_selected_backend_and_no_source_or_experience(discovery, monkeypatch):
    env, service = discovery
    seen = []
    original = service.curation.prepare
    def observed(operation, arguments):
        seen.append((operation, deepcopy(arguments)))
        return original(operation, arguments)
    monkeypatch.setattr(service.curation, 'prepare', observed)
    result = service.prepare(request())
    assert len(seen) == 1 and seen[0][0] == 'discover' and seen[0][1]['kind'] == 'code'
    assert result['items'] and result['non_exhaustive']
    assert set(result['items'][0]) == set(ITEM_FIELDS)
    assert result['items'][0]['location']['path'] == 'main.py'
    assert 'return 1' not in json.dumps(result) and 'content' not in result['items'][0]
    assert result['native_fallback'] == 'unknown' and result['assurance'] == 'prepared_only'
    assert len(encoded(result)) <= 4096
    exposures = env.app.store.code_document_items(env.scope.subject_id, env.project, 'curation-exposure')
    assert len(exposures) == 1
    assert exposures[0]['value']['navigation_request'] == request()


def test_delivery_revalidates_and_retains_exact_navigation_wire(discovery):
    env, service = discovery
    prepared = service.prepare(request())
    final = service.for_delivery(prepared)
    wire = json.dumps(final) + '\n'
    service.written(prepared, final, wire=wire)
    row = env.app.store.code_document_items(env.scope.subject_id, env.project, 'curation-exposure')[0]['value']
    assert row['navigation_delivered'] == final and row['delivered_wire'] == wire
    assert 'not_model_acknowledged' in row['navigation_assurance']
    assert not service.pending and not service.curation.pending


def test_edit_between_preparation_and_delivery_withholds(discovery):
    env, service = discovery
    prepared = service.prepare(request())
    (env.root / 'main.py').write_text('def main(): return 2\n')
    final = service.for_delivery(prepared)
    assert final['status'] == 'withheld' and final['items'] == []
    assert final['reason'] == 'evidence_changed_before_delivery'


def test_no_match_does_not_claim_current_coverage(discovery):
    _, service = discovery
    result = service.prepare(request(query='zzznomatch'))
    assert result['items'] == [] and result['non_exhaustive']
    assert result['freshness'] == 'not_established'


def test_small_budget_and_max_ids_are_bounded(discovery):
    _, service = discovery
    result = service.prepare(request(request_id='r' * 128, turn_id='t' * 128, budget=512))
    assert len(encoded(result)) <= 512


def test_small_budget_projects_before_discarding_candidate_metadata(discovery):
    _, service = discovery
    result = service.prepare(request(budget=1000))
    assert result['items'] and result['freshness'] == 'current_at_preparation'
    assert len(encoded(result)) <= 1000
    assert service.for_delivery(result) == result


def test_mcp_shapes_query_only_request_and_keeps_portable_contract(discovery):
    env, _ = discovery
    server = CodeKnowledgeMCP(env.app, env.scope, str(env.root), tool_profile='navigation')
    schema = server._tool_definitions()[0]['inputSchema']
    assert schema['required'] == ['query']
    assert set(schema['properties']) == {'query', 'limit', 'budget'}
    result = server.query('repository_discover', {'query': 'main', 'budget': 1000})
    assert result['items'] and len(encoded(result)) <= 1000
    assert result['request_id'] and result['turn_id']
    legacy = server.query('repository_discover', request())
    assert legacy['request_id'] == 'request-01'


@pytest.mark.parametrize('arguments,field', [
    ({'query': 'main', 'budget': 3}, 'budget'),
    ({'query': 'main', 'limit': True}, 'limit'),
    ({'query': ''}, 'query'),
    ({'query': 'main', 'root': '/etc'}, 'arguments'),
])
def test_mcp_navigation_errors_are_actionable_and_do_not_echo_values(discovery, monkeypatch, arguments, field):
    env, _ = discovery
    server = CodeKnowledgeMCP(env.app, env.scope, str(env.root), tool_profile='navigation')
    monkeypatch.setattr(server.navigation, 'prepare', lambda *a: pytest.fail('invalid call reached backend'))
    reply = server._call_tool(1, 'repository_discover', arguments)['result']
    assert reply['isError']
    error = json.loads(reply['content'][0]['text'])
    assert error['field'] == field and error['error'] == 'invalid_argument'
    assert '/etc' not in reply['content'][0]['text']


def test_pending_duplicate_does_not_repeat_backend(discovery, monkeypatch):
    _, service = discovery
    service.prepare(request())
    monkeypatch.setattr(service.curation, 'prepare', lambda *a: pytest.fail('duplicate reached backend'))
    with pytest.raises(ValueError, match='pending'):
        service.prepare(request())


def test_unvalidated_or_tampered_output_cannot_be_reported_written(discovery):
    _, service = discovery
    prepared = service.prepare(request())
    with pytest.raises(ValueError, match='revalidated'):
        service.written(prepared, prepared, wire='not written')
    final = service.for_delivery(prepared)
    with pytest.raises(ValueError, match='revalidated'):
        service.written(prepared, {**final, 'source_body': 'injected'}, wire='not written')


def test_failure_does_not_try_another_provider(discovery, monkeypatch):
    _, service = discovery
    seen = []
    def fail(*args):
        seen.append(args)
        raise PermissionError('authority refused')
    monkeypatch.setattr(service.curation, 'prepare', fail)
    with pytest.raises(PermissionError):
        service.prepare(request())
    assert len(seen) == 1 and not service.pending


def test_mcp_navigation_exposes_only_discovery_and_retains_written_wire(discovery):
    env, _ = discovery
    server = CodeKnowledgeMCP(env.app, env.scope, str(env.root), tool_profile='navigation')
    assert [t['name'] for t in server._tool_definitions()] == ['repository_discover']
    reply = server._call_tool(1, 'repository_discover', request())
    assert not reply['result']['isError']
    stream = StringIO()
    server._write(stream, reply)
    final = json.loads(json.loads(stream.getvalue())['result']['content'][0]['text'])
    assert final['items'] and 'return 1' not in stream.getvalue()
    row = env.app.store.code_document_items(env.scope.subject_id, env.project, 'curation-exposure')[0]['value']
    assert json.loads(row['delivered_wire']) == json.loads(stream.getvalue())
    assert row['navigation_delivered'] == final


def test_mcp_edits_before_write_cannot_emit_old_location(discovery):
    env, _ = discovery
    server = CodeKnowledgeMCP(env.app, env.scope, str(env.root), tool_profile='navigation')
    reply = server._call_tool(1, 'repository_discover', request())
    (env.root / 'main.py').write_text('def replaced(): return 4\n')
    stream = StringIO()
    server._write(stream, reply)
    final = json.loads(json.loads(stream.getvalue())['result']['content'][0]['text'])
    assert final['status'] == 'withheld' and not final['items']


def test_other_scope_cannot_retrieve_shared_code_projection(discovery):
    env, _ = discovery
    other = Discovery(env.app, replace(env.scope, profile_id='private', agent_id='claude'), str(env.root))
    assert not other.prepare(request())['items']


def test_governed_exposure_deletion_prevents_delivery(discovery):
    env, service = discovery
    prepared = service.prepare(request())
    env.app.store.delete_code_documents(env.scope.subject_id, env.project, 'curation-exposure')
    with pytest.raises(PermissionError):
        service.for_delivery(prepared)


def test_secret_query_rejected_before_backend(discovery, monkeypatch):
    _, service = discovery
    monkeypatch.setattr(service.curation, 'prepare', lambda *a: pytest.fail('secret reached backend'))
    with pytest.raises(PermissionError):
        service.prepare(request(query='my API key is sk-proj-' + 'abcd1234' * 12))


def test_unknown_mcp_tool_cannot_fetch_source(discovery):
    env, _ = discovery
    server = CodeKnowledgeMCP(env.app, env.scope, str(env.root), tool_profile='navigation')
    result = server._call_tool(1, 'code_source', {'path': 'main.py'})
    assert 'error' in result


def test_navigation_evidence_roundtrips_existing_encrypted_bundle(discovery, tmp_path):
    from atmem.code.portable import CodePortable, FORMAT_V3
    from atmem.code.application import CodeApplication
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
    from atmem.memory import Memory
    env, service = discovery
    prepared = service.prepare(request())
    final = service.for_delivery(prepared)
    service.written(prepared, final, wire=json.dumps(final) + '\n')
    public, secret = generate_recipient_keypair()
    signer, signing_secret = generate_signing_keypair()
    portable = CodePortable(env.app)
    sealed = portable.export(env.project, recipient_public_key=public,
        signing_public_key=signer, signing_secret_key=signing_secret)
    assert 'main implementation' not in json.dumps(sealed)
    opened = portable.open(sealed, recipient_secret_key=secret, trusted_signing_public_key=signer)
    assert opened['manifest']['format'] == FORMAT_V3
    retained = opened['state']['documents']['curation-exposure'][0]['value']
    assert retained['navigation_request'] == request() and retained['navigation_delivered'] == final
    target = Memory(':memory:', auto_vectors=False)
    try:
        new = CodePortable(CodeApplication(target, subject_id='local'))
        root = tmp_path / 'restored-clone'
        root.mkdir()
        preview = new.preview(opened, root=str(root))
        assert new.restore(opened, root=str(root), preview_token=preview['preview_token'])['imported']
        assert target.store.code_documents('local', env.project, 'curation-exposure') == env.app.store.code_documents('local', env.project, 'curation-exposure')
    finally:
        target.close()


def test_navigation_configuration_is_explicit_and_never_claims_routed_host(discovery, monkeypatch):
    from atmem.code.knowledge_setup import mcp_configuration
    env, _ = discovery
    # The in-memory fixture cannot generate a runnable persistent-MCP config;
    # its refusal must not create a real host configuration as a fallback.
    with pytest.raises(ValueError, match='persistent'):
        mcp_configuration(env.app, env.scope, str(env.root), tool_profile='navigation')
    monkeypatch.setattr(env.app.store, 'path', str(env.root / 'fixture.db'))
    settings = env.app.settings(env.project)
    result = mcp_configuration(env.app, env.scope, str(env.root), tool_profile='navigation')
    assert result['tools'] == ['repository_discover']
    assert result['discovery_routing'] == 'unqualified_optional_tool_only'
    assert len(result['discovery_hosts']) == 15
    assert all(c['capability'] == 'unprobed' for c in result['discovery_hosts'])
    assert not result['automatic_host_configuration_changed']
    assert result['automatic_recall_enabled'] and result['navigation_context_warning']
    assert '--experience' not in result['configuration']['mcpServers']['atmem_code']['args']
    assert env.app.settings(env.project) == settings
    env.app.settings(env.project, {'auto_recall': False})
    disabled = mcp_configuration(env.app, env.scope, str(env.root), tool_profile='navigation')
    assert not disabled['automatic_recall_enabled'] and disabled['navigation_context_warning'] is None
    assert env.app.settings(env.project)['auto_capture'] == settings['auto_capture']
