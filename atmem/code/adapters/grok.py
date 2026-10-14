"""Grok event capture; prompt-hook output is not an injection boundary."""
from atmem.code.adapters.json_hooks import JsonHookAdapter


class GrokAdapter(JsonHookAdapter):
    host = "grok"
    relative_path = ".grok/hooks/atmem-code.json"
    # Grok currently discards UserPromptSubmit additionalContext. A caller
    # must verify a different supported context boundary before activation.
