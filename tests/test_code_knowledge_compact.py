"""Compact transport equivalence and authority; not coding efficiency evidence."""
from io import StringIO
import json

import pytest

from atmem.knowledge.code.mcp import CodeKnowledgeMCP
from tests.test_code_knowledge_mcp import server


def profiles(env):
    expanded = server(env)
    compact = CodeKnowledgeMCP(env.app, env.scope, str(env.root), tool_profile='compact')
    return expanded, compact


@pytest.mark.parametrize('operation,config', [
    ('query_facts', {'name': 'main'}), ('explore', {'id': 'main'}),
    ('traverse', {'node_ids': ['main'], 'max_depth': 3}),
    ('find_path', {'source_id': 'main', 'target_id': 'main'}),
    ('impact_analysis', {'id': 'main'}), ('architecture', {'max_nodes': 3}),
    ('delta', {}), ('insights', {'limit': 3}),
])
def test_all_graph_outputs_are_exact_existing_service(code_env, operation, config):
    expanded, compact = profiles(code_env)
    identity = expanded.query('code_search', {'query': 'main'})['symbols'][0]['id']
    config = {key: identity if value == 'main' else [identity] if value == ['main'] else value
              for key, value in config.items()}
    expected = expanded.query('code_search', {'operation': operation, 'arguments': config, 'budget': 32768})
    actual = compact.query('code_query', {'operation': operation, 'arguments': config, 'budget': 32768})
    assert actual == expected and actual['status'] == 'current'


@pytest.mark.parametrize('operation,target,args', [
    ('context', 'code_context', {'query': 'main', 'budget': 1024}),
    ('search', 'code_search', {'query': 'main', 'offset': 0}),
    ('source', 'code_source', {'path': 'main.py', 'line_count': 2}),
])
def test_source_search_context_are_exact_existing_service(code_env, operation, target, args):
    expanded, compact = profiles(code_env)
    assert compact.query('code_query', {'operation': operation, 'arguments': args}) == expanded.query(target, args)


@pytest.mark.parametrize('payload', [
    {'operation': 'delete'}, {'operation': 'experience'}, {'operation': ['source']},
    {'operation': 'context', 'arguments': {'query': 'main', 'root': '/elsewhere'}},
    {'operation': 'source', 'arguments': {'path': '../../other'}},
    {'operation': 'source', 'arguments': {'path': 'main.py', 'line_count': 101}},
    {'operation': 'traverse', 'arguments': {'max_depth': 21}},
    {'operation': 'query_facts', 'arguments': {'subject_id': 'other'}},
    {'operation': 'query_facts', 'arguments': {'min_confidence': float('nan')}},
    {'operation': 'search', 'arguments': {'operation': 'architecture'}},
    {'operation': 'context', 'arguments': {'query': 'main'}, 'budget': True},
    {'operation': 'context', 'arguments': {'query': 'main', 'budget': 1024}, 'budget': 2048},
    {'operation': 'source', 'arguments': {'path': 'main.py'}, 'budget': 1024},
    {'operation': 'architecture', 'arguments': [], 'budget': 1024},
    {'operation': 'architecture', 'root': '/elsewhere'},
])
def test_compact_interface_does_not_widen_authority_or_limits(code_env, payload):
    _, compact = profiles(code_env)
    reply = compact._call_tool(1, 'code_query', payload)
    assert reply['result']['isError'] is True
    assert 'return 1' not in str(reply)


def test_catalog_reduced_and_default_unchanged(code_env):
    expanded, compact = profiles(code_env)
    request = {'id': 1, 'method': 'initialize'}
    listed = {'id': 2, 'method': 'tools/list'}
    original = [expanded.handle(request), expanded.handle(listed)]
    reduced = [compact.handle(request), compact.handle(listed)]
    assert [t['name'] for t in original[1]['result']['tools']] == ['code_context', 'code_search', 'code_explore', 'code_source']
    assert [t['name'] for t in reduced[1]['result']['tools']] == ['code_query']
    assert len(json.dumps(reduced).encode()) < len(json.dumps(original).encode()) * .6
    assert compact._call_tool(3, 'code_source', {'path': 'main.py'})['error']['code'] == -32602
    assert expanded._call_tool(3, 'code_query', {'operation': 'source'})['error']['code'] == -32602


def test_final_stream_freshness_check_unchanged(code_env):
    _, compact = profiles(code_env)
    reply = compact._call_tool(1, 'code_query', {'operation': 'source', 'arguments': {'path': 'main.py'}})
    assert 'return 1' in str(reply)
    (code_env.root / 'main.py').write_text('def changed(): return 2\n')
    output = StringIO()
    compact._write(output, reply)
    result = json.loads(json.loads(output.getvalue())['result']['content'][0]['text'])
    assert result == {'status': 'withheld', 'reason': 'source_changed_before_delivery'}
    assert 'return 1' not in output.getvalue()


def test_experience_requires_explicit_operator_enablement(code_env):
    server(code_env)
    from atmem.code.experience_view import experiences
    compact = CodeKnowledgeMCP(code_env.app, code_env.scope, str(code_env.root), tool_profile='compact', experience=True)
    assert 'experience' in compact._tool_definitions()[0]['inputSchema']['properties']['operation']['enum']
    assert compact.query('code_query', {'operation': 'experience'}) == experiences(code_env.app, code_env.scope, str(code_env.root))


def test_generated_configuration_and_cli_selection(tmp_path):
    from atmem.code.knowledge_setup import mcp_configuration
    import argparse
    from atmem.code.cli import add_commands
    from atmem.memory import Memory
    from atmem.code.application import CodeApplication
    from atmem.code.identity import CodeIdentity
    from atmem.service.household import HouseholdApplication
    HouseholdApplication.initialize(tmp_path / 'configuration.db', encrypted=True)
    memory = Memory(tmp_path / 'configuration.db', auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(tmp_path, subject_id='local', profile_id='shared', agent_id='codex')
        app = CodeApplication(memory, subject_id='local')
        result = mcp_configuration(app, scope, str(tmp_path), tool_profile='compact')
        assert result['tools'] == ['code_query'] and result['tool_profile'] == 'compact'
        assert result['configuration']['mcpServers']['atmem_code']['args'][-2:] == ['--tool-profile', 'compact']
        assert not result['automatic_host_configuration_changed']
        with pytest.raises(ValueError, match='profile'):
            mcp_configuration(app, scope, str(tmp_path), tool_profile='invalid')
    finally:
        memory.close()
    parser = argparse.ArgumentParser()
    add_commands(parser, default_db='memory.db')
    assert parser.parse_args(['mcp-config', '--tool-profile', 'compact']).tool_profile == 'compact'
