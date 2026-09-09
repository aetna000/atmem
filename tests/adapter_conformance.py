"""Reusable black-box assertions for callback framework adapters."""
from __future__ import annotations
from typing import Any
from atmem.adapters.base import AtMemAdapterIdentity

class ConformanceManager:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
    def delegated_context_applies(self, **kwargs): return False
    def capture(self, message, **kwargs): return {"captured": 1}
    def prepare(self, query, **kwargs):
        return {"inject": True, "context": "remembered", "preview_id": "p", "exposure_id": "e", "candidate_ids": []}
    def confirm_exposure(self, value): return value == "e"
    def record_blackbox_event(self, **kwargs): self.events.append(kwargs); return {"event_id": str(len(self.events))}

def identity(framework="generic"):
    return AtMemAdapterIdentity(agent_id="agent", workspace_id="workspace", subject_id="subject", session_id="session", framework=framework)

def exercise(adapter, *, failure=False, cancelled=False):
    adapter.begin("run", "private prompt")
    messages = adapter.model_input("run", ["private prompt"], model="fixture")
    adapter.tool_requested("run", "search", "call", {"q": "private"})
    adapter.tool_completed("run", "search", "call", {"ok": True})
    adapter.model_output("run", "answer", model="fixture")
    adapter.finish("run", error=RuntimeError("fixture") if failure else None, cancelled=cancelled)
    return messages
