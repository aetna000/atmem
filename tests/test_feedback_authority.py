"""Real credentials and vault grants, not model-provided actor/role labels."""

from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts.feedback import FeedbackScope
from atmem.evidence.models import EvidenceRole, EvidenceScope
from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService, FeedbackSession
from atmem.feedback.store import FeedbackError


@pytest.fixture
def configured(tmp_path):
    evidence = EvidenceService(tmp_path / "control", vault_id="feedback", home_root=tmp_path)
    credentials = evidence.create_demo_accounts(subject_id="alice")
    owner = credentials[2]
    user = credentials[1]
    now = [1_700_000_000]
    service = FeedbackService(evidence, clock=lambda: now[0])
    scope = FeedbackScope("local", "alice", "writer", "project")
    service.grant_agent(owner["token"], scope, principal_id=user["principal_id"],
                        operations=("read", "search", "inspect", "report", "propose"), expires_at=now[0]+60)
    return service, scope, credentials, now


def test_authentication_scope_and_capability_are_both_required(configured):
    service, scope, credentials, _ = configured
    session = service.bind(credentials[1]["token"], agent_id="writer", workspace_id="project")
    assert service.capabilities(session)["scope"] == scope.to_dict()
    assert service.capabilities(session)["external_host_tools"] == "advisory"
    assert credentials[1]["token"] not in repr(session)
    for other in (replace(scope, agent_id="other"), replace(scope, workspace_id="other"),
                  replace(scope, subject_id="bob"), replace(scope, tenant_id="other")):
        with pytest.raises(FeedbackError, match="denied"):
            service.capabilities(FeedbackSession(other, session.credential))
    for token in ("invalid", credentials[0]["token"]):
        with pytest.raises(FeedbackError, match="denied"):
            service.bind(token, agent_id="writer", workspace_id="project")
    with pytest.raises(FeedbackError, match="denied"):
        with service._authorized(session, "execute"):
            pytest.fail("missing agent capability was accepted")


@pytest.mark.parametrize("revoke", ["agent", "credential", "expiry"])
def test_existing_session_does_not_survive_revocation_or_expiry(configured, revoke):
    service, scope, credentials, now = configured
    session = service.bind(credentials[1]["token"], agent_id="writer", workspace_id="project")
    if revoke == "agent":
        service.revoke_agent(credentials[2]["token"], scope, principal_id=credentials[1]["principal_id"])
    elif revoke == "credential":
        service.evidence.revoke(service.evidence.authenticate(credentials[2]["token"]), principal_id=credentials[1]["principal_id"])
    else:
        now[0] += 61
    with pytest.raises(FeedbackError, match="denied"):
        service.capabilities(session)


def test_owner_cannot_delegate_another_subject_or_grant_owner_operations(configured):
    service, scope, credentials, now = configured
    with pytest.raises(FeedbackError, match="denied"):
        service.grant_agent(credentials[1]["token"], scope, principal_id="model",
                            operations=("search",), expires_at=now[0]+60)
    with pytest.raises(FeedbackError, match="denied"):
        service.grant_agent(credentials[2]["token"], replace(scope, subject_id="bob"), principal_id="model",
                            operations=("search",), expires_at=now[0]+60)
    for operations in (("review",), ("activate",), ("export",), ("search", "search")):
        with pytest.raises(ValueError):
            service.grant_agent(credentials[2]["token"], scope, principal_id="model",
                                operations=operations, expires_at=now[0]+60)


def test_scoped_evidence_credential_cannot_bind_a_different_workspace(configured):
    service, _, credentials, now = configured
    evidence = service.evidence
    credential = evidence.grant(evidence.authenticate(credentials[2]["token"]), principal_id="scoped",
                                role=EvidenceRole.INVESTIGATOR,
                                scope=EvidenceScope("local", "alice", "project"))
    with pytest.raises(FeedbackError, match="denied"):
        service.bind(credential["token"], agent_id="writer", workspace_id="other")


def test_review_reuses_core_issued_identity_and_refuses_replay(configured):
    service, scope, credentials, _ = configured
    principal_id = credentials[1]["principal_id"]
    memory = Memory(":memory:", auto_vectors=False, review_authorities=({
        "principal_id": principal_id, "subject_id": "alice", "agent_id": "writer",
        "workspace_id": "project", "scopes": ("procedure:review",),
    },))
    service.memory = memory
    session = service.bind(credentials[1]["token"], agent_id="writer", workspace_id="project")
    authorization = memory.issue_review_authorization(principal_id, scopes=("procedure:review",))
    stored = {"subject_id": "alice", "agent_id": "writer", "workspace_id": "project"}
    with pytest.raises(FeedbackError, match="denied"):
        service.authorize_review(session, stored, replace(authorization, token="forged"))
    assert service.authorize_review(session, stored, authorization) == principal_id
    with pytest.raises(FeedbackError, match="denied"):
        service.authorize_review(session, stored, authorization)
    memory.close()


def test_denied_agent_access_has_protected_audit_and_no_data(configured):
    service, scope, credentials, _ = configured
    missing = FeedbackSession(replace(scope, agent_id="missing"), credentials[1]["token"])
    with pytest.raises(FeedbackError, match="denied"):
        service.capabilities(missing)
    with service.store.transaction(missing.scope) as tx:
        assert any(row["allowed"] is False for row in tx.list("audit"))


def test_revoked_owner_cannot_finish_a_waiting_privileged_grant(configured, monkeypatch):
    import threading
    service, scope, credentials, now = configured
    owner = service.evidence.authenticate(credentials[2]["token"])
    other = service.evidence.grant(owner, principal_id="other-controller", role=EvidenceRole.EVIDENCE_COLLECTOR,
                                  scope=scope.evidence_scope())
    entered, release = threading.Event(), threading.Event()
    main = threading.get_ident()
    original = service._principal
    calls = [0]
    errors = []
    def delayed(token):
        principal = original(token)
        if threading.get_ident() != main and token == credentials[2]["token"]:
            calls[0] += 1
            if calls[0] == 2:
                entered.set()
                assert release.wait(5)
        return principal
    monkeypatch.setattr(service, "_principal", delayed)
    def work():
        try:
            service.grant_agent(credentials[2]["token"], scope, principal_id="new-grantee",
                                operations=("search",), expires_at=now[0]+60)
        except FeedbackError as error:
            errors.append(error.code)
    thread = threading.Thread(target=work)
    thread.start()
    assert entered.wait(5)
    service.evidence.revoke(service.evidence.authenticate(other["token"]), principal_id=owner.principal_id)
    release.set()
    thread.join(5)
    assert not thread.is_alive() and errors == ["denied"]
    with service.owner_transaction(other["token"], scope) as (tx, _):
        assert tx.get("agent_grant", "new-grantee") is None
