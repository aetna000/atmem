from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


TOPOLOGY_FORMAT = "atmem-openclaw-agent-topology-v1"


def discover_openclaw_agents(
    executable: str | None = None,
    *,
    fallback_workspace: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return OpenClaw's persistent agents with canonical local paths.

    Older OpenClaw versions may not expose ``agents list``.  In that case the
    legacy single-agent workspace remains fully supported.
    """

    command = executable or shutil.which("openclaw")
    rows: list[Mapping[str, Any]] = []
    if command:
        try:
            result = subprocess.run(
                [command, "agents", "list", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            result = None
        if result is not None and result.returncode == 0:
            try:
                payload = json.loads(result.stdout)
                candidate_rows = (
                    payload
                    if isinstance(payload, list)
                    else payload.get("agents", [])
                    if isinstance(payload, dict)
                    else []
                )
                rows = [row for row in candidate_rows if isinstance(row, Mapping)]
            except json.JSONDecodeError:
                rows = []

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        agent_id = str(row.get("id") or "").strip()
        workspace_value = row.get("workspace") or row.get("workspaceDir")
        if not agent_id or agent_id in seen_ids or not workspace_value:
            continue
        workspace = Path(str(workspace_value)).expanduser().resolve(strict=False)
        agent_dir_value = row.get("agentDir") or row.get("agent_dir")
        normalized.append(
            {
                "agent_id": agent_id,
                "name": str(row.get("name") or agent_id),
                "workspace": str(workspace),
                "agent_dir": (
                    str(Path(str(agent_dir_value)).expanduser().resolve(strict=False))
                    if agent_dir_value
                    else None
                ),
                "model": str(row.get("model") or "") or None,
                "is_default": bool(row.get("isDefault") or row.get("is_default")),
            }
        )
        seen_ids.add(agent_id)

    if normalized:
        if not any(row["is_default"] for row in normalized):
            normalized[0]["is_default"] = True
        return normalized

    workspace = Path(
        fallback_workspace or Path.home() / ".openclaw" / "workspace"
    ).expanduser().resolve(strict=False)
    return [
        {
            "agent_id": "main",
            "name": "main",
            "workspace": str(workspace),
            "agent_dir": None,
            "model": None,
            "is_default": True,
        }
    ]


def build_agent_topology(
    agents: Iterable[Mapping[str, Any]],
    *,
    base_subject_id: str,
) -> dict[str, Any]:
    """Group persistent agents by exact workspace and assign memory subjects."""

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in agents:
        agent_id = str(raw.get("agent_id") or raw.get("id") or "").strip()
        workspace_value = raw.get("workspace") or raw.get("workspaceDir")
        if not agent_id or agent_id in seen_ids or not workspace_value:
            continue
        workspace = Path(str(workspace_value)).expanduser().resolve(strict=False)
        normalized.append(
            {
                "agent_id": agent_id,
                "name": str(raw.get("name") or agent_id),
                "workspace": str(workspace),
                "agent_dir": raw.get("agent_dir") or raw.get("agentDir"),
                "model": raw.get("model"),
                "is_default": bool(raw.get("is_default") or raw.get("isDefault")),
            }
        )
        seen_ids.add(agent_id)
    if not normalized:
        raise ValueError("OpenClaw agent topology contains no valid persistent agents")

    default = next((row for row in normalized if row["is_default"]), normalized[0])
    default["is_default"] = True
    primary_workspace = str(default["workspace"])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in normalized:
        grouped.setdefault(str(row["workspace"]), []).append(row)

    ordered_paths = [primary_workspace, *sorted(path for path in grouped if path != primary_workspace)]
    workspaces: list[dict[str, Any]] = []
    by_path: dict[str, dict[str, Any]] = {}
    for workspace_path in ordered_paths:
        workspace_id = _workspace_id(workspace_path)
        subject_id = (
            base_subject_id
            if workspace_path == primary_workspace
            else f"{base_subject_id}:workspace:{workspace_id}"
        )
        row = {
            "workspace_id": workspace_id,
            "workspace": workspace_path,
            "subject_id": subject_id,
            "agent_ids": [agent["agent_id"] for agent in grouped[workspace_path]],
            "is_primary": workspace_path == primary_workspace,
            "parent_workspace_id": None,
        }
        workspaces.append(row)
        by_path[workspace_path] = row

    # Nested workspaces remain independent.  Recording the nearest parent lets
    # the mirror exclude child files from a recursive parent import.
    for child in workspaces:
        child_path = Path(str(child["workspace"]))
        parents = [
            parent
            for parent in workspaces
            if parent is not child and _is_relative_to(child_path, Path(str(parent["workspace"])))
        ]
        if parents:
            nearest = max(parents, key=lambda row: len(Path(str(row["workspace"])).parts))
            child["parent_workspace_id"] = nearest["workspace_id"]

    workspace_by_path = {row["workspace"]: row for row in workspaces}
    public_agents: list[dict[str, Any]] = []
    for agent in normalized:
        scope = workspace_by_path[str(agent["workspace"])]
        public_agents.append(
            {
                **agent,
                "workspace_id": scope["workspace_id"],
                "subject_id": scope["subject_id"],
            }
        )

    return {
        "format": TOPOLOGY_FORMAT,
        "default_agent_id": str(default["agent_id"]),
        "primary_workspace_id": workspace_by_path[primary_workspace]["workspace_id"],
        "agents": public_agents,
        "workspaces": workspaces,
        "agent_subjects": {
            row["agent_id"]: row["subject_id"] for row in public_agents
        },
        "agent_workspaces": {
            row["agent_id"]: row["workspace"] for row in public_agents
        },
    }


def discover_agent_topology(
    *,
    base_subject_id: str,
    executable: str | None = None,
    fallback_workspace: str | Path | None = None,
) -> dict[str, Any]:
    return build_agent_topology(
        discover_openclaw_agents(
            executable, fallback_workspace=fallback_workspace
        ),
        base_subject_id=base_subject_id,
    )


def _workspace_id(workspace: str) -> str:
    return hashlib.sha256(workspace.encode("utf-8")).hexdigest()[:16]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return path != root
