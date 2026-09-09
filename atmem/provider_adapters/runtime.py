"""Shared execution runtime for provider adapters."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import threading
from time import perf_counter
from typing import Any

from atmem.delegated.contracts import MAX_CONTEXT_BYTES, REQUEST_CONTRACT_ID, DelegatedBinding
from atmem.delegated.validation import parse_json_strict
from .models import ContextItem, ProviderProposal, ProviderRequest, ProviderRuntimeIdentity
from .signing import signed_envelope


_REQUEST_FIELDS = {"contract_id", "binding", "query", "query_sha256", "max_context_bytes", "deadline"}


def parse_request(raw: bytes | str | dict[str, Any]) -> ProviderRequest:
    value = raw if isinstance(raw, dict) else parse_json_strict(raw)
    if not isinstance(value, dict) or set(value) != _REQUEST_FIELDS:
        raise ValueError("delegated request fields do not match the contract")
    if value["contract_id"] != REQUEST_CONTRACT_ID:
        raise ValueError("unsupported delegated request contract")
    query = value["query"]
    if not isinstance(query, str) or not query or len(query.encode("utf-8")) > 100_000:
        raise ValueError("invalid delegated query")
    if sha256(query.encode("utf-8")).hexdigest() != value["query_sha256"]:
        raise ValueError("delegated query digest mismatch")
    maximum = value["max_context_bytes"]
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= MAX_CONTEXT_BYTES:
        raise ValueError("invalid delegated context byte limit")
    deadline = value["deadline"]
    if not isinstance(deadline, str) or not deadline.endswith("Z"):
        raise ValueError("invalid delegated request deadline")
    try:
        parsed_deadline = datetime.fromisoformat(deadline[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid delegated request deadline") from exc
    if parsed_deadline <= datetime.now(timezone.utc):
        raise TimeoutError("delegated request deadline has elapsed")
    return ProviderRequest(
        binding=DelegatedBinding.from_dict(value["binding"]),
        query=query,
        query_sha256=value["query_sha256"],
        max_context_bytes=maximum,
        deadline=deadline,
    )


def build_context(items: tuple[ContextItem, ...], maximum: int) -> tuple[bytes, tuple[str, ...]]:
    accepted: list[bytes] = []
    refs: list[str] = []
    for item in items:
        block = ("Memory: " + item.text.replace("\x00", "") + "\n").encode("utf-8")
        if sum(map(len, accepted)) + len(block) > maximum:
            continue
        accepted.append(block)
        if item.source_ref not in refs:
            refs.append(item.source_ref)
    return b"".join(accepted), tuple(refs[:32])


class ProviderRuntime:
    def __init__(self, *, provider: Any, identity: ProviderRuntimeIdentity, private_key: Any, adapter_kind: str):
        self.provider = provider
        self.identity = identity
        self.private_key = private_key
        self.adapter_kind = adapter_kind
        self._metrics_lock = threading.Lock()
        self._last_decision: str | None = None
        self._last_adapter_latency_ms: float | None = None
        self._requests = 0

    async def handle_async(self, raw: bytes | str | dict[str, Any]) -> dict[str, Any]:
        request = parse_request(raw)
        deadline = datetime.fromisoformat(request.deadline[:-1] + "+00:00")
        timeout = max(0.0, (deadline - datetime.now(timezone.utc)).total_seconds())
        decide = self.provider.decide
        if inspect.iscoroutinefunction(decide):
            proposal = await asyncio.wait_for(decide(request), timeout=timeout)
        else:
            proposal = await asyncio.wait_for(asyncio.to_thread(decide, request), timeout=timeout)
            if inspect.isawaitable(proposal):
                proposal = await asyncio.wait_for(proposal, timeout=timeout)
        if isinstance(proposal, dict):
            proposal = ProviderProposal.from_dict(proposal)
        if not isinstance(proposal, ProviderProposal):
            raise ValueError("provider did not return a proposal")
        proposal = proposal.validated()
        context = b""
        if proposal.decision == "inject":
            context, admitted_refs = build_context(proposal.items, request.max_context_bytes)
            if not context:
                proposal = ProviderProposal.withhold()
            else:
                declared = set(proposal.source_refs)
                proposal = ProviderProposal(
                    decision="inject",
                    items=proposal.items,
                    source_refs=tuple(ref for ref in admitted_refs if ref in declared),
                    attribution=proposal.attribution,
                ).validated()
        signing_started = perf_counter()
        result = signed_envelope(
            request=request,
            proposal=proposal,
            context_bytes=context,
            identity=self.identity,
            private_key=self.private_key,
            adapter_kind=self.adapter_kind,
        )
        latency = (perf_counter() - signing_started) * 1000
        with self._metrics_lock:
            self._requests += 1
            self._last_decision = proposal.decision
            self._last_adapter_latency_ms = round(latency, 3)
        return result

    def handle(self, raw: bytes | str | dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self.handle_async(raw))

    def status(self) -> dict[str, Any]:
        with self._metrics_lock:
            operational = {
                "requests": self._requests,
                "last_decision": self._last_decision,
                "last_adapter_latency_ms": self._last_adapter_latency_ms,
            }
        attribution = getattr(self.provider, "attribution", {})
        return {
            **operational,
            "provider_id": self.identity.provider_id,
            "provider_version": self.identity.provider_version,
            "instance_id": self.identity.instance_id,
            "key_id": self.identity.key_id,
            "adapter": self.adapter_kind,
            "attribution": dict(attribution) if isinstance(attribution, dict) else {},
        }
