"""Dependency-free Python client for the AtMem v1 loopback API."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


class AtMemClient:
    def __init__(self, endpoint: str, token: str, *, timeout: float = 5.0, role: str = "agent", subject_id: str = "local-user", agent_id: str = "main") -> None:
        self.endpoint = endpoint.rstrip("/")
        self.token, self.timeout, self.role, self.subject_id, self.agent_id = token, timeout, role, subject_id, agent_id

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = Request(f"{self.endpoint}/v1/{path.lstrip('/')}", data=data, method=method, headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "X-AtMem-Role": self.role, "X-AtMem-Subject": self.subject_id, "X-AtMem-Agent": self.agent_id})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())

    def health(self) -> dict[str, Any]: return self.request("GET", "health")
    def capabilities(self) -> dict[str, Any]: return self.request("GET", "capabilities")
    def memories(self, *, query: str = "", limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        from urllib.parse import urlencode
        return self.request("GET", "memories?" + urlencode({"query": query, "limit": limit, **({"cursor": cursor} if cursor else {})}))
    def remember(self, message: str, *, idempotency_key: str, session_id: str | None = None) -> dict[str, Any]: return self.request("POST", "memories", {"message": message, "idempotency_key": idempotency_key, "session_id": session_id})
    def query(self, query: str) -> dict[str, Any]: return self.request("POST", "query", {"query": query})
