"""Frozen offline qualification evidence; synthetic data cannot activate behavior.

No model runner or paid dependency is invoked. Observations must already exist
in the protected store and come from registered independent readback verifiers.
Default evaluation is diagnostic and inconclusive. This component does not turn
an owner assertion of power, benchmark quality or a pasted score into acceptance.
"""
from __future__ import annotations

from hashlib import sha256
import time
import uuid

from atmem.contracts.feedback import OutcomeRecord, QualificationReceipt, identifier
from atmem.core.canonical import canonical_json
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.baseline import validate_baseline
from atmem.feedback.metrics import paired_episode_interval, rate
from atmem.feedback.store import FeedbackError, snapshot
from atmem.feedback.verification import action_results


class QualificationService:
    def __init__(self, feedback, *, timer=time.monotonic):
        self.feedback = feedback
        self.timer = timer

    def _owner(self, credential, scope):
        principal = self.feedback._principal(credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        return principal

    def freeze(self, owner_credential, scope, manifest, *, artifact_sha256):
        from atmem.contracts.feedback import digest
        principal = self._owner(owner_credential, scope)
        digest(artifact_sha256)
        preflight = validate_baseline(manifest)
        manifest = snapshot(manifest)
        value = {"manifest": manifest, "manifest_sha256": preflight.digest,
                 "artifact_sha256": artifact_sha256, "actor_id": principal.principal_id,
                 "execution_authorized": False, "paid_calls_authorized": False}
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            old = tx.get("evaluation_manifest", preflight.digest)
            if old is not None:
                if old != value:
                    raise FeedbackError("conflicting_retry")
                return old
            tx.put("evaluation_manifest", preflight.digest, value, expected_revision=0)
            tx.audit(principal.principal_id, "freeze_evaluation", allowed=True)
            return value

    def evaluate(self, owner_credential, scope, *, manifest_sha256, idempotency_key):
        """Reserve before replay; failed/crashed attempts cannot reset the ceiling."""
        principal = self._owner(owner_credential, scope)
        identifier(manifest_sha256)
        identifier(idempotency_key)
        started = self.timer()
        frozen, payload, attempt_id, cached = self._reserve(owner_credential, scope, manifest_sha256, idempotency_key)
        if cached is not None:
            return cached
        try:
            return self._compute(owner_credential, scope, manifest_sha256, idempotency_key,
                                 frozen, payload, attempt_id, started)
        except Exception as exc:
            # The reservation already committed. If authority/storage is lost,
            # it stays pending/unknown and still consumes an attempt.
            try:
                with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
                    attempt = tx.get("evaluation_attempt", attempt_id)
                    if attempt is not None and attempt["status"] == "pending":
                        tx.put("evaluation_attempt", attempt_id, {**attempt, "status":"failed",
                            "error":exc.code if type(exc) is FeedbackError else "evaluation_failed"},
                            expected_revision=tx.revision("evaluation_attempt", attempt_id))
            except Exception:
                pass
            raise

    def _reserve(self, credential, scope, manifest_sha256, idempotency_key):
        denial = None
        attempt_id = sha256(("evaluate\0"+idempotency_key).encode()).hexdigest()
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            frozen = tx.get("evaluation_manifest", manifest_sha256)
            if frozen is None:
                raise FeedbackError("missing_evidence")
            manifest = frozen["manifest"]
            if validate_baseline(manifest).digest != manifest_sha256:
                raise FeedbackError("stale_revision")
            payload = {"manifest_sha256": manifest_sha256, "artifact_sha256": frozen["artifact_sha256"],
                       "actor_id": principal.principal_id}
            cached = tx.cached("evaluate", idempotency_key, payload)
            if cached is not None:
                return frozen, payload, attempt_id, cached
            hypothesis = manifest["candidate"]["failure_hypothesis"]
            payload_sha256 = sha256(canonical_json(payload).encode()).hexdigest()
            previous = tx.get("evaluation_attempt", attempt_id)
            if previous is not None:
                if previous["payload_sha256"] != payload_sha256:
                    raise FeedbackError("conflicting_retry")
                raise FeedbackError(previous["error"] if previous["status"] == "failed" else "evaluation_inflight_or_unknown")
            budget_key = sha256(hypothesis.encode()).hexdigest()
            budget = tx.get("evaluation_budget", budget_key)
            # Explicit development-ledger compatibility: old completed attempts
            # remain charged when the durable control counter is first created.
            used = budget["attempts"] if budget is not None else sum(
                r.get("hypothesis") == hypothesis or r.get("hypothesis_sha256") == budget_key
                for r in tx.iter_kind("evaluation_attempt"))
            if used >= min(3, manifest["candidate"]["max_attempts"]):
                if budget is None:
                    tx.put("evaluation_budget", budget_key, {"attempts":used}, expected_revision=0)
                tx.audit(principal.principal_id, "reserve_evaluation", allowed=False)
                denial = "attempt_budget_exhausted"
            else:
                tx.put("evaluation_budget", budget_key, {"attempts":used+1}, expected_revision=tx.revision("evaluation_budget", budget_key))
                tx.put("evaluation_attempt", attempt_id, {"hypothesis_sha256":budget_key,
                    "manifest_sha256":manifest_sha256, "payload_sha256":payload_sha256, "status":"pending"}, expected_revision=0)
                tx.audit(principal.principal_id, "reserve_evaluation", allowed=True)
        if denial:
            raise FeedbackError(denial)
        return frozen, payload, attempt_id, None

    def _compute(self, credential, scope, manifest_sha256, idempotency_key, frozen, payload, attempt_id, started):
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            attempt = tx.get("evaluation_attempt", attempt_id)
            if (tx.get("evaluation_manifest", manifest_sha256) != frozen or attempt is None or attempt["status"] != "pending"
                    or principal.principal_id != payload["actor_id"]):
                raise FeedbackError("evaluation_changed")
            manifest = frozen["manifest"]
            retained = list(tx.iter_kind("verification"))
            pairs, arms, missing = [], {"native": [], "atmem": [], "candidate": []}, []
            # Outcome IDs are frozen by convention rather than supplied result
            # totals: eval:<manifest>:<arm>:<task>. They fit the identifier bound.
            for task in manifest["tasks"]:
                before_after = {}
                for arm in arms:
                    key = f"eval:{manifest_sha256}:{arm}:{task['id']}"
                    row = tx.get("outcome", key)
                    if row is None:
                        missing.append(key)
                        before_after[arm] = False
                        arms[arm].append(False)
                        continue
                    outcome = OutcomeRecord.from_dict(row["outcome"])
                    actual_required = [(r.action_id, r.tool, r.kind, list(r.checks)) for r in outcome.required]
                    expected_required = [(r["id"], r["tool"], r["kind"], r["checks"]) for r in task["actions"]]
                    if actual_required != expected_required:
                        raise FeedbackError("task_contract_changed")
                    actions = action_results(outcome, retained)
                    if any(a["status"] in ("unknown", "disputed", "no_call") for a in actions):
                        missing.append(key)
                    passed = all(a["verified_success"] for a in actions)
                    before_after[arm] = passed
                    arms[arm].append(passed)
                pairs.append((task["episode"], before_after["atmem"], before_after["candidate"]))
            paired = paired_episode_interval(tuple(pairs), seed=manifest["seed"])
            elapsed = self.timer()-started
            if elapsed > manifest["budget"]["seconds"]:
                raise FeedbackError("time_budget_exhausted")
            metrics = {"arms": {arm: rate(sum(values), len(values)) for arm, values in arms.items()},
                       "paired_interval": paired,
                       "unknown_items": len(missing), "missing_ids": missing[:128], "model_calls": 0,
                       "tokens": 0, "usd": 0, "elapsed_seconds": elapsed,
                       "claim": "diagnostic_only", "production_gates": "not_qualified",
                       "attempt_id":attempt_id, "disk_budget_basis":"serialized_qualification_payload_only"}
            now = int(self.feedback.clock())
            receipt = QualificationReceipt("qualification-" + uuid.uuid4().hex, scope, frozen["artifact_sha256"],
                manifest_sha256, manifest["versions"], "inconclusive", now, now+604800, metrics).to_dict()
            if len(canonical_json(receipt).encode()) > manifest["budget"]["disk_bytes"]:
                raise FeedbackError("disk_budget_exhausted")
            def publish():
                tx.put("qualification", receipt["receipt_id"], receipt, expected_revision=0)
                tx.put("evaluation_attempt", attempt_id, {**attempt, "receipt_id":receipt["receipt_id"],
                    "status":"inconclusive"}, expected_revision=tx.revision("evaluation_attempt", attempt_id))
                return receipt
            return tx.once("evaluate", idempotency_key, payload, publish)
