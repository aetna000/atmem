"""Short upstream CODE integration; no product changes or owner configuration.

The MCP transport forwards typed operations to the full upstream public SDK.
It does not replace the graph backend, extraction, ranking or response contents.
"""
import argparse
import asyncio
from contextlib import redirect_stdout
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import sys

OPERATIONS = ("query_facts", "explore", "traverse", "find_path", "impact_analysis",
              "insights", "architecture", "delta")
DATASET = "click_short_structure"


def worker_environment(state, python):
    state = Path(state).absolute()
    if not state.name.startswith("cognee-") or not state.is_dir():
        raise ValueError("dedicated existing Cognee benchmark state required")
    return {"PATH": str(Path(python).parent) + ":/usr/bin:/bin",
            "HOME": str(state), "LANG": "en_US.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1", "TELEMETRY_DISABLED": "1",
            "COGNEE_TRACING_ENABLED": "false", "AUTO_FEEDBACK": "false",
            "CACHING": "true", "ENABLE_BACKEND_ACCESS_CONTROL": "true",
            "DATA_ROOT_DIRECTORY": str(state / "data"),
            "SYSTEM_ROOT_DIRECTORY": str(state / "system"),
            "CACHE_ROOT_DIRECTORY": str(state / "cache"),
            "COGNEE_LOGS_DIR": str(state / "logs"),
            "COGNEE_REPOS_DIR": str(state / "repos"),
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "ENOLA_NO_UPDATE_CHECK": "1", "ENOLA_NO_PROMPTS": "1"}


def tool_definition():
    return {"name": "code_search",
            "description": "Search Cognee's indexed pre-change code graph. Choose query_facts to find symbols/modules (query is a name substring), explore to inspect a symbol, or traverse/find_path/impact_analysis/insights/architecture/delta. Native source and tests remain available; current source takes precedence after edits.",
            "inputSchema": {"type": "object", "additionalProperties": False,
                "properties": {"operation": {"type": "string", "enum": list(OPERATIONS)},
                    "arguments": {"type": "object"}, "query": {"type": "string", "maxLength": 1000},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 100}},
                "required": ["operation"]}}


async def sdk_query(arguments):
    if (not isinstance(arguments, dict) or set(arguments) - {"operation", "arguments", "query", "top_k"}
            or arguments.get("operation") not in OPERATIONS):
        raise ValueError("invalid code-search request")
    fields = arguments.get("arguments") or {}
    if not isinstance(fields, dict) or "operation" in fields:
        raise ValueError("operation must be selected outside arguments")
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", 15)
    if not isinstance(query, str) or len(query) > 1000 or type(top_k) is not int or not 1 <= top_k <= 100:
        raise ValueError("bounded query required")
    import cognee
    from cognee import SearchType
    return await cognee.search(query_type=SearchType.CODE, query_text=query,
        datasets=[DATASET], top_k=top_k,
        code_query={"operation": arguments["operation"], **fields})


async def serve():
    """Minimal stdio MCP transport; SDK results are forwarded without repacking."""
    output = sys.stdout
    for line in sys.stdin:
        if len(line.encode()) > 100_000:
            raise ValueError("MCP request too large")
        request = json.loads(line)
        if "id" not in request:
            continue
        method, params = request.get("method"), request.get("params", {})
        try:
            if method == "initialize":
                result = {"protocolVersion": params["protocolVersion"], "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cognee-code-benchmark-transport", "version": "1"}}
            elif method == "tools/list":
                result = {"tools": [tool_definition()]}
            elif method == "ping":
                result = {}
            elif method == "tools/call" and params.get("name") == "code_search":
                with redirect_stdout(sys.stderr):
                    value = await sdk_query(params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value, default=str)}], "isError": False}
            else:
                raise ValueError("unsupported read-only MCP method")
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": request["id"],
                "error": {"code": -32602, "message": str(exc)}}
        output.write(json.dumps(response) + "\n")
        output.flush()


async def index(root):
    import cognee
    from cognee.tasks.code_graph import get_code_graph_tasks
    await cognee.run_custom_pipeline(tasks=get_code_graph_tasks(str(root), index_vectors=False),
        data=str(root), dataset=DATASET, pipeline_name="click_short_code_graph",
        skip_connection_test=True)
    return await sdk_query({"operation": "query_facts",
                            "arguments": {"name": "get_help_option", "kinds": ["symbol"], "limit": 10}})


def arguments(config):
    """Encode only the two predeclared read-only provider configurations."""
    if config is None:
        return []
    from benchmarks.code_replay.progressive import arguments as atmem_arguments
    if config["enabled_tools"] != ["code_search"]:
        return atmem_arguments(config)
    expected = {"command", "args", "enabled_tools", "required", "startup_timeout_sec",
                "tool_timeout_sec", "default_tools_approval_mode"}
    if set(config) != expected or config["required"] is not True:
        raise ValueError("strict Cognee benchmark transport configuration required")
    def toml(value):
        return str(value).lower() if type(value) is bool else json.dumps(value)
    return ["-c", "mcp_servers.code_structure={" + ",".join(k + "=" + toml(v) for k, v in config.items()) + "}"]


def runner():
    """Reuse the existing runner with exactly one transport-encoder substitution."""
    from benchmarks.code_replay import runner as existing
    source = inspect.getsource(existing.run_cli)
    old = "from benchmarks.code_replay.progressive import arguments as mcp_arguments"
    if source.count(old) != 1:
        raise ValueError("existing runner changed; review adaptation")
    source = source.replace(old, "from benchmarks.code_replay.cognee_click import arguments as mcp_arguments")
    namespace = dict(vars(existing))
    exec(compile(source, "<short-cognee-transport-runner>", "exec"), namespace)
    return namespace["run_cli"], source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("index", "serve"))
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.mode == "index":
        with redirect_stdout(sys.stderr):
            result = asyncio.run(index(args.root))
        print(json.dumps(result, default=str))
    else:
        asyncio.run(serve())


if __name__ == "__main__":
    main()
