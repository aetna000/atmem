import pytest

from atmem.feedback.store import FeedbackError
from atmem.rules.lifecycle import RuleLifecycle
from test_feedback_review import review_fixture


def test_shadow_requires_review_and_activation_requires_real_acceptance(tmp_path):
    f, memory, review, rule = review_fixture(tmp_path)
    try:
        lifecycle = RuleLifecycle(f.feedback)
        review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal")
        with pytest.raises(FeedbackError, match="review_required"):
            lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="shadow", expected_generation=0)
        auth = memory.issue_review_authorization(f.user["principal_id"], scopes=("procedure:review",))
        review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256=rule.content_digest,
            decision="approve", reason="explicit rule review", authorization=auth)
        shadow = lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="shadow", expected_generation=0)
        assert shadow["generation"] == 1
        with pytest.raises(FeedbackError, match="qualification_inconclusive"):
            lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="active", expected_generation=1)
        with pytest.raises(FeedbackError, match="stale_revision"):
            lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="suspended", expected_generation=0)
        lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="revoked", expected_generation=1)
        with pytest.raises(FeedbackError, match="new_review_required"):
            lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="shadow", expected_generation=2)
    finally:
        memory.close()


def test_rollback_is_a_new_generation_and_rechecks_sources_versions_and_expiry(tmp_path):
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    f, memory, rule, lifecycle = reviewed_shadow(tmp_path)
    try:
        key = seed_trusted_test_receipt(f, rule)
        lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="active", expected_generation=1,
                             qualification_id=key, versions=VERSIONS)
        lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="suspended", expected_generation=2)
        args = dict(artifact_id="rule", target_generation=2, expected_generation=3, versions=VERSIONS)
        with pytest.raises(FeedbackError, match="denied"):
            lifecycle.rollback(f.user["token"], f.scope, **args)
        with pytest.raises(FeedbackError, match="version_changed"):
            lifecycle.rollback(f.owner["token"], f.scope, **{**args, "versions": {"reader": "changed"}})
        result = lifecycle.rollback(f.owner["token"], f.scope, **args)
        assert result["generation"] == 4 and result["rollback_of_generation"] == 2
        lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="suspended", expected_generation=4)
        args["expected_generation"] = 5
        f.feedback.clock = lambda:1_699_999_999
        with pytest.raises(FeedbackError, match="qualification_not_yet_valid"):
            lifecycle.rollback(f.owner["token"], f.scope, **args)
        f.feedback.clock = lambda:1_700_000_100
        with pytest.raises(FeedbackError, match="qualification_expired"):
            lifecycle.rollback(f.owner["token"], f.scope, **args)
        f.feedback.clock = lambda:1_700_000_000
        memory.forget_record("alice", rule.sources[0].source_id)
        with pytest.raises(FeedbackError, match="stale_source"):
            lifecycle.rollback(f.owner["token"], f.scope, **args)
        with f.feedback.store.transaction(f.scope) as tx:
            assert tx.get("rule_lifecycle", "rule")["state"] == "suspended"
            assert len(tx.list("activation")) == 5
    finally:
        memory.close()


def test_activation_storage_failure_rolls_back_state_and_receipt_before_retry(tmp_path, monkeypatch):
    from atmem.feedback.store import FeedbackTransaction
    from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS
    f, memory, rule, lifecycle = reviewed_shadow(tmp_path)
    try:
        key = seed_trusted_test_receipt(f, rule)
        original = FeedbackTransaction.put
        def interrupted(self, kind, *args, **kwargs):
            if kind == "activation":
                raise OSError("synthetic interruption after lifecycle write")
            return original(self, kind, *args, **kwargs)
        args = dict(artifact_id="rule", state="active", expected_generation=1, qualification_id=key, versions=VERSIONS)
        with monkeypatch.context() as patch:
            patch.setattr(FeedbackTransaction, "put", interrupted)
            with pytest.raises(OSError):
                lifecycle.transition(f.owner["token"], f.scope, **args)
        with f.feedback.store.transaction(f.scope) as tx:
            assert tx.get("rule_lifecycle", "rule")["state"] == "shadow"
            assert tx.get("rule_lifecycle", "rule")["generation"] == 1
            assert len(tx.list("activation")) == 1
        assert lifecycle.transition(f.owner["token"], f.scope, **args)["generation"] == 2
        with pytest.raises(FeedbackError, match="stale_revision"):
            lifecycle.transition(f.owner["token"], f.scope, **args)
        with f.feedback.store.transaction(f.scope) as tx:
            assert len(tx.list("activation")) == 2
    finally:
        memory.close()
