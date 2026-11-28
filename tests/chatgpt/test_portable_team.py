"""Exercise optional team tools through the real OAuth + streamable HTTP endpoint."""

import hashlib
import json
import os
from pathlib import Path

from atmem.agent_team.client import TeamClient
from tools.team_qualification.workspace import Project, QUESTION
from .test_integration import call


def test_account_bound_handoff_transport(cloud, tmp_path, monkeypatch):
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path / "local-home"))
    project = Project(tmp_path)
    project.serve()
    root = Path(json.loads(cloud.config.read_text())["home"]) / "team-bindings"
    root.mkdir(mode=0o700)
    try:
        user = cloud.user()
        other = cloud.user()
        readonly = cloud.user(scopes="memory:read")
        file = root / (hashlib.sha256(user["uid"].encode()).hexdigest() + ".json")
        project.bind("chatgpt", destination=file, account=user["uid"])
        sender = TeamClient.from_file(project.bind("openclaw"), "openclaw")
        run = sender.call(
            "offer", {"question": QUESTION, "recipient": "team:chatgpt:cloud", "request_id": "oauth-test"}
        )
        cloud.restart()
        args = {"run_id": run["run_id"]}
        assert call(cloud, other, "team_receive", args)["code"] == "team_binding_unavailable"
        assert call(cloud, readonly, "team_receive", args)["code"] == "permission_rejected"
        delivery = call(cloud, user, "team_receive", args)
        assert delivery["ok"] and "AX-100" in delivery["data"]["passages"][0]["text"]
        result = call(
            cloud,
            user,
            "team_complete",
            {**args, "quote": "AX-100", "delivery_id": delivery["data"]["delivery_id"]},
        )
        assert result["data"]["outcome"] == "answered"
        if destination := os.environ.get("ATMEM_TEAM_OAUTH_RECEIPT"):
            Path(destination).write_text(
                json.dumps(
                    {
                        "host": "chatgpt",
                        "transport": "OAuth 2 PKCE + streamable HTTP MCP",
                        "authority": "isolated Firebase Auth and Firestore emulators",
                        "tools": ["team_receive", "team_complete"],
                        "run_id": run["run_id"],
                        "foreign_account": "denied",
                        "read_only_grant": "denied",
                        "outcome": result["data"]["outcome"],
                        "live_chatgpt_ui": False,
                    },
                    indent=2,
                )
                + "\n"
            )
    finally:
        project.close()
        for path in root.glob("*.json"):
            path.unlink()
        root.rmdir()
        cloud.restart()
