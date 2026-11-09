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


def review_fixture(tmp_path, *, include_owner=False):
    f, _ = actions_fixture(tmp_path)
    principals = (f.user["principal_id"], f.owner["principal_id"]) if include_owner else (f.user["principal_id"],)
    f.feedback.memory = memory = Memory(":memory:", auto_vectors=False, review_authorities=tuple({
        "principal_id": principal, "subject_id": "alice", "agent_id": "writer",
        "workspace_id": "project", "scopes": ("procedure:review",)} for principal in principals))
    scope = f.scope.authority_scope()
    captured = memory.capture_source(SourceCaptureRequest("source-1", "capture", scope,
        "The project destination is staging.", session_id="session", turn_id="turn"))
    admitted = memory.submit_proposal(_proposal(captured.source_sha256, scope=scope,
        fact="The project destination is staging.", fact_key="project::destination"))
    record = memory.store.get_record("alice", admitted.record_ids[0])
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
