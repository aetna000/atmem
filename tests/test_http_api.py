from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer


def _server(tmp_path):
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path / "state.json", control_root=tmp_path / "control", memory_db=tmp_path / "memory.db")
    manager.configure_agent_topology([{"agent_id": "main", "workspace": str(tmp_path), "is_default": True}])
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html="safe")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _request(base, token, path, *, method="GET", body=None, role="agent", subject="local-user"):
    return Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-AtMem-Role": role, "X-AtMem-Subject": subject, "X-AtMem-Agent": "main"})


def test_authenticated_v1_idempotency_pagination_and_authority(tmp_path) -> None:
    server, thread = _server(tmp_path)
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener()
    token = json.loads(opener.open(base + "/api/session").read())["csrf_token"]
    try:
        with __import__("pytest").raises(HTTPError) as missing:
            opener.open(base + "/v1/health")
        assert missing.value.code == 401
        first = json.loads(opener.open(_request(base, token, "/v1/memories", method="POST", body={"message": "My city is Sydney.", "idempotency_key": "one"})).read())
        replay = json.loads(opener.open(_request(base, token, "/v1/memories", method="POST", body={"message": "My city is Sydney.", "idempotency_key": "one"})).read())
        assert replay == first
        with __import__("pytest").raises(HTTPError) as conflict:
            opener.open(_request(base, token, "/v1/memories", method="POST", body={"message": "different", "idempotency_key": "one"}))
        assert conflict.value.code == 409
        page = json.loads(opener.open(_request(base, token, "/v1/memories?limit=1", role="admin")).read())
        assert page["count"] == 1
        with __import__("pytest").raises(HTTPError) as forbidden:
            opener.open(_request(base, token, "/v1/audit"))
        assert forbidden.value.code == 403
        admin = json.loads(opener.open(_request(base, token, "/v1/configuration", role="admin")).read())
        assert admin["format"] == "atmem-api-configuration-v1"
        feature = json.loads(opener.open(_request(base, token, "/v1/features/adapters")).read())
        assert feature["available"] and feature["framework_adapters"]["mcp"]["exact_injection"] is False
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
