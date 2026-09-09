"""Pydantic AI-backed delegated context provider."""

from __future__ import annotations

import inspect
from typing import Any

from .models import ProviderProposal, ProviderRequest


class PydanticAIContextProvider:
    def __init__(self, agent: Any, *, provider: str = "configured", model: str = "configured", egress: str = "local"):
        if egress not in {"local", "hosted"}:
            raise ValueError("Pydantic AI egress must be local or hosted")
        self.agent = agent
        self.attribution = {"adapter": "pydantic-ai", "provider": provider, "model": model, "egress": egress}

    async def decide(self, request: ProviderRequest) -> ProviderProposal:
        prompt = {
            "query": request.query,
            "query_sha256": request.query_sha256,
            "binding": request.binding.to_dict(),
            "max_context_bytes": request.max_context_bytes,
            "deadline": request.deadline,
        }
        if hasattr(self.agent, "run"):
            result = self.agent.run(prompt)
            if inspect.isawaitable(result):
                result = await result
        elif hasattr(self.agent, "run_sync"):
            result = self.agent.run_sync(prompt)
        else:
            raise ValueError("Pydantic AI provider requires an agent with run or run_sync")
        output = getattr(result, "output", None)
        if output is None:
            raise ValueError("Pydantic AI result has no validated output")
        if hasattr(output, "model_dump"):
            output = output.model_dump(mode="python")
        proposal = ProviderProposal.from_dict(output)
        return ProviderProposal(
            decision=proposal.decision,
            items=proposal.items,
            source_refs=proposal.source_refs,
            withhold_reason=proposal.withhold_reason,
            attribution={**self.attribution, **proposal.attribution},
        ).validated()


def proposal_output_model() -> type[Any]:
    try:
        from pydantic import BaseModel, ConfigDict, Field
    except ImportError as exc:
        raise RuntimeError("install atmem[pydantic-provider] to build a Pydantic AI provider") from exc

    class ContextItemOutput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        text: str = Field(min_length=1, max_length=100_000)
        source_ref: str = Field(min_length=1, max_length=512)

    class ProposalOutput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        decision: str
        items: list[ContextItemOutput] = Field(default_factory=list, max_length=32)
        source_refs: list[str] = Field(default_factory=list, max_length=32)
        withhold_reason: dict[str, Any] | None = None
        attribution: dict[str, str] = Field(default_factory=dict)

    return ProposalOutput


def create_agent(*, model: Any, instructions: str) -> Any:
    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        raise RuntimeError("install atmem[pydantic-provider] to build a Pydantic AI provider") from exc
    return Agent(model, instructions=instructions, output_type=proposal_output_model())
