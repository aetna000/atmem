"""Explicit installed Code MCP configuration for disposable replay hosts only."""
import json
from pathlib import Path


def configuration(python, dependency_roots, *, database, root, scope, focused=False):
    # Preserve the venv executable path: resolving its symlink would silently
    # launch the base interpreter without the candidate's installed package.
    python = Path(python).absolute()
    if not python.is_file():
        raise ValueError("installed candidate interpreter required")
    database, root = Path(database).resolve(strict=True), Path(root).resolve(strict=True)
    if not database.is_file() or not root.is_dir():
        raise ValueError("existing isolated project and database required")
    dependencies = []
    for path in dependency_roots:
        path = Path(path).resolve(strict=True)
        if path.name != "site-packages":
            raise ValueError("installed dependency root required")
        dependencies.append(str(path))
    bootstrap = "import sys,runpy;sys.path.extend(" + repr(dependencies) + ");runpy.run_module('atmem.knowledge.code.mcp',run_name='__main__')"
    return {"command": str(python), "args": ["-I", "-c", bootstrap, "--db", str(database), "--root", str(root),
        "--subject", scope.subject_id, "--project-id", scope.project_id, "--profile", scope.profile_id, "--agent", scope.agent_id],
        "enabled_tools": (["code_context"] if focused else []) + ["code_search", "code_explore", "code_source"], "required": True,
        "startup_timeout_sec": 30, "tool_timeout_sec": 30, "default_tools_approval_mode": "approve"}


def arguments(config):
    if config is None:
        return []
    if (set(config) != {"command", "args", "enabled_tools", "required", "startup_timeout_sec", "tool_timeout_sec", "default_tools_approval_mode"}
        or config["enabled_tools"] not in (["code_search", "code_explore", "code_source"], ["code_context", "code_search", "code_explore", "code_source"]) or config["required"] is not True):
        raise ValueError("exact read-only progressive configuration required")
    def toml(value):
        if type(value) is bool:
            return str(value).lower()
        if isinstance(value, (int, float, str, list)):
            return json.dumps(value)
        raise ValueError("invalid inline configuration value")
    return ["-c", "mcp_servers.atmem_code={" + ",".join(key + "=" + toml(value) for key, value in config.items()) + "}"]


def prepare_navigation(lane, prepared):
    """Repack a separately receipted capability notice, not imaginary source.

    The original runtime pack remains prepared-only and is never marked
    submitted. Only this exact notice is sent as initial additional context.
    """
    from dataclasses import replace
    from hashlib import sha256
    import time
    from atmem.code.contracts import CodeContextPackage
    from atmem.code.receipts import CodeReceipts
    start = time.monotonic()
    generation = lane.knowledge.current(str(lane.root))
    graph = prepared["exposure"]["graph_evidence"]
    if generation is None or generation["snapshot_id"] != graph["knowledge_snapshot_id"]:
        raise PermissionError("progressive source generation changed")
    content = ("AtMem Code has indexed this project's current structure. Read-only atmem_code MCP tools are available: "
        "code_search uses an identifier substring (not an entire issue); code_explore follows a returned symbol ID; "
        "code_source reads bounded source at a returned path/line. Fetch relevant implementation before relying on an outline. "
        "Native search and tests remain available. After edits the index may be withheld; use current native source then. "
        "This notice contains no implementation or remembered experience. Snapshot: " + generation["snapshot_id"])
    if len(content.encode()) > prepared["request"].max_context_bytes:
        raise ValueError("progressive notice exceeds shared context budget")
    request = replace(prepared["request"], request_id=prepared["request"].request_id + "-navigation")
    package = CodeContextPackage(request.request_id, content, sha256(content.encode()).hexdigest(), ())
    exposure = CodeReceipts(lane.memory.store).prepare(request, package, host="codex", graph_evidence=graph,
                                                       repository_root=str(lane.root))
    return {**prepared, "request": request, "package": package, "exposure": exposure,
            "context_ms": prepared["context_ms"] + int((time.monotonic() - start) * 1000),
            "progressive_generation": generation}


def source_observations(events, generation):
    """Verify actual client-visible source answers against the frozen pre-state.

    No claim of independent full model-input capture or causal model use.
    """
    import base64
    from hashlib import sha256
    import re
    from atmem.knowledge.contracts import source_path
    verified = []
    for event in events:
        item = event.get("item", {})
        if (event.get("type") != "item.completed" or item.get("type") != "mcp_tool_call" or
            item.get("server") != "atmem_code" or item.get("tool") not in {"code_source", "code_context"} or item.get("status") != "completed"):
            continue
        try:
            answer = json.loads(item["result"]["content"][0]["text"])
            if answer["status"] != "current" or answer["snapshot_id"] != generation["snapshot_id"]:
                continue
            if item["tool"] == "code_context":
                from atmem.knowledge.code.packing import pack_generation
                args = item["arguments"]
                expected = pack_generation(generation, args["query"], budget=args.get("budget", 4096))
                if answer["content"] != expected or answer["content_sha256"] != sha256(expected.encode()).hexdigest():
                    raise ValueError("MCP focused source bytes differ")
                if re.search(r"(?m)^\d+:\s*(?:async\s+def|def|class)\s+\w+", expected):
                    verified.append({"item_id": item["id"], "kind": "focused_source_pack", "snapshot_id": answer["snapshot_id"],
                        "content_sha256": answer["content_sha256"], "assurance": "actual_cli_mcp_response_not_independent_full_model_input"})
                continue
            path = source_path(answer["path"])
            raw = base64.b64decode(generation["source_bytes"][path], validate=True)
            if sha256(raw).hexdigest() != answer["source_sha256"]:
                raise ValueError("MCP source hash differs")
            args = item["arguments"]
            start, count = args.get("start_line", 1), args.get("line_count", 30)
            if type(start) is not int or type(count) is not int or not 1 <= count <= 100 or start < 1:
                raise ValueError("MCP source bounds differ")
            if answer["content"] != "\n".join(raw.decode().splitlines()[start - 1:start - 1 + count]):
                raise ValueError("MCP source bytes differ")
            if re.search(r"(?m)^\s*(?:async\s+def|def|class)\s+\w+", answer["content"]):
                verified.append({"item_id": item["id"], "path": path, "start_line": start, "line_count": count,
                    "snapshot_id": answer["snapshot_id"], "content_sha256": sha256(answer["content"].encode()).hexdigest(),
                    "assurance": "actual_cli_mcp_response_not_independent_full_model_input"})
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
    return verified


def require_qualified_configuration(events):
    """The scored bridge must retain the exact host-qualified configuration.

    New scoring/receipt helpers may be appended; they may not silently alter
    the configuration factory, CLI launcher or its already tested behavior.
    """
    import base64
    from hashlib import sha256
    started = [e["envelope"]["payload"] for e in events if e["envelope"]["event_type"] == "mcp.host_started"]
    retained = [e["envelope"]["payload"] for e in events if e["envelope"]["event_type"] == "mcp.host_source_retention"]
    if len(started) != 1 or len(retained) != 1:
        raise ValueError("frozen host source qualification absent")
    for name in ("progressive.py", "runner.py"):
        old = base64.b64decode(retained[0]["files_base64"][name], validate=True)
        current = Path(__file__).with_name(name).read_bytes()
        if sha256(old).hexdigest() != started[0]["harness_sha256"][name]:
            raise ValueError("retained host source differs from qualification")
        if (not current.startswith(old) if name == "progressive.py" else current != old):
            raise ValueError("host-qualified configuration/launcher changed")
