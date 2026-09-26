from dataclasses import replace
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

import pytest

from atmem.adapters.hermes.service import HermesService
from atmem.adapters.hermes.client import HermesRPCClient, HermesRPCError
from atmem.control import ControlPlaneManager
from atmem.control.web import ControlDashboardServer
from atmem.service import APIError, APIPrincipal


@pytest.fixture
def service(tmp_path):
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path / "state.json",
                                        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db")
    workspace = manager.agent_topology()["workspaces"][0]
    admin = APIPrincipal("operator", "admin", workspace["subject_id"])
    service = HermesService(manager)
    grant = service.provision(admin, profile_id="profile-canary-private", agent_id="main",
                              workspace_id=workspace["workspace_id"], accept_reduced_capture=True)
    return service, admin, grant


def test_encrypted_restart_revocation_and_inactive_default(service):
    service, admin, grant = service
    token = grant["credential"]
    assert not service.dispatch(token, "status", {})["enabled"]
    with pytest.raises(APIError, match="not activated"):
        service.dispatch(token, "recall", {"query": "q", "session_id": "s", "turn_id": "t"})
    raw = (Path(service.manager.state().control_dir) / "hermes-bindings.enc.json").read_bytes()
    assert b"profile-canary-private" not in raw
    assert token.encode() not in raw
    restarted = HermesService(ControlPlaneManager(service.manager.state_path))
    assert restarted.dispatch(token, "status", {})["profile_id"] == "profile-canary-private"
    service.revoke(admin, grant["binding"]["binding_id"])
    with pytest.raises(APIError):
        restarted.dispatch(token, "status", {})


def test_scope_cannot_be_overridden_and_agent_cannot_provision(service):
    service, admin, grant = service
    for field in ("subject_id", "workspace_id", "role", "agent_id", "profile_id"):
        for operation, body in (("status", {}), ("recall", {"query": "q", "session_id": "s", "turn_id": "t"}),
                                ("observe", {"text": "t", "session_id": "s", "observation_id": "o"})):
            with pytest.raises(ValueError):
                service.dispatch(grant["credential"], operation, {**body, field: "other"})
    with pytest.raises(APIError):
        service.provision(replace(admin, role="agent"), profile_id="p", agent_id="main", workspace_id="w")
    with pytest.raises(PermissionError):
        service.configure(replace(admin, subject_id="other"), grant["binding"]["binding_id"], enabled=True)
    with pytest.raises(ValueError, match="explicit acceptance"):
        service.provision(admin, profile_id="p", agent_id="main", workspace_id="w")


def test_stale_topology_and_expired_token_deny(service):
    service, admin, grant = service
    row = service._load(grant["binding"]["binding_id"])
    row["expires_at"] = 0
    service._save(row)
    with pytest.raises(APIError):
        service.dispatch(grant["credential"], "status", {})
    row["expires_at"] = 9999999999
    row["identity"]["workspace_id"] = "not-authorized"
    service._save(row)
    with pytest.raises(PermissionError):
        service.dispatch(grant["credential"], "status", {})


def test_duplicate_provision_is_non_destructive(service):
    service, admin, grant = service
    with pytest.raises(APIError, match="already has"):
        service.provision(admin, profile_id=grant["binding"]["profile_id"], agent_id="main",
                          workspace_id=grant["binding"]["identity"]["workspace_id"], accept_reduced_capture=True)
    assert service.dispatch(grant["credential"], "status", {})["generation"] == 1
    with pytest.raises(APIError, match="distinct authorized"):
        service.provision(admin, profile_id="other-profile", agent_id="main",
                          workspace_id=grant["binding"]["identity"]["workspace_id"], accept_reduced_capture=True)


def test_revoke_during_slow_recall_succeeds_and_withholds_late_result(service, monkeypatch):
    service, admin, grant = service
    service.configure(admin, grant["binding"]["binding_id"], enabled=True)
    started, finish = threading.Event(), threading.Event()
    results = []
    def slow_prepare(*args, **kwargs):
        started.set()
        assert finish.wait(5)
        return {"inject": True, "context": "must not leave", "candidate_ids": []}
    monkeypatch.setattr(service.manager, "prepare", slow_prepare)
    def recall():
        try:
            results.append(service.dispatch(grant["credential"], "recall",
                                           {"query": "q", "session_id": "s", "turn_id": "t"}))
        except APIError as error:
            results.append(error.code)
    worker = threading.Thread(target=recall)
    worker.start()
    try:
        assert started.wait(5)
        assert service.revoke(admin, grant["binding"]["binding_id"])["revoked"]
    finally:
        finish.set()
        worker.join(5)
    assert results == ["unauthenticated"]


def test_revoke_does_not_wait_for_real_prepare_control_store(service, monkeypatch):
    service, admin, grant = service
    service.configure(admin, grant["binding"]["binding_id"], enabled=True)
    started, finish = threading.Event(), threading.Event()
    results = []
    def slow_expansion(self, query):
        started.set()
        assert finish.wait(5)
        return {"expanded_queries": [query], "content_received": False}
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.expand_query", slow_expansion)
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.query",
                        lambda self, query, candidates: {"ranked_record_ids": []})
    def recall():
        try:
            results.append(service.dispatch(grant["credential"], "recall",
                                           {"query": "q", "session_id": "s", "turn_id": "t"}))
        except APIError as error:
            results.append(error.code)
    worker = threading.Thread(target=recall)
    worker.start()
    try:
        assert started.wait(5)
        assert service.revoke(admin, grant["binding"]["binding_id"])["revoked"]
        assert not finish.is_set()
    finally:
        finish.set()
        worker.join(5)
    assert results == ["unauthenticated"]


def test_write_completed_during_revocation_is_uncertain_not_plain_denial(service, monkeypatch):
    service, admin, grant = service
    service.configure(admin, grant["binding"]["binding_id"], enabled=True)
    def accepted_then_revoked(self, **kwargs):
        service.revoke(admin, grant["binding"]["binding_id"])
        return {"result": {"captured": 1}}
    monkeypatch.setattr("atmem.adapters.hermes.binding.HermesMemoryBinding.observe_user", accepted_then_revoked)
    with pytest.raises(APIError) as error:
        service.dispatch(grant["credential"], "observe", {"text": "message", "session_id": "s", "observation_id": "o"})
    assert error.value.status == 409
    assert error.value.code == "observation_uncertain"


def test_rotation_invalidates_old_generation_and_requires_reactivation(service):
    service, admin, grant = service
    service.configure(admin, grant["binding"]["binding_id"], enabled=True)
    rotated = service.rotate(admin, grant["binding"]["binding_id"])
    assert rotated["binding"]["generation"] == 3
    assert not rotated["binding"]["enabled"]
    with pytest.raises(APIError):
        service.dispatch(grant["credential"], "status", {})
    assert service.dispatch(rotated["credential"], "status", {})["generation"] == 3
    assert "token_digest" not in service.list_bindings(admin)[0]
    assert service.list_bindings(replace(admin, subject_id="other")) == []


def test_post_write_auth_store_failure_reports_uncertain(service, monkeypatch):
    service, admin, grant = service
    service.configure(admin, grant["binding"]["binding_id"], enabled=True)
    def accepted_then_storage_failure(self, **kwargs):
        def unavailable(*args, **kwargs):
            raise RuntimeError("private storage error")
        monkeypatch.setattr(service, "_load", unavailable)
        return {"result": {"captured": 1}}
    monkeypatch.setattr("atmem.adapters.hermes.binding.HermesMemoryBinding.observe_user", accepted_then_storage_failure)
    with pytest.raises(APIError) as error:
        service.dispatch(grant["credential"], "observe", {"text": "message", "session_id": "s", "observation_id": "o"})
    assert error.value.status == 409
    assert error.value.code == "observation_uncertain"
    assert "private storage" not in str(error.value)


def test_locked_vault_and_changed_admin_scope_deny(service, monkeypatch):
    service, admin, grant = service
    with pytest.raises(PermissionError):
        service.configure(replace(admin, workspace_id="other"), grant["binding"]["binding_id"], enabled=True)
    monkeypatch.setattr("atmem.evidence.service.EvidenceService.storage_key",
                        lambda self: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(PermissionError):
        service.dispatch(grant["credential"], "status", {})


def test_two_real_profile_scopes_cannot_recall_each_others_memory(service, monkeypatch):
    service, admin, first = service
    manager = service.manager
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.propose",
                        lambda self, message: {"proposals": [], "companion": {"available": False}})
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
                        lambda self, query: {"expanded_queries": [query], "content_received": False})
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.query",
                        lambda self, query, candidates: {"ranked_record_ids": [row["record_id"] for row in candidates],
                                                        "companion": {"available": False}})
    topology = manager.configure_agent_topology([
        {"agent_id": "main", "workspace": "default", "is_default": True},
        {"agent_id": "secondary", "workspace": "separate"},
    ])
    other = next(row for row in topology["workspaces"] if "secondary" in row["agent_ids"])
    other_admin = replace(admin, subject_id=other["subject_id"])
    second = service.provision(other_admin, profile_id="separate-profile", agent_id="secondary",
                               workspace_id=other["workspace_id"], accept_reduced_capture=True)
    service.configure(admin, first["binding"]["binding_id"], enabled=True)
    service.configure(other_admin, second["binding"]["binding_id"], enabled=True)
    observation = {"text": "My preferred editor is Neovim.", "session_id": "s", "observation_id": "o"}
    result = service.dispatch(first["credential"], "observe", observation)
    assert result["result"]["captured"] > 0
    import json
    assert service.dispatch(first["credential"], "observe", observation) == json.loads(json.dumps(result))
    with pytest.raises(APIError, match="different payload"):
        service.dispatch(first["credential"], "observe", {**observation, "text": "changed"})
    for candidate in result["result"]["candidate_ids"]:
        manager.review_memory(candidate, "approve")
    manager.activate()
    query = {"query": "preferred editor", "session_id": "fresh", "turn_id": "1"}
    assert "Neovim" in service.dispatch(first["credential"], "recall", query)["context"]
    assert "Neovim" not in service.dispatch(second["credential"], "recall", query)["context"]


def test_actual_http_credential_is_not_general_api_authority(service, monkeypatch):
    service, admin, grant = service
    server = ControlDashboardServer(("127.0.0.1", 0), service.manager, html="safe")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    client = HermesRPCClient(endpoint, grant["credential"], profile_id=grant["binding"]["profile_id"])
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    opener = build_opener(ProxyHandler({}))
    try:
        assert client.status()["enabled"] is False
        assert client.recall("q", session_id="s", turn_id="t").context == ""
        for route in ("/v1/memories", "/v1/configuration", "/v1/evidence/status"):
            request = Request(endpoint + route, headers={"Authorization": "Bearer " + grant["credential"],
                                                        "X-AtMem-Role": "admin"})
            with pytest.raises(HTTPError) as error:
                opener.open(request)
            assert error.value.code == 401
        request = Request(endpoint + "/v1/hermes/status", data=b"{}", headers={
            "Authorization": "Bearer " + server.csrf_token})
        with pytest.raises(HTTPError) as error:
            opener.open(request)
        assert error.value.code == 401
        # Exercise the copied client's error protocol through the actual HTTP
        # boundary, including an unexpected structured server error code.
        for code, expected in (("observation_uncertain", "observation_uncertain"),
                               ("idempotency_conflict", "idempotency_conflict"),
                               ({"private": "value"}, "unavailable_or_denied")):
            def denied(self, *args, **kwargs):
                raise APIError(code, "private server details", status=409)
            monkeypatch.setattr(HermesService, "dispatch", denied)
            with pytest.raises(HermesRPCError) as client_error:
                client.observe_user("message", session_id="s", observation_id="o")
            assert client_error.value.status == 409
            assert client_error.value.code == expected
            assert "private" not in str(client_error.value)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


@pytest.mark.parametrize("url", ["https://127.0.0.1:80", "http://example.org:80", "http://127.0.0.1:80/path",
                                     "http://u:p@127.0.0.1:80", "http://127.0.0.1:80?secret=x"])
def test_client_rejects_nonlocal_or_ambiguous_endpoints(url):
    with pytest.raises(ValueError):
        HermesRPCClient(url, "hermes_test", profile_id="p")
