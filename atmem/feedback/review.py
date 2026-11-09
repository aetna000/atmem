"""Evidence-bound behavior proposals behind the existing ReviewService."""
from __future__ import annotations

from hashlib import sha256

from atmem.contracts.feedback import RetrievalProfileCandidate, RuleCandidate, identifier
from atmem.feedback.store import FeedbackError
from atmem.feedback.recovery import ensure_sources_not_revoked


def current_sources(memory, candidate, *, egress_class="remote"):
    """Current eligible canonical records, never arbitrary document instructions."""
    if egress_class not in ("local", "remote"):
        raise FeedbackError("denied")
    if memory is None:
        raise FeedbackError("missing_evidence")
    if memory.store.path != ":memory:" and memory.policy.state != "encrypted":
        raise FeedbackError("encrypted_memory_required")
    expected = candidate.scope.authority_scope().to_dict()
    allowed = memory.store.authorized_record_ids(candidate.scope.subject_id, candidate.scope.workspace_id,
        [source.source_id for source in candidate.sources], remote=egress_class == "remote", agent_id=candidate.scope.agent_id)
    rows = []
    for source in candidate.sources:
        if source.source_id not in allowed:
            raise FeedbackError("stale_source")
        record = memory.store.get_record(candidate.scope.subject_id, source.source_id)
        if (record is None or record["status"] != "active"
                or record["raw"].get("authority_scope") != expected
                or record["generation"] != source.revision
                or sha256(record["content"].encode()).hexdigest() != source.content_sha256):
            raise FeedbackError("stale_source")
        rows.append(record)
    return rows


def _proposal_receipt(value):
    """Proposal permission never returns raw canonical records or review prose."""
    fields = ("format", "kind", "artifact_id", "candidate_sha256", "revision", "scope", "state", "activation")
    if "candidate" not in value:
        return {key:value[key] for key in fields}
    candidate = value["candidate"]
    kind = "rule" if "rule_id" in candidate else "profile"
    return {"format":"atmem-feedback-proposal-receipt-v1", "kind":kind, "artifact_id":candidate[kind+"_id"],
            "candidate_sha256":value["candidate_sha256"], "revision":candidate["revision"], "scope":candidate["scope"],
            "state":value["state"], "activation":"not_active"}


def propose(review, feedback, session, candidate, *, idempotency_key):
    if type(candidate) not in (RuleCandidate, RetrievalProfileCandidate):
        raise ValueError("known behavior candidate required")
    candidate = type(candidate).from_dict(candidate.to_dict())
    kind = "rule" if type(candidate) is RuleCandidate else "profile"
    candidate_id = candidate.rule_id if kind == "rule" else candidate.profile_id
    if candidate.scope != session.scope or review.memory is not feedback.memory:
        raise FeedbackError("denied")
    identifier(idempotency_key)
    # Hold canonical source changes out through the proposal commit. The core
    # memory transaction always precedes the feedback transaction on this path.
    with review.memory.store.transaction(), feedback._authorized(session, "propose") as (tx, principal):
        sources = current_sources(review.memory, candidate, egress_class=feedback.egress_class)
        ensure_sources_not_revoked(tx, candidate.sources)
        payload = {"candidate": candidate.to_dict(), "actor_id": principal.principal_id}
        cached = tx.cached(f"propose_{kind}", idempotency_key, payload)
        if cached is not None:
            return _proposal_receipt(cached)
        old = tx.get(f"{kind}_proposal", candidate_id)
        if old and candidate.revision != old["candidate"]["revision"]+1:
            if old["candidate"] == candidate.to_dict():
                return _proposal_receipt(tx.once(f"propose_{kind}", idempotency_key, payload, lambda: _proposal_receipt(old)))
            raise FeedbackError("stale_revision")
        if old is None and candidate.revision != 1:
            raise FeedbackError("stale_revision")
        def publish():
            value = {**payload, "candidate_sha256": candidate.content_digest,
                     "sources": sources, "state": "proposed"}
            tx.put(f"{kind}_proposal", candidate_id, value, expected_revision=tx.revision(f"{kind}_proposal", candidate_id))
            return _proposal_receipt(value)
        return tx.once(f"propose_{kind}", idempotency_key, payload, publish)


def decide(review, feedback, session, *, rule_id, candidate_sha256, decision, reason, authorization, kind="rule"):
    if kind not in ("rule", "profile"):
        raise ValueError("known behavior candidate kind required")
    if decision not in ("approve", "reject") or type(reason) is not str or not 0 < len(reason.encode()) <= 4096:
        raise ValueError("explicit decision and bounded rationale required")
    if review.memory is not feedback.memory:
        raise FeedbackError("denied")
    with review.memory.store.transaction(), feedback._authorized(session, "propose") as (tx, principal):
        old = tx.get(f"{kind}_proposal", identifier(rule_id))
        if old is None or old["candidate_sha256"] != candidate_sha256 or old["state"] != "proposed":
            raise FeedbackError("stale_revision")
        candidate = (RuleCandidate if kind == "rule" else RetrievalProfileCandidate).from_dict(old["candidate"])
        current_sources(review.memory, candidate, egress_class=feedback.egress_class)
        ensure_sources_not_revoked(tx, candidate.sources)
        if getattr(authorization, "principal_id", None) != principal.principal_id:
            raise FeedbackError("denied")
        stored_scope = {k: getattr(session.scope, k) for k in ("subject_id", "agent_id", "workspace_id")}
        try:
            actor = review.memory.verify_review_authorization(authorization, stored_scope, required_scopes=("procedure:review",))
        except PermissionError:
            raise FeedbackError("denied") from None
        value = {**old, "state": "reviewed" if decision == "approve" else "rejected",
                 "review": {"actor_id": actor, "decision": decision, "reason": reason,
                            "candidate_sha256": candidate_sha256}, "activation": "not_active"}
        tx.put(f"{kind}_proposal", rule_id, value, expected_revision=tx.revision(f"{kind}_proposal", rule_id))
        tx.audit(actor, f"review_{kind}", allowed=True)
        return value
