"""Native Anthropic Messages API provider without storing API secrets."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atbot.domain import ProviderResult


class AnthropicProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        endpoint: str,
        api_key_env: str | None,
        egress_class: str = "remote",
        timeout: float = 90.0,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("Anthropic provider endpoint must use HTTPS")
        self.name = name
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key_env = api_key_env or "ANTHROPIC_API_KEY"
        self.egress_class = egress_class
        self.timeout = timeout

    @property
    def api_base(self) -> str:
        return self.endpoint if self.endpoint.endswith("/v1") else f"{self.endpoint}/v1"

    def _headers(self) -> dict[str, str]:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ValueError(f"provider key is missing: {self.api_key_env}")
        return {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": key,
        }

    def available(self) -> bool:
        if not os.environ.get(self.api_key_env):
            return False
        try:
            request = Request(f"{self.api_base}/models", headers=self._headers(), method="GET")
            with urlopen(request, timeout=1.5) as response:
                return 200 <= response.status < 300
        except (OSError, ValueError, HTTPError, URLError):
            return False

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> ProviderResult:
        schema_instruction = ""
        if schema:
            schema_instruction = (
                "\nReturn only JSON matching this JSON Schema:\n"
                + json.dumps(schema, separators=(",", ":"), sort_keys=True)
            )
        payload = {
            "model": self.model,
            "max_tokens": 2_048,
            "temperature": 0,
            "system": system + schema_instruction,
            "messages": [{"role": "user", "content": prompt}],
        }
        request = Request(
            f"{self.api_base}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            value = json.loads(response.read())
        text = "".join(
            str(block.get("text") or "")
            for block in value.get("content") or []
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        structured = json.loads(text) if schema else None
        usage = value.get("usage") or {}
        return ProviderResult(
            text=text,
            structured=structured,
            provider=self.name,
            model=self.model,
            egress_class=self.egress_class,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
