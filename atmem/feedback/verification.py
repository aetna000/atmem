"""Registered authenticated readback, not agent self-grading.

An owner chooses a trusted implementation and its supported tool/check version.
Model tools cannot register verifiers or supply trusted check outcomes. Readbacks
must be read-only; this boundary does not replay the original action.
"""
from __future__ import annotations

from contextvars import copy_context
from dataclasses import dataclass
import queue
import threading
import time
import uuid

from atmem.contracts.feedback import ActionCheck, OutcomeRecord, VerificationReceipt, identifier
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, snapshot
from atmem.feedback.observability import measured

FAILURE_CLASSES = frozenset({"source_fact_absent", "retrieval_miss", "authority_withheld", "stale_conflicting_state",
                             "delivered_but_not_applied", "wrong_argument_value", "wording_precision", "no_call",
                             "execution_failure", "unknown"})


@dataclass(frozen=True)
class Readback:
    checks: tuple[ActionCheck, ...]
    evidence: dict
    assessments: tuple[dict, ...] = ()


class VerificationService:
    def __init__(self, feedback, *, timeout_seconds=5):
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 30:
            raise ValueError("bounded readback timeout required")
        self.feedback, self.timeout_seconds = feedback, timeout_seconds
        self._handlers = {}
        self._running = set()
        self._lock = threading.Lock()

    def register(self, owner_credential, scope, *, principal_id, version, tool, schema_version,
                 check_ids, readback, assurance="independent_readback", assessment_metrics=(), binding="state_only", effect_namespace=None):
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        for item in (principal_id, version, tool, schema_version):
            identifier(item)
        if (assurance not in ("independent_readback", "human_attestation", "host_report", "model_judgement")
                or type(check_ids) is not tuple or not 0 < len(check_ids) <= 32
                or len(set(check_ids)) != len(check_ids) or not callable(readback)):
            raise ValueError("explicit verifier contract required")
        for item in check_ids:
            identifier(item)
        if binding not in ("state_only", "effect_receipt"):
            raise ValueError("explicit supported readback binding required")
        effect_namespace = identifier(effect_namespace or tool)
        if (type(assessment_metrics) is not tuple or len(set(assessment_metrics)) != len(assessment_metrics)
                or any(item not in {"wrong_answer_rate", "evidence_precision", "false_denial_rate", "required_fact_write_failure"}
                       for item in assessment_metrics)):
            raise ValueError("explicit assessment metrics required")
        value = {"principal_id": principal_id, "version": version, "tool": tool,
                 "schema_version": schema_version, "checks": list(check_ids), "assurance": assurance,
                 "assessment_metrics": list(assessment_metrics), "active": True}
        value.update(binding=binding, effect_namespace=effect_namespace)
        key = self._key(principal_id, tool, schema_version)
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            # Reattaching code is an authority generation change even if its
            # declared version is unchanged. In-flight readbacks must notice it.
            tx.put("verifier", key, value, expected_revision=tx.revision("verifier", key))
            tx.audit(principal.principal_id, "register_verifier", allowed=True)
        with self._lock:
            self._handlers[(scope.content_digest, key, version)] = readback

    @staticmethod
    def _key(principal_id, tool, schema):
        from hashlib import sha256
        return sha256((principal_id + "\0" + tool + "\0" + schema).encode()).hexdigest()

    def revoke(self, owner_credential, scope, *, principal_id, tool, schema_version):
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        key = self._key(principal_id, tool, schema_version)
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            registered = tx.get("verifier", key)
            if registered is None:
                raise FeedbackError("denied")
            registered["active"] = False
            tx.put("verifier", key, registered, expected_revision=tx.revision("verifier", key))
            tx.audit(principal.principal_id, "revoke_verifier", allowed=True)

    def _read(self, key, invoke):
        with self._lock:
            callback = self._handlers.get(key)
            if callback is None:
                raise FeedbackError("verifier_unavailable")
            if key in self._running or len(self._running) >= 8:
                raise FeedbackError("verifier_busy")
            self._running.add(key)
        results = queue.Queue(maxsize=1)
        context = copy_context()
        deadline = time.monotonic() + self.timeout_seconds
        def run():
            try:
                results.put((True, context.run(invoke, callback, deadline)))
            except BaseException:
                results.put((False, None))
            finally:
                with self._lock:
                    self._running.discard(key)
        try:
            threading.Thread(target=run, daemon=True, name="atmem-feedback-readback").start()
        except RuntimeError:
            with self._lock:
                self._running.discard(key)
            raise FeedbackError("verifier_unavailable") from None
        try:
            ok, result = results.get(timeout=max(0, deadline-time.monotonic()))
        except queue.Empty:
            raise FeedbackError("verifier_timeout") from None
        if not ok:
            raise FeedbackError("verifier_unavailable")
        return result

    @measured("verification.readback")
    def verify(self, session, *, outcome_id, outcome_sha256, invocation_id, idempotency_key):
        for item in (outcome_id, outcome_sha256, invocation_id, idempotency_key):
            identifier(item)
        payload = {"outcome_id": outcome_id, "outcome_sha256": outcome_sha256, "invocation_id": invocation_id}
        with self.feedback._authorized(session, "verify") as (tx, principal):
            row = tx.get("outcome_revision", outcome_sha256)
            if row is None or row["outcome"]["outcome_id"] != outcome_id:
                raise FeedbackError("denied")
            outcome = OutcomeRecord.from_dict(row["outcome"])
            observation = next((v for v in outcome.observations if v.invocation_id == invocation_id), None)
            if observation is None:
                raise FeedbackError("missing_evidence")
            requirement = next(v for v in outcome.required if v.action_id == observation.action_id)
            key = self._key(principal.principal_id, observation.tool, observation.schema_version)
            registered = tx.get("verifier", key)
            if (registered is None or not registered["active"] or observation.tool != requirement.tool
                    or observation.schema_version != requirement.schema_version
                    or not set(requirement.checks) <= set(registered["checks"])):
                raise FeedbackError("denied")
            if registered["assurance"] == "independent_readback" and principal.principal_id == row["actor_id"]:
                raise FeedbackError("not_independent")
            payload.update(verifier=registered, actor_id=principal.principal_id,
                           registry_revision=tx.revision("verifier", key))
            cached = tx.cached("verify", idempotency_key, payload)
            if cached is not None:
                return cached
            version = tx.revision("verifier", key)
            attempt_id = "readback-attempt-" + uuid.uuid4().hex
            tx.put("verification_attempt", attempt_id, {**payload, "status": "pending"}, expected_revision=0)
        handler_key = (session.scope.content_digest, key, registered["version"])
        try:
            readback = self._read(handler_key, lambda callback, deadline: callback(
                OutcomeRecord.from_dict(outcome.to_dict()),
                type(observation).from_dict(observation.to_dict()), deadline=deadline))
        except FeedbackError as exc:
            try:
                with self.feedback._authorized(session, "verify") as (tx, _):
                    tx.put("verification_attempt", attempt_id, {**payload, "status": "failed", "error": exc.code}, expected_revision=1)
            except FeedbackError:
                pass  # Keep pending/unknown if access has been revoked.
            raise
        if type(readback) is not Readback or type(readback.checks) is not tuple or not readback.checks:
            raise FeedbackError("invalid_readback")
        checks = tuple(ActionCheck.from_dict(v.to_dict()) for v in readback.checks)
        ids = [v.check_id for v in checks]
        if len(set(ids)) != len(ids) or set(ids) != set(requirement.checks):
            raise FeedbackError("invalid_readback")
        evidence = snapshot(readback.evidence)
        if not evidence or type(evidence) is not dict:
            raise FeedbackError("missing_evidence")
        effect_key = None
        effect_status = "unknown"
        if registered["binding"] == "effect_receipt":
            from hashlib import sha256
            from atmem.core.canonical import canonical_json
            expected = {"observed_outcome_id": outcome.outcome_id, "observed_invocation_id": invocation_id,
                        "observed_run_id": outcome.run_id, "observed_turn_id": outcome.turn_id,
                        "arguments_sha256": sha256(canonical_json(observation.arguments).encode()).hexdigest()}
            reference = evidence.get("effect_reference")
            effect_status = evidence.get("effect_status")
            if (any(evidence.get(k) != value for k, value in expected.items())
                    or type(reference) is not str or not 0 < len(reference.encode()) <= 2048
                    or effect_status not in ("succeeded", "failed", "not_dispatched", "unknown")):
                raise FeedbackError("invalid_effect_binding")
            effect_key = sha256(canonical_json([registered["effect_namespace"], reference]).encode()).hexdigest()
        if type(readback.assessments) is not tuple or len(readback.assessments) > 128:
            raise FeedbackError("invalid_readback")
        assessments = snapshot(list(readback.assessments))
        for item in assessments:
            if (type(item) is not dict or set(item) != {"metric", "unit_id", "positive"}
                    or item["metric"] not in registered["assessment_metrics"]
                    or item["positive"] is not None and type(item["positive"]) is not bool):
                raise FeedbackError("invalid_readback")
            identifier(item["unit_id"])
        with self.feedback._authorized(session, "verify") as (tx, principal):
            if tx.revision("verifier", key) != version or tx.get("verifier", key) != registered:
                raise FeedbackError("verifier_changed")
            if tx.get("outcome_revision", outcome_sha256) != row:
                raise FeedbackError("missing_evidence")
            if effect_key is not None:
                bound = tx.get("verified_effect", effect_key)
                if bound is not None and (bound["outcome_id"] != outcome_id or bound["invocation_id"] != invocation_id):
                    raise FeedbackError("effect_already_bound")
            def publish():
                evidence_id = "readback-" + uuid.uuid4().hex
                receipt = VerificationReceipt("verification-" + uuid.uuid4().hex, session.scope, outcome_id,
                    outcome_sha256, invocation_id, principal.principal_id, registered["version"], evidence_id,
                    checks, registered["assurance"], registered["binding"], effect_status).to_dict()
                tx.put("readback_evidence", evidence_id, {"evidence": evidence, "actor_id": principal.principal_id,
                       "outcome_sha256": outcome_sha256, "invocation_id": invocation_id,
                       "assessments": assessments}, expected_revision=0)
                tx.put("verification", receipt["receipt_id"], receipt, expected_revision=0)
                if effect_key is not None and tx.get("verified_effect", effect_key) is None:
                    tx.put("verified_effect", effect_key, {"outcome_id": outcome_id, "invocation_id": invocation_id}, expected_revision=0)
                tx.put("verification_attempt", attempt_id, {**payload, "status": "complete", "receipt_id": receipt["receipt_id"]}, expected_revision=1)
                return receipt
            return tx.once("verify", idempotency_key, payload, publish)

    def resolve_dispute(self, owner_credential, scope, *, outcome_sha256, invocation_id,
                        receipt_ids: tuple[str, ...], chosen_receipt_id: str, reason: str):
        """Append a review decision; retain every disagreeing original receipt."""
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        if (type(receipt_ids) is not tuple or not 2 <= len(receipt_ids) <= 32
                or len(set(receipt_ids)) != len(receipt_ids) or chosen_receipt_id not in receipt_ids
                or type(reason) is not str or not 1 <= len(reason.encode()) <= 4096):
            raise ValueError("explicit receipt-bound resolution and reason required")
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            receipts = [tx.get("verification", identifier(key)) for key in receipt_ids]
            actual = [r["receipt_id"] for r in tx.iter_kind("verification")
                      if r["outcome_sha256"] == outcome_sha256 and r["invocation_id"] == invocation_id]
            if (set(actual) != set(receipt_ids) or any(r is None or r["outcome_sha256"] != outcome_sha256
                    or r["invocation_id"] != invocation_id for r in receipts)):
                raise FeedbackError("stale_revision")
            value = {"outcome_sha256": outcome_sha256, "invocation_id": invocation_id,
                     "receipt_ids": list(receipt_ids), "chosen_receipt_id": chosen_receipt_id,
                     "actor_id": principal.principal_id, "reason": reason,
                     "assurance": "human_attestation"}
            key = self._key(outcome_sha256, invocation_id, "resolution")
            tx.put("dispute_resolution", key, value, expected_revision=tx.revision("dispute_resolution", key))
            tx.audit(principal.principal_id, "resolve_dispute", allowed=True)
            return value

    def propose_attribution(self, session, *, outcome_sha256, invocation_id, failure_class, reason, evidence_ids):
        """Store a diagnosis proposal; a model cannot certify causal failure."""
        if failure_class not in FAILURE_CLASSES or type(reason) is not str or not 0 < len(reason.encode()) <= 4096:
            raise ValueError("bounded known failure class and rationale required")
        if type(evidence_ids) is not tuple or not 0 < len(evidence_ids) <= 32:
            raise ValueError("retained evidence references required")
        with self.feedback._authorized(session, "propose") as (tx, principal):
            row = tx.get("outcome_revision", identifier(outcome_sha256))
            if row is None or not any(v["invocation_id"] == invocation_id for v in row["outcome"]["observations"]):
                raise FeedbackError("missing_evidence")
            for key in evidence_ids:
                if tx.get("readback_evidence", identifier(key)) is None and tx.get("context_evidence", key) is None:
                    raise FeedbackError("missing_evidence")
            key = "attribution-" + uuid.uuid4().hex
            value = {"attribution_id": key, "outcome_sha256": outcome_sha256, "invocation_id": invocation_id,
                     "failure_class": failure_class, "reason": reason, "evidence_ids": list(evidence_ids),
                     "actor_id": principal.principal_id, "status": "proposed", "verified_causality": False}
            tx.put("attribution", key, value, expected_revision=0)
            return value


def action_results(outcome: OutcomeRecord, receipts: list[dict]) -> list[dict]:
    """Require all checks on one exact call; preserve disagreement as disputed."""
    receipts = [VerificationReceipt.from_dict(r) for r in receipts]
    receipts = [r for r in receipts if r.scope == outcome.scope and r.outcome_id == outcome.outcome_id
                and r.outcome_sha256 == outcome.content_digest]
    results = []
    for requirement in outcome.required:
        calls = []
        for observation in outcome.observations:
            if observation.action_id != requirement.action_id:
                continue
            eligible = [r for r in receipts if r.invocation_id == observation.invocation_id
                        and r.assurance == "independent_readback"]
            by_check = {check: [] for check in requirement.checks}
            for receipt in eligible:
                for check in receipt.checks:
                    if check.check_id in by_check:
                        by_check[check.check_id].append(check)
            checks = []
            for name, values in by_check.items():
                states = {v.result for v in values}
                state = "unknown" if not states else "disputed" if len(states) > 1 or "disputed" in states else next(iter(states))
                checks.append({"check_id": name, "result": state, "kinds": sorted({v.kind for v in values}),
                               "reasons": [v.reason for v in values]})
            correct_tool = observation.tool == requirement.tool and observation.schema_version == requirement.schema_version
            bound = any(r.binding == "effect_receipt" for r in eligible)
            statuses = {r.effect_status for r in eligible if r.binding == "effect_receipt" and r.effect_status != "unknown"}
            effect_status = "disputed" if len(statuses)>1 else next(iter(statuses)) if statuses else "unknown"
            complete_receipt = any(r.binding == "effect_receipt"
                and r.effect_status == "succeeded"
                and {c.check_id for c in r.checks} == set(requirement.checks)
                and all(c.result == "pass" for c in r.checks) for r in eligible)
            passed = correct_tool and complete_receipt and effect_status == "succeeded" and all(v["result"] == "pass" for v in checks)
            calls.append({"invocation_id": observation.invocation_id, "checks": checks, "verified_success": passed,
                          "schema_matches": correct_tool, "tool": observation.tool, "schema_version": observation.schema_version,
                          "arguments": observation.arguments, "reported_result": observation.result,
                          "reported_checks": [v.to_dict() for v in observation.checks], "evidence_id": observation.evidence_id,
                          "effect_binding": "effect_receipt" if bound else "state_only" if eligible else "not_captured",
                          "effect_status": effect_status})
        successes = [c for c in calls if c["verified_success"]]
        results.append({"action_id": requirement.action_id, "tool": requirement.tool,
                        "schema_version": requirement.schema_version, "kind": requirement.kind,
                        "calls": calls, "verified_success": bool(successes),
                        "satisfying_invocation_id": successes[0]["invocation_id"] if successes else None,
                        "status": "pass" if successes else "no_call" if not calls else "disputed" if any(c["effect_status"] == "disputed" for c in calls) or any(
                            ch["result"] == "disputed" for c in calls for ch in c["checks"]) else "fail" if any(
                            ch["result"] == "fail" for c in calls for ch in c["checks"]) or any(
                            c["effect_status"] in ("failed", "not_dispatched") for c in calls) else "unknown"})
    return results
