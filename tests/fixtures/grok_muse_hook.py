"""Harmless canary; records only inputs from the isolated qualification project."""
import json
from pathlib import Path
import sys

payload = json.load(sys.stdin)
with Path("probe-hooks.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(payload) + "\n")
event = payload.get("hook_event_name")
if event in {"UserPromptSubmit", "user_prompt_submit"}:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
        "additionalContext": "ATMEM_CODE_CANARY_7e46a92f"}}))
