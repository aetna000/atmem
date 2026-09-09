"""Mem0-backed delegated context provider."""

from __future__ import annotations

import inspect
import os
from typing import Any

from .models import ContextItem, ProviderProposal, ProviderRequest


class Mem0ContextProvider:
    def __init__(self, client: Any, *, top_k: int = 10, mode: str = "injected"):
        if not 1 <= top_k <= 100:
            raise ValueError("Mem0 top_k must be between 1 and 100")
        self.client = client
        self.top_k = top_k
        self.mode = mode
        self.attribution = {"adapter": "mem0", "mode": mode}

    async def decide(self, request: ProviderRequest) -> ProviderProposal:
        filters = {
            "user_id": request.binding.user_id,
            "agent_id": request.binding.agent_id,
            "app_id": request.binding.workspace_id,
        }
        result = self.client.search(request.query, filters=filters, top_k=self.top_k)
        if inspect.isawaitable(result):
            result = await result
        rows = result.get("results") if isinstance(result, dict) else result
        if not isinstance(rows, list):
            raise ValueError("Mem0 search returned an unsupported result shape")
        items: list[ContextItem] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            memory_id = row.get("id") or row.get("memory_id")
            text = row.get("memory") or row.get("text")
            if not isinstance(memory_id, str) or not memory_id.strip() or not isinstance(text, str) or not text.strip():
                continue
            if memory_id in seen or self._contradicts_scope(row, filters):
                continue
            seen.add(memory_id)
            items.append(ContextItem(text=text.strip(), source_ref=f"mem0:{memory_id}"))
        if not items:
            return ProviderProposal.withhold()
        return ProviderProposal.inject(items, attribution={"adapter": "mem0", "mode": self.mode})

    @staticmethod
    def _contradicts_scope(row: dict[str, Any], filters: dict[str, str]) -> bool:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        for key, expected in filters.items():
            actual = row.get(key, metadata.get(key))
            if actual is not None and actual != expected:
                return True
        return False


def create_mem0_provider(*, mode: str = "oss", top_k: int = 10) -> Mem0ContextProvider:
    if mode == "platform":
        try:
            from mem0 import MemoryClient
        except ImportError as exc:
            raise RuntimeError("install atmem[mem0] to use the Mem0 provider") from exc
        if not os.environ.get("MEM0_API_KEY"):
            raise RuntimeError("MEM0_API_KEY is required for Mem0 platform mode")
        return Mem0ContextProvider(MemoryClient(), top_k=top_k, mode=mode)
    if mode == "oss":
        try:
            from mem0 import Memory
        except ImportError as exc:
            raise RuntimeError("install atmem[mem0] to use the Mem0 provider") from exc
        return Mem0ContextProvider(Memory(), top_k=top_k, mode=mode)
    raise ValueError("Mem0 mode must be oss or platform")
