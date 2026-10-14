"""Copilot CLI hooks use camelCase events and a separate SessionStart recall."""

import json
from atmem.code.adapters.json_hooks import JsonHookAdapter


class CopilotAdapter(JsonHookAdapter):
    host = "copilot"
    relative_path = ".github/hooks/atmem-code.json"
    events = ("sessionStart", "userPromptSubmitted", "postToolUse", "sessionEnd")

    def planned_configuration(self, previous: bytes | None) -> bytes:
        value = json.loads(previous) if previous else {"version": 1}
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("Copilot hook configuration requires version 1")
        hooks = value.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("Copilot hooks must be an object")
        for event in self.events:
            handlers = hooks.setdefault(event, [])
            if not isinstance(handlers, list):
                raise ValueError("Copilot event handlers must be a list")
            handler = {"type": "command", "command": self.command, "timeoutSec": 10}
            if handler not in handlers:
                handlers.append(handler)
        return (json.dumps(value, indent=2) + "\n").encode()
