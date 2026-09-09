from atmem.adapters.callbacks import CallbackAtMemAdapter
from atmem.adapters.crewai import create_crewai_adapter
from atmem.adapters.google_adk import create_google_adk_adapter
from atmem.adapters.microsoft_agent import create_microsoft_agent_adapter
from atmem.adapters.openai_agents import create_openai_agents_adapter
from atmem.adapters.smolagents import create_smolagents_adapter
from atmem.contracts.versions import capabilities
from tests.adapter_conformance import ConformanceManager, exercise, identity

FACTORIES = [create_openai_agents_adapter, create_microsoft_agent_adapter, create_google_adk_adapter, create_smolagents_adapter, create_crewai_adapter]

def test_every_callback_adapter_has_identical_evidence_contract():
    for factory in FACTORIES:
        manager = ConformanceManager()
        adapter = factory(manager, identity())
        assert isinstance(adapter, CallbackAtMemAdapter)
        messages = exercise(adapter)
        assert sum(message.endswith("\nremembered") for message in messages) == 1
        assert [e["event_type"] for e in manager.events] == ["turn.input", "context.disposition", "model.input", "tool.requested", "tool.completed", "model.output", "turn.ended"]
        assert "private prompt" not in str(manager.events)

def test_failure_cancellation_retry_and_multi_agent_are_run_isolated():
    manager = ConformanceManager(); adapter = CallbackAtMemAdapter(manager, identity(), framework="generic")
    exercise(adapter, failure=True)
    exercise(adapter, cancelled=True)
    exercise(adapter)
    ended = [e["payload"] for e in manager.events if e["event_type"] == "turn.ended"]
    assert ended[0]["failure_kind"] == "RuntimeError"
    assert ended[1]["cancelled"] is True
    assert ended[2]["success"] is True

def test_capability_response_is_the_authoritative_adapter_matrix():
    rows = capabilities()["framework_adapters"]
    assert rows["mcp"]["exact_injection"] is False
    assert rows["pydantic-ai"]["exact_injection"] is True
    assert {factory(None, identity()).framework for factory in FACTORIES} <= set(rows)
