from dataclasses import replace
from hashlib import sha256

import pytest

from atmem import Memory
from atmem.contracts import SourceCaptureRequest
from atmem.contracts.feedback import RuleCandidate, RulePredicate, SourceRevision
from atmem.extract.review import ReviewService
from atmem.feedback.store import FeedbackError
from test_contracts_v1 import _proposal
from test_feedback_actions import actions_fixture


def review_fixture(tmp_path, *, include_owner=False, sensitivity="personal", source_agent_id="writer"):
    f, _ = actions_fixture(tmp_path)
    principals = (f.user["principal_id"], f.owner["principal_id"]) if include_owner else (f.user["principal_id"],)
    f.feedback.memory = memory = Memory(":memory:", auto_vectors=False, review_authorities=tuple({
        "principal_id": principal, "subject_id": "alice", "agent_id": "writer",
        "workspace_id": "project", "scopes": ("procedure:review",)} for principal in principals))
    scope = replace(f.scope.authority_scope(), agent_id=source_agent_id)
    captured = memory.capture_source(SourceCaptureRequest("source-1", "capture", scope,
        "The project destination is staging.", session_id="session", turn_id="turn"))
    admitted = memory.submit_proposal(_proposal(captured.source_sha256, scope=scope,
        fact="The project destination is staging.", fact_key="project::destination", sensitivity=sensitivity))
    record = memory.store.get_record("alice", (admitted.record_ids or admitted.candidate_ids)[0])
    if record["status"] == "quarantined":
        memory.promote("alice", record["id"], actor="synthetic-owner-confirmation")
        record = memory.store.get_record("alice", record["id"])
    rule = RuleCandidate("rule", f.scope, "fixture.write", "v1",
        (SourceRevision(record["id"], record["generation"], sha256(record["content"].encode()).hexdigest()),),
        (RulePredicate("equals", ("target",), "staging"),), "Require the reviewed project destination.")
    review = ReviewService(memory)
    return f, memory, review, rule


def test_existing_review_authority_binds_exact_proposal_and_never_activates(tmp_path):
    f, memory, review, rule = review_fixture(tmp_path)
    try:
        proposed = review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal")
        assert proposed["state"] == "proposed"
        assert proposed["format"] == "atmem-feedback-proposal-receipt-v1" and "sources" not in proposed
        assert "The project destination is staging." not in str(proposed)
        with f.feedback.store.transaction(f.scope) as tx:
            assert "The project destination is staging." in str(tx.get("rule_proposal", "rule")["sources"])
        assert review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal") == proposed
        # A prior development producer cached full proposal/source dictionaries.
        # Upgraded retries must sanitize that legacy response as well.
        with f.feedback.store.transaction(f.scope) as tx:
            key = sha256(b"propose_rule\0proposal").hexdigest()
            cached = tx.get("idempotency", key)
            legacy = tx.get("rule_proposal", "rule")
            legacy["review"] = {"reason":"PRIVATE HUMAN REVIEW NOTE"}
            tx.put("idempotency", key, {**cached, "result":legacy}, expected_revision=tx.revision("idempotency", key))
        assert review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal") == proposed
        authorization = memory.issue_review_authorization(f.user["principal_id"], scopes=("procedure:review",))
        with pytest.raises(FeedbackError, match="denied"):
            review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256=rule.content_digest,
                decision="approve", reason="reviewed exact source", authorization=replace(authorization, token="forged"))
        result = review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256=rule.content_digest,
            decision="approve", reason="reviewed exact source", authorization=authorization)
        assert result["state"] == "reviewed" and result["activation"] == "not_active"
        with pytest.raises(FeedbackError, match="stale_revision"):
            review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256=rule.content_digest,
                decision="approve", reason="repeat", authorization=authorization)
    finally:
        memory.close()


def test_changed_scope_source_revision_and_candidate_invalidate_review(tmp_path):
    f, memory, review, rule = review_fixture(tmp_path)
    try:
        with pytest.raises(FeedbackError, match="denied"):
            review.propose_feedback_rule(f.feedback, f.session, replace(rule, scope=replace(f.scope, workspace_id="other")), idempotency_key="foreign")
        with pytest.raises(FeedbackError, match="stale_source"):
            review.propose_feedback_rule(f.feedback, f.session, replace(rule, sources=(replace(rule.sources[0], content_sha256="a"*64),)), idempotency_key="stale")
        review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal")
        with pytest.raises(FeedbackError, match="stale_revision"):
            review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256="b"*64,
                decision="approve", reason="wrong revision", authorization=None)
        memory.forget_record("alice", rule.sources[0].source_id)
        auth = memory.issue_review_authorization(f.user["principal_id"], scopes=("procedure:review",))
        with pytest.raises(FeedbackError, match="stale_source"):
            review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256=rule.content_digest,
                decision="approve", reason="deleted source", authorization=auth)
    finally:
        memory.close()


def test_real_other_tenant_credential_cannot_reuse_local_canonical_subject_records(tmp_path):
    from atmem.evidence.models import EvidenceRole
    from atmem.feedback.service import FeedbackService
    f, memory, review, rule = review_fixture(tmp_path)
    try:
        other_scope = replace(f.scope, tenant_id="other-tenant")
        # Trusted bootstrap provisions a separate tenant authority in the vault.
        # The attack uses a real valid credential/grant, not a forged scope dict.
        other = f.evidence.accounts.grant("other-controller", EvidenceRole.EVIDENCE_COLLECTOR, other_scope.evidence_scope())
        documents_only = FeedbackService(f.evidence, clock=f.feedback.clock)
        documents_only.grant_agent(other["token"], other_scope, principal_id=other["principal_id"],
            operations=("read", "propose"), expires_at=1_700_010_000)
        session = documents_only.bind(other["token"], agent_id="writer", workspace_id="project")
        assert documents_only.capabilities(session)["scope"] == other_scope.to_dict()
        with pytest.raises(FeedbackError, match="denied"):
            f.feedback.bind(other["token"], agent_id="writer", workspace_id="project")
        with pytest.raises(FeedbackError, match="denied"):
            review.propose_feedback_rule(f.feedback, session, replace(rule, scope=other_scope), idempotency_key="cross-tenant")
        assert "project destination is staging" in memory.store.get_record("alice", rule.sources[0].source_id)["content"]
    finally:
        memory.close()


@pytest.mark.parametrize("private_case", ["other_agent", "restricted_egress"])
def test_source_authority_and_sensitivity_are_checked_before_loading_content(tmp_path, monkeypatch, private_case):
    from atmem.feedback.service import FeedbackService
    f, memory, review, rule = review_fixture(tmp_path,
        sensitivity="restricted" if private_case == "restricted_egress" else "personal",
        source_agent_id="other-agent" if private_case == "other_agent" else "writer")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(memory.store, "get_record", lambda *a,**k:pytest.fail("withheld canonical content was loaded"))
            with pytest.raises(FeedbackError, match="stale_source"):
                review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="withheld")
        if private_case == "restricted_egress":
            # A trusted local-only application may explicitly retain the source
            # for human review. Even there, proposer output stays a receipt.
            local = FeedbackService(f.evidence, clock=f.feedback.clock, memory=memory, egress_class="local")
            result = review.propose_feedback_rule(local, f.session, rule, idempotency_key="local-review")
            assert result["state"] == "proposed" and "sources" not in result
    finally:
        memory.close()
