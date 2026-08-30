"""Pydantic AI adapter for Ollama and OpenAI-compatible model servers."""

from __future__ import annotations

import importlib.util
import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from atbot.domain import ProviderResult


class PydanticAIProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        endpoint: str,
        api_key_env: str | None = None,
        egress_class: str = "local",
    ) -> None:
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost", "https://")):
            raise ValueError("provider endpoint must be loopback HTTP or HTTPS")
        self.name = name
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key_env = api_key_env
        self.egress_class = egress_class

    @property
    def api_base(self) -> str:
        return self.endpoint if self.endpoint.endswith("/v1") else f"{self.endpoint}/v1"

    def available(self) -> bool:
        if importlib.util.find_spec("pydantic_ai") is None:
            return False
        if self.api_key_env and not os.environ.get(self.api_key_env):
            return False
        try:
            request = Request(f"{self.api_base}/models", method="GET")
            with urlopen(request, timeout=1.5) as response:
                return 200 <= response.status < 300
        except (OSError, URLError):
            return False

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> ProviderResult:
        # Lazy imports keep AtBot diagnostics and deterministic fallback usable
        # even before the optional model framework has been installed.
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        key = os.environ.get(self.api_key_env or "") or "local-not-secret"
        model = OpenAIChatModel(
            self.model,
            provider=OpenAIProvider(base_url=self.api_base, api_key=key),
        )
        schema_instruction = ""
        if schema:
            schema_instruction = (
                "\nReturn only valid JSON matching this JSON Schema:\n"
                + json.dumps(schema, separators=(",", ":"), sort_keys=True)
            )
        agent = Agent(
            model,
            system_prompt=system + schema_instruction,
            model_settings={"temperature": 0},
        )
        result = agent.run_sync(prompt)
        text = str(result.output)
        structured = json.loads(text) if schema else None
        return ProviderResult(
            text=text,
            structured=structured,
            provider=self.name,
            model=self.model,
            egress_class=self.egress_class,
        )
