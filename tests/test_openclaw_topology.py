from __future__ import annotations

from pathlib import Path

from atmem.control.openclaw_topology import build_agent_topology


def test_agents_with_the_same_workspace_share_one_subject(tmp_path: Path) -> None:
    workspace = tmp_path / "shared"
    topology = build_agent_topology(
        [
            {"id": "main", "workspace": workspace, "isDefault": True},
            {"id": "research", "workspace": workspace},
        ],
        base_subject_id="user-1",
    )

    assert len(topology["agents"]) == 2
    assert len(topology["workspaces"]) == 1
    assert topology["agent_subjects"] == {
        "main": "user-1",
        "research": "user-1",
    }
    assert topology["workspaces"][0]["agent_ids"] == ["main", "research"]


def test_separate_and_nested_workspaces_are_isolated(tmp_path: Path) -> None:
    primary = tmp_path / "workspace"
    nested = primary / "projects" / "private-agent"
    separate = tmp_path / "research"
    topology = build_agent_topology(
        [
            {"id": "main", "workspace": primary, "isDefault": True},
            {"id": "private", "workspace": nested},
            {"id": "research", "workspace": separate},
        ],
        base_subject_id="user-1",
    )

    subjects = topology["agent_subjects"]
    assert subjects["main"] == "user-1"
    assert subjects["private"] != subjects["main"]
    assert subjects["research"] not in {subjects["main"], subjects["private"]}
    private_scope = next(
        row for row in topology["workspaces"] if "private" in row["agent_ids"]
    )
    assert private_scope["parent_workspace_id"] == topology["primary_workspace_id"]


def test_first_agent_is_default_when_openclaw_marks_none(tmp_path: Path) -> None:
    topology = build_agent_topology(
        [
            {"id": "alpha", "workspace": tmp_path / "a"},
            {"id": "beta", "workspace": tmp_path / "b"},
        ],
        base_subject_id="user-1",
    )

    assert topology["default_agent_id"] == "alpha"
    assert topology["agents"][0]["is_default"] is True
