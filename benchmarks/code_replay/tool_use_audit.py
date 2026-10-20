"""Observed tool uptake/output volumes, not token attribution or causality."""
import base64
from collections import Counter
from hashlib import sha256
import json


def audit_trial(events):
    def one(kind):
        values = [e["envelope"]["payload"] for e in events if e["envelope"]["event_type"] == kind]
        if len(values) != 1:
            raise ValueError("exactly one retained " + kind + " required")
        return values[0]
    attempt, terminal = one("agent.attempt"), one("trial.completed")
    raw = base64.b64decode(attempt["stdout_base64"], validate=True)
    completed, started, invalid = {}, {}, 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("event object required")
        except (ValueError, UnicodeError):
            invalid += 1
            continue
        item = message.get("item", {})
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        destination = completed if message.get("type") == "item.completed" else started if message.get("type") == "item.started" else None
        if destination is not None:
            if item["id"] in destination and item != destination[item["id"]]:
                raise ValueError("conflicting repeated tool event")
            destination[item["id"]] = item
    kinds = Counter(item.get("type") for item in completed.values())
    native = [item for item in completed.values() if item.get("type") == "command_execution"]
    outputs = [item["aggregated_output"].encode() for item in native if isinstance(item.get("aggregated_output"), str)]
    hashes = Counter(sha256(output).hexdigest() for output in outputs if output)
    mcp = [item for item in completed.values() if item.get("type") == "mcp_tool_call"]
    result = terminal["result"]
    return {"run_id": result["run_id"], "arm": result["arm"], "stdout_sha256": sha256(raw).hexdigest(),
        "invalid_stream_lines": invalid, "completed_native_commands": len(native),
        "completed_mcp_calls": len(mcp), "atmem_completed_mcp_calls": sum(item.get("server") == "atmem_code" for item in mcp),
        "atmem_tool_counts": dict(Counter(item.get("tool") for item in mcp if item.get("server") == "atmem_code")),
        "observed_native_output_bytes": sum(map(len, outputs)), "largest_native_output_bytes": max(map(len, outputs), default=0),
        "exact_nonempty_output_repeats": sum(n - 1 for n in hashes.values()),
        "native_outputs_available": len(outputs), "completed_item_types": dict(kinds),
        "started_mcp_calls": sum(item.get("type") == "mcp_tool_call" for item in started.values()),
        "recorded_input_tokens": result["tokens"]["input_tokens"], "recorded_functional_pass": result["functional_pass"],
        "complete_tool_trace_claimed": False, "tokens_attributed_to_outputs": False,
        "assurance": "observed_completed_cli_items_only_not_complete_host_exposure_or_causal_token_attribution"}
