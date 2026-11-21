"""Trusted-store boundary fixtures, NOT production qualification evidence.

The production evaluator deliberately cannot accept synthetic evidence. These
tests seed a receipt directly to test how consumers handle trusted authority.
No runtime option, CLI or MCP tool exposes this fixture operation.
"""
from atmem.contracts.feedback import QualificationReceipt
from atmem.rules.lifecycle import RuleLifecycle
from test_feedback_review import review_fixture


VERSIONS = {"reader": "test-reader", "verifier": "test-verifier", "tool_schema": "v1", "adapter": "test-adapter"}


def reviewed_shadow(tmp_path):
    f, memory, review, rule = review_fixture(tmp_path)
    review.propose_feedback_rule(f.feedback, f.session, rule, idempotency_key="proposal")
    authorization = memory.issue_review_authorization(f.user["principal_id"], scopes=("procedure:review",))
    review.decide_feedback_rule(f.feedback, f.session, rule_id="rule", candidate_sha256=rule.content_digest,
        decision="approve", reason="synthetic boundary test only", authorization=authorization)
    lifecycle = RuleLifecycle(f.feedback)
    lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="shadow", expected_generation=0)
    return f, memory, rule, lifecycle


def seed_trusted_test_receipt(f, rule, key="test-only-qualification"):
    now = int(f.feedback.clock())
    receipt = QualificationReceipt(key, f.scope, rule.content_digest, "a"*64, VERSIONS,
        "accept", now, now+60, {"claim": "TEST_FIXTURE_NOT_EFFICACY"}).to_dict()
    with f.feedback.store.transaction(f.scope) as tx:
        tx.put("qualification", key, receipt, expected_revision=0)
    return key
