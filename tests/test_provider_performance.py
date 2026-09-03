from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import quantiles
from time import perf_counter

from atmem.delegated.contracts import DelegatedBinding, DelegatedContextRequest
from atmem.provider_adapters.models import ContextItem, ProviderProposal, ProviderRuntimeIdentity
from atmem.provider_adapters.runtime import ProviderRuntime
from atmem.provider_adapters.signing import generate_keypair, load_private_key


def test_provider_independent_runtime_p95_is_below_25ms(tmp_path: Path) -> None:
    class Provider:
        def decide(self, request):
            return ProviderProposal.inject([ContextItem("stable", "source:1")])

    private, public = tmp_path / "private", tmp_path / "public"
    generate_keypair(private, public)
    runtime = ProviderRuntime(
        provider=Provider(), identity=ProviderRuntimeIdentity("p", "1", "i", "k"),
        private_key=load_private_key(private), adapter_kind="test",
    )
    binding = DelegatedBinding("r", "t", "s", "a", "u", "w")
    timings = []
    for _ in range(100):
        request = DelegatedContextRequest.create(binding=binding, query="q", max_context_bytes=1024, timeout_ms=5000).to_dict()
        start = perf_counter()
        runtime.handle(request)
        timings.append((perf_counter() - start) * 1000)
    assert quantiles(timings, n=20)[18] < 25
