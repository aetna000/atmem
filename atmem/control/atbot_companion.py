"""Optional loopback client for AtBot intelligence with safe local fallback."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AtBotCompanionClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:8770", *, timeout: float = 90.0) -> None:
        if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("AtBot companion endpoint must be loopback")
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        try:
            with urlopen(f"{self.endpoint}/api/companion/health", timeout=2.0) as response:
                value = json.loads(response.read())
            if value.get("role") != "atmem-intelligence-companion":
                raise ValueError("unexpected companion role")
            return {**value, "available": True, "endpoint": self.endpoint}
        except (OSError, ValueError, HTTPError, URLError, json.JSONDecodeError) as exc:
            return {
                "format": "atbot-companion-health-v1",
                "available": False,
                "endpoint": self.endpoint,
                "reason": str(exc),
            }

    def ensure_running(self) -> dict[str, Any]:
        """Start an installed/configured companion without making it authoritative."""
        current = self.health()
        if current.get("available"):
            return {**current, "managed_start": False}
        executable = shutil.which("atbot")
        config = Path.home() / ".atbot" / "config.json"
        if not executable:
            return {
                **current,
                "managed_start": False,
                "setup_action": "Install the AtMem intelligence extra when AtMem 2.2 is released.",
            }
        if not config.is_file():
            return {
                **current,
                "managed_start": False,
                "setup_action": "Run `atbot init` once to select a local model.",
            }
        try:
            subprocess.Popen(
                [executable, "serve"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            return {**current, "managed_start": False, "reason": str(exc)}
        for _ in range(10):
            time.sleep(0.1)
            refreshed = self.health()
            if refreshed.get("available"):
                return {**refreshed, "managed_start": True}
        return {**self.health(), "managed_start": True}

    def query(self, query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        health = self.health()
        allowed_ids = {
            str(row.get("record_id") or row.get("id"))
            for row in candidates
            if row.get("record_id") or row.get("id")
        }
        if not health.get("available"):
            return _fallback(query, candidates, health)
        try:
            body = json.dumps(
                {"query": query, "candidates": candidates}, default=str
            ).encode("utf-8")
            request = Request(
                f"{self.endpoint}/api/companion/query",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-AtBot-CSRF": str(health["csrf_token"]),
                },
                method="POST",
            )
            with urlopen(request, timeout=self.timeout) as response:
                value = json.loads(response.read())
            ranked = [str(item) for item in value.get("ranked_record_ids") or []]
            if any(record_id not in allowed_ids for record_id in ranked):
                raise ValueError("AtBot returned a record outside AtMem eligibility")
            return {**value, "companion": {"available": True, "fallback": False}}
        except (OSError, ValueError, HTTPError, URLError, json.JSONDecodeError) as exc:
            return _fallback(query, candidates, {**health, "reason": str(exc)})

    def expand_query(self, query: str) -> dict[str, Any]:
        """Send query text only; candidate content is prohibited on this call."""
        clean = " ".join(query.split())
        health = self.health()
        fallback = {
            "format": "atbot-query-expansion-v1",
            "query": clean,
            "expanded_queries": [clean],
            "content_received": False,
            "companion": {"available": False, "fallback": True},
        }
        if not health.get("available"):
            return fallback
        request = Request(
            f"{self.endpoint}/api/companion/expand-query",
            data=json.dumps({"query": clean}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-AtBot-CSRF": str(health["csrf_token"]),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=min(self.timeout, 10.0)) as response:
                value = json.loads(response.read())
            queries: list[str] = []
            for raw in value.get("expanded_queries") or []:
                item = " ".join(str(raw).split())[:200]
                if item and item.casefold() not in {row.casefold() for row in queries}:
                    queries.append(item)
                if len(queries) >= 6:
                    break
            if not queries or value.get("content_received") is not False:
                raise ValueError("invalid content-free expansion result")
            return {
                **value,
                "expanded_queries": queries,
                "companion": {"available": True, "fallback": False},
            }
        except (OSError, ValueError, HTTPError, URLError, json.JSONDecodeError):
            return fallback

    def propose(self, message: str) -> dict[str, Any]:
        """Request interpretation only; AtMem remains responsible for admission."""
        clean = " ".join(message.split())
        fallback = {
            "format": "atbot-memory-proposals-v1",
            "proposals": [],
            "interpreter": None,
            "content_received": False,
            "authority_decision": None,
            "canonical_storage": False,
            "companion": {"available": False, "fallback": True},
        }
        if not clean or len(clean) > 20_000:
            return fallback
        health = self.health()
        if not health.get("available"):
            return {**fallback, "companion": {**fallback["companion"], "reason": health.get("reason")}}
        request = Request(
            f"{self.endpoint}/api/companion/propose",
            data=json.dumps({"message": clean}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-AtBot-CSRF": str(health["csrf_token"]),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                value = json.loads(response.read())
            if (
                value.get("format") != "atbot-memory-proposals-v1"
                or value.get("content_received") is not True
                or value.get("authority_decision") is not None
                or value.get("canonical_storage") is not False
            ):
                raise ValueError("invalid AtBot proposal boundary")
            proposals: list[dict[str, Any]] = []
            for row in value.get("proposals") or []:
                if not isinstance(row, dict):
                    continue
                fact = " ".join(str(row.get("fact") or "").split())
                if not fact or len(fact) > 2_000:
                    continue
                confidence = float(row.get("confidence", 0.0))
                sensitivity = str(row.get("sensitivity") or "personal")
                action = str(row.get("suggested_action") or "uncertain")
                if not 0.0 <= confidence <= 1.0:
                    continue
                if sensitivity not in {"public", "internal", "personal", "sensitive", "restricted"}:
                    continue
                if action not in {"add", "duplicate", "supports", "extends", "contradicts", "supersedes", "uncertain"}:
                    continue
                entities = [
                    {str(key): str(item) for key, item in entity.items()}
                    for entity in row.get("entities") or []
                    if isinstance(entity, dict)
                ][:50]
                proposals.append(
                    {
                        "fact": fact,
                        "fact_key": str(row["fact_key"]).strip() if row.get("fact_key") else None,
                        "confidence": confidence,
                        "sensitivity": sensitivity,
                        "entities": entities,
                        "suggested_action": action,
                        # No records were disclosed to AtBot for extraction.
                        "related_record_ids": [],
                    }
                )
                if len(proposals) >= 8:
                    break
            interpreter = value.get("interpreter")
            if not isinstance(interpreter, dict):
                raise ValueError("AtBot omitted interpreter identity")
            return {
                **value,
                "proposals": proposals,
                "interpreter": interpreter,
                "companion": {"available": True, "fallback": False},
            }
        except (OSError, ValueError, TypeError, HTTPError, URLError, json.JSONDecodeError) as exc:
            return {**fallback, "companion": {**fallback["companion"], "reason": str(exc)}}


def _fallback(
    query: str, candidates: list[dict[str, Any]], health: dict[str, Any]
) -> dict[str, Any]:
    del query
    if not candidates:
        answer = "I couldn't find governed memory that answers that question."
        ranked: list[str] = []
    else:
        first = candidates[0]
        content = str(first.get("content") or first.get("match_excerpt") or "")
        answer = f"The closest governed memory is: {content}"
        ranked = [str(first.get("record_id") or first.get("id"))]
    return {
        "format": "atbot-memory-query-result-v1",
        "answer": answer,
        "ranked_record_ids": ranked,
        "explanation": "AtMem used its safe fallback because AtBot was unavailable.",
        "provider": "atmem-fallback",
        "model": "authority-ranking-v1",
        "companion": {
            "available": False,
            "fallback": True,
            "reason": health.get("reason"),
        },
    }
