from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from atmem.delegated.contracts import DelegatedBinding, DelegatedContextRequest
from atmem.delegated.validation import parse_and_verify_envelope
from atmem.provider_adapters.langgraph import LangGraphContextProvider
from atmem.provider_adapters.mem0 import Mem0ContextProvider
from atmem.provider_adapters.models import ProviderRuntimeIdentity
from atmem.provider_adapters.pydantic_ai import PydanticAIContextProvider
from atmem.provider_adapters.runtime import ProviderRuntime
from atmem.provider_adapters.signing import generate_keypair, load_private_key


def test_all_adapters_cross_the_existing_signed_verification_boundary(tmp_path: Path) -> None:
    class Mem0:
        def search(self, query, *, filters, top_k):
            return [{"id": "m1", "memory": "User likes burgers"}]

    class Graph:
        def invoke(self, value, config):
            return {"context_decision": {
                "decision": "inject", "items": [{"text": "User likes burgers", "source_ref": "g1"}], "source_refs": ["g1"],
            }}

    class Agent:
        async def run(self, prompt):
            return SimpleNamespace(output={
                "decision": "inject", "items": [{"text": "User likes burgers", "source_ref": "p1"}], "source_refs": ["p1"],
            })

    providers = [Mem0ContextProvider(Mem0()), LangGraphContextProvider(Graph()), PydanticAIContextProvider(Agent())]
    binding = DelegatedBinding("run", "turn", "session", "agent", "user", "workspace")
    request = DelegatedContextRequest.create(binding=binding, query="favorite food", max_context_bytes=4096, timeout_ms=5000).to_dict()
    for number, provider in enumerate(providers):
        private, public = tmp_path / f"private-{number}", tmp_path / f"public-{number}"
        public_value = generate_keypair(private, public)
        identity = ProviderRuntimeIdentity(f"provider-{number}", "1.0", f"instance-{number}", "primary")
        runtime = ProviderRuntime(provider=provider, identity=identity, private_key=load_private_key(private), adapter_kind="test")
        envelope = asyncio.run(runtime.handle_async(request))
        trust = SimpleNamespace(
            provider_id=identity.provider_id, provider_version="1.0", provider_instance_id=identity.instance_id,
            key_id="primary", public_key_base64=public_value, workspace_ids=("workspace",), agent_ids=("agent",), user_ids=("user",),
        )
        verified = parse_and_verify_envelope(__import__("json").dumps(envelope), expected_binding=binding, trust=trust)
        assert verified.context_text == "Memory: User likes burgers\n"


def test_mem0_adapter_cannot_return_content_from_another_scope() -> None:
    class Mem0:
        def search(self, query, *, filters, top_k):
            return [{"id": "m1", "memory": "private", "metadata": {"user_id": "other"}}]

    request = SimpleNamespace(
        binding=DelegatedBinding("r", "t", "s", "agent", "user", "workspace"), query="q",
    )
    proposal = asyncio.run(Mem0ContextProvider(Mem0()).decide(request))
    assert proposal.decision == "withhold"
