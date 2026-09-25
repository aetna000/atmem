"""Product-owned integration for dynamically chosen, durably recorded tool calls."""
from dataclasses import dataclass
from hashlib import sha256
import json
import uuid
from urllib.error import HTTPError, URLError

from .client import ContinuityClient, RecoveryBlocked, Tool


@dataclass(frozen=True)
class RegisteredTool:
    tool: Tool
    capability: str = "none"
    timeout_seconds: float = 30
    retention_seconds: float = 0
    retired: bool = False


class GovernedToolRunner:
    """No local journal or recovery decisions: all authority comes from AtMem.

    Registry and namespace belong to application configuration, never the model.
    Disabling stops calls; it never falls through to an ungoverned execution.
    """
    def __init__(self, client: ContinuityClient, namespace: str, tools: dict[str, RegisteredTool], *, enabled=False):
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("a stable deployment namespace is required")
        self.client, self.namespace, self.tools, self.enabled = client, namespace, dict(tools), enabled
        self.run_id = "run_" + uuid.uuid4().hex

    def run_message(self, *, thread_id, checkpoint_ns, message_id, calls, durable=False):
        if not self.enabled or durable is not True:
            raise RecoveryBlocked("governed_tools_disabled_or_host_not_durable")
        if not all(isinstance(value, str) and value for value in (thread_id, message_id)) or not isinstance(checkpoint_ns, str):
            raise RecoveryBlocked("durable_host_identity_required")
        if not isinstance(calls, list) or not calls or len(calls) > 32:
            raise RecoveryBlocked("invalid_tool_call_batch")
        seen = set()
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("id"), str) or not call["id"] or call["id"] in seen:
                raise RecoveryBlocked("duplicate_or_missing_call_identity")
            seen.add(call["id"])
            if not isinstance(call.get("name"), str):
                raise RecoveryBlocked("invalid_tool_name")
            registered = self.tools.get(call.get("name"))
            if registered is None or registered.retired or not isinstance(call.get("args"), dict):
                raise RecoveryBlocked("tool_not_registered_or_retired")
        results = []
        for call in calls:
            registered = self.tools[call["name"]]
            identity = ["atmem-host-call-v1", self.namespace, thread_id, checkpoint_ns, message_id, call["id"]]
            workflow_key = "call_" + sha256(json.dumps(identity, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
            try:
                workflow = self.client.request("POST", "/v1/continuity", {"workflow_key": workflow_key, "activate": True,
                    "operations": [{"name": "call", "tool": call["name"], "arguments": call["args"],
                        "capability": registered.capability, "timeout_seconds": registered.timeout_seconds,
                        "retention_seconds": registered.retention_seconds}]})
                # Create replay never re-enables operator-paused work.
                result = self.client.run_operation(workflow["workflow_id"], "call", {call["name"]: registered.tool}, run_id=self.run_id)
            except HTTPError as exc:
                detail = ""
                try:
                    failure = json.loads(exc.read(8192)).get("error", {})
                    message = failure.get("message", "") if isinstance(failure, dict) else ""
                    if isinstance(message, str):
                        detail = ": " + message[:512]
                except Exception:
                    pass
                finally:
                    exc.close()
                raise RecoveryBlocked("controller_refused_" + str(exc.code) + detail) from exc
            except (URLError, TimeoutError, ConnectionError) as exc:
                raise RecoveryBlocked("controller_unavailable") from exc
            results.append({"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": json.dumps(result, allow_nan=False)})
        return results


def governed_langgraph_tools(runner: GovernedToolRunner):
    """A serialized tool node for a LangGraph graph with synchronous checkpoints.

    Tested against the pinned LangGraph profile. Missing framework durability
    markers fail closed rather than silently weakening the checkpoint contract.
    """
    def node(state, config):
        from importlib.metadata import version
        if version("langgraph") not in {"1.1.5", "1.2.12"}:
            raise RecoveryBlocked("unqualified_langgraph_version_use_1_1_5_or_1_2_12")
        configured = config.get("configurable", {})
        if configured.get("__pregel_durability") != "sync" or configured.get("__pregel_checkpointer") is None:
            raise RecoveryBlocked("invoke_with_sync_durability_and_persistent_checkpointer")
        checkpointer = configured["__pregel_checkpointer"]
        if type(checkpointer).__module__ != "langgraph.checkpoint.sqlite":
            raise RecoveryBlocked("supported_persistent_sqlite_checkpointer_required")
        with checkpointer.lock:
            if not any(row[1] == "main" and row[2] for row in checkpointer.conn.execute("PRAGMA database_list")):
                raise RecoveryBlocked("supported_persistent_sqlite_checkpointer_required")
        messages = state.get("messages", [])
        if not messages:
            raise RecoveryBlocked("durable_assistant_message_required")
        message = messages[-1]
        role = message.get("role") if isinstance(message, dict) else getattr(message, "type", None)
        if role not in {"assistant", "ai"}:
            raise RecoveryBlocked("assistant_tool_message_required")
        message_id = message.get("id") if isinstance(message, dict) else getattr(message, "id", None)
        calls = message.get("tool_calls") if isinstance(message, dict) else getattr(message, "tool_calls", None)
        return {"messages": runner.run_message(thread_id=configured.get("thread_id"),
            # Pregel's task checkpoint_ns contains ephemeral node/task IDs.
            # Use the application's stable graph namespace, not that task ID.
            checkpoint_ns=configured.get("continuity_namespace", "root"), message_id=message_id,
            calls=calls, durable=True)}
    return node
