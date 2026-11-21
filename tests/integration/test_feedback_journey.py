"""Actual local effects with test-seeded authority; no efficacy claim or model.

Acceptance of a synthetic qualification is tested separately to be impossible.
This journey tests dispatch/recovery consumers under a trusted-store fixture.
"""
import pytest

from atmem.contracts.feedback import MCPInvocation
from atmem.feedback.recovery import FeedbackRecovery
from atmem.feedback.store import FeedbackError
from atmem.mcp.guarded import GuardedDispatcher
from feedback_lifecycle_fixtures import reviewed_shadow, seed_trusted_test_receipt, VERSIONS


def test_scoped_rule_effects_shadow_active_revoke_and_restore_quarantine(tmp_path):
    f, memory, rule, lifecycle = reviewed_shadow(tmp_path)
    path = tmp_path/"actual-local-effect.txt"
    try:
        f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
            operations=("read", "execute"), expires_at=1_700_010_000)
        dispatcher = GuardedDispatcher(f.feedback, versions=VERSIONS)
        schema = {"type": "object", "properties": {"target": {"type": "string"}},
                  "required": ["target"], "additionalProperties": False}
        dispatcher.register(f.owner["token"], f.scope, tool="fixture.write", schema_version="v1", schema=schema,
            invoke=lambda args:path.write_text(args["target"]), native_guard=lambda args:args["target"]!="native-denied")
        shadow = dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"target":"production"}, "shadow"))
        assert shadow["status"] == "reported_complete" and path.read_text() == "production"
        assert shadow["shadow"][0]["would_allow"] is False
        key = seed_trusted_test_receipt(f, rule)
        lifecycle.transition(f.owner["token"], f.scope, artifact_id="rule", state="active", expected_generation=1,
                             qualification_id=key, versions=VERSIONS)
        blocked = dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"target":"production"}, "active-denial"))
        assert blocked["status"] == "blocked" and path.read_text() == "production"
        allowed = dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"target":"staging"}, "active-allow"))
        assert allowed["status"] == "reported_complete" and path.read_text() == "staging"
        assert dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"target":"native-denied"}, "native-denial"))["status"] == "blocked"
        recovery = FeedbackRecovery(f.feedback)
        restored = recovery.reconcile_after_restore(f.owner["token"], f.scope, restore_id="restore-1")
        assert restored["status"] == "requalification_required"
        assert recovery.reconcile_after_restore(f.owner["token"], f.scope, restore_id="restore-1") == restored
        with pytest.raises(FeedbackError, match="denied"):
            dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"target":"staging"}, "restored"))
        f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
            operations=("read", "execute"), expires_at=1_700_010_000)
        with pytest.raises(FeedbackError, match="restore_requalification_required"):
            dispatcher.execute(f.session, MCPInvocation("fixture.write", "v1", {"target":"staging"}, "restored"))
        with pytest.raises(FeedbackError, match="fresh_qualification_required"):
            lifecycle.rollback(f.owner["token"], f.scope, artifact_id="rule", target_generation=2,
                               expected_generation=3, versions=VERSIONS)
        assert path.read_text() == "staging"
    finally:
        memory.close()
