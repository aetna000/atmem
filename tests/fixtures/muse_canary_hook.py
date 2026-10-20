"""Offline fixture for probing Muse's prompt-context hook boundary."""

import json
from pathlib import Path
import sys

payload = json.load(sys.stdin)
Path("host-hook-payload.json").write_text(json.dumps(payload), encoding="utf-8")
if payload.get("hook_event_name") == "UserPromptSubmit":
    Path("muse-hook-fired").write_text("UserPromptSubmit", encoding="utf-8")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "ATMEM_CODE_CANARY_7e46a92f",
    }}))
