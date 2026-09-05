from __future__ import annotations

from typing import Any

import pytest

from atmem.adapters import AtMemAdapterIdentity, AtMemTurnLifecycle
from atmem.adapters.langgraph import create_langgraph_middleware
from atmem.adapters.pydantic_ai import PydanticAIAtMemAdapter
from atmem.control import ControlPlaneManager
from atmem.core.canonical import sha256_hex


class _Manager:
    def __init__(self, *, inject: bool = True) -> None:
        self.inject = inject
        self.events: list[dict[str, Any]] = []
        self.captures: list[dict[str, Any]] = []
        self.confirmed: list[str] = []
        self.task_confirmed: list[str] = []

    def capture(self, message: str, **kwargs: Any) -> dict[str, Any]:
        self.captures.append({"message": message, **kwargs})
        return {"captured": 1, "record_ids": ["rec_fact"]}

    def prepare(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "inject": self.inject,
            "context": "<atmem_control_plane>\n- User likes tea.\n</atmem_control_plane>"
            if self.inject
            else "",
            "preview_id": "preview-1",
            "context_receipt_id": "preview-1",
            "exposure_id": "exposure-1" if self.inject else None,
            "candidate_ids": ["rec_fact"] if self.inject else [],
        }

    def confirm_exposure(self, exposure_id: str) -> bool:
        self.confirmed.append(exposure_id)
        return True

    def prepare_task_context(self, **kwargs: Any) -> dict[str, Any]:
        context = "<<<atmem-governed-task-data>>>\ngoal: Ship safely\n<<<end-atmem-governed-task-data>>>"
        return {
            "disposition": "injected",
            "context": context,
            "context_sha256": f"sha256:{sha256_hex(context)}",
            "delivery_id": "task-delivery-1",
            "revision": 2,
            "reason_codes": [],
        }

    def confirm_task_exposure(self, delivery_id: str) -> bool:
        self.task_confirmed.append(delivery_id)
        return True

    def record_blackbox_event(self, **kwargs: Any) -> dict[str, Any]:
        self.events.append(kwargs)
        return {"recorded": True, "event_id": f"event-{len(self.events)}"}


def _identity(framework: str = "test") -> AtMemAdapterIdentity:
    return AtMemAdapterIdentity(
        agent_id="main",
        workspace_id="ws_default",
        subject_id="user-1",
        session_id="session-1",
        run_id="run-1",
        turn_id="turn-1",
        framework=framework,
    )


def test_shared_lifecycle_captures_injects_confirms_and_closes() -> None:
    manager = _Manager()
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]

    turn.begin("I like tea")
    governed = turn.context_for_model()
    turn.model_input(["I like tea", governed], provider="test", model="fake")
    turn.tool_requested("calendar.read", "call-1", {"date": "today"})
    turn.tool_completed("calendar.read", "call-1", {"events": []})
    turn.model_output("You like tea.", provider="test", model="fake")
    turn.end(success=True)

    assert manager.captures[0]["authenticated_user"] is True
    assert "governed memory data" in governed
    assert manager.confirmed == ["exposure-1"]
    assert [row["event_type"] for row in manager.events] == [
        "turn.input",
        "context.disposition",
        "model.input",
        "tool.requested",
        "tool.completed",
        "model.output",
        "turn.ended",
    ]
    assert all("I like tea" not in str(row["payload"]) for row in manager.events)


def test_shared_lifecycle_shadow_mode_never_injects_or_confirms() -> None:
    manager = _Manager(inject=False)
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]
    turn.begin("I like tea")
    assert turn.context_for_model() == ""
    turn.model_input("I like tea")
    assert manager.confirmed == []
    disposition = next(
        row for row in manager.events if row["event_type"] == "context.disposition"
    )
    assert disposition["payload"]["disposition"] == "not_injected"


def test_shared_lifecycle_passes_real_generic_contract(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
        memory_db=tmp_path / "memory.db",
    )
    topology = manager.agent_topology()
    workspace = topology["workspaces"][0]
    manager.activate()
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.propose",
        lambda self, message: {
            "proposals": [],
            "companion": {"available": False, "fallback": True},
        },
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
        lambda self, query: {"expanded_queries": [query], "content_received": False},
    )
    monkeypatch.setattr(
        "atmem.control.atbot_companion.AtBotCompanionClient.query",
        lambda self, query, candidates: {
            "ranked_record_ids": [row["record_id"] for row in candidates],
            "companion": {"available": False, "fallback": True},
        },
    )
    turn = AtMemTurnLifecycle(
        manager,
        AtMemAdapterIdentity(
            agent_id="main",
            workspace_id=workspace["workspace_id"],
            subject_id=workspace["subject_id"],
            session_id="session-contract",
            run_id="run-contract",
            turn_id="turn-contract",
        ),
    )

    turn.begin("I prefer jasmine tea.")
    context = turn.context_for_model()
    turn.model_input(["I prefer jasmine tea.", context], model="test")
    turn.model_output("You prefer jasmine tea.", model="test")
    turn.end(success=True)

    report = manager.verify_blackbox_flight("run-contract")
    assert "jasmine tea" in context
    assert report["timeline_chain_valid"] is True
    assert report["structurally_complete"] is True
    assert report["verdict"] == "completed_successfully"
    assert report["context"]["disposition"] == "injected"


def test_shared_lifecycle_fails_closed_on_cross_workspace_identity(tmp_path) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
        memory_db=tmp_path / "memory.db",
    )
    topology = manager.configure_agent_topology(
        [
            {"agent_id": "main", "workspace": "shared", "is_default": True},
            {"agent_id": "private", "workspace": "private"},
        ]
    )
    private_workspace = next(
        row for row in topology["workspaces"] if row["workspace"] == "private"
    )
    turn = AtMemTurnLifecycle(
        manager,
        AtMemAdapterIdentity(
            agent_id="main",
            workspace_id=private_workspace["workspace_id"],
            subject_id=private_workspace["subject_id"],
            run_id="run-cross-scope",
        ),
    )

    with pytest.raises(ValueError, match="different (?:scopes|workspaces)"):
        turn.begin("I prefer jasmine tea.")


def test_pydantic_ai_hooks_inject_at_the_model_boundary() -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    manager = _Manager()
    capability = PydanticAIAtMemAdapter(
        manager, _identity("pydantic-ai")  # type: ignore[arg-type]
    ).capability()
    agent = Agent(TestModel(custom_output_text="You like tea."), capabilities=[capability])

    result = agent.run_sync("What do I like?")

    assert result.output == "You like tea."
    assert manager.confirmed == ["exposure-1"]
    assert manager.captures[0]["message"] == "What do I like?"
    assert [row["event_type"] for row in manager.events][-1] == "turn.ended"


def test_pydantic_ai_hooks_deliver_exact_governed_task_state() -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    manager = _Manager()
    capability = PydanticAIAtMemAdapter(
        manager, _identity("pydantic-ai").for_task("task-1")  # type: ignore[arg-type]
    ).capability()
    Agent(TestModel(custom_output_text="done"), capabilities=[capability]).run_sync("continue")

    assert manager.task_confirmed == ["task-delivery-1"]
    assert "task.context.prepared" in [row["event_type"] for row in manager.events]
    assert "task.context.exposed" in [row["event_type"] for row in manager.events]


def test_pydantic_ai_hooks_record_tool_request_and_completion() -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    manager = _Manager(inject=False)
    capability = PydanticAIAtMemAdapter(
        manager, _identity("pydantic-ai")  # type: ignore[arg-type]
    ).capability()
    agent = Agent(TestModel(call_tools=["lookup_preference"]), capabilities=[capability])

    @agent.tool_plain
    def lookup_preference(query: str) -> str:
        return f"preference for {query}"

    agent.run_sync("Use the preference tool")

    event_types = [row["event_type"] for row in manager.events]
    assert event_types.count("tool.requested") == 1
    assert event_types.count("tool.completed") == 1


def test_langgraph_middleware_injects_at_the_model_boundary() -> None:
    pytest.importorskip("langchain")
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    manager = _Manager()
    middleware = create_langgraph_middleware(
        manager, _identity("langgraph")  # type: ignore[arg-type]
    )
    agent = create_agent(
        model=FakeMessagesListChatModel(responses=[AIMessage(content="You like tea.")]),
        tools=[],
        middleware=[middleware],
    )

    result = agent.invoke({"messages": [{"role": "user", "content": "What do I like?"}]})

    assert result["messages"][-1].content == "You like tea."
    assert manager.confirmed == ["exposure-1"]
    assert manager.captures[0]["message"] == "What do I like?"
    assert [row["event_type"] for row in manager.events][-1] == "turn.ended"


def test_langgraph_hooks_deliver_exact_governed_task_state() -> None:
    pytest.importorskip("langchain")
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    manager = _Manager()
    middleware = create_langgraph_middleware(
        manager, _identity("langgraph").for_task("task-1")  # type: ignore[arg-type]
    )
    agent = create_agent(
        model=FakeMessagesListChatModel(responses=[AIMessage(content="done")]),
        tools=[], middleware=[middleware],
    )
    agent.invoke({"messages": [{"role": "user", "content": "continue"}]})

    assert manager.task_confirmed == ["task-delivery-1"]
    assert "task.context.prepared" in [row["event_type"] for row in manager.events]
    assert "task.context.exposed" in [row["event_type"] for row in manager.events]


def test_langgraph_middleware_records_tool_request_and_completion() -> None:
    pytest.importorskip("langchain")
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool

    class ToolCapableFakeMessagesListChatModel(FakeMessagesListChatModel):
        def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[no-untyped-def]
            del tools, tool_choice, kwargs
            return self

    manager = _Manager(inject=False)
    middleware = create_langgraph_middleware(
        manager, _identity("langgraph")  # type: ignore[arg-type]
    )

    @tool
    def lookup_preference(query: str) -> str:
        """Look up a preference."""
        return f"preference for {query}"

    model = ToolCapableFakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_preference",
                        "args": {"query": "tea"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="You like tea."),
        ]
    )
    agent = create_agent(model=model, tools=[lookup_preference], middleware=[middleware])

    agent.invoke({"messages": [{"role": "user", "content": "What do I like?"}]})

    event_types = [row["event_type"] for row in manager.events]
    assert event_types.count("tool.requested") == 1
    assert event_types.count("tool.completed") == 1
