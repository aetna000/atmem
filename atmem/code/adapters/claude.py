"""Claude Code local project settings preserve existing owner hooks."""
from atmem.code.adapters.json_hooks import JsonHookAdapter


class ClaudeAdapter(JsonHookAdapter):
    host = "claude"
    relative_path = ".claude/settings.local.json"
