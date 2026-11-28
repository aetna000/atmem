"""Drive actual host tool adapters with a deterministic tool selection for each case."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def server_spec(project, host):
    python = project.root / "tool-venv/bin/python"
    if not python.exists():
        import venv

        venv.EnvBuilder(system_site_packages=True, with_pip=False).create(python.parents[1])
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-build-isolation",
                "--no-deps",
                "--editable",
                str(ROOT),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
    return {
        "command": str(python),
        "args": ["-m", "atmem.agent_team", "serve", "--binding", str(project.paths[host]), "--host", host],
        "env": {"ATMEM_HOME": str(project.root / "unused-client-home")},
    }


def unpack(value):
    if isinstance(value, str):
        return unpack(json.loads(value))
    if isinstance(value, list):
        return unpack(value[0])
    if not isinstance(value, dict):
        raise ValueError("Unexpected host tool payload")
    if "run_id" in value or "runs" in value or "outcome" in value:
        return value
    for key in ("structuredContent", "content", "text", "result", "output", "data"):
        if key in value:
            return unpack(value[key])
    raise ValueError("Unexpected host tool payload: " + str(value)[:500])


def host_call(project, host, operation, args, hermes_root=None, openclaw_dist=None):
    tool = "team_" + operation
    config = server_spec(project, host)
    if host in {"openclaw", "hermes"}:
        env = {
            k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}
        }
        env.update(
            HOME=str(project.root),
            OPENCLAW_STATE_DIR=str(project.root / "openclaw-state"),
            HERMES_HOME=str(project.root / "hermes-home"),
            ATMEM_HOME=str(project.root / "unused-client-home"),
        )
        spec = {"workspace": str(project.root), "tool": tool, "args": args, "server": config}
        path = project.root / ("call-" + host + ".json")
        if host == "openclaw":
            dist = openclaw_dist or Path(shutil.which("openclaw")).resolve().parent / "dist"
            spec["openclawDist"] = str(dist)
            command = [shutil.which("node"), str(HERE / "openclaw.mjs"), str(path)]
        else:
            hermes_root = Path(hermes_root or Path.home() / ".hermes/hermes-agent")
            # Read the committed dependency selection without invoking host installation or repair.
            locator = (
                "import json,sys; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root)); "
                "from pm.environments import committed_venv,site_packages; from hermes_cli._launchers import resolve_store_python; "
                "print(json.dumps([str(resolve_store_python(root)),str(site_packages(committed_venv(root)))]))"
            )
            python, deps = json.loads(
                subprocess.check_output([sys.executable, "-I", "-c", locator, str(hermes_root)], text=True)
            )
            env["HERMES_RUNTIME_DIR"] = str(hermes_root.parent / "tools")
            driver = (
                "import runpy,sys; sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)]; "
                "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
            )
            command = [
                python,
                "-I",
                "-B",
                "-c",
                driver,
                str(hermes_root),
                deps,
                str(HERE / "hermes.py"),
                str(path),
            ]
        path.write_text(json.dumps(spec))
        process = subprocess.run(
            command, cwd=project.root, env=env, capture_output=True, text=True, timeout=90
        )
        if process.returncode:
            raise RuntimeError(f"{host} tool failed: {process.stderr[-2500:]}")
        record = json.loads(process.stdout.strip().splitlines()[-1])
        reply = record["reply"]
        if host == "openclaw" and "structuredContent" in reply.get("details", {}):
            return reply["details"]["structuredContent"], record["tool"]
        return unpack(reply), record["tool"]
    if host == "mcp":
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def invoke():
            async with stdio_client(StdioServerParameters(**config)) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    assert tool in [t.name for t in (await session.list_tools()).tools]
                    result = await session.call_tool(tool, args)
                    assert not result.isError, result.content
                    return (
                        result.structuredContent
                        if result.structuredContent is not None
                        else unpack(result.content[0].text)
                    )

        return asyncio.run(invoke()), tool
    if host == "langgraph":
        from langgraph.prebuilt import ToolNode
        from langgraph.graph import StateGraph, MessagesState, START, END
        from langchain_core.messages import AIMessage
        from atmem.agent_team.client import langgraph_tools

        graph = StateGraph(MessagesState)
        graph.add_node("tools", ToolNode(langgraph_tools(project.paths[host])))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        messages = graph.compile().invoke(
            {
                "messages": [
                    AIMessage(content="", tool_calls=[{"name": tool, "args": args, "id": "qualification"}])
                ]
            }
        )
        return unpack(messages["messages"][-1].content), tool
    if host == "pydantic-ai":
        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart, ToolReturnPart
        from pydantic_ai.models.function import FunctionModel
        from atmem.agent_team.client import pydantic_tools

        observed = []

        def select(messages, info):
            parts = messages[-1].parts
            for part in parts:
                if isinstance(part, ToolReturnPart):
                    observed.append(part.content)
                    return ModelResponse(parts=[TextPart("Complete")])
            assert tool in {t.name for t in info.function_tools}
            return ModelResponse(parts=[ToolCallPart(tool, args, tool_call_id="qualification")])

        Agent(FunctionModel(select), tools=pydantic_tools(project.paths[host])).run_sync(
            "Exercise the selected handoff tool."
        )
        return unpack(observed[0]), tool
    raise ValueError("Unknown qualification transport.")
