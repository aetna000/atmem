from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest

from atmem.control.manager import ControlPlaneManager
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.integrations.atflows import auth_mode, fetch_traces, review_leads


@contextmanager
def _atflows_server(rows: list[dict], *, delegated: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: ANN002
            pass

        def do_POST(self):  # noqa: N802
            if self.path == "/api/auth/login":
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if body.get("password") != "secret-password":
                    self.send_error(401)
                    return
                self._json({"authenticated": True, "password_change_required": False}, cookie=True)
                return
            if self.path == "/api/auth/logout":
                self._json({"authenticated": False})
                return
            self.send_error(404)

        def do_GET(self):  # noqa: N802
            if self.path == "/api/auth/status":
                self._json({"mode": "atmem" if delegated else "standalone", "authenticated": False})
                return
            expected = "atmem_session=fixture" if delegated else "atflows_session=fixture"
            if not self.path.startswith("/api/traces?") or expected not in self.headers.get("Cookie", ""):
                self.send_error(401)
                return
            self._json(rows)

        def _json(self, value, *, cookie=False):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if cookie:
                self.send_header("Set-Cookie", "atflows_session=fixture; Path=/; HttpOnly")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _manager(tmp_path: Path) -> ControlPlaneManager:
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
        subject_id="subject-a",
        memory_db=tmp_path / "memory.db",
    )
    manager.record_blackbox_event(
        event_type="tool.requested",
        run_id="run-1",
        session_id="session-1",
        execution_id="run-1",
        event_id="event-1",
        producer_instance_id="fixture",
        producer_epoch="epoch-1",
        producer_sequence=1,
        event_time="2026-09-20T00:00:00.000Z",
        subject_id="subject-a",
        payload={"tool_name": "test.tool", "_atmem_evidence": {"parts": [{"type": "text", "text": "PRIVATE PROMPT"}]}},
    )
    return manager


def test_atflows_lead_requires_exact_authorized_session_and_omits_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {"trace_id": "trace-1", "session_id": "session-1", "timestamp": 1000, "status": 500, "error": "PRIVATE ERROR", "request_body": "PRIVATE PROMPT"},
        {"trace_id": "trace-1", "session_id": "session-1", "timestamp": 1100, "status": 200, "error": None},
    ]
    with _atflows_server(rows) as base_url:
        traces = fetch_traces(base_url=base_url, password="secret-password", session_id="session-1", since_ms=500, until_ms=1500)
    assert len(traces) == 2
    assert "PRIVATE" not in json.dumps(traces)

    service = _manager(tmp_path).evidence_service()
    monkeypatch.setattr(
        service, "_materialize_artifacts",
        lambda *_args: pytest.fail("review must not load exact artifact bytes"),
    )
    investigator = EvidencePrincipal("investigator", EvidenceRole.INVESTIGATOR, EvidenceScope("local", "subject-a"))
    report = review_leads(service, investigator, run_id="run-1", session_id="session-1", traces=traces, since_ms=500, until_ms=1500)
    assert report["correlation"] == "matching_session_id_untrusted_telemetry"
    assert report["leads"] == [{"reason_code": "observed_trace_error", "trace_id": "trace-1", "first_seen_ms": 1000, "last_seen_ms": 1100}]
    assert "PRIVATE" not in json.dumps(report)

    unlinked = review_leads(service, investigator, run_id="run-1", session_id="other-session", traces=traces, since_ms=500, until_ms=1500)
    assert unlinked.keys() == report.keys()
    assert unlinked["leads"] == []
    assert unlinked["correlation"] == "unverified"
    assert unlinked["coverage"] == {"reported": False, "atflows_rows": None, "unique_traces": None, "truncated": None}
    other = review_leads(service, EvidencePrincipal("other", EvidenceRole.INVESTIGATOR, EvidenceScope("local", "other-subject")), run_id="run-1", session_id="session-1", traces=traces, since_ms=500, until_ms=1500)
    assert other["leads"] == []
    assert other["coverage"]["reported"] is False
    with pytest.raises(PermissionError):
        review_leads(service, EvidencePrincipal("restricted", EvidenceRole.INVESTIGATOR, EvidenceScope("local", "subject-a", run_id="other-run")), run_id="run-1", session_id="session-1", traces=traces, since_ms=500, until_ms=1500)
    with pytest.raises(PermissionError):
        review_leads(service, EvidencePrincipal("viewer", EvidenceRole.VIEWER, EvidenceScope("local", "subject-a")), run_id="run-1", session_id="session-1", traces=traces, since_ms=500, until_ms=1500)

    collector = EvidencePrincipal("collector", EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope("local", "subject-a"))
    service.delete_run(collector, "run-1", confirmation="DELETE run-1")
    deleted = review_leads(service, investigator, run_id="run-1", session_id="session-1", traces=traces, since_ms=500, until_ms=1500)
    assert deleted["leads"] == []
    assert deleted["coverage"]["reported"] is False


def test_atflows_fetch_rejects_non_loopback_and_out_of_window_rows() -> None:
    with pytest.raises(ValueError, match="loopback"):
        fetch_traces(base_url="http://example.com:1337", password="secret-password", session_id="session-1", since_ms=500, until_ms=1500)
    rows = [{"trace_id": "trace-1", "session_id": "session-1", "timestamp": 2000, "status": 500}]
    with _atflows_server(rows) as base_url:
        with pytest.raises(ValueError, match="time window"):
            fetch_traces(base_url=base_url, password="secret-password", session_id="session-1", since_ms=500, until_ms=1500)
        with pytest.raises(RuntimeError, match="authentication"):
            fetch_traces(base_url=base_url, password="wrong", session_id="session-1", since_ms=500, until_ms=1500)


def test_atflows_delegated_review_reuses_atmem_session() -> None:
    rows = [{"trace_id": "trace-1", "session_id": "session-1", "timestamp": 1000, "error": "private"}]
    with _atflows_server(rows, delegated=True) as base_url:
        assert auth_mode(base_url) == "atmem"
        traces = fetch_traces(base_url=base_url, atmem_session="fixture", session_id="session-1", since_ms=500, until_ms=1500)
        assert traces[0]["has_error"] is True
        with pytest.raises(RuntimeError, match="authentication"):
            fetch_traces(base_url=base_url, atmem_session="bad", session_id="session-1", since_ms=500, until_ms=1500)
    with pytest.raises(ValueError, match="loopback"):
        auth_mode("https://example.com")
