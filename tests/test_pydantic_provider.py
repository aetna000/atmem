from __future__ import annotations

import asyncio
from types import SimpleNamespace

from atmem.delegated.contracts import DelegatedBinding
from atmem.provider_adapters.models import ProviderRequest
from atmem.provider_adapters.pydantic_ai import PydanticAIContextProvider, proposal_output_model


REQUEST = ProviderRequest(DelegatedBinding("r", "t", "s", "a", "u", "w"), "query", "digest", 1000, "2099-01-01T00:00:00Z")


def test_pydantic_provider_reads_validated_output_and_records_egress() -> None:
    Output = proposal_output_model()
    output = Output(decision="inject", items=[{"text": "fact", "source_ref": "ai:1"}], source_refs=["ai:1"])

    class Agent:
        async def run(self, prompt):
            return SimpleNamespace(output=output)

    proposal = asyncio.run(PydanticAIContextProvider(Agent(), provider="openai", model="mini", egress="hosted").decide(REQUEST))
    assert proposal.items[0].text == "fact"
    assert proposal.attribution["egress"] == "hosted"
