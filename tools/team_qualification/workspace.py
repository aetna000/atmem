"""Disposable encrypted project used by team transport and outcome qualification."""

import json
from pathlib import Path
import threading

from atmem import Memory
from atmem.contracts import SourceCaptureRequest
from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer, dashboard_html
from atmem.evidence import CaptureMode, EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.extract.formation import form_typed_proposals
from atmem.service.household import HouseholdApplication

AGENTS = {
    "openclaw": "dispatcher",
    "hermes": "reviewer",
    "mcp": "observer",
    "langgraph": "graph",
    "pydantic-ai": "typed",
    "chatgpt": "cloud",
}
QUESTION = "What is my Atlas routing code?"


class Project:
    def __init__(self, root):
        self.root = Path(root)
        self.state_path = self.root / "state.json"
        db = self.root / "memory.db"
        HouseholdApplication.initialize(db, encrypted=True, backend="file")
        self.manager = ControlPlaneManager.start(
            host="generic", state_path=self.state_path, control_root=self.root / "control", memory_db=db
        )
        topology = self.manager.configure_agent_topology(
            [
                {"agent_id": agent, "workspace": "portable-project", "is_default": host == "openclaw"}
                for host, agent in AGENTS.items()
            ]
            + [{"agent_id": "outsider", "workspace": "other-project"}]
        )
        subject = topology["agent_subjects"]["dispatcher"]
        self.scope, self.db = self.manager._memory_authority_scope(
            self.manager.state(), subject_id=subject, agent_id="dispatcher"
        )
        self.access = EvidenceScope("local", subject, self.scope.workspace_id)
        self.owner = EvidencePrincipal(
            "project-owner", EvidenceRole.ADMINISTRATOR, EvidenceScope("local", subject)
        )
        self.session = {
            "account": {
                "username": "project-owner",
                "role": "administrator",
                "scope": self.access.to_dict(),
                "password_change_required": False,
            }
        }
        self.remember("routing-v1", "My Atlas routing code is AX-100.")
        self.manager.transition("active", actor="synthetic project owner")
        self.manager.evidence_service().set_capture_mode(self.owner, CaptureMode.FULL)
        self.server = None
        self.paths = {}

    def remember(self, source, fact):
        memory = Memory(self.db, auto_vectors=False)
        try:
            memory.capture_source(SourceCaptureRequest(source, source, self.scope, fact))
            proposals = form_typed_proposals(fact, scope=self.scope, source_id=source, formation_id=source)
            assert proposals
            for proposal in proposals:
                result = memory.submit_extraction_proposal(proposal, source_text=fact)
                assert result["review_state"] == "committed", result["review_state"]
        finally:
            memory.close()

    def serve(self, port=0):
        self.server = ControlDashboardServer(("127.0.0.1", port), self.manager, html=dashboard_html())
        self.endpoint = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(3)
            self.server = None

    def restart(self):
        port = self.server.server_port
        self.close()
        self.manager = ControlPlaneManager(self.state_path)
        self.serve(port)

    def bind(self, host, *, agent=None, destination=None, account=None):
        name = "team:" + host + ":" + (agent or AGENTS[host])
        grant = self.manager.evidence_service().grant(
            self.owner, principal_id=name, role=EvidenceRole.TEAM_HOST, scope=self.access
        )
        data = {**grant, "format": "atmem-team-binding-v1", "endpoint": self.endpoint}
        if account:
            data["account"] = account
        path = destination or self.root / (host + ".json")
        import os

        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
            json.dump(data, f)
        self.paths[host] = path
        return path
