"""Local Ollama and frontier OpenAI-compatible provider adapter."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from atbot.domain import ProviderResult


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        endpoint: str,
        api_key_env: str | None = None,
        egress_class: str = "local",
        timeout: float = 90.0,
    ) -> None:
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost", "https://")):
            raise ValueError("provider endpoint must be loopback HTTP or HTTPS")
        self.name = name
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key_env = api_key_env
        self.egress_class = egress_class
        self.timeout = timeout

    def available(self) -> bool:
        if self.api_key_env and not os.environ.get(self.api_key_env):
            return False
        try:
            request = Request(f"{self.endpoint}/v1/models", method="GET")
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
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            key = os.environ.get(self.api_key_env)
            if not key:
                raise ValueError(f"provider key is missing: {self.api_key_env}")
            headers["Authorization"] = f"Bearer {key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "atbot_output", "schema": schema},
            }
        request = Request(
            f"{self.endpoint}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            value = json.loads(response.read())
        content = str(value["choices"][0]["message"]["content"])
        structured = None
        if schema:
            structured = json.loads(content)
        usage = value.get("usage") or {}
        return ProviderResult(
            text=content,
            structured=structured,
            provider=self.name,
            model=self.model,
            egress_class=self.egress_class,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
