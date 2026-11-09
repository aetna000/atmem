from dataclasses import replace
import json

import pytest

from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair, decrypt_export
from atmem.feedback.export import ExampleExportService
from atmem.feedback.store import FeedbackError
from test_feedback_verification import verifier_fixture, verify


def test_real_recipient_encryption_preview_binding_and_withdrawal(tmp_path):
    pytest.importorskip("pqcrypto")
    f, original, verifier, reader, destination = verifier_fixture(tmp_path)
    observation = replace(original.observations[1], arguments={"body": "ten days"})
    outcome = replace(original, outcome_id="exportable", required=(original.required[1],), observations=(observation,))
    f.simulated_write(outcome, observation)
    f.feedback.report_outcome(f.session, outcome, idempotency_key="exportable")
    verify(verifier, reader, outcome, key="verified-exportable")
    public, secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    service = ExampleExportService(f.feedback)
    service.consent(f.owner["token"], f.scope, consent_id="consent", purpose="synthetic regression example",
                     recipient_public_key=public, outcome_ids=("exportable", "outcome", "missing"), expires_at=1_700_000_060)
    preview = service.preview(f.owner["token"], f.scope, consent_id="consent")
    assert len(preview["examples"]) == 1 and len(preview["excluded"]) == 2
    with pytest.raises(FeedbackError, match="denied"):
        service.preview(f.user["token"], f.scope, consent_id="consent")
    options = dict(consent_id="consent", preview_sha256=preview["preview_sha256"], confirm_sha256=preview["preview_sha256"],
                   recipient_public_key=public, signing_secret_key=signing_secret, signing_public_key=signing_public)
    with pytest.raises(FeedbackError, match="stale_preview"):
        service.export(f.owner["token"], f.scope, **{**options, "confirm_sha256": "a"*64})
    result = service.export(f.owner["token"], f.scope, **options)
    assert service.export(f.owner["token"], f.scope, **options) == result
    recovered = json.loads(decrypt_export(result["encrypted_bundle"], secret))
    assert recovered == preview
    assert "five days" not in json.dumps(result["encrypted_bundle"])
    other, _ = generate_recipient_keypair()
    with pytest.raises(FeedbackError, match="wrong_recipient"):
        service.export(f.owner["token"], f.scope, **{**options, "recipient_public_key": other})
    assert service.withdraw(f.owner["token"], f.scope, consent_id="consent")["external_copies"] == "not_recalled"
    with pytest.raises(FeedbackError, match="consent_unavailable"):
        service.export(f.owner["token"], f.scope, **options)


def test_test_split_cannot_be_consented_and_revised_consent_stales_preview(tmp_path):
    pytest.importorskip("pqcrypto")
    f, _, verifier, reader, _ = verifier_fixture(tmp_path)
    public, _ = generate_recipient_keypair()
    service = ExampleExportService(f.feedback)
    args = dict(consent_id="consent", purpose="fixture only", recipient_public_key=public,
                outcome_ids=("outcome",), expires_at=1_700_000_060)
    with pytest.raises(ValueError):
        service.consent(f.owner["token"], f.scope, **args, split="test")
    service.consent(f.owner["token"], f.scope, **args)
    before = service.preview(f.owner["token"], f.scope, consent_id="consent")
    service.consent(f.owner["token"], f.scope, **{**args, "purpose": "new purpose"})
    after = service.preview(f.owner["token"], f.scope, consent_id="consent")
    assert before["preview_sha256"] != after["preview_sha256"]


@pytest.mark.parametrize("change,reason", [("revoke", "source_revoked"), ("revision", "source_changed"),
                                         ("missing", "source_revalidation_unavailable")])
def test_export_rechecks_rag_lineage_after_preview_and_on_cached_retry(tmp_path, change, reason):
    pytest.importorskip("pqcrypto")
    from atmem.knowledge.rag.contracts import RagQuery
    f, original, verifier, reader, _ = verifier_fixture(tmp_path)
    # Fixture normally grants report only; grant search for actual retrieval.
    f.feedback.grant_agent(f.owner["token"], f.scope, principal_id=f.user["principal_id"],
        operations=("read", "report", "search"), expires_at=1_700_010_000)
    receipt = f.rag.search(f.session, RagQuery("law", "deadline"), idempotency_key="export-rag")
    observation = replace(original.observations[1], arguments={"body":"ten days"}, evidence_id=receipt["receipt_id"])
    outcome = replace(original, outcome_id="rag-example", required=(original.required[1],), observations=(observation,))
    f.simulated_write(outcome, observation)
    f.feedback.report_outcome(f.session, outcome, idempotency_key="rag-example")
    verify(verifier, reader, outcome, key="verified-rag")
    public, _ = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    service = ExampleExportService(f.feedback)
    args = dict(consent_id="consent", purpose="synthetic document example", recipient_public_key=public,
                outcome_ids=(outcome.outcome_id,), expires_at=1_700_000_060)
    service.consent(f.owner["token"], f.scope, **args)
    before = service.preview(f.owner["token"], f.scope, consent_id="consent")
    service.consent(f.owner["token"], f.scope, **args)
    assert service.preview(f.owner["token"], f.scope, consent_id="consent") == before
    assert len(before["examples"]) == 1
    options = dict(consent_id="consent", preview_sha256=before["preview_sha256"], confirm_sha256=before["preview_sha256"],
                   recipient_public_key=public, signing_secret_key=signing_secret, signing_public_key=signing_public)
    service.export(f.owner["token"], f.scope, **options)
    if change == "revoke":
        f.rag.revoke(f.owner["token"], f.scope, "law")
    elif change == "revision":
        f.rag.register(f.owner["token"], replace(f.source, revision="revision-new", generation=2), f.provider)
    else:
        with f.feedback.owner_transaction(f.owner["token"], f.scope) as (tx, _):
            tx.put("rag_receipt", receipt["receipt_id"], {},
                   expected_revision=tx.revision("rag_receipt", receipt["receipt_id"]), deleted=True)
    after = service.preview(f.owner["token"], f.scope, consent_id="consent")
    assert not after["examples"] and after["excluded"] == [{"outcome_id":outcome.outcome_id, "reason":reason}]
    with pytest.raises(FeedbackError, match="stale_preview"):
        service.export(f.owner["token"], f.scope, **options)
