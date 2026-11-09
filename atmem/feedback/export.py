"""Default-off, previewed verified-example export to a bound recipient key.

This returns a recipient-encrypted bundle, never writes plaintext training files
or starts training. Withdrawal prevents future exports; it cannot erase copies
already held by recipients or remove information from trained weights.
"""
from __future__ import annotations

from hashlib import sha256
from contextlib import nullcontext
import uuid

from atmem.contracts.feedback import OutcomeRecord, identifier
from atmem.core.canonical import canonical_json
from atmem.extract.validation import screen_content
from atmem.evidence.crypto import encrypted_export
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, snapshot
from atmem.feedback.verification import action_results


class ExampleExportService:
    def __init__(self, feedback):
        self.feedback = feedback

    def _owner(self, credential, scope):
        principal = self.feedback._principal(credential)
        try:
            principal.authorize(EvidenceOperation.PLAINTEXT_EXPORT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        return principal

    def consent(self, owner_credential, scope, *, consent_id, purpose, recipient_public_key: bytes,
                outcome_ids: tuple[str, ...], expires_at, split="development"):
        principal = self._owner(owner_credential, scope)
        identifier(consent_id)
        if (type(purpose) is not str or not 0 < len(purpose.encode()) <= 1024
                or type(recipient_public_key) is not bytes or len(recipient_public_key) != 1184
                or type(outcome_ids) is not tuple or not 0 < len(outcome_ids) <= 64
                or len(set(outcome_ids)) != len(outcome_ids) or split not in ("train", "development")
                or type(expires_at) is not int or not self.feedback.clock() < expires_at <= self.feedback.clock()+604800):
            raise ValueError("explicit bounded purpose, recipient, records and expiry required; no test split")
        for key in outcome_ids:
            identifier(key)
        with self.feedback.owner_transaction(owner_credential, scope, operation=EvidenceOperation.PLAINTEXT_EXPORT) as (tx, principal):
            value = {"consent_id": consent_id, "purpose": purpose, "recipient_sha256": sha256(recipient_public_key).hexdigest(),
                     "outcome_ids": list(outcome_ids), "expires_at": expires_at, "split": split,
                     "active": True, "actor_id": principal.principal_id}
            if tx.get("export_consent", consent_id) == value:
                return value
            tx.put("export_consent", consent_id, value, expected_revision=tx.revision("export_consent", consent_id))
            tx.audit(principal.principal_id, "export_consent", allowed=True)
            return value

    def withdraw(self, owner_credential, scope, *, consent_id):
        principal = self._owner(owner_credential, scope)
        with self.feedback.owner_transaction(owner_credential, scope, operation=EvidenceOperation.PLAINTEXT_EXPORT) as (tx, principal):
            value = tx.get("export_consent", identifier(consent_id))
            if value is None:
                raise FeedbackError("denied")
            value["active"] = False
            tx.put("export_consent", consent_id, value, expected_revision=tx.revision("export_consent", consent_id))
            tx.audit(principal.principal_id, "withdraw_export", allowed=True)
            return {"status": "withdrawn", "external_copies": "not_recalled"}

    def _rag_lineage_failure(self, tx, outcome):
        """Revalidate registered document lineage without calling a provider.

        Receipt identifiers are scoped lookups. A lost RAG receipt cannot be
        silently reclassified as a tool-only example. Whole source snapshots
        bind generation, revision, collection, scope and egress configuration.
        """
        from atmem.feedback.recovery import revocation_key
        for observation in outcome.observations:
            key = observation.evidence_id
            if key is None:
                continue
            receipt = tx.get("rag_receipt", key)
            if receipt is None:
                if key.startswith("rag-"):
                    return "source_revalidation_unavailable"
                continue
            source = receipt.get("source", {})
            source_id = source.get("source_id")
            if receipt.get("scope") != tx.scope.to_dict() or not source_id:
                return "source_revalidation_unavailable"
            current = tx.get("rag_source", source_id)
            if (current is None or not current.get("active")
                    or tx.get("source_revocation", revocation_key(source_id, "rag")) is not None):
                return "source_revoked"
            if current != source:
                return "source_changed"
        return None

    def _preview(self, tx, consent_id):
        consent = tx.get("export_consent", identifier(consent_id))
        if consent is None or not consent["active"] or consent["expires_at"] <= self.feedback.clock():
            raise FeedbackError("consent_unavailable")
        receipts = list(tx.iter_kind("verification"))
        test_ids = {t["id"] for m in tx.iter_kind("evaluation_manifest") for t in m["manifest"]["tasks"] if t["split"] == "test"}
        examples, excluded = [], []
        for outcome_id in consent["outcome_ids"]:
            row = tx.get("outcome", outcome_id)
            reason = None
            if row is None:
                reason = "missing_or_deleted"
            else:
                outcome = OutcomeRecord.from_dict(row["outcome"])
                if outcome.scope != tx.scope:
                    reason = "foreign_scope"
                elif outcome.turn_id in test_ids or outcome.run_id.startswith("eval:") or outcome.outcome_id.startswith("eval:"):
                    reason = "evaluation_excluded"
                elif not all(a["verified_success"] for a in action_results(outcome, receipts)):
                    reason = "not_independently_verified"
                elif "secret_material_detected" in screen_content(canonical_json(row), trusted=True).reason_codes:
                    reason = "secret_material"
                elif outcome.context_receipt_id is not None:
                    context = tx.get("context_evidence", outcome.context_receipt_id)
                    from atmem.feedback.recovery import revocation_key
                    if (context is None or self.feedback.memory is None
                            or context["package"]["generation"] != self.feedback.memory.store.record_generation(outcome.scope.subject_id)):
                        reason = "source_revalidation_unavailable"
                    elif any(tx.get("source_revocation", revocation_key(key)) is not None for key in context["package"].get("record_ids", [])):
                        reason = "source_revoked"
                if reason is None:
                    reason = self._rag_lineage_failure(tx, outcome)
            if reason:
                excluded.append({"outcome_id": outcome_id, "reason": reason})
                continue
            selected = [r for r in receipts if r["outcome_sha256"] == outcome.content_digest and r["assurance"] == "independent_readback"
                        and r.get("binding", "state_only") == "effect_receipt"]
            examples.append({"outcome": outcome.to_dict(), "verifications": selected,
                             "lineage": {"consent_id": consent_id, "split": consent["split"], "purpose": consent["purpose"]}})
        value = {"format": "atmem-verified-example-preview-v1", "scope": tx.scope.to_dict(),
                 "consent": consent, "consent_revision": tx.revision("export_consent", consent_id),
                 "examples": examples, "excluded": excluded, "anonymization": "not_claimed",
                 "manual_sensitive_data_review": "required", "training": "not_performed"}
        value = snapshot(value)
        return {**value, "preview_sha256": sha256(canonical_json(value).encode()).hexdigest()}

    def preview(self, owner_credential, scope, *, consent_id):
        principal = self._owner(owner_credential, scope)
        canonical = self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical, self.feedback.owner_transaction(owner_credential, scope, operation=EvidenceOperation.PLAINTEXT_EXPORT) as (tx, principal):
            value = self._preview(tx, consent_id)
            tx.audit(principal.principal_id, "preview_export", allowed=True)
            return value

    def export(self, owner_credential, scope, *, consent_id, preview_sha256, confirm_sha256,
               recipient_public_key, signing_secret_key, signing_public_key):
        principal = self._owner(owner_credential, scope)
        canonical = self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical, self.feedback.owner_transaction(owner_credential, scope, operation=EvidenceOperation.PLAINTEXT_EXPORT) as (tx, principal):
            value = self._preview(tx, consent_id)
            if value["preview_sha256"] != preview_sha256 or confirm_sha256 != preview_sha256:
                raise FeedbackError("stale_preview")
            if sha256(recipient_public_key).hexdigest() != value["consent"]["recipient_sha256"]:
                raise FeedbackError("wrong_recipient")
            if not value["examples"]:
                raise FeedbackError("no_eligible_examples")
            payload = {"preview_sha256": preview_sha256, "recipient_sha256": sha256(recipient_public_key).hexdigest(),
                       "signing_public_sha256": sha256(signing_public_key).hexdigest()}
            cached = tx.cached("export_examples", preview_sha256, payload)
            if cached is not None:
                return cached
            bundle = encrypted_export(canonical_json(value).encode(), recipient_public_key=recipient_public_key,
                                      signing_secret_key=signing_secret_key, signing_public_key=signing_public_key)
            from pqcrypto.sign.ml_dsa_65 import verify
            import base64
            try:
                verify(signing_public_key, canonical_json({k:v for k,v in bundle.items() if k != "signature"}).encode(),
                       base64.b64decode(bundle["signature"], validate=True))
            except (ValueError, TypeError):
                raise FeedbackError("invalid_signing_key") from None
            receipt_id = "export-"+uuid.uuid4().hex
            receipt = {"export_id": receipt_id, "preview_sha256": preview_sha256, "consent_id": consent_id,
                       "consent_revision": value["consent_revision"], "actor_id": principal.principal_id,
                       "recipient_sha256": value["consent"]["recipient_sha256"],
                       "examples": len(value["examples"]), "external_deletion": "not_guaranteed"}
            tx.put("example_export", receipt_id, {"receipt": receipt, "encrypted_bundle": bundle}, expected_revision=0)
            tx.audit(principal.principal_id, "export_examples", allowed=True)
            return tx.once("export_examples", preview_sha256, payload,
                           lambda: {"receipt": receipt, "encrypted_bundle": bundle})
