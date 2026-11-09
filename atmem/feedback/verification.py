"""Registered authenticated readback, not agent self-grading.

An owner chooses a trusted implementation and its supported tool/check version.
Model tools cannot register verifiers or supply trusted check outcomes. Readbacks
must be read-only; this boundary does not replay the original action.
"""
from __future__ import annotations

from contextvars import copy_context
from contextlib import nullcontext
from dataclasses import dataclass
import queue
import threading
import time
import uuid

from atmem.contracts.feedback import ActionCheck, AttributionVerification, OutcomeRecord, VerificationReceipt, identifier
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, snapshot
from atmem.feedback.observability import measured

FAILURE_CLASSES = frozenset({"source_fact_absent", "retrieval_miss", "authority_withheld", "stale_conflicting_state",
                             "delivered_but_not_applied", "wrong_argument_value", "wording_precision", "no_call",
                             "execution_failure", "unknown"})

# Operational proof obligations, not explanations of an agent's internal cause.
# A trace or a model's proposed label cannot satisfy this interface. Trusted
# application code must perform the registered independent readback itself.
ATTRIBUTION_CHECKS = {
    "source_fact_absent": ("complete_authorized_snapshot", "snapshot_precedes_turn", "required_fact_absent"),
    "retrieval_miss": ("complete_authorized_snapshot", "snapshot_precedes_turn", "required_fact_present",
                       "query_eligible", "absent_from_delivered_context"),
    "authority_withheld": ("authorization_receipt_valid", "fact_withheld"),
    "stale_conflicting_state": ("state_versions_captured", "conflict_or_staleness_verified"),
    "delivered_but_not_applied": ("delivery_receipt_valid", "required_fact_delivered",
                                  "fact_missing_from_write", "effect_correlated"),
    "wrong_argument_value": ("authoritative_value_captured", "wrong_argument", "effect_correlated"),
    "wording_precision": ("precision_contract_frozen", "precision_check_failed", "effect_correlated"),
    "no_call": ("capture_complete", "no_matching_invocation"),
    "execution_failure": ("effect_correlated", "backend_failure"),
    "unknown": ("insufficient_evidence",),
}


@dataclass(frozen=True)
class Readback:
    checks: tuple[ActionCheck, ...]
    evidence: dict
    assessments: tuple[dict, ...] = ()


@dataclass(frozen=True)
class AttributionReadback:
    failure_class: str
    checks: tuple[ActionCheck, ...]
    evidence: dict


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

    def propose_attribution(self, session, *, outcome_sha256, invocation_id=None, action_id=None,
                            failure_class, reason, evidence_ids=()):
        """Store a diagnosis proposal; a model cannot certify causal failure."""
        if failure_class not in FAILURE_CLASSES or type(reason) is not str or not 0 < len(reason.encode()) <= 4096:
            raise ValueError("bounded known failure class and rationale required")
        if (type(evidence_ids) is not tuple or len(evidence_ids) > 32
                or not evidence_ids and failure_class not in ("no_call", "unknown")):
            raise ValueError("retained evidence references required")
        with self.feedback._authorized(session, "propose") as (tx, principal):
            row = tx.get("outcome_revision", identifier(outcome_sha256))
            if row is None:
                raise FeedbackError("missing_evidence")
            record = OutcomeRecord.from_dict(row["outcome"])
            observation = next((v for v in record.observations if v.invocation_id == invocation_id), None)
            if observation is not None:
                if action_id is not None and action_id != observation.action_id:
                    raise FeedbackError("missing_evidence")
                action_id = observation.action_id
            elif (invocation_id is not None or failure_class not in ("no_call", "unknown")
                  or not any(v.action_id == action_id for v in record.required)
                  or any(v.action_id == action_id for v in record.observations)):
                raise FeedbackError("missing_evidence")
            for key in evidence_ids:
                if tx.get("readback_evidence", identifier(key)) is None and tx.get("context_evidence", key) is None:
                    raise FeedbackError("missing_evidence")
            key = "attribution-" + uuid.uuid4().hex
            value = {"attribution_id": key, "outcome_sha256": outcome_sha256, "invocation_id": invocation_id,
                     "action_id":action_id,
                     "failure_class": failure_class, "reason": reason, "evidence_ids": list(evidence_ids),
                     "actor_id": principal.principal_id, "status": "proposed", "verified_causality": False}
            tx.put("attribution", key, value, expected_revision=0)
            return value

    def register_attribution_verifier(self, owner_credential, scope, *, principal_id,
                                      version, tool, schema_version, failure_classes, readback):
        """Trusted independent checker registration; never a model-facing tool.

        The checker must retain the actual snapshot/readback material supporting
        every fixed proof obligation. A boolean or diagnostic label from a host
        is not an independent check. Registration itself certifies no outcome.
        """
        for item in (principal_id, version, tool, schema_version):
            identifier(item)
        if (type(failure_classes) is not tuple or not failure_classes
                or len(failure_classes) > len(ATTRIBUTION_CHECKS)
                or len(set(failure_classes)) != len(failure_classes)
                or any(v not in ATTRIBUTION_CHECKS for v in failure_classes)
                or not callable(readback)):
            raise ValueError("bounded explicit attribution checker required")
        key = self._key(principal_id, tool, "attribution:" + schema_version)
        value = {"principal_id":principal_id, "version":version, "tool":tool,
                 "schema_version":schema_version, "failure_classes":list(failure_classes),
                 "active":True, "assurance":"independent_readback"}
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            tx.put("attribution_verifier", key, value,
                   expected_revision=tx.revision("attribution_verifier", key))
            tx.audit(principal.principal_id, "register_attribution_verifier", allowed=True)
        with self._lock:
            self._handlers[(scope.content_digest, "attribution:"+key, version)] = readback

    def revoke_attribution_verifier(self, owner_credential, scope, *, principal_id, tool, schema_version):
        key = self._key(principal_id, tool, "attribution:" + schema_version)
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            value = tx.get("attribution_verifier", key)
            if value is None:
                raise FeedbackError("denied")
            tx.put("attribution_verifier", key, {**value, "active":False},
                   expected_revision=tx.revision("attribution_verifier", key))
            tx.audit(principal.principal_id, "revoke_attribution_verifier", allowed=True)

    @staticmethod
    def _attribution_evidence(tx, proposal, outcome):
        """Only evidence actually bound to this outcome/call may support it."""
        retained = []
        for evidence_id in proposal["evidence_ids"]:
            value = tx.get("readback_evidence", evidence_id)
            if value is not None:
                if (value.get("outcome_sha256") != outcome.content_digest
                        or value.get("invocation_id") != proposal["invocation_id"]):
                    raise FeedbackError("unbound_attribution_evidence")
            else:
                value = tx.get("context_evidence", evidence_id)
                if value is None or evidence_id != outcome.context_receipt_id:
                    raise FeedbackError("unbound_attribution_evidence")
            retained.append({"evidence_id":evidence_id, "value":value})
        return retained

    def _attribution_sources(self, tx, scope, sources):
        from types import SimpleNamespace
        from atmem.contracts.feedback import SourceRevision
        from atmem.feedback.review import current_sources
        from atmem.feedback.recovery import ensure_sources_not_revoked
        from atmem.knowledge.rag.contracts import RagSource
        if type(sources) is not list or len(sources) > 32:
            raise FeedbackError("invalid_attribution_sources")
        seen = set()
        for item in sources:
            if type(item) is not dict or set(item) != {"kind", "source"}:
                raise FeedbackError("invalid_attribution_sources")
            if item["kind"] == "rag":
                source = RagSource.from_dict(item["source"])
                if (source.scope != scope or not source.active
                        or tx.get("rag_source", source.source_id) != source.to_dict()):
                    raise FeedbackError("stale_source")
            elif item["kind"] == "memory":
                source = SourceRevision.from_dict(item["source"])
                if self.feedback.memory is None:
                    raise FeedbackError("missing_evidence")
                current_sources(self.feedback.memory, SimpleNamespace(scope=scope, sources=(source,)),
                                egress_class=self.feedback.egress_class)
                ensure_sources_not_revoked(tx, (source,))
            else:
                raise FeedbackError("invalid_attribution_sources")
            identity = (item["kind"], source.source_id)
            if identity in seen:
                raise FeedbackError("invalid_attribution_sources")
            seen.add(identity)

    def verify_attribution(self, session, *, attribution_id, idempotency_key):
        """Append bounded independent classification; never infer mental cause.

        Fixed mechanical proof obligations and retained material are mandatory.
        The result cannot qualify or activate a policy. Original proposals and
        disagreements survive rather than being overwritten by the checker.
        """
        identifier(attribution_id)
        identifier(idempotency_key)
        with self.feedback._authorized(session, "verify") as (tx, principal):
            proposal = tx.get("attribution", attribution_id)
            if proposal is None:
                raise FeedbackError("denied")
            row = tx.get("outcome_revision", proposal["outcome_sha256"])
            if row is None:
                raise FeedbackError("missing_evidence")
            outcome = OutcomeRecord.from_dict(row["outcome"])
            observation = next((v for v in outcome.observations
                                if v.invocation_id == proposal["invocation_id"]), None)
            requirement = next((v for v in outcome.required if v.action_id == proposal.get("action_id")), None)
            if requirement is None and observation is not None:
                requirement = next(v for v in outcome.required if v.action_id == observation.action_id)
            if requirement is None or observation is None and proposal["failure_class"] not in ("no_call", "unknown"):
                raise FeedbackError("missing_evidence")
            if principal.principal_id in (row["actor_id"], proposal["actor_id"]):
                raise FeedbackError("not_independent")
            key = self._key(principal.principal_id, requirement.tool,
                            "attribution:" + requirement.schema_version)
            registered = tx.get("attribution_verifier", key)
            if (registered is None or not registered["active"]
                    or proposal["failure_class"] not in registered["failure_classes"]):
                raise FeedbackError("denied")
            retained = self._attribution_evidence(tx, proposal, outcome)
            if proposal["failure_class"] in ("delivered_but_not_applied", "retrieval_miss"):
                if outcome.delivery != "delivered" or outcome.context_receipt_id not in proposal["evidence_ids"]:
                    raise FeedbackError("missing_delivery_evidence")
            payload = {"attribution_id":attribution_id, "actor_id":principal.principal_id,
                       "verifier":registered, "registry_revision":tx.revision("attribution_verifier", key)}
            cached = tx.cached("verify_attribution", idempotency_key, payload)
            if cached is not None:
                return cached
            generation = tx.revision("attribution_verifier", key)
            attempt_id = "classification-attempt-" + uuid.uuid4().hex
            tx.put("attribution_attempt", attempt_id, {**payload, "status":"pending"}, expected_revision=0)
        try:
            readback = self._read((session.scope.content_digest, "attribution:"+key, registered["version"]),
                lambda callback, deadline: callback(OutcomeRecord.from_dict(outcome.to_dict()),
                    type(observation).from_dict(observation.to_dict()) if observation is not None else None,
                    snapshot(proposal), snapshot(retained), deadline=deadline))
        except FeedbackError as exc:
            try:
                with self.feedback._authorized(session, "verify") as (tx, _):
                    tx.put("attribution_attempt", attempt_id, {**payload, "status":"failed", "error":exc.code},
                           expected_revision=1)
            except FeedbackError:
                pass
            raise
        if (type(readback) is not AttributionReadback or readback.failure_class != proposal["failure_class"]
                or type(readback.checks) is not tuple):
            raise FeedbackError("invalid_attribution_readback")
        if any(type(v) is not ActionCheck for v in readback.checks):
            raise FeedbackError("invalid_attribution_readback")
        checks = tuple(ActionCheck.from_dict(v.to_dict()) for v in readback.checks)
        required = ATTRIBUTION_CHECKS[readback.failure_class]
        if (len(checks) != len(required) or {v.check_id for v in checks} != set(required)
                or any(v.kind != "mechanical" for v in checks)):
            raise FeedbackError("incomplete_attribution_proof")
        material = snapshot(readback.evidence)
        if (type(material) is not dict
                or set(material) != {"scope", "outcome_sha256", "invocation_id", "proofs", "sources"}
                or material["scope"] != session.scope.to_dict()
                or material["outcome_sha256"] != outcome.content_digest
                or material["invocation_id"] != proposal["invocation_id"]
                or type(material["proofs"]) is not dict or set(material["proofs"]) != set(required)
                or any(type(v) is not dict or set(v) != {"method", "observed", "expected"}
                       for v in material["proofs"].values())):
            raise FeedbackError("missing_evidence")
        for proof in material["proofs"].values():
            identifier(proof["method"])
        canonical = self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical, self.feedback._authorized(session, "verify") as (tx, principal):
            if (tx.get("attribution_verifier", key) != registered
                    or tx.revision("attribution_verifier", key) != generation):
                raise FeedbackError("verifier_changed")
            if (tx.get("attribution", attribution_id) != proposal
                    or tx.get("outcome_revision", outcome.content_digest) != row
                    or self._attribution_evidence(tx, proposal, outcome) != retained):
                raise FeedbackError("missing_evidence")
            self._attribution_sources(tx, session.scope, material["sources"])
            if not material["sources"] and readback.failure_class in (
                    "retrieval_miss", "stale_conflicting_state", "delivered_but_not_applied",
                    "wrong_argument_value", "wording_precision"):
                raise FeedbackError("missing_attribution_source")
            receipts = [v for v in tx.iter_kind("verification")
                        if v["outcome_sha256"] == outcome.content_digest]
            action = next(v for v in action_results(outcome, receipts)
                          if v["action_id"] == requirement.action_id)
            bound = [v for v in receipts if v["invocation_id"] == proposal["invocation_id"]
                     and v["assurance"] == "independent_readback" and v["binding"] == "effect_receipt"]
            if "effect_correlated" in required:
                expected_status = "failed" if readback.failure_class == "execution_failure" else "succeeded"
                if not any(v["effect_status"] == expected_status
                           and {c["check_id"] for c in v["checks"]} == set(requirement.checks)
                           and (expected_status == "failed" or any(c["result"] == "fail" for c in v["checks"]))
                           for v in bound):
                    raise FeedbackError("missing_independent_effect")
            passed = all(v.result == "pass" for v in checks)
            prior = [v for v in tx.iter_kind("attribution_verification")
                     if v["attribution_id"] == attribution_id]
            check_states = {v.check_id:v.result for v in checks}
            disputed = action["status"] == "disputed" or any(
                {v["check_id"]:v["result"] for v in previous["checks"]} != check_states for previous in prior)
            def publish():
                receipt_id = "classification-" + uuid.uuid4().hex
                value = {"format":"atmem-feedback-attribution-verification-v1",
                    "receipt_id":receipt_id, "scope":session.scope.to_dict(),
                    "attribution_id":attribution_id, "outcome_sha256":outcome.content_digest,
                    "invocation_id":proposal["invocation_id"], "action_id":requirement.action_id,
                    "failure_class":readback.failure_class,
                    "verifier_id":principal.principal_id, "verifier_version":registered["version"],
                    "registry_revision":generation, "checks":[v.to_dict() for v in checks],
                    "evidence":material, "evidence_ids":proposal["evidence_ids"],
                    "sources":material["sources"],
                    "verification_ids":[v["receipt_id"] for v in bound],
                    "status":"disputed" if disputed else "verified" if passed and readback.failure_class != "unknown" else "inconclusive",
                    "supports_classification": (None if readback.failure_class == "unknown" else
                        False if any(v.result == "fail" for v in checks) else True if passed else None),
                    "assurance":"independent_readback", "claim":"bounded_operational_classification",
                    "verified_causality":False, "qualifies_policy":False}
                value = AttributionVerification.from_dict(value).to_dict()
                tx.put("attribution_verification", receipt_id, value, expected_revision=0)
                # This defining dependency edge owns the diagnosis identity.
                # Source deletion must remove the proposal and every derived
                # classification/cache, without walking back into its outcome.
                tx.put("attribution_lineage", receipt_id, {
                    "attribution_id":attribution_id, "sources":material["sources"]}, expected_revision=0)
                tx.put("attribution_attempt", attempt_id, {**payload, "status":value["status"],
                       "receipt_id":receipt_id}, expected_revision=1)
                return value
            return tx.once("verify_attribution", idempotency_key, payload, publish)

    @staticmethod
    def attribution_views(tx, outcome_sha256):
        proposals = [v for v in tx.iter_kind("attribution") if v["outcome_sha256"] == outcome_sha256]
        if not proposals:
            return []
        checked = [v for v in tx.iter_kind("attribution_verification") if v["outcome_sha256"] == outcome_sha256]
        if len(proposals) > 128 or len(checked) > 128:
            raise FeedbackError("result_budget_exhausted")
        row = tx.get("outcome_revision", outcome_sha256)
        if row is None:
            raise FeedbackError("denied")
        actions = {v["action_id"]:v for v in action_results(OutcomeRecord.from_dict(row["outcome"]),
            [v for v in tx.iter_kind("verification") if v["outcome_sha256"] == outcome_sha256])}
        result = []
        for proposal in proposals:
            verified = [v for v in checked if v["attribution_id"] == proposal["attribution_id"]]
            signatures = {tuple(sorted((c["check_id"], c["result"]) for c in v["checks"])) for v in verified}
            action_id = proposal.get("action_id")
            if action_id is None:
                action_id = next((v.action_id for v in OutcomeRecord.from_dict(row["outcome"]).observations
                                  if v.invocation_id == proposal["invocation_id"]), None)
            disputed = len(signatures) > 1 or actions.get(action_id, {}).get("status") == "disputed"
            status = ("disputed" if disputed else "verified" if any(v["status"] == "verified" for v in verified)
                      else "inconclusive" if verified else "proposed")
            resolution = tx.get("attribution_resolution", proposal["attribution_id"])
            resolution_current = resolution is not None and set(resolution["receipt_ids"]) == {v["receipt_id"] for v in verified}
            if resolution_current:
                status = "resolved_human"
            summaries = [{key:v[key] for key in ("receipt_id", "verifier_id", "verifier_version", "assurance", "checks", "supports_classification")}
                         for v in verified]
            result.append({"attribution_id":proposal["attribution_id"], "action_id":action_id,
                "invocation_id":proposal["invocation_id"], "failure_class":proposal["failure_class"],
                "reason":proposal["reason"], "status":status, "verifications":summaries,
                "resolution_generation":tx.revision("attribution_resolution",proposal["attribution_id"]),
                "resolution":resolution if resolution_current else None,
                "verified_causality":False, "qualifies_policy":False})
        return result

    def attributions(self, session, *, outcome_sha256):
        identifier(outcome_sha256)
        with self.feedback._authorized(session, "read") as (tx, _):
            return {"outcome_sha256":outcome_sha256,
                    "classifications":self.attribution_views(tx, outcome_sha256)}

    def resolve_attribution(self, owner_credential, scope, *, attribution_id, receipt_ids,
                            chosen_receipt_id, reason, expected_generation):
        """Append an owner decision at the human tier; never erase disagreement."""
        identifier(attribution_id)
        if (type(receipt_ids) is not tuple or not 2 <= len(receipt_ids) <= 128
                or len(set(receipt_ids)) != len(receipt_ids) or chosen_receipt_id not in receipt_ids
                or type(expected_generation) is not int or expected_generation < 0
                or type(reason) is not str or not reason.strip() or len(reason.encode()) > 4096):
            raise ValueError("exact revision-bound classification resolution required")
        for key in receipt_ids:
            identifier(key)
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            if tx.get("attribution", attribution_id) is None:
                raise FeedbackError("denied")
            actual = {v["receipt_id"] for v in tx.iter_kind("attribution_verification")
                      if v["attribution_id"] == attribution_id}
            if actual != set(receipt_ids):
                raise FeedbackError("stale_revision")
            chosen = tx.get("attribution_verification", chosen_receipt_id)
            value = {"attribution_id":attribution_id,"receipt_ids":sorted(receipt_ids),
                     "chosen_receipt_id":chosen_receipt_id,"actor_id":principal.principal_id,
                     "reason":reason,"generation":expected_generation+1,"assurance":"human_attestation",
                     "selected_verdict":chosen["supports_classification"],
                     "qualifies_policy":False}
            if tx.get("attribution_resolution", attribution_id) == value:
                return value
            if tx.revision("attribution_resolution", attribution_id) != expected_generation:
                raise FeedbackError("stale_revision")
            tx.put("attribution_resolution", attribution_id, value, expected_revision=expected_generation)
            tx.audit(principal.principal_id,"resolve_attribution",allowed=True)
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
