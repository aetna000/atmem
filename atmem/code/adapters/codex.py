"""Codex project hooks require the host's hook trust review."""
from atmem.code.adapters.json_hooks import JsonHookAdapter


class CodexAdapter(JsonHookAdapter):
    host = "codex"
    relative_path = ".codex/hooks.json"
