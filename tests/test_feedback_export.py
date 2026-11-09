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
