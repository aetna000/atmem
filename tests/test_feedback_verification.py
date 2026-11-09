"""Actual destination readback and independently authenticated verification."""
from dataclasses import replace
from hashlib import sha256
import json
import threading
import uuid

import pytest

from atmem.contracts.feedback import ActionCheck
from atmem.core.canonical import canonical_json
from atmem.evidence.models import EvidenceRole
from atmem.feedback.store import FeedbackError
from atmem.feedback.verification import Readback, VerificationService, action_results
from test_feedback_actions import actions_fixture


def verifier_fixture(tmp_path):
    f, outcome = actions_fixture(tmp_path)
    f.feedback.report_outcome(f.session, outcome, idempotency_key="reported")
    credential = f.evidence.grant(f.evidence.authenticate(f.owner["token"]), principal_id="destination-reader",
                                  role=EvidenceRole.INVESTIGATOR, scope=f.scope.evidence_scope())
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=credential["principal_id"],
                           operations=("read", "verify"), expires_at=1_700_010_000)
    reader = f.feedback.bind(credential["token"], agent_id="writer", workspace_id="project")
    service = VerificationService(f.feedback)
    destination = tmp_path / "simulated-destination.txt"
    journal = tmp_path / "simulated-backend-journal.json"
    def simulated_write(record, observation, *, effect_status="succeeded"):
        if effect_status == "succeeded":
            destination.write_text(observation.arguments["body"])
        journal.write_text(json.dumps({
            "observed_outcome_id": record.outcome_id,
            "observed_invocation_id": observation.invocation_id,
            "observed_run_id": record.run_id, "observed_turn_id": record.turn_id,
            "arguments_sha256": sha256(canonical_json(observation.arguments).encode()).hexdigest(),
            "effect_reference": uuid.uuid4().hex,
            "effect_status": effect_status,
        }))
    f.simulated_write = simulated_write
    simulated_write(outcome, outcome.observations[1])
    def readback(outcome, observation, *, deadline):
        text = destination.read_text()
        return Readback((ActionCheck("fact", "mechanical", "pass" if text == observation.arguments.get("body") == "ten days" else "fail", "compare exact call and destination"),
                         ActionCheck("destination", "mechanical", "pass" if text == observation.arguments.get("body") else "fail", "destination read directly")),
                        {**json.loads(journal.read_text()), "expected": "ten days", "observed": text, "arguments": observation.arguments,
                         "invocation_id": observation.invocation_id, "path": str(destination)})
    service.register(f.owner["token"], f.scope, principal_id=credential["principal_id"], version="v1",
                     tool="fixture.write", schema_version="v1", check_ids=("fact", "destination"), readback=readback,
                     binding="effect_receipt")
    return f, outcome, service, reader, destination


def verify(service, reader, outcome, key="verification"):
    return service.verify(reader, outcome_id=outcome.outcome_id, outcome_sha256=outcome.content_digest,
                          invocation_id="call-write", idempotency_key=key)


def test_actual_readback_beats_host_success_and_retains_failure_evidence(tmp_path):
    f, outcome, service, reader, destination = verifier_fixture(tmp_path)
    receipt = verify(service, reader, outcome)
    assert receipt["assurance"] == "independent_readback"
    assert receipt["checks"][0]["result"] == "fail"
    assert verify(service, reader, outcome) == receipt
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.get("readback_evidence", receipt["evidence_id"])["evidence"]["observed"] == "five days"
    summary = action_results(outcome, [receipt])
    assert not summary[0]["verified_success"]  # unverified read, despite host pass
    assert summary[1]["status"] == "fail" and not summary[1]["verified_success"]
    destination.write_text("ten days")
    second = verify(service, reader, outcome, key="later-readback")
    assert action_results(outcome, [receipt, second])[1]["status"] == "disputed"
    assert not action_results(outcome, [receipt, second])[1]["verified_success"]


def test_partial_calls_cannot_be_combined_or_forged_tiers_promoted(tmp_path):
    f, outcome, service, reader, _ = verifier_fixture(tmp_path)
    receipt = verify(service, reader, outcome)
    late = replace(outcome.observations[1], invocation_id="retry-write")
    revised = replace(outcome, revision=2, predecessor_id="outcome", observations=outcome.observations+(late,))
    f.feedback.report_outcome(f.session, revised, idempotency_key="revised")
    assert action_results(revised, [receipt])[1]["status"] == "unknown"  # old outcome digest
    # Each individual invocation still fails/unknown even if different calls
    # happen to satisfy different checks.
    from atmem.contracts.feedback import VerificationReceipt
    a = VerificationReceipt.from_dict(receipt)
    a = replace(a, outcome_sha256=revised.content_digest,
                checks=(ActionCheck("fact", "mechanical", "pass", "first call fact"),))
    b = replace(a, receipt_id="second", invocation_id="retry-write",
                checks=(ActionCheck("destination", "mechanical", "pass", "second destination"),))
    assert not action_results(revised, [a.to_dict(), b.to_dict()])[1]["verified_success"]
    assert not action_results(outcome, [replace(VerificationReceipt.from_dict(receipt), assurance="host_report").to_dict()])[1]["verified_success"]


def test_correct_state_without_correlated_effect_is_not_action_success(tmp_path):
    f, original, service, reader, destination = verifier_fixture(tmp_path)
    observation = replace(original.observations[1], arguments={"body": "ten days"})
    outcome = replace(original, outcome_id="unbound", observations=(observation,))
    destination.write_text("ten days")  # State existed; there was no matching tool call.
    f.feedback.report_outcome(f.session, outcome, idempotency_key="unbound")
    with pytest.raises(FeedbackError, match="invalid_effect_binding"):
        verify(service, reader, outcome)
    service.register(f.owner["token"], f.scope, principal_id="destination-reader", version="state",
        tool="fixture.write", schema_version="v1", check_ids=("fact", "destination"),
        readback=lambda *a, **k: Readback((ActionCheck("fact", "mechanical", "pass", "current state"),
            ActionCheck("destination", "mechanical", "pass", "current state")), {"observed": destination.read_text()}))
    receipt = verify(service, reader, outcome, key="state-only")
    result = action_results(outcome, [receipt])[1]
    assert result["status"] == "unknown" and not result["verified_success"]
    assert result["calls"][0]["effect_binding"] == "state_only"


def test_effect_reference_cannot_be_reused_for_a_different_outcome(tmp_path):
    f, outcome, service, reader, destination = verifier_fixture(tmp_path)
    verify(service, reader, outcome)
    other = replace(outcome, outcome_id="different")
    f.feedback.report_outcome(f.session, other, idempotency_key="different")
    journal = tmp_path / "simulated-backend-journal.json"
    data = json.loads(journal.read_text())
    data["observed_outcome_id"] = other.outcome_id
    journal.write_text(json.dumps(data))
    with pytest.raises(FeedbackError, match="effect_already_bound"):
        verify(service, reader, other, key="reused-effect")


@pytest.mark.parametrize("status", ["failed", "not_dispatched", "unknown"])
def test_existing_correct_state_does_not_turn_failed_or_pending_operation_into_success(tmp_path, status):
    f, original, service, reader, destination = verifier_fixture(tmp_path)
    observation = replace(original.observations[1], arguments={"body":"ten days"})
    outcome = replace(original, outcome_id="unsuccessful-operation", required=(original.required[1],), observations=(observation,))
    destination.write_text("ten days")  # Correct state supplied independently before this attempt.
    f.simulated_write(outcome, observation, effect_status=status)  # Journal only; no destination write.
    f.feedback.report_outcome(f.session, outcome, idempotency_key="failed-attempt")
    proof = verify(service, reader, outcome)
    assert all(check["result"] == "pass" for check in proof["checks"])
    result = action_results(outcome, [proof])[0]
    assert not result["verified_success"]
    assert result["status"] == ("unknown" if status == "unknown" else "fail")
    assert result["calls"][0]["effect_status"] == status


def test_verifier_registration_and_auth_are_not_model_capabilities(tmp_path):
    f, outcome, service, reader, _ = verifier_fixture(tmp_path)
    with pytest.raises(FeedbackError, match="denied"):
        service.register(f.user["token"], f.scope, principal_id="forged", version="v1", tool="fixture.write",
                         schema_version="v1", check_ids=("fact",), readback=lambda *a, **k: None)
    with pytest.raises(FeedbackError, match="denied"):
        verify(service, f.session, outcome)
    service.revoke(f.owner["token"], f.scope, principal_id="destination-reader", tool="fixture.write", schema_version="v1")
    with pytest.raises(FeedbackError, match="denied"):
        verify(service, reader, outcome)


def test_revocation_while_readback_is_running_denies_publication(tmp_path):
    f, outcome, service, reader, _ = verifier_fixture(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def waiting(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return Readback((ActionCheck("fact", "mechanical", "pass", "fixture"),
                         ActionCheck("destination", "mechanical", "pass", "fixture")), {"observed": "ten days"})
    service.register(f.owner["token"], f.scope, principal_id="destination-reader", version="v2", tool="fixture.write",
                     schema_version="v1", check_ids=("fact", "destination"), readback=waiting)
    failures = []
    def work():
        try:
            verify(service, reader, outcome)
        except FeedbackError as exc:
            failures.append(exc.code)
    thread = threading.Thread(target=work)
    thread.start()
    assert entered.wait(3)
    service.revoke(f.owner["token"], f.scope, principal_id="destination-reader", tool="fixture.write", schema_version="v1")
    release.set()
    thread.join(5)
    assert not thread.is_alive() and failures == ["verifier_changed"]
    with f.feedback.store.transaction(f.scope) as tx:
        assert tx.list("verification") == []


def test_readback_failure_and_deadline_cannot_be_success(tmp_path):
    f, outcome, service, reader, _ = verifier_fixture(tmp_path)
    release = threading.Event()
    service.timeout_seconds = .02
    service.register(f.owner["token"], f.scope, principal_id="destination-reader", version="hung", tool="fixture.write",
                     schema_version="v1", check_ids=("fact", "destination"), readback=lambda *a, **k: release.wait(3))
    try:
        with pytest.raises(FeedbackError, match="verifier_timeout"):
            verify(service, reader, outcome)
        with pytest.raises(FeedbackError, match="verifier_busy"):
            verify(service, reader, outcome)
    finally:
        release.set()
