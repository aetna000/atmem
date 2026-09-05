"""Optional loopback client for AtBot intelligence with safe local fallback."""

from __future__ import annotations

import json
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
            if str(value.get("protocol_version") or "") != "1":
                raise ValueError("incompatible AtBot companion protocol")
            if value.get("canonical_storage") is not False:
                raise ValueError("AtBot companion claimed canonical storage authority")
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
        from atmem.control.atbot_service import AtBotServiceManager

        return AtBotServiceManager().ensure_running()

    def query(self, query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        from atmem.control.atbot_service import AtBotServiceManager

        if AtBotServiceManager().fallback_selected():
            return _fallback(
                query,
                candidates,
                {"available": False, "reason": "safe fallback was selected"},
            )
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
                {
                    "query": query,
                    "candidates": candidates,
                    "remote": AtBotServiceManager().configured_egress_class() == "remote",
                },
                default=str,
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
        from atmem.control.atbot_service import AtBotServiceManager

        health = (
            {"available": False, "reason": "safe fallback was selected"}
            if AtBotServiceManager().fallback_selected()
            else self.health()
        )
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
        from atmem.control.atbot_service import AtBotServiceManager

        health = (
            {"available": False, "reason": "safe fallback was selected"}
            if AtBotServiceManager().fallback_selected()
            else self.health()
        )
        if not health.get("available"):
            return {**fallback, "companion": {**fallback["companion"], "reason": health.get("reason")}}
        request = Request(
            f"{self.endpoint}/api/companion/propose",
            data=json.dumps(
                {
                    "message": clean,
                    "remote": AtBotServiceManager().configured_egress_class() == "remote",
                }
            ).encode("utf-8"),
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

    def propose_task_state(
        self,
        *,
        snapshot: dict[str, Any],
        observation: str,
        task_id: str,
        base_revision: int,
    ) -> dict[str, Any]:
        """Request a delta from AtBot and revalidate its authority boundary."""
        from atmem.control.atbot_service import AtBotServiceManager

        fallback = {
            "format": "atbot-task-state-proposal-result-v1",
            "delta": None,
            "authority_decision": None,
            "canonical_storage": False,
            "companion": {"available": False, "fallback": True},
        }
        if (
            str(snapshot.get("task_id") or "") != str(task_id)
            or int(snapshot.get("revision") or 0) != int(base_revision)
        ):
            raise ValueError("AtMem authorized snapshot identity is inconsistent")
        health = self.health()
        if not health.get("available"):
            return {**fallback, "companion": {**fallback["companion"], "reason": health.get("reason")}}
        body = {
            "snapshot": snapshot,
            "observation": " ".join(str(observation).split()),
            "task_id": task_id,
            "base_revision": int(base_revision),
            "remote": AtBotServiceManager().configured_egress_class() == "remote",
        }
        try:
            request = Request(
                f"{self.endpoint}/api/companion/task-state/propose",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-AtBot-CSRF": str(health["csrf_token"]),
                },
                method="POST",
            )
            with urlopen(request, timeout=self.timeout) as response:
                value = json.loads(response.read())
            if (
                value.get("format") != fallback["format"]
                or value.get("authority_decision") is not None
                or value.get("canonical_storage") is not False
            ):
                raise ValueError("invalid AtBot task-state boundary")
            delta = value.get("delta")
            if delta is not None:
                if not isinstance(delta, dict):
                    raise ValueError("AtBot task delta must be an object")
                if (
                    delta.get("format") != "atbot-task-state-delta-v1"
                    or str(delta.get("task_id")) != str(task_id)
                    or int(delta.get("base_revision") or 0) != int(base_revision)
                ):
                    raise ValueError("AtBot changed task identity or base revision")
                known_items = {
                    str(row.get("item_id"))
                    for row in snapshot.get("items") or ()
                    if isinstance(row, dict) and row.get("item_id")
                }
                known_constraints = {
                    str(row.get("constraint_id"))
                    for row in snapshot.get("constraints") or ()
                    if isinstance(row, dict) and row.get("constraint_id")
                }
                known_sources = {str(row) for row in snapshot.get("sources_to_inspect") or ()}
                known_phases = {str(row) for row in snapshot.get("phases") or ()}
                for operation in delta.get("operations") or ():
                    if not isinstance(operation, dict):
                        raise ValueError("AtBot returned a malformed task operation")
                    if operation.get("item_id") and str(operation["item_id"]) not in known_items:
                        raise ValueError("AtBot returned an item outside the authorized snapshot")
                    if (
                        operation.get("constraint_id")
                        and str(operation["constraint_id"]) not in known_constraints
                    ):
                        raise ValueError("AtBot returned a constraint outside the authorized snapshot")
                    if operation.get("source_id") and str(operation["source_id"]) not in known_sources:
                        raise ValueError("AtBot returned a source outside the authorized snapshot")
                    if operation.get("phase") and str(operation["phase"]) not in known_phases:
                        raise ValueError("AtBot returned a phase outside the authorized snapshot")
            return {**value, "companion": {"available": True, "fallback": False}}
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
