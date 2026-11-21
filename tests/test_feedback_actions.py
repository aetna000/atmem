"""Action observations stay immutable, exact-call and explicitly unverified."""
from dataclasses import replace

import pytest

from atmem import Memory
from atmem.contracts import ContextRequest, ExposureConfirmation, RecallRequest
from atmem.contracts.feedback import ActionCheck, ActionObservation, ActionRequirement, OutcomeRecord
from atmem.feedback.store import FeedbackError
from rag_fixtures import setup_rag


def actions_fixture(tmp_path):
    f = setup_rag(tmp_path)
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
                           operations=("read", "report", "propose"), expires_at=1_700_010_000)
    required = (ActionRequirement("read", "fixture.read", "v1", "read", ("record",)),
                ActionRequirement("write", "fixture.write", "v1", "write", ("fact", "destination")))
    observations = (
        ActionObservation("read", "call-read", "fixture.read", "v1", {}, {"fact": "ten days"},
                          (ActionCheck("record", "mechanical", "pass", "read complete"),)),
        ActionObservation("write", "call-write", "fixture.write", "v1", {"body": "five days"}, {"accepted": True},
                          (ActionCheck("fact", "mechanical", "fail", "wrong number"),
                           ActionCheck("destination", "mechanical", "pass", "write landed"))),
    )
    outcome = OutcomeRecord("outcome", f.scope, "run", "turn", required, observations)
    return f, outcome


def test_real_context_receipt_retains_exact_bytes_and_does_not_prove_model_use(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    memory = Memory(":memory:", auto_vectors=False)
    f.feedback.memory = memory
    try:
        scope = f.scope.authority_scope()
        candidates = memory.eligible_candidates(RecallRequest("recall", scope, "fictional filing deadline", signals=("lexical",)))
        package = memory.prepare_context_v1(ContextRequest("context", candidates.candidate_set_id, scope, ()))
        confirmation = ExposureConfirmation("confirmation", package.preparation_id, scope, package.context_sha256, "run")
        receipt = memory.confirm_exposure_v1(confirmation)
        retained = f.feedback.retain_context(f.session, confirmation_id="confirmation")
        assert retained["package"]["context"] == package.context
        assert retained["model_use"] == "unknown"
        assert f.feedback.retain_context(f.session, confirmation_id="confirmation") == retained
        reported = f.feedback.report_outcome(f.session, replace(outcome, context_receipt_id=receipt.receipt_id, delivery="delivered"), idempotency_key="delivered")
        assert reported["assurance"] == "host_report" and not reported["verified_success"]
    finally:
        memory.close()


def test_fake_delivery_and_foreign_scope_are_not_accepted(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    with pytest.raises(FeedbackError, match="missing_evidence"):
        f.feedback.report_outcome(f.session, replace(outcome, context_receipt_id="fake", delivery="delivered"), idempotency_key="fake")
    with pytest.raises(FeedbackError, match="denied"):
        f.feedback.report_outcome(f.session, replace(outcome, scope=replace(f.scope, subject_id="bob")), idempotency_key="foreign")


def test_read_success_cannot_mask_failed_write_or_merge_partial_calls(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    reported = f.feedback.report_outcome(f.session, outcome, idempotency_key="first")
    assert reported["outcome"]["observations"][0]["checks"][0]["result"] == "pass"
    assert reported["outcome"]["observations"][1]["checks"][0]["result"] == "fail"
    assert reported["verified_success"] is False
    assert f.feedback.report_outcome(f.session, outcome, idempotency_key="first") == reported
    late = replace(outcome.observations[1], invocation_id="call-write-retry",
                   checks=(ActionCheck("fact", "mechanical", "pass", "corrected"),))
    updated = replace(outcome, revision=2, predecessor_id="outcome", observations=outcome.observations+(late,))
    f.feedback.report_outcome(f.session, updated, idempotency_key="late")
    original = f.feedback.outcome(f.session, "outcome", revision_sha256=outcome.content_digest)
    assert original == reported
    with pytest.raises(FeedbackError, match="conflicting_retry"):
        f.feedback.report_outcome(f.session, updated, idempotency_key="first")
    mutated = replace(updated, revision=3, observations=(outcome.observations[0], late))
    with pytest.raises(FeedbackError, match="immutable_observation"):
        f.feedback.report_outcome(f.session, mutated, idempotency_key="mutate")
    assert f.feedback.outcome(f.session, "outcome")["outcome"]["revision"] == 2
