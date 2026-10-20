"""Read-only diagnosis of retained CLI usage; never impute or regrade tokens."""
import base64
from collections import Counter
from hashlib import sha256
import json


def audit_trial(events):
    envelopes = [event["envelope"] for event in events]
    completed = [event["payload"]["result"] for event in envelopes
                 if event["event_type"] == "trial.completed"]
    if len(completed) != 1:
        raise ValueError("exactly one terminal trial required; interruptions are separate")
    result = completed[0]
    attempts = [event["payload"] for event in envelopes if event["event_type"] == "agent.attempt"]
    if len(attempts) != 1:
        raise ValueError("exactly one retained CLI stream required")
    raw = base64.b64decode(attempts[0]["stdout_base64"], validate=True)
    parsed, invalid = [], 0
    for line in raw.splitlines():
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("event object required")
            parsed.append(event)
        except (ValueError, UnicodeDecodeError):
            invalid += 1
    terminals = [event for event in parsed if event.get("type") == "turn.completed"]
    missing = any(result["tokens"].get(key) is None
                  for key in ("input_tokens", "output_tokens", "cached_tokens"))
    if not missing:
        diagnosis = "receipt_recorded"
    elif invalid:
        diagnosis = "invalid_retained_stream"
    elif terminals:
        diagnosis = "completed_turn_requires_usage_schema_review"
    elif result["solver_exit_code"] == -9 and result["reason"] in {
            "tool_budget", "wall_budget", "output_budget"}:
        diagnosis = "harness_killed_before_terminal_usage"
    else:
        diagnosis = "no_terminal_usage_unresolved"
    return {"run_id": result["run_id"], "usage_missing": missing,
            "diagnosis": diagnosis, "reason": result["reason"],
            "exit_code": result["solver_exit_code"], "tool_calls": result["tool_calls"],
            "stdout_sha256": sha256(raw).hexdigest(), "stdout_bytes": len(raw),
            "invalid_json_lines": invalid,
            "event_types": dict(Counter(event.get("type") for event in parsed)),
            "top_level_usage_events": sum("usage" in event for event in parsed),
            "tokens_imputed": False}
