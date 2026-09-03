"""LangGraph-backed delegated context provider."""

from __future__ import annotations

import inspect
from typing import Any

from .models import ProviderProposal, ProviderRequest


class LangGraphContextProvider:
    def __init__(self, graph: Any):
        self.graph = graph
        self.attribution = {"adapter": "langgraph"}

    async def decide(self, request: ProviderRequest) -> ProviderProposal:
        graph_input = {"delegated_request": {
            "query": request.query,
            "query_sha256": request.query_sha256,
            "binding": request.binding.to_dict(),
            "max_context_bytes": request.max_context_bytes,
            "deadline": request.deadline,
        }}
        config = {"configurable": {"thread_id": f"{request.binding.session_id}:{request.binding.turn_id}"}}
        if hasattr(self.graph, "ainvoke"):
            output = await self.graph.ainvoke(graph_input, config=dict(config))
        elif hasattr(self.graph, "invoke"):
            output = self.graph.invoke(graph_input, config=dict(config))
            if inspect.isawaitable(output):
                output = await output
        elif callable(self.graph):
            output = self.graph(graph_input, dict(config))
            if inspect.isawaitable(output):
                output = await output
        else:
            raise ValueError("LangGraph provider requires an invokable graph or callable")
        interrupts = getattr(output, "interrupts", ())
        if interrupts:
            raise ValueError("LangGraph interrupted before a context decision")
        value = getattr(output, "value", output)
        if not isinstance(value, dict) or set(value) != {"context_decision"}:
            raise ValueError("LangGraph output must contain only context_decision")
        return ProviderProposal.from_dict(value["context_decision"])
