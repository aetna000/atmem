from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os

from atmem.core.canonical import canonical_json, sha256_hex


TOPOLOGY_FORMAT = "atmem-agent-topology-v1"
TOPOLOGY_NAME = "agent-topology.json"


def default_topology(subject_id: str) -> dict[str, Any]:
    return build_topology(
        [{"agent_id": "main", "name": "main", "workspace": "default", "is_default": True}],
        base_subject_id=subject_id,
    )


def build_topology(
    agents: list[dict[str, Any]], *, base_subject_id: str
) -> dict[str, Any]:
    if not agents:
        raise ValueError("agent topology requires at least one agent")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in agents:
        agent_id = str(raw.get("agent_id") or "").strip()
        workspace = str(raw.get("workspace") or "").strip()
        if not agent_id or not workspace:
            raise ValueError("every agent requires agent_id and workspace")
        if agent_id in seen:
            raise ValueError(f"duplicate agent ID: {agent_id}")
        seen.add(agent_id)
        normalized.append(
            {
                "agent_id": agent_id,
                "name": str(raw.get("name") or agent_id),
                "workspace": workspace,
                "parent_workspace": (
                    str(raw["parent_workspace"]).strip()
                    if raw.get("parent_workspace")
                    else None
                ),
                "is_default": bool(raw.get("is_default")),
                "persistent": bool(raw.get("persistent", True)),
            }
        )
    default = next((row for row in normalized if row["is_default"]), normalized[0])
    for row in normalized:
        row["is_default"] = row is default
    primary = str(default["workspace"])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in normalized:
        grouped.setdefault(str(row["workspace"]), []).append(row)
    workspace_ids = {value: _workspace_id(value) for value in grouped}
    parents: dict[str, str | None] = {}
    for workspace, members in grouped.items():
        parent_values = {
            str(row["parent_workspace"])
            for row in members
            if row.get("parent_workspace")
        }
        if len(parent_values) > 1:
            raise ValueError(f"workspace {workspace!r} has conflicting parents")
        parent = next(iter(parent_values), None)
        if parent and parent not in workspace_ids:
            raise ValueError(f"unknown parent workspace: {parent}")
        parents[workspace] = parent
    for workspace in grouped:
        visited: set[str] = set()
        current: str | None = workspace
        while current is not None:
            if current in visited:
                raise ValueError(f"workspace nesting contains a cycle at {current!r}")
            visited.add(current)
            current = parents.get(current)
    workspaces: list[dict[str, Any]] = []
    for workspace, members in grouped.items():
        workspace_id = workspace_ids[workspace]
        parent = parents[workspace]
        subject = (
            base_subject_id
            if workspace == primary
            else f"{base_subject_id}:workspace:{workspace_id}"
        )
        workspaces.append(
            {
                "workspace_id": workspace_id,
                "workspace": workspace,
                "subject_id": subject,
                "agent_ids": [str(row["agent_id"]) for row in members],
                "is_primary": workspace == primary,
                "parent_workspace_id": workspace_ids.get(parent) if parent else None,
            }
        )
    scope_by_workspace = {row["workspace"]: row for row in workspaces}
    public_agents = [
        {
            **row,
            "workspace_id": scope_by_workspace[str(row["workspace"])]["workspace_id"],
            "subject_id": scope_by_workspace[str(row["workspace"])]["subject_id"],
        }
        for row in normalized
    ]
    body = {
        "format": TOPOLOGY_FORMAT,
        "default_agent_id": str(default["agent_id"]),
        "primary_workspace_id": workspace_ids[primary],
        "agents": public_agents,
        "workspaces": workspaces,
        "agent_subjects": {row["agent_id"]: row["subject_id"] for row in public_agents},
        "agent_workspaces": {row["agent_id"]: row["workspace"] for row in public_agents},
    }
    body["topology_sha256"] = sha256_hex(canonical_json(body))
    return body


def topology_path(control_dir: str | Path) -> Path:
    return Path(control_dir) / TOPOLOGY_NAME


def write_topology(control_dir: str | Path, topology: dict[str, Any]) -> dict[str, Any]:
    target = topology_path(control_dir)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps(topology, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, target)
    return topology


def load_topology(control_dir: str | Path, *, subject_id: str) -> dict[str, Any]:
    source = topology_path(control_dir)
    if not source.is_file():
        return default_topology(subject_id)
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("format") != TOPOLOGY_FORMAT:
        raise ValueError("unsupported agent topology")
    claimed = str(value.get("topology_sha256") or "")
    unsigned = {key: item for key, item in value.items() if key != "topology_sha256"}
    if claimed != sha256_hex(canonical_json(unsigned)):
        raise ValueError("agent topology digest mismatch")
    return value


def _workspace_id(workspace: str) -> str:
    return "ws_" + sha256_hex(workspace)[:16]
