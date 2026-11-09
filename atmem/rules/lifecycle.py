"""Revision-bound opt-in lifecycle. Inconclusive qualification never activates."""
from __future__ import annotations
from contextlib import nullcontext
import uuid

from atmem.contracts.feedback import ActivationReceipt, QualificationReceipt, RetrievalProfileCandidate, RuleCandidate, identifier
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.review import current_sources
from atmem.feedback.store import FeedbackError
from atmem.feedback.recovery import ensure_sources_not_revoked


STATES = frozenset({"shadow", "qualified", "active", "suspended", "revoked", "expired"})


class RuleLifecycle:
    def __init__(self, feedback):
        self.feedback = feedback

    def transition(self, owner_credential, scope, *, artifact_id, kind="rule", state, expected_generation,
                   qualification_id=None, versions=None, candidate_sha256=None):
        if kind not in ("rule", "profile") or state not in STATES:
            raise ValueError("known lifecycle transition required")
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        identifier(artifact_id)
        stopping = state in ("suspended", "revoked", "expired")
        if self.feedback.memory is None and not stopping:
            raise FeedbackError("missing_evidence")
        canonical = self.feedback.memory.store.transaction() if self.feedback.memory is not None else nullcontext()
        with canonical, self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            old = tx.get(kind+"_lifecycle", artifact_id)
            proposal = tx.get(kind+"_proposal", artifact_id)
            if not stopping and (proposal is None or proposal["state"] != "reviewed"):
                raise FeedbackError("review_required")
            if stopping and old is None:
                raise FeedbackError("invalid_transition")
            candidate = (RuleCandidate if kind == "rule" else RetrievalProfileCandidate).from_dict(proposal["candidate"]) if not stopping else None
            artifact_digest = old["candidate_sha256"] if stopping else candidate.content_digest
            if candidate_sha256 is not None and artifact_digest != candidate_sha256:
                raise FeedbackError("stale_revision")
            generation = old["generation"] if old else 0
            if type(expected_generation) is not int or expected_generation != generation:
                raise FeedbackError("stale_revision")
            if old and old["state"] in ("revoked", "expired") and not stopping and old["candidate_sha256"] == artifact_digest:
                raise FeedbackError("new_review_required")
            if state in ("shadow", "qualified", "active"):
                current_sources(self.feedback.memory, candidate)
                ensure_sources_not_revoked(tx, candidate.sources)
            if state in ("qualified", "active"):
                qualification = tx.get("qualification", identifier(qualification_id)) if qualification_id else None
                if qualification is None:
                    raise FeedbackError("qualification_inconclusive")
                receipt = QualificationReceipt.from_dict(qualification)
                if old and old.get("block_covered") and tx.rows[("qualification", qualification_id)]["sequence"] <= old.get("qualification_barrier", 0):
                    raise FeedbackError("fresh_qualification_required")
                if (receipt.scope != scope or receipt.artifact_sha256 != candidate.content_digest
                        or receipt.decision != "accept"):
                    raise FeedbackError("qualification_inconclusive")
                if receipt.expires_at <= self.feedback.clock():
                    raise FeedbackError("qualification_expired")
                if versions is None or receipt.versions != versions:
                    raise FeedbackError("version_changed")
            if state == "active" and (old is None or old["state"] not in ("shadow", "qualified", "suspended")):
                raise FeedbackError("shadow_required")
            value = {"artifact_id": artifact_id, "kind": kind, "candidate_sha256": artifact_digest,
                     "state": state, "generation": generation+1, "actor_id": principal.principal_id,
                     "qualification_id": qualification_id, "versions": versions or {}, "previous": old,
                     "tool": (old or {}).get("tool") if stopping else getattr(candidate, "tool", None),
                     "block_covered": bool((old or {}).get("block_covered")) and state not in ("active", "revoked", "expired"),
                     "qualification_barrier": (old or {}).get("qualification_barrier", 0)}
            # Keep lineage bounded rather than nesting all historical generations;
            # the append-only store already retains every preceding value.
            if old:
                value["previous"] = {k: old[k] for k in ("generation", "state", "candidate_sha256")}
            tx.put(kind+"_lifecycle", artifact_id, value, expected_revision=tx.revision(kind+"_lifecycle", artifact_id))
            receipt = ActivationReceipt("activation-"+uuid.uuid4().hex, scope, artifact_digest,
                qualification_id or "not-qualified", principal.principal_id, generation+1, state).to_dict()
            tx.put("activation", receipt["activation_id"], receipt, expected_revision=0)
            tx.audit(principal.principal_id, "transition_"+kind, allowed=True)
            return value

    def rollback(self, owner_credential, scope, *, artifact_id, target_generation, expected_generation,
                 versions, kind="rule"):
        """Restore an exact previously active generation after current authority checks.

        History is evidence, never permission by itself. Revoked/expired heads,
        removed sources, stale qualifications and restore barriers cannot be undone.
        A rollback is a new generation; historical receipts are never overwritten.
        """
        if (kind not in ("rule", "profile") or type(target_generation) is not int
                or type(expected_generation) is not int or not 0 < target_generation < expected_generation):
            raise ValueError("exact earlier generation required")
        identifier(artifact_id)
        if self.feedback.memory is None:
            raise FeedbackError("missing_evidence")
        with self.feedback.memory.store.transaction(), self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            current = tx.get(kind+"_lifecycle", artifact_id)
            if current is None or current["generation"] != expected_generation:
                raise FeedbackError("stale_revision")
            if current["state"] in ("revoked", "expired"):
                raise FeedbackError("new_review_required")
            history = list(tx.store.documents(partition_id=scope.partition))
            target = next((r["value"] for r in history if r["kind"] == kind+"_lifecycle"
                and r["key"] == artifact_id and not r["deleted"] and r["value"]["generation"] == target_generation), None)
            if target is None or target["state"] != "active":
                raise FeedbackError("invalid_rollback_target")
            proposal = next((r["value"] for r in reversed(history) if r["kind"] == kind+"_proposal"
                and r["key"] == artifact_id and not r["deleted"] and r["value"]["state"] == "reviewed"
                and r["value"]["candidate_sha256"] == target["candidate_sha256"]), None)
            if proposal is None:
                raise FeedbackError("review_required")
            candidate = (RuleCandidate if kind == "rule" else RetrievalProfileCandidate).from_dict(proposal["candidate"])
            current_sources(self.feedback.memory, candidate)
            ensure_sources_not_revoked(tx, candidate.sources)
            qualification_id = target["qualification_id"]
            raw = tx.get("qualification", qualification_id)
            if raw is None:
                raise FeedbackError("qualification_inconclusive")
            receipt = QualificationReceipt.from_dict(raw)
            if (receipt.decision != "accept" or receipt.scope != scope or receipt.artifact_sha256 != candidate.content_digest):
                raise FeedbackError("qualification_inconclusive")
            if receipt.expires_at <= self.feedback.clock():
                raise FeedbackError("qualification_expired")
            if receipt.versions != versions or target["versions"] != versions:
                raise FeedbackError("version_changed")
            if tx.rows[("qualification", qualification_id)]["sequence"] <= current.get("qualification_barrier", 0):
                raise FeedbackError("fresh_qualification_required")
            value = {**target, "generation": expected_generation+1, "actor_id": principal.principal_id,
                     "previous": {k: current[k] for k in ("generation", "state", "candidate_sha256")},
                     "rollback_of_generation": target_generation, "block_covered": False,
                     "qualification_barrier": current.get("qualification_barrier", 0)}
            tx.put(kind+"_proposal", artifact_id, proposal, expected_revision=tx.revision(kind+"_proposal", artifact_id))
            tx.put(kind+"_lifecycle", artifact_id, value, expected_revision=tx.revision(kind+"_lifecycle", artifact_id))
            activation = ActivationReceipt("activation-"+uuid.uuid4().hex, scope, candidate.content_digest,
                qualification_id, principal.principal_id, value["generation"], "active").to_dict()
            tx.put("activation", activation["activation_id"], activation, expected_revision=0)
            tx.audit(principal.principal_id, "rollback_"+kind, allowed=True,
                     detail={"target_generation": target_generation, "generation": value["generation"]})
            return value

    def current(self, tx, *, kind, versions, tool=None):
        """Called at admission with canonical source and evidence locks held."""
        result = []
        for row in tx.iter_kind(kind+"_lifecycle"):
            if row.get("block_covered") and (kind != "rule" or tool is None or row.get("tool") in (None, tool)):
                raise FeedbackError("restore_requalification_required")
            if row["state"] not in ("active", "shadow"):
                continue
            proposal = tx.get(kind+"_proposal", row["artifact_id"])
            if proposal is None or proposal["state"] != "reviewed" or proposal["candidate_sha256"] != row["candidate_sha256"]:
                if row["state"] == "shadow":
                    continue
                raise FeedbackError("stale_policy")
            candidate = (RuleCandidate if kind == "rule" else RetrievalProfileCandidate).from_dict(proposal["candidate"])
            if kind == "rule" and tool is not None and candidate.tool != tool:
                continue
            try:
                current_sources(self.feedback.memory, candidate)
                ensure_sources_not_revoked(tx, candidate.sources)
            except FeedbackError:
                if row["state"] == "shadow":
                    continue
                raise
            if row["state"] == "active":
                receipt = tx.get("qualification", row["qualification_id"])
                if (receipt is None or receipt["decision"] != "accept" or receipt["artifact_sha256"] != candidate.content_digest
                        or receipt["scope"] != candidate.scope.to_dict() or receipt["expires_at"] <= self.feedback.clock()
                        or receipt["versions"] != versions or row["versions"] != versions):
                    raise FeedbackError("qualification_expired")
            result.append((row, candidate))
        return result
