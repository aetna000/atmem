"""Ordinary SDK calls against the actual control-plane HTTP service."""
import threading
from urllib.error import HTTPError

import pytest

from atmem.continuity.client import ContinuityClient, RecoveryBlocked, Tool
from atmem.control.manager import ControlPlaneManager
from atmem.control.web import ControlDashboardServer
from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope


@pytest.fixture
def running(tmp_path):
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path / "state.json",
        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db")
    manager.configure_agent_topology([{"agent_id": "main", "workspace": str(tmp_path), "is_default": True}])
    vault = manager.evidence_service()
    actor = EvidencePrincipal("owner", EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope("local", "local-user"))
    credential = vault.grant(actor, principal_id="operator", role=actor.role, scope=actor.scope)
    server = ControlDashboardServer(("127.0.0.1", 0), manager, html="safe")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = ContinuityClient(f"http://127.0.0.1:{server.server_port}", credential["token"])
    try:
        yield client, vault, actor, manager
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_user_sdk_skips_completed_work_without_benchmark(running):
    client, vault, owner, _ = running
    workflow = client.create("ordinary-upload", [{"name": "upload", "tool": "upload", "arguments": {"text": "hello"}}])
    workflow_id = workflow["workflow_id"]
    calls = []
    def upload(arguments, operation_id, key, timeout):
        calls.append(operation_id)
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id,
                "effect_id": "file-1", "result": {"file": "file-1"}}
    tools = {"upload": Tool(upload)}
    with pytest.raises(RecoveryBlocked):
        client.run(workflow_id, tools)
    assert not calls
    client.configure(workflow_id, True)
    grant = vault.grant(owner, principal_id="worker", role=EvidenceRole.CONTINUITY_HOST,
        scope=EvidenceScope("local", "local-user", run_id=workflow_id))
    worker = ContinuityClient(client.url, grant["token"])
    assert worker.run(workflow_id, tools) == {"upload": {"file": "file-1"}}
    restarted = ContinuityClient(client.url, grant["token"])
    assert restarted.run(workflow_id, tools) == {"upload": {"file": "file-1"}}
    assert len(calls) == 1
    with pytest.raises(HTTPError) as denied:
        worker.configure(workflow_id, False)
    assert denied.value.code == 403
    vault.revoke(owner, principal_id="worker")
    with pytest.raises(HTTPError) as revoked:
        restarted.run(workflow_id, tools)
    assert revoked.value.code == 401


def test_observer_outage_does_not_change_tool_result(running):
    client, _, _, _ = running
    workflow = client.create("observer-outage", [{"name": "work", "tool": "work"}])
    client.configure(workflow["workflow_id"], True)
    def offline(event):
        raise ConnectionError("observer is offline")
    client.observer = offline
    def work(arguments, operation_id, key, timeout):
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id,
                "effect_id": "effect", "result": 42}
    assert client.run(workflow["workflow_id"], {"work": Tool(work)}) == {"work": 42}
    assert client.observation_errors == ["ConnectionError", "ConnectionError"]


def test_operator_onboarding_uses_real_login_not_demo_accounts(running):
    from atmem.continuity.client import operator_credential
    client, vault, _, manager = running
    identity = manager.identity_service()
    bootstrap = identity.bootstrap()
    session = identity.login("administrator", bootstrap["password"])
    identity.change_password(session["session_token"], bootstrap["password"], "A strong local continuity password 99!")
    identity.logout(session["session_token"])
    grant = operator_credential(client.url, "administrator", "A strong local continuity password 99!", "new-operator")
    actor = vault.authenticate(grant["token"])
    assert actor.role is EvidenceRole.EVIDENCE_COLLECTOR


def test_usage_is_emitted_by_product_callback_and_bound_to_real_attempt(running):
    from atmem.continuity.client import record_charge
    client, _, _, _ = running
    events = []
    client.observer = events.append
    workflow = client.create("usage", [{"name": "work", "tool": "work"}])
    client.configure(workflow["workflow_id"], True)
    def work(arguments, operation_id, key, timeout):
        assert record_charge(charge_id="provider-response-1", charge_source="test-provider",
            input_tokens=10, output_tokens=2, cost_microusd=11, price_source="test-rate-v1")
        return {"outcome": "confirmed_succeeded", "operation_id": operation_id, "effect_id": "effect", "result": 42}
    assert client.run(workflow["workflow_id"], {"work": Tool(work)}) == {"work": 42}
    assert [event["event"] for event in events] == ["execute", "usage", "completed"]
    assert len({event["attempt_id"] for event in events}) == 1
    assert events[1]["cost_microusd"] == 11
    assert not record_charge(charge_id="outside", charge_source="test-provider")


def test_builtin_observer_has_wall_clock_bound_even_if_transport_stalls(monkeypatch):
    import time
    from atmem.continuity.client import AtFlowsObserver
    release = threading.Event()
    observer = AtFlowsObserver("http://127.0.0.1:1", "test-secret")
    monkeypatch.setattr(observer, "_send", lambda event: release.wait(10))
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            observer({"event": "execute"})
        assert time.monotonic() - started < 3.5
    finally:
        release.set()
