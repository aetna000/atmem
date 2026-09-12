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
        server.manager.record_blackbox_event(
            event_type="model.input",
            run_id="http-execution",
            execution_id="http-execution",
            event_id="http-event-1",
            producer_instance_id="http-fixture",
            producer_epoch="epoch-1",
            producer_sequence=1,
            event_time="2026-09-12T00:00:00.000Z",
            subject_id="local-user",
            payload={"provider": "fixture", "model": "fixture"},
        )
        executions = json.loads(opener.open(_request(base, token, "/v1/executions", role="admin")).read())
        assert executions["count"] == 1
        execution = json.loads(opener.open(_request(base, token, "/v1/executions/http-execution", role="admin")).read())
        assert execution["event_count"] == 1
        server.manager.record_blackbox_event(
            event_type="model.input",
            run_id="encoded-execution",
            execution_id="encoded/execution",
            event_id="http-event-encoded",
            producer_instance_id="http-fixture-encoded",
            producer_epoch="epoch-1",
            producer_sequence=1,
            event_time="2026-09-12T00:00:01.000Z",
            subject_id="local-user",
            payload={"provider": "fixture", "model": "fixture"},
        )
        encoded = json.loads(
            opener.open(
                _request(base, token, "/v1/executions/encoded%2Fexecution", role="admin")
            ).read()
        )
        assert encoded["execution_id"] == "encoded/execution"
        with __import__("pytest").raises(HTTPError) as hidden:
            opener.open(_request(base, token, "/v1/executions/http-execution", role="admin", subject="other-user"))
        assert hidden.value.code == 404
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_evidence_accounts_enforce_view_reconstruct_and_plaintext_export(tmp_path) -> None:
    server, thread = _server(tmp_path)
    base = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener()
    try:
        server.manager.record_blackbox_event(
            event_type="turn.input",
            run_id="protected-http-run",
            execution_id="protected-http-run",
            event_id="protected-http-event",
            producer_instance_id="http-protected-fixture",
            producer_epoch="epoch-1",
            producer_sequence=1,
            event_time="2026-09-13T00:00:00.000Z",
            subject_id="local-user",
            payload={
                "prompt_sha256": "2" * 64,
                "prompt_chars": 22,
                "_atmem_evidence": {"prompt": "HTTP-PLAINTEXT-SECRET"},
            },
        )
        rows = server.manager.evidence_service().create_demo_accounts(
            subject_id="local-user"
        )
        tokens = {row["role"]: row["token"] for row in rows}

        def evidence_request(path, role, *, method="GET", body=None):
            return Request(
                base + path,
                method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={
                    "Authorization": f"Bearer {tokens[role]}",
                    "Content-Type": "application/json",
                    # This untrusted compatibility header must not elevate the account.
                    "X-AtMem-Role": "admin",
                },
            )

        viewed = json.loads(
            opener.open(
                evidence_request(
                    "/v1/evidence/runs/protected-http-run", "viewer"
                )
            ).read()
        )
        assert viewed["events"][0]["envelope"]["evidence"]["prompt"] == "HTTP-PLAINTEXT-SECRET"
        searched = json.loads(
            opener.open(
                evidence_request(
                    "/v1/evidence/search?query=HTTP-PLAINTEXT-SECRET", "viewer"
                )
            ).read()
        )
        assert len(searched["events"]) == 1
        with __import__("pytest").raises(HTTPError) as viewer_reconstruct:
            opener.open(
                evidence_request(
                    "/v1/evidence/reconstruct",
                    "viewer",
                    method="POST",
                    body={"run_id": "protected-http-run"},
                )
            )
        assert viewer_reconstruct.value.code == 403
        reconstruction = json.loads(
            opener.open(
                evidence_request(
                    "/v1/evidence/reconstruct",
                    "investigator",
                    method="POST",
                    body={"run_id": "protected-http-run"},
                )
            ).read()
        )
        assert reconstruction["reconstructable"] is True
        replay = json.loads(
            opener.open(
                evidence_request(
                    "/v1/evidence/replay-manifest",
                    "investigator",
                    method="POST",
                    body={"run_id": "protected-http-run"},
                )
            ).read()
        )
        assert replay["executable"] is False
        with __import__("pytest").raises(HTTPError) as investigator_export:
            opener.open(
                evidence_request(
                    "/v1/evidence/export/plaintext",
                    "investigator",
                    method="POST",
                    body={
                        "run_id": "protected-http-run",
                        "confirmation": "EXPORT protected-http-run",
                    },
                )
            )
        assert investigator_export.value.code == 403
        exported = json.loads(
            opener.open(
                evidence_request(
                    "/v1/evidence/export/plaintext",
                    "evidence_collector",
                    method="POST",
                    body={
                        "run_id": "protected-http-run",
                        "confirmation": "EXPORT protected-http-run",
                    },
                )
            ).read()
        )
        assert "content_base64" in exported
        rotated = json.loads(
            opener.open(
                evidence_request(
                    "/v1/evidence/settings/rotate",
                    "evidence_collector",
                    method="POST",
                    body={"confirmation": "ROTATE EVIDENCE KEY"},
                )
            ).read()
        )
        assert rotated["rotated"] is True
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
