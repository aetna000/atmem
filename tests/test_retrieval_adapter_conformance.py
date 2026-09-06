from __future__ import annotations

import json

import pytest

from atmem import Memory
from atmem.adapters import AtMemAdapterIdentity, AtMemTurnLifecycle
from atmem.control import ControlMode, ControlPlaneManager
from atmem.control.server import ControlMCPServer


@pytest.fixture
def governed_manager(tmp_path, monkeypatch):
    memory_path = tmp_path / "memory.db"
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "migrations",
        memory_db=memory_path,
    )
    memory = Memory(memory_path)
    try:
        memory.remember(
            "local-user",
            "JT likes burgers.",
            interpreted_fact="JT likes burgers.",
            interpreted_fact_key="food preference",
        )
        memory.remember("local-user", "Javad is bald.")
    finally:
        memory.close()
    manager.transition(ControlMode.ACTIVE)
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.health",
        lambda self: {"available": False, "reason": "conformance fallback"},
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {"expanded_queries": [query], "content_received": False},
    )
    return manager


@pytest.mark.parametrize("framework", ["pydantic-ai", "langgraph"])
def test_framework_lifecycle_preserves_no_useful_memory(
    governed_manager, framework
) -> None:
    topology = governed_manager.agent_topology()
    workspace = topology["workspaces"][0]
    turn = AtMemTurnLifecycle(
        governed_manager,
        AtMemAdapterIdentity(
            agent_id="main",
            workspace_id=workspace["workspace_id"],
            subject_id=workspace["subject_id"],
            session_id=f"{framework}-session",
            run_id=f"{framework}-run",
            turn_id=f"{framework}-turn",
            framework=framework,
        ),
    )
    turn.begin("what cars are available in Australia?")
    assert turn.context_for_model() == ""
    assert turn.prepared["retrieval"]["decision"]["support_class"] == "no_useful_memory"


def test_control_mcp_preserves_no_useful_memory(governed_manager) -> None:
    response = ControlMCPServer(governed_manager).handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "control_prepare",
                "arguments": {
                    "query": "what cars are available in Australia?",
                    "agent_id": "main",
                },
            },
        }
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["inject"] is False
    assert payload["candidate_ids"] == []
    assert payload["retrieval"]["decision"]["support_class"] == "no_useful_memory"
