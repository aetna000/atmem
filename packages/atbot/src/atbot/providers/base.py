from __future__ import annotations

from typing import Any, Protocol

from atbot.domain import ProviderResult


class ModelProvider(Protocol):
    name: str
    model: str
    egress_class: str

    def available(self) -> bool: ...

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> ProviderResult: ...
