"""Policy-aware local-first provider selection."""

from __future__ import annotations

from atbot.config import AtBotConfig
from atbot.providers.base import ModelProvider
from atbot.providers.local import DeterministicLocalProvider
from atbot.providers.pydantic_ai import PydanticAIProvider


class ModelRouter:
    def __init__(self, config: AtBotConfig) -> None:
        self.config = config
        self._providers: list[ModelProvider] = []
        for row in config.providers:
            if row.kind in {"ollama", "openai-compatible"}:
                self._providers.append(
                    PydanticAIProvider(
                        name=row.name,
                        model=row.model,
                        endpoint=row.endpoint,
                        api_key_env=row.api_key_env,
                        egress_class=row.egress_class,
                    )
                )
        self._providers.append(DeterministicLocalProvider())

    def select(self, *, sensitivity: str = "personal", remote: bool = False) -> ModelProvider:
        for provider in self._providers:
            if provider.egress_class == "remote":
                if not remote or not self.config.remote_egress_allowed:
                    continue
                if sensitivity in {"sensitive", "restricted"}:
                    continue
            elif remote:
                continue
            if provider.available():
                return provider
        return DeterministicLocalProvider()

    def status(self) -> list[dict[str, object]]:
        return [
            {
                "name": provider.name,
                "model": provider.model,
                "egress_class": provider.egress_class,
                "available": provider.available(),
            }
            for provider in self._providers
        ]
