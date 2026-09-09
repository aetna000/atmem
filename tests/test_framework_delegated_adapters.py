from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from atmem.adapters import AtMemAdapterIdentity, AtMemTurnLifecycle
from atmem.adapters.langgraph import (
    _langgraph_execution_identity,
    create_langgraph_middleware,
)
from atmem.adapters.pydantic_ai import (
    PydanticAIAtMemAdapter,
    _pydantic_execution_identity,
)
from atmem.control import ControlPlaneManager
from atmem.core.canonical import sha256_hex
from atmem.delegated.config import DelegatedConfigStore, DelegatedRegistration
from atmem.delegated.transport import RequestAuthenticator, configure_keyring
from atmem.provider_adapters.models import (
    ContextItem,
    ProviderProposal,
    ProviderRuntimeIdentity,
)
from atmem.provider_adapters.runtime import ProviderRuntime
from atmem.provider_adapters.server import create_server
from atmem.provider_adapters.signing import generate_keypair, load_private_key

EXACT_CONTEXT = "delegated line one\r\nline two: 🧳"


class _DelegatedManager:
    def __init__(
        self,
        *,
        decision: str = "inject",
        authority: str = "delegated",
        applies: bool = True,
    ) -> None:
        self.decision = decision
        self.authority = authority
        self.applies = applies
        self.preparations: list[dict[str, Any]] = []
        self.captures: list[dict[str, Any]] = []
        self.confirmed: list[str] = []
        self.events: list[dict[str, Any]] = []

    def delegated_context_applies(self, **identity: Any) -> bool:
        self.applicable_identity = identity
        return self.applies

    def prepare(self, query: str, **kwargs: Any) -> dict[str, Any]:
        self.preparations.append({"query": query, **kwargs})
        authority = self.authority if kwargs.get("allow_delegation") else "atmem"
        decision = self.decision if authority == "delegated" else "native_context"
        inject = decision == "inject" or authority in {"atmem", "atmem_fallback"}
        context = EXACT_CONTEXT if inject else ""
        return {
            "authority": authority,
            "decision": (
                "native_context" if authority == "atmem_fallback" else decision
            ),
            "native_fallback": authority == "atmem_fallback",
            "inject": inject,
            "context": context,
            "context_sha256": sha256_hex(context) if context else None,
            "context_byte_length": len(context.encode("utf-8")),
            "exposure_id": "delegated-delivery-1" if inject else None,
            "context_receipt_id": "receipt-1",
            "authorization_event_id": "authorization-1",
            "result_sha256": "a" * 64,
            "receipt": {"id": "receipt-1", "sha256": "b" * 64},
            "provider": {
                "id": "fixture-provider",
                "version": "1.0.0",
                "instance_id": "local",
            },
            "candidate_ids": [],
        }

    def capture(self, message: str, **kwargs: Any) -> dict[str, Any]:
        self.captures.append({"message": message, **kwargs})
        return {"captured": 1}

    def confirm_exposure(self, exposure_id: str) -> bool:
        self.confirmed.append(exposure_id)
        return True

    def record_blackbox_event(self, **kwargs: Any) -> dict[str, Any]:
        self.events.append(kwargs)
        return {"recorded": True, "event_id": f"event-{len(self.events)}"}

    def prepare_task_context(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {"disposition": "withheld", "reason_codes": []}


def _identity(framework: str = "test") -> AtMemAdapterIdentity:
    return AtMemAdapterIdentity(
        agent_id="main",
        workspace_id="ws-main",
        user_id="authenticated-user-1",
        subject_id="subject-1",
        session_id="session-1",
        run_id="run-1",
        turn_id="turn-1",
        framework=framework,
    )


@contextmanager
def _authenticated_provider(tmp_path: Path, *, workspace_id: str):
    auth_path = tmp_path / "request-auth.json"
    credential = configure_keyring(
        auth_path, provider_id="framework-provider", instance_id="local"
    )
    public = generate_keypair(tmp_path / "private.key", tmp_path / "public.key")
    calls: list[str] = []

    class Provider:
        def decide(self, request: Any) -> ProviderProposal:
            calls.append(request.query)
            return ProviderProposal(
                decision="inject",
                items=(ContextItem("Trip 🧠\r\nBooked", "ref:trip"),),
                source_refs=("ref:trip",),
            )

    runtime = ProviderRuntime(
        provider=Provider(),
        identity=ProviderRuntimeIdentity(
            "framework-provider", "test", "local", "primary"
        ),
        private_key=load_private_key(tmp_path / "private.key"),
        adapter_kind="test",
    )
    runtime.request_authenticator = RequestAuthenticator(
        auth_path, tmp_path / "transport-nonces.db"
    )
    server = create_server(runtime, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    registration = DelegatedRegistration(
        provider_id="framework-provider",
        provider_version="test",
        provider_instance_id="local",
        key_id="primary",
        public_key_base64=public,
        endpoint=(f"http://127.0.0.1:{server.server_port}/v1/delegated-context"),
        workspace_ids=(workspace_id,),
        agent_ids=("main",),
        user_ids=("authenticated-user-1",),
        request_key_id=credential["request_key_id"],
        request_secret_file=credential["request_secret_file"],
    )
    try:
        yield registration, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_shared_lifecycle_routes_exact_query_and_context_without_capture() -> None:
    manager = _DelegatedManager()
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]

    turn.begin("  exact user query\r\nwith spacing  ")
    governed = turn.context_for_model()
    turn.model_input(
        ["user segment", governed],
        context_segments=["user segment", governed],
        context_location="test:message",
    )

    assert manager.captures == []
    assert manager.preparations == [
        {
            "query": "exact user query with spacing",
            "delegated_query": "  exact user query\r\nwith spacing  ",
            "allow_delegation": True,
            "session_id": "session-1",
            "host_run_id": "run-1",
            "turn_id": "turn-1",
            "user_id": "authenticated-user-1",
            "workspace_id": "ws-main",
            "subject_id": "subject-1",
            "agent_id": "main",
        }
    ]
    assert governed == EXACT_CONTEXT
    assert turn.raw_query == ""
    assert manager.confirmed == ["delegated-delivery-1"]
    assert turn.prepared is not None and turn.prepared["context"] == ""
    event_types = [row["event_type"] for row in manager.events]
    assert event_types == [
        "turn.input",
        "context.provider_authorization",
        "context.injected",
        "context.disposition",
        "model.input",
    ]
    assert all(EXACT_CONTEXT not in str(row["payload"]) for row in manager.events)
    assert all("exact user query" not in str(row["payload"]) for row in manager.events)


def test_nonmatching_scope_freezes_native_capture_and_preparation() -> None:
    manager = _DelegatedManager(applies=False)
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]

    turn.begin("  native query\r\nwith spacing  ")
    governed = turn.context_for_model()

    assert manager.captures[0]["message"] == "native query with spacing"
    assert manager.preparations[0]["query"] == "native query with spacing"
    assert manager.preparations[0]["allow_delegation"] is False
    assert governed.startswith("The following block is governed memory data")
    assert turn.raw_query == ""


def test_lifecycle_completes_authenticated_http_provider_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
        memory_db=tmp_path / "memory.db",
    )
    topology = manager.configure_agent_topology(
        [{"agent_id": "main", "workspace": "main", "is_default": True}]
    )
    workspace = topology["agents"][0]
    manager.activate()
    config_path = tmp_path / "delegated.json"
    monkeypatch.setenv("ATMEM_DELEGATED_CONFIG", str(config_path))

    with _authenticated_provider(tmp_path, workspace_id=workspace["workspace_id"]) as (
        registration,
        calls,
    ):
        config = DelegatedConfigStore(config_path)
        config.register(registration)
        config.set_enabled(registration.registration_id, True)
        monkeypatch.setattr(
            manager,
            "capture",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("delegated query reached canonical capture")
            ),
        )
        turn = AtMemTurnLifecycle(
            manager,
            AtMemAdapterIdentity(
                agent_id="main",
                workspace_id=workspace["workspace_id"],
                user_id="authenticated-user-1",
                subject_id=workspace["subject_id"],
                session_id="framework-session",
                run_id="framework-run",
                turn_id="framework-turn",
                framework="pydantic-ai",
            ),
        )
        raw_query = "  plan my trip 🧳\r\nwithout normalization  "
        turn.begin(raw_query)
        context = turn.context_for_model()
        turn.model_input(
            [raw_query, context],
            context_segments=[raw_query, context],
            context_location="pydantic-ai:user-prompt-part",
            provider="test",
            model="test-model",
        )
        turn.model_output("done", provider="test", model="test-model")
        turn.end(success=True)

        unauthenticated = AtMemTurnLifecycle(
            manager,
            AtMemAdapterIdentity(
                agent_id="main",
                workspace_id=workspace["workspace_id"],
                user_id="authenticated-user-1",
                subject_id=workspace["subject_id"],
                session_id="unauthenticated-session",
                run_id="unauthenticated-run",
                turn_id="unauthenticated-turn",
                authenticated_user=False,
                framework="pydantic-ai",
            ),
        )
        unauthenticated.begin("must not reach provider or native capture")
        assert unauthenticated.context_for_model() == ""

    assert calls == [raw_query]
    assert "Trip 🧠\r\nBooked" in context
    for path in (
        tmp_path / "memory.db",
        tmp_path / "control" / "evidence.db",
        tmp_path / "control" / "evidence.db-wal",
    ):
        if path.exists():
            assert raw_query.encode("utf-8") not in path.read_bytes()
    report = manager.verify_blackbox_flight("framework-run")
    assert report["timeline_chain_valid"] is True
    assert report["structurally_complete"] is True
    assert report["verdict"] == "completed_successfully"


@pytest.mark.parametrize("decision", ["withhold", "provider_failure"])
def test_shared_lifecycle_noninject_is_exclusive_and_content_free(
    decision: str,
) -> None:
    manager = _DelegatedManager(decision=decision)
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]

    turn.begin("private delegated query")
    assert turn.context_for_model() == ""
    turn.model_input(
        ["private delegated query"], context_segments=["private delegated query"]
    )

    assert manager.captures == []
    assert manager.confirmed == []
    assert "context.injected" not in [row["event_type"] for row in manager.events]


@pytest.mark.parametrize(
    "tamper",
    ["duplicate", "prefix", "suffix", "normalize", "digest", "byte_length"],
)
def test_shared_lifecycle_fails_before_confirmation_on_delivery_tamper(
    tamper: str,
) -> None:
    manager = _DelegatedManager()
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]
    turn.begin("query")
    governed = turn.context_for_model()

    segments = {
        "duplicate": [governed, governed],
        "prefix": ["prefix" + governed],
        "suffix": [governed + "suffix"],
        "normalize": [governed.replace("\r\n", "\n")],
        "digest": [governed],
        "byte_length": [governed],
    }[tamper]
    assert turn.prepared is not None
    if tamper == "digest":
        turn.prepared["context_sha256"] = "c" * 64
    elif tamper == "byte_length":
        turn.prepared["context_byte_length"] += 1

    with pytest.raises(RuntimeError, match="exact model-input delivery proof"):
        turn.model_input(
            segments,
            context_segments=segments,
        )

    assert manager.confirmed == []
    assert turn.prepared["context"] == ""
    delivery = next(
        row for row in manager.events if row["event_type"] == "context.injected"
    )
    assert delivery["payload"]["success"] is False


def test_shared_lifecycle_labels_explicit_native_fallback() -> None:
    manager = _DelegatedManager(authority="atmem_fallback")
    turn = AtMemTurnLifecycle(manager, _identity())  # type: ignore[arg-type]

    turn.begin("fallback query")
    governed = turn.context_for_model()
    turn.model_input([governed], context_segments=[governed])

    assert manager.captures[0]["message"] == "fallback query"
    assert governed.startswith("The following block is governed memory data")
    disposition = next(
        row for row in manager.events if row["event_type"] == "context.disposition"
    )
    assert disposition["payload"]["mode"] == "atmem_fallback"


def test_framework_identity_reads_only_explicit_authenticated_user_field() -> None:
    class PydanticContext:
        deps: ClassVar[dict[str, str]] = {
            "user_id": "untrusted-generic-name",
            "atmem_authenticated_user_id": "trusted-pydantic-user",
        }

    class LangGraphRuntime:
        config: ClassVar[dict[str, dict[str, str]]] = {
            "configurable": {
                "user_id": "untrusted-generic-name",
                "atmem_authenticated_user_id": "trusted-langgraph-user",
            }
        }
        context: ClassVar[dict[str, str]] = {}

    assert _pydantic_execution_identity(PydanticContext())["user_id"] == (
        "trusted-pydantic-user"
    )
    assert _langgraph_execution_identity(LangGraphRuntime())["user_id"] == (
        "trusted-langgraph-user"
    )


def test_pydantic_ai_delivers_delegated_context_at_real_model_hook() -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    manager = _DelegatedManager()
    capability = PydanticAIAtMemAdapter(
        manager,
        _identity("pydantic-ai"),  # type: ignore[arg-type]
    ).capability()
    result = Agent(
        TestModel(custom_output_text="done"), capabilities=[capability]
    ).run_sync("  exact framework query\r\n  ")

    assert result.output == "done"
    assert manager.preparations[0]["delegated_query"] == (
        "  exact framework query\r\n  "
    )
    assert manager.captures == []
    assert manager.confirmed == ["delegated-delivery-1"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_langgraph_delivers_delegated_context_at_real_model_hook(
    asynchronous: bool,
) -> None:
    pytest.importorskip("langchain")
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage

    manager = _DelegatedManager()
    middleware = create_langgraph_middleware(
        manager,
        _identity("langgraph"),  # type: ignore[arg-type]
    )
    agent = create_agent(
        model=FakeMessagesListChatModel(responses=[AIMessage(content="done")]),
        tools=[],
        middleware=[middleware],
    )
    request = {"messages": [{"role": "user", "content": "exact graph query"}]}

    result = (
        asyncio.run(agent.ainvoke(request)) if asynchronous else agent.invoke(request)
    )

    assert result["messages"][-1].content == "done"
    assert manager.captures == []
    assert manager.confirmed == ["delegated-delivery-1"]


def test_langgraph_delivery_tamper_never_calls_model_handler() -> None:
    pytest.importorskip("langchain")
    from langchain_core.messages import HumanMessage

    manager = _DelegatedManager()
    middleware = create_langgraph_middleware(
        manager,
        _identity("langgraph"),  # type: ignore[arg-type]
    )
    runtime = SimpleNamespace(
        config={"configurable": {"thread_id": "run-1"}}, context={}
    )
    middleware.before_agent(
        {"messages": [HumanMessage(content=EXACT_CONTEXT)]}, runtime
    )
    request = SimpleNamespace(
        runtime=runtime,
        messages=[HumanMessage(content=EXACT_CONTEXT)],
        model=SimpleNamespace(model_name="fake"),
        tools=[],
    )
    model_calls: list[Any] = []

    with pytest.raises(RuntimeError, match="exact model-input delivery proof"):
        middleware.wrap_model_call(request, model_calls.append)

    assert model_calls == []
    assert manager.confirmed == []
