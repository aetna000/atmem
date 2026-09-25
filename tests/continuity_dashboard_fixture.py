"""Isolated browser-test server. Never opens the user's Home or services."""
import json
from pathlib import Path
import secrets
import sys

from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer, dashboard_html
from atmem.continuity.service import ContinuityService
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope


root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=False)
manager = ControlPlaneManager.start(host="generic", state_path=root / "state.json",
    control_root=root / "control", memory_db=root / "memory.db")
manager.configure_agent_topology([{"agent_id": "main", "workspace": str(root), "is_default": True}])
identity = manager.identity_service()
bootstrap = identity.bootstrap()
password = secrets.token_urlsafe(30)
session = identity.login("administrator", bootstrap["password"])
identity.change_password(session["session_token"], bootstrap["password"], password)
identity.logout(session["session_token"])
actor = EvidencePrincipal("browser-fixture", EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope("local", "local-user"))
service = ContinuityService(manager.evidence_service())
workflow = service.create(actor, "Publish-course-notes", [
    {"name": "publish", "tool": "documents.publish", "arguments": {}},
    {"name": "notify", "tool": "email.send", "arguments": {}},
])
service.configure(actor, workflow["workflow_id"], enabled=True)
first = service.begin(actor, workflow["workflow_id"], "publish", "run1", "attempt1")
service.outcome(actor, workflow["workflow_id"], "publish", first["lease_token"], {
    "outcome": "confirmed_succeeded", "operation_id": first["operation_id"],
    "effect_id": "course-notes", "result": {"published": "course-notes.md"},
}, run_id="run1", attempt_id="attempt1")
second = service.begin(actor, workflow["workflow_id"], "notify", "run1", "attempt2")
service.outcome(actor, workflow["workflow_id"], "notify", second["lease_token"], {"outcome": "unknown"}, run_id="run1", attempt_id="attempt2")
server = ControlDashboardServer(("127.0.0.1", 0), manager, html=dashboard_html())
print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "password": password}), flush=True)
server.serve_forever()
