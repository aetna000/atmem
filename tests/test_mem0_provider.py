from __future__ import annotations

import asyncio

from atmem.delegated.contracts import DelegatedBinding
from atmem.provider_adapters.mem0 import Mem0ContextProvider
from atmem.provider_adapters.models import ProviderRequest


def request() -> ProviderRequest:
    return ProviderRequest(DelegatedBinding("r", "t", "s", "agent", "user", "workspace"), "food", "digest", 1000, "2099-01-01T00:00:00Z")


def test_mem0_always_applies_three_scope_filters_and_normalizes_results() -> None:
    class Client:
        def search(self, query, *, filters, top_k):
            self.call = (query, filters, top_k)
            return {"results": [
                {"id": "1", "memory": "Likes burgers"},
                {"id": "1", "memory": "duplicate"},
                {"id": "2", "memory": "wrong", "user_id": "someone-else"},
            ]}

    client = Client()
    proposal = asyncio.run(Mem0ContextProvider(client).decide(request()))
    assert client.call[1] == {"user_id": "user", "agent_id": "agent", "app_id": "workspace"}
    assert [item.text for item in proposal.items] == ["Likes burgers"]
    assert proposal.source_refs == ("mem0:1",)


def test_mem0_empty_or_malformed_rows_withhold() -> None:
    class Client:
        async def search(self, *args, **kwargs):
            return [{"id": ""}, "bad"]

    proposal = asyncio.run(Mem0ContextProvider(Client()).decide(request()))
    assert proposal.decision == "withhold"
