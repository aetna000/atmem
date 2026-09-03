from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from atmem.delegated.contracts import DelegatedBinding
from atmem.provider_adapters.langgraph import LangGraphContextProvider
from atmem.provider_adapters.models import ProviderRequest


REQUEST = ProviderRequest(DelegatedBinding("r", "t", "s", "a", "u", "w"), "query", "digest", 1000, "2099-01-01T00:00:00Z")
DECISION = {"decision": "inject", "items": [{"text": "fact", "source_ref": "graph:1"}], "source_refs": ["graph:1"]}


def test_langgraph_ainvoke_gets_fresh_bound_input_and_v2_output() -> None:
    class Graph:
        async def ainvoke(self, value, config):
            self.value, self.config = deepcopy(value), deepcopy(config)
            return SimpleNamespace(value={"context_decision": DECISION}, interrupts=())

    graph = Graph()
    proposal = asyncio.run(LangGraphContextProvider(graph).decide(REQUEST))
    assert graph.value["delegated_request"]["binding"]["workspace_id"] == "w"
    assert graph.config["configurable"]["thread_id"] == "s:t"
    assert proposal.source_refs == ("graph:1",)


def test_langgraph_interrupt_fails_closed() -> None:
    class Graph:
        def invoke(self, value, config):
            return SimpleNamespace(value={"context_decision": DECISION}, interrupts=("review",))

    with pytest.raises(ValueError, match="interrupted"):
        asyncio.run(LangGraphContextProvider(Graph()).decide(REQUEST))
