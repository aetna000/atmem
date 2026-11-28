"""Use the real Hermes MCP discovery and tool dispatch registry in an isolated profile."""

import json
from pathlib import Path
import sys
from tools.mcp_tool_discovery import register_mcp_servers
from tools.registry import registry

spec = json.loads(Path(sys.argv[1]).read_text())
tools = register_mcp_servers({"atmem_team": spec["server"]})
name = next((item for item in tools if item.endswith(spec["tool"])), None)
if not name:
    raise RuntimeError(f"Hermes did not discover {spec['tool']}: {tools}")
result = registry.dispatch(name, spec["args"])
print(json.dumps({"tool": name, "reply": result}), flush=True)
