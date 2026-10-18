import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

from benchmarks.code_replay.cognee_click import arguments, sdk_query, tool_definition, worker_environment, runner


def test_worker_environment_excludes_owner_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-an-actual-key")
    state = tmp_path / "cognee-test"
    state.mkdir()
    env = worker_environment(state, "/isolated/bin/python")
    assert "OPENAI_API_KEY" not in env
    assert env["ENABLE_BACKEND_ACCESS_CONTROL"] == "true"
    assert env["CACHING"] == "true"
    assert env["TELEMETRY_DISABLED"] == "1"


def test_actual_sdk_call_preserves_typed_filters(monkeypatch):
    seen = []
    async def search(**kwargs):
        seen.append(kwargs)
        return [{"search_result": [{"facts": ["a-source-symbol"]}]}]
    monkeypatch.setitem(sys.modules, "cognee", SimpleNamespace(search=search, SearchType=SimpleNamespace(CODE="CODE")))
    result = asyncio.run(sdk_query({"operation": "query_facts", "arguments": {"name": "get_help_option", "limit": 10}}))
    assert seen[0]["code_query"] == {"operation": "query_facts", "name": "get_help_option", "limit": 10}
    assert seen[0]["datasets"] == ["click_short_structure"]
    assert result[0]["search_result"][0]["facts"] == ["a-source-symbol"]


@pytest.mark.parametrize("payload", [{"operation": "delete"}, {"operation": "explore", "top_k": True},
    {"operation": "explore", "arguments": {"operation": "delete"}}, {"operation": "explore", "path": "/"}])
def test_invalid_or_mutating_calls_rejected(payload):
    with pytest.raises(ValueError):
        asyncio.run(sdk_query(payload))


def test_runner_only_substitutes_mcp_encoder():
    method, source = runner()
    assert method.__name__ == "run_cli"
    assert "cognee_click import arguments" in source
    assert '"gpt-6-luna"' in source
    assert "os.killpg" in source
    assert arguments(None) == []
    assert tool_definition()["name"] == "code_search"
    assert set(tool_definition()["inputSchema"]["properties"]) == {"operation", "arguments", "query", "top_k"}
