"""Host-neutral MCP surfaces for memory control and agent-flight evidence.

The same manager operations back this server, the CLI, and the dashboard. A
deployment must still decide which tools are exposed to an agent versus an
operator. Host mode exposes only runtime observations; operator mode exposes
the complete host-neutral control and investigation surface. Adapter
installation and native-state restore drills remain local maintenance commands.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, TextIO

from atmem.mcp.server import PROTOCOL_VERSION, SERVER_VERSION
from atmem.control.manager import ControlPlaneManager


class ControlMCPServer:
    def __init__(self, manager: ControlPlaneManager, *, operator: bool = False) -> None:
        self.manager = manager
        self.operator = operator

    def serve(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
        for line in stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                response = self.handle(message)
            except Exception as exc:
                response = _error(None, -32700, str(exc))
            if response is not None:
                stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
                stdout.flush()

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if "id" not in message:
            return None
        request_id = message.get("id")
        method = message.get("method")
        try:
            if method == "initialize":
                params = message.get("params") or {}
                return _result(
                    request_id,
                    {
                        "protocolVersion": params.get(
                            "protocolVersion", PROTOCOL_VERSION
                        ),
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "atmem-control-operator" if self.operator else "atmem-control-plane",
                            "version": SERVER_VERSION,
                        },
                    },
                )
            if method == "ping":
                return _result(request_id, {})
            if method == "tools/list":
                return _result(
                    request_id,
                    {
                        "tools": _tools(
                            operator=self.operator,
                            host=self.manager.state().host,
                        )
                    },
                )
            if method == "tools/call":
                params = message.get("params") or {}
                return _result(
                    request_id,
                    self._call(
                        str(params.get("name") or ""),
                        params.get("arguments") or {},
                    ),
                )
            return _error(request_id, -32601, f"method not found: {method}")
        except Exception as exc:
            return _result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                },
            )

    def _call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.operator and name not in _host_tool_names(self.manager.state().host):
            raise ValueError(f"operator tool is not available to the host integration: {name}")
        if name == "control_capture":
            value = self.manager.capture(
                str(arguments["message"]),
                session_id=arguments.get("session_id"),
                authenticated_user=bool(arguments.get("authenticated_user", False)),
                subject_id=arguments.get("subject_id"),
                agent_id=arguments.get("agent_id"),
            )
        elif name == "control_sync_memory":
            value = self.manager.sync_memory()
        elif name == "control_sync_openclaw_memory":
            state = self.manager.state()
            if state.host != "openclaw":
                raise ValueError("native memory sync is available only for OpenClaw")
            from atmem.control.openclaw_native import MIRROR_MANIFEST_NAME, mirror_status

            if not (Path(state.control_dir) / MIRROR_MANIFEST_NAME).is_file():
                raise ValueError("the OpenClaw mirror has not been initialized")
            value = mirror_status(state, refresh=True)
        elif name == "control_prepare":
            value = self.manager.prepare(
                str(arguments["query"]),
                session_id=arguments.get("session_id"),
                host_run_id=arguments.get("host_run_id"),
                turn_id=arguments.get("turn_id"),
                user_id=arguments.get("user_id"),
                workspace_id=arguments.get("workspace_id"),
                subject_id=arguments.get("subject_id"),
                agent_id=arguments.get("agent_id"),
            )
        elif name == "control_exposure_shown":
            value = {
                "confirmed": self.manager.confirm_exposure(
                    str(arguments["exposure_id"])
                )
            }
        elif name == "control_prepare_task_context":
            value = self.manager.prepare_task_context(
                task_id=arguments.get("task_id"),
                subject_id=arguments.get("subject_id"),
                agent_id=arguments.get("agent_id"),
                workspace_id=arguments.get("workspace_id"),
                host_run_id=arguments.get("host_run_id"),
                session_id=arguments.get("session_id"),
                budget_chars=int(arguments.get("budget_chars") or 4_000),
            )
        elif name == "control_task_exposure_shown":
            value = {
                "confirmed": self.manager.confirm_task_exposure(
                    str(arguments["delivery_id"])
                )
            }
        elif name == "control_record_blackbox_event":
            value = self.manager.record_blackbox_event(
                event_type=str(arguments["event_type"]),
                run_id=str(arguments["run_id"]),
                session_id=arguments.get("session_id"),
                tool_call_id=arguments.get("tool_call_id"),
                turn_id=arguments.get("turn_id"),
                retrieval_id=arguments.get("retrieval_id"),
                context_event_id=arguments.get("context_event_id"),
                context_receipt_id=arguments.get("context_receipt_id"),
                outcome_id=arguments.get("outcome_id"),
                agent_id=arguments.get("agent_id"),
                workspace_id=arguments.get("workspace_id"),
                subject_id=arguments.get("subject_id"),
                payload=arguments.get("payload") or {},
            )
        elif name == "control_status":
            value = self.manager.status()
        elif name == "control_verify":
            value = self.manager.verify(probe=bool(arguments.get("probe", False)))
        elif name == "control_memory_status":
            value = self.manager.memory_status()
        elif name == "control_search_memory":
            value = self.manager.memory_search(
                str(arguments.get("query") or ""),
                limit=int(arguments.get("limit") or 50),
                subject_id=arguments.get("subject_id"),
                agent_id=arguments.get("agent_id"),
            )
        elif name == "control_list_memory_reviews":
            value = self.manager.memory_reviews()
        elif name == "control_get_memory_record":
            value = self.manager.memory_record(str(arguments["record_id"]))
        elif name == "control_search_memory_audit":
            value = self.manager.memory_audit(
                query=str(arguments.get("query") or ""),
                event_type=str(arguments.get("event_type") or ""),
                actor=str(arguments.get("actor") or ""),
                session_id=str(arguments.get("session_id") or ""),
                record_id=str(arguments.get("record_id") or ""),
                since=str(arguments.get("since") or ""),
                until=str(arguments.get("until") or ""),
                direction=str(arguments.get("direction") or "desc"),
                cursor=(
                    int(arguments["cursor"])
                    if arguments.get("cursor") is not None
                    else None
                ),
                limit=int(arguments.get("limit") or 100),
                include_facets=bool(arguments.get("include_facets", False)),
            )
        elif name == "control_export_memory_audit":
            filters = {
                key: str(arguments.get(key) or "")
                for key in (
                    "query",
                    "event_type",
                    "actor",
                    "session_id",
                    "record_id",
                    "since",
                    "until",
                    "direction",
                )
            }
            filters["direction"] = filters["direction"] or "desc"
            output_format = str(arguments.get("format") or "json")
            content, content_type = self.manager.export_memory_audit(
                output_format=output_format, filters=filters
            )
            value = {
                "format": output_format,
                "content_type": content_type,
                "content": content,
            }
        elif name == "control_review_memory":
            value = self.manager.review_memory(
                str(arguments["record_id"]), str(arguments["decision"])
            )
        elif name == "control_list_flights":
            value = self.manager.blackbox_runs(
                limit=int(arguments.get("limit") or 50),
                offset=int(arguments.get("offset") or 0),
            )
        elif name == "control_get_flight":
            value = self.manager.verify_blackbox_flight(str(arguments["run_id"]))
        elif name == "control_get_flight_story":
            value = self.manager.blackbox_flight_story(str(arguments["run_id"]))
        elif name == "control_export_flight":
            report = self.manager.verify_blackbox_flight(str(arguments["run_id"]))
            output_format = str(arguments.get("format") or "json")
            if output_format == "json":
                value = {"format": "json", "report": report}
            elif output_format == "text":
                from atmem.control.blackbox import format_flight_report

                value = {"format": "text", "content": format_flight_report(report)}
            else:
                raise ValueError("format must be json or text")
        elif name == "control_acknowledge_finding":
            value = self.manager.acknowledge_blackbox_attention(
                str(arguments["run_id"]),
                str(arguments["attention_code"]),
                actor=str(arguments.get("actor") or "mcp-operator"),
            )
        elif name == "control_list_agents":
            value = self.manager.agent_topology()
        elif name == "control_configure_agents":
            value = self.manager.configure_agent_topology(list(arguments["agents"]))
        elif name == "control_activate":
            value = self.manager.activate(actor=str(arguments.get("actor") or "mcp-operator"))
        elif name == "control_return_to_shadow":
            value = self.manager.deactivate(actor=str(arguments.get("actor") or "mcp-operator"))
        else:
            raise ValueError(f"unknown migration tool: {name}")
        return {
            "content": [
                {"type": "text", "text": json.dumps(value, indent=2, sort_keys=True)}
            ],
            "isError": False,
        }


def _host_tool_names(host: str) -> set[str]:
    sync_tool = (
        "control_sync_openclaw_memory" if host == "openclaw" else "control_sync_memory"
    )
    return {
        "control_capture",
        sync_tool,
        "control_prepare",
        "control_exposure_shown",
        "control_prepare_task_context",
        "control_task_exposure_shown",
        "control_record_blackbox_event",
        "control_status",
    }


def _tools(*, operator: bool = False, host: str = "generic") -> list[dict[str, Any]]:
    tools = [
        {
            "name": "control_capture",
            "description": "Capture candidate facts from an authenticated user turn.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "session_id": {"type": "string"},
                    "authenticated_user": {"type": "boolean"},
                    "subject_id": {"type": "string"},
                    "agent_id": {"type": "string"},
                },
                "required": ["message", "authenticated_user"],
                "additionalProperties": False,
            },
        },
        {
            "name": "control_sync_memory",
            "description": "Synchronize adapter-owned memory, or report event-driven generic shadow status.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "control_sync_openclaw_memory",
            "description": "Refresh the isolated mirror from OpenClaw's native memory files without reading the conversation transcript.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "control_prepare",
            "description": "Build a preview and inject it only when migration mode permits.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "session_id": {"type": "string"},
                    "host_run_id": {"type": "string"},
                    "turn_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "workspace_id": {"type": "string"},
                    "subject_id": {"type": "string"},
                    "agent_id": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "control_exposure_shown",
            "description": "Confirm that the host placed one requested context exposure.",
            "inputSchema": {
                "type": "object",
                "properties": {"exposure_id": {"type": "string"}},
                "required": ["exposure_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "control_prepare_task_context",
            "description": "Prepare governed task state for one exact task identity; absent identity withholds.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "host_run_id": {"type": "string"},
                    "subject_id": {"type": "string"},
                    "agent_id": {"type": "string"},
                    "workspace_id": {"type": "string"},
                    "budget_chars": {"type": "integer"}
                },
                "required": ["task_id", "agent_id", "workspace_id"],
                "additionalProperties": False
            },
        },
        {
            "name": "control_task_exposure_shown",
            "description": "Confirm exactly once that a prepared governed-task block reached the model boundary.",
            "inputSchema": {
                "type": "object",
                "properties": {"delivery_id": {"type": "string"}},
                "required": ["delivery_id"],
                "additionalProperties": False
            },
        },
        {
            "name": "control_record_blackbox_event",
            "description": "Append one content-minimizing host observation to the tamper-evident agent flight record.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "run_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "tool_call_id": {"type": "string"},
                    "turn_id": {"type": "string"},
                    "retrieval_id": {"type": "string"},
                    "context_event_id": {"type": "string"},
                    "context_receipt_id": {"type": "string"},
                    "outcome_id": {"type": "string"},
                    "agent_id": {"type": "string"},
                    "workspace_id": {"type": "string"},
                    "subject_id": {"type": "string"},
                    "payload": {"type": "object"},
                },
                "required": ["event_type", "run_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "control_status",
            "description": "Read fail-closed migration status and evidence counts.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "control_memory_status",
            "description": "Read host-neutral memory counts, integrity, and current shadow/active mode.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "control_verify",
            "description": "Run the same adapter-aware readiness and integrity verification used by CLI and dashboard.",
            "inputSchema": {
                "type": "object",
                "properties": {"probe": {"type": "boolean"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "control_search_memory",
            "description": "Search memory visible to one registered agent workspace.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}, "limit": {"type": "integer"},
                    "subject_id": {"type": "string"}, "agent_id": {"type": "string"},
                },
                "required": ["query"], "additionalProperties": False,
            },
        },
        {
            "name": "control_list_memory_reviews",
            "description": "List shadow memories waiting for an operator decision.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "control_get_memory_record",
            "description": "Inspect one memory and its provenance and lifecycle evidence.",
            "inputSchema": {
                "type": "object", "properties": {"record_id": {"type": "string"}},
                "required": ["record_id"], "additionalProperties": False,
            },
        },
        {
            "name": "control_search_memory_audit",
            "description": "Search the complete host-neutral memory evidence chain.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}, "event_type": {"type": "string"},
                    "actor": {"type": "string"}, "session_id": {"type": "string"},
                    "record_id": {"type": "string"}, "since": {"type": "string"},
                    "until": {"type": "string"}, "limit": {"type": "integer"},
                    "direction": {"type": "string", "enum": ["asc", "desc"]},
                    "cursor": {"type": "integer"},
                    "include_facets": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "control_review_memory",
            "description": "Approve or reject one exact shadow memory.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "record_id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["approve", "reject"]},
                },
                "required": ["record_id", "decision"], "additionalProperties": False,
            },
        },
        {
            "name": "control_export_memory_audit",
            "description": "Export the complete filtered memory evidence view in a portable format.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["json", "ndjson", "csv", "text"],
                    },
                    "query": {"type": "string"},
                    "event_type": {"type": "string"},
                    "actor": {"type": "string"},
                    "session_id": {"type": "string"},
                    "record_id": {"type": "string"},
                    "since": {"type": "string"},
                    "until": {"type": "string"},
                    "direction": {"type": "string", "enum": ["asc", "desc"]},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "control_list_flights",
            "description": "List recorded agent flights with pagination and active findings.",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer"}, "offset": {"type": "integer"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "control_get_flight",
            "description": "Verify and inspect one complete agent flight.",
            "inputSchema": {
                "type": "object", "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"], "additionalProperties": False,
            },
        },
        {
            "name": "control_get_flight_story",
            "description": "Get the concise human-readable story for one agent flight.",
            "inputSchema": {
                "type": "object", "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"], "additionalProperties": False,
            },
        },
        {
            "name": "control_export_flight",
            "description": "Export one portable verified flight report as JSON or human-readable text.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "format": {"type": "string", "enum": ["json", "text"]},
                },
                "required": ["run_id"], "additionalProperties": False,
            },
        },
        {
            "name": "control_acknowledge_finding",
            "description": "Acknowledge one exact current finding without altering its evidence.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"}, "attention_code": {"type": "string"},
                    "actor": {"type": "string"},
                },
                "required": ["run_id", "attention_code"], "additionalProperties": False,
            },
        },
        {
            "name": "control_list_agents",
            "description": "List registered agents and shared, isolated, or nested workspace scopes.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "control_configure_agents",
            "description": "Replace the generic adapter's explicit agent/workspace topology.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent_id": {"type": "string"}, "name": {"type": "string"},
                                "workspace": {"type": "string"}, "parent_workspace": {"type": "string"},
                                "is_default": {"type": "boolean"}, "persistent": {"type": "boolean"},
                            },
                            "required": ["agent_id", "workspace"], "additionalProperties": False,
                        },
                    }
                },
                "required": ["agents"], "additionalProperties": False,
            },
        },
        {
            "name": "control_activate",
            "description": "Explicitly allow the adapter to inject AtMem context after shadow review.",
            "inputSchema": {
                "type": "object", "properties": {"actor": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "control_return_to_shadow",
            "description": "Stop context injection while preserving capture and evidence.",
            "inputSchema": {
                "type": "object", "properties": {"actor": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    ]
    if operator:
        return [
            tool
            for tool in tools
            if tool["name"] != "control_sync_openclaw_memory"
        ]
    return [tool for tool in tools if tool["name"] in _host_tool_names(host)]


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
