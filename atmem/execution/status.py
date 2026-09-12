"""Evidence-bounded execution lifecycle classification."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def classify_execution(events: Iterable[Mapping[str, Any]]) -> str:
    bodies = [dict(item.get("body") or item) for item in events]
    terminal = next((b for b in reversed(bodies) if b.get("event_type") == "turn.ended"), None)
    if terminal is not None:
        payload = terminal.get("payload") or {}
        if payload.get("cancelled") is True:
            return "cancelled"
        return "succeeded" if payload.get("success") is True else "failed"
    if any(body.get("event_type") == "execution.waiting" for body in bodies):
        return "waiting"
    requested = {
        str(body.get("tool_call_id"))
        for body in bodies
        if body.get("event_type") == "tool.requested" and body.get("tool_call_id")
    }
    completed = {
        str(body.get("tool_call_id"))
        for body in bodies
        if body.get("event_type") == "tool.completed" and body.get("tool_call_id")
    }
    if requested - completed:
        return "waiting"
    return "running" if bodies else "incomplete"
