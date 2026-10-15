"""Harmless hook diagnostics, only used inside temporary test projects."""

import json
from pathlib import Path
import sys

payload = json.load(sys.stdin)
with Path("copilot-hook-inputs.jsonl").open("a") as stream:
    stream.write(json.dumps(payload) + "\n")
marker = "ATMEM_COPILOT_STARTUP_7e46a92f" if "initialPrompt" in payload else "ATMEM_COPILOT_PROMPT_7e46a92f"
print(json.dumps({"additionalContext": marker}))
