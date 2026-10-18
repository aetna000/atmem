"""Installed stdio MCP diagnostic on actual indexed public source; no solver."""
import json
import subprocess
import sys

from atmem.knowledge.code.mcp import CodeKnowledgeMCP


def probe_mcp(lane, *, stale=False, focused=False):
    server = CodeKnowledgeMCP(lane.app, lane.scope, str(lane.root))
    prepared = server.query("code_search", {"query": "getLogger"})
    calls = [("code_search", {"query": "getLogger"})]
    if stale:
        calls.append(("code_source", {"path": "logging/__init__.py"}))
    else:
        symbol = prepared["symbols"][0]
        calls.extend((("code_explore", {"id": symbol["id"]}),
            ("code_source", {"path": symbol["file"], "start_line": symbol["line"], "line_count": 30})))
    if focused:
        calls.append(("code_context", {"query": "logging.getLogger()", "budget": 4096}))
        if not stale:
            calls.append(("code_source", {"path": "logging/__init__.py", "line_count": 130}))
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    requests.extend({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}}
                    for i, (name, args) in enumerate(calls, 3))
    # Resolve only installed package/dependency roots. Never put the source
    # checkout ahead of the installed wheel in this independent process.
    dependencies = [p for p in sys.path if p.endswith("site-packages")]
    bootstrap = "import sys,runpy;sys.path.extend(" + repr(dependencies) + ");runpy.run_module('atmem.knowledge.code.mcp',run_name='__main__')"
    command = [sys.executable, "-I", "-c", bootstrap, "--db", str(lane.memory.store.path),
               "--root", str(lane.root), "--subject", lane.scope.subject_id,
               "--project-id", lane.scope.project_id, "--profile", lane.scope.profile_id, "--agent", lane.scope.agent_id]
    result = subprocess.run(command, input="\n".join(json.dumps(r) for r in requests) + "\n",
                            text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError("installed Code MCP diagnostic process failed: " + result.stderr[-1000:])
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    if len(replies) != len(requests) or [r.get("id") for r in replies] != list(range(1, len(requests) + 1)):
        raise ValueError("MCP request/reply binding failed")
    tools = replies[1]["result"]["tools"]
    if {t["name"] for t in tools} != ({"code_context"} if focused else set()) | {"code_search", "code_explore", "code_source"}:
        raise ValueError("read-only Code tool inventory differs")
    answers = []
    argument_error_verified = False
    for (name, args), reply in zip(calls, replies[2:]):
        if reply["result"].get("isError"):
            if focused and args.get("line_count") == 130:
                error = json.loads(reply["result"]["content"][0]["text"])
                argument_error_verified = error.get("field") == "line_count" and "1 to 100" in error.get("message", "")
                if argument_error_verified:
                    continue
            raise ValueError("Code MCP positive control refused")
        answer = json.loads(reply["result"]["content"][0]["text"])
        if answer["status"] != ("not_current" if stale else "current"):
            raise ValueError("Code MCP freshness control failed")
        answers.append(answer)
    if not stale and (not answers[0]["symbols"] or not answers[1]["symbols"] or "def getLogger(" not in answers[2]["content"]):
        raise ValueError("Code MCP actual implementation control failed")
    if focused and not stale:
        expected = lane.knowledge.context(str(lane.root), "logging.getLogger()", budget=4096)
        if answers[-1]["content"] != expected["content"] or "def getLogger(" not in answers[-1]["content"]:
            raise ValueError("focused context differs from the actual source pack")
        if not argument_error_verified:
            raise ValueError("safe bound feedback not observed")
    return {"passed": True, "stale": stale, "requests": requests, "replies": replies,
            "argument_error_verified": argument_error_verified,
            "transport": "installed_independent_stdio_process", "host_agent": "not_exercised", "model_calls": 0}
