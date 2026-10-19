from tools.qualify_cognee_snapshot import has_nodes
import asyncio
from pathlib import Path
import pytest
from benchmarks.code_replay.swebench_cognee import environment, query, ROOT, tool_definition


def test_upstream_code_facts_are_graph_results_not_an_empty_node_list():
    # Actual upstream SearchType.CODE wraps query_facts under search_result.facts,
    # not search_result.nodes. This tests only our probe, not a replacement SDK.
    assert has_nodes([{'search_result': {'operation': 'query_facts', 'facts': [{'id': 'public-symbol'}]}}])
    assert has_nodes({'nodes': [{'id': 'public-symbol'}]})
    assert not has_nodes([{'search_result': {'facts': [], 'total': 0}}])


def test_real_provider_environment_does_not_inherit_owner_credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'fixture-secret-never-forwarded')
    env = environment(ROOT / 'cognee-states/atmem-swe-lite-example', '/isolated/bin/python')
    assert 'OPENAI_API_KEY' not in env and 'ANTHROPIC_API_KEY' not in env
    assert env['TELEMETRY_DISABLED'] == '1'
    assert env['HOME'].startswith(str(ROOT / 'cognee-states'))
    with pytest.raises(ValueError):
        environment(Path('/home/owner'), '/isolated/bin/python')


@pytest.mark.parametrize('arguments', [
    {'operation': 'delete'}, {'operation': 'architecture', 'top_k': True},
    {'operation': 'query_facts', 'query': 'x' * 1001},
    {'operation': 'architecture', 'arguments': {'operation': 'delete'}},
    {'operation': 'architecture', 'root': '/owner'},
])
def test_provider_rejects_invalid_requests_before_sdk_invocation(arguments):
    with pytest.raises(ValueError):
        asyncio.run(query(arguments))


def test_upstream_transport_exposes_only_read_only_code_search():
    tool = tool_definition()
    assert tool['name'] == 'code_search'
    assert len(tool['inputSchema']['properties']['operation']['enum']) == 8
    assert tool['inputSchema']['additionalProperties'] is False
