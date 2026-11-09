"""Real stdio MCP clients against real encrypted AtMem stores, no Hermes."""
import io
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from atmem.evidence.models import EvidenceRole, EvidenceScope
from atmem.feedback.service import FeedbackService
from atmem.mcp.governed import GovernedMCPServer, MAX_MESSAGE_BYTES
from atmem.private_paths import protect_private_path
from rag_fixtures import setup_rag


def request(method, params=None, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def initialize(server, version="2025-11-25"):
    result = server.handle(request("initialize", {"protocolVersion": version, "capabilities": {},
                                                "clientInfo": {"name": "fixture", "version": "1"}}))
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return result


def test_protocol_scope_and_revocation(tmp_path):
    f = setup_rag(tmp_path)
    server = GovernedMCPServer(f.feedback, f.rag, f.session)
    assert "error" in server.handle(request("tools/list"))
    assert "error" in initialize(server, "2026-07-28")
    assert initialize(server)["result"]["protocolVersion"] == "2025-11-25"
    names = {t["name"] for t in server.handle(request("tools/list"))["result"]["tools"]}
    assert names == {"feedback_capabilities", "rag_sources", "rag_search", "rag_inspect",
                     "feedback_outcome", "feedback_quality", "feedback_report_outcome"}
    for extra in ("subject_id", "role", "credential", "endpoint", "workspace_id"):
        result = server.handle(request("tools/call", {"name": "rag_sources", "arguments": {extra: "admin"}}))
        assert result["error"]["code"] == -32602
    f.feedback.revoke_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"])
    assert server.handle(request("tools/list"))["error"]["code"] == -32001


def test_malformed_oversized_and_notification_frames(tmp_path):
    f = setup_rag(tmp_path)
    server = GovernedMCPServer(f.feedback, f.rag, f.session)
    for bad in ([], None, {}, {"jsonrpc": "2.0", "id": True, "method": "ping"}):
        assert server.handle(bad)["error"]["code"] == -32600
    sink = io.StringIO()
    server.serve(io.BytesIO(b'{nope}\n' + b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}\n'
                           + b'{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n' + b'x' * (MAX_MESSAGE_BYTES+2)), sink)
    responses = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert [r["error"]["code"] for r in responses] == [-32700, -32700, -32700, -32600]


class Client:
    def __init__(self, f, tmp_path, credential, name, *, command=None):
        path = tmp_path / (name + ".token")
        path.touch()
        protect_private_path(path)
        path.write_text(credential)
        self.process = subprocess.Popen((command or [sys.executable, "-m", "atmem.cli_feedback"]) + [
            "--root", str(f.evidence.root), "--vault-id", "rag", "--credential-file", str(path),
            "--agent", "writer", "--workspace", "project", "serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.counter = 0
        response = self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                           "clientInfo": {"name": name, "version": "1"}})
        assert response["result"]["protocolVersion"] == "2025-06-18"
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def call(self, method, params=None):
        self.counter += 1
        self.send(request(method, params, self.counter))
        line = self.process.stdout.readline()
        assert line, "stdio server unexpectedly exited"
        return json.loads(line)

    def tool(self, name, **arguments):
        return self.call("tools/call", {"name": name, "arguments": arguments})["result"]

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
            assert self.process.returncode == 0
            assert self.process.stderr.read() == ""
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()


def test_two_actual_clients_search_inspect_restart_and_isolation(tmp_path):
    f = setup_rag(tmp_path)
    f.feedback.clock = time.time
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
                           operations=("read", "search", "inspect", "report"), expires_at=int(time.time())+600)
    # An Alice owner cannot mint another subject's credential.
    with pytest.raises(PermissionError):
        f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="bob",
                         role=EvidenceRole.INVESTIGATOR, scope=EvidenceScope("local", "bob", "project"))
    second = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="second-reader",
                              role=EvidenceRole.INVESTIGATOR, scope=EvidenceScope("local", "alice", "project"))
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id="second-reader", operations=("read", "search", "inspect"), expires_at=int(time.time())+600)
    clients = []
    try:
        a = Client(f, tmp_path, f.user["token"], "client-a")
        clients.append(a)
        b = Client(f, tmp_path, second["token"], "client-b")
        clients.append(b)
        result = a.tool("rag_search", source_id="law", query="filing deadline", jurisdiction="XX", as_of="2026-01-01", idempotency_key="search-1")
        assert not result["isError"]
        receipt = result["structuredContent"]
        assert len(receipt["hits"]) == 1
        inspected = b.tool("rag_inspect", receipt_id=receipt["receipt_id"], document_id="fictional-act", chunk_id="current")
        assert inspected["structuredContent"]["hit"]["text"] == f.hits[0].text
        assert a.tool("rag_search", source_id="law", query="filing deadline", jurisdiction="XX", as_of="2026-01-01", idempotency_key="search-1")["structuredContent"] == receipt
        from atmem.contracts.feedback import ActionRequirement, OutcomeRecord
        outcome = OutcomeRecord("reported", f.scope, "run", "turn",
                                (ActionRequirement("write", "fixture.write", "v1", "write", ("fact",)),), ()).to_dict()
        outcome.pop("scope")
        reported = a.tool("feedback_report_outcome", outcome=outcome, idempotency_key="reported")
        assert not reported["isError"] and not reported["structuredContent"]["verified_success"]
        assert b.tool("feedback_outcome", outcome_id="reported")["structuredContent"] == reported["structuredContent"]
        assert b.tool("feedback_report_outcome", outcome=outcome, idempotency_key="forbidden")["isError"]
        f.feedback.revoke_agent(f.owner["token"], f.scope, principal_id="second-reader")
        assert b.call("tools/list")["error"]["code"] == -32001
        assert not a.tool("rag_sources")["isError"]
    finally:
        for client in clients:
            client.close()


def test_cli_requires_explicit_existing_store_and_private_token(tmp_path):
    token = tmp_path / "token"
    token.write_text("synthetic-token-not-real")
    process = subprocess.run([sys.executable, "-m", "atmem.cli_feedback", "--root", str(tmp_path / "missing"),
                              "--vault-id", "rag", "--credential-file", str(token), "--agent", "writer",
                              "--workspace", "project", "sources"], capture_output=True, text=True, timeout=10)
    assert process.returncode == 2 and not process.stdout
    assert "synthetic-token-not-real" not in process.stderr
    assert not (tmp_path / "missing").exists()
