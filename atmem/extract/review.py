"""Human review for proposals policy would not admit on its own.

Quarantine is not a failure state; it is the safe default for anything
uncertain, sensitive, ambiguous, or destructive. This module is the single
review service behind both the CLI and the dashboard, so a reviewer sees the
same queue, the same evidence, and the same allowed actions in either surface.

Every decision is recorded with actor, time, reason, and the resulting record
ids. Approving a proposal re-validates it first: a decision made against a
value that has since changed fails closed rather than committing stale intent.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from atmem.core.canonical import sha256_hex
from atmem.extract.models import ProposalAction
from atmem.store.sqlite import utc_now


DECISIONS = ("approve", "edit_and_approve", "reject")

_SENSITIVE_RE = re.compile(
    r"\b(?:diagnos\w+|medication|therapy|hiv|pregnan\w+|salary|income|debt|"
    r"immigration|visa status|criminal|arrest|religio\w+|orientation|"
    r"passport|social security|ssn|credit card|bank account)\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class ReviewPolicy:
    """What must wait for a person, expressed as data rather than code paths."""

    min_confidence: float = 0.6
    quarantine_sensitive: bool = True
    quarantine_destructive: bool = True
    quarantine_ambiguous: bool = True
    quarantine_non_durable: bool = True

    def requires_review(self, proposal: Any) -> tuple[str, ...]:
        """Reason codes forcing review, or an empty tuple to allow admission."""
        reasons: list[str] = []
        if float(proposal.confidence) < self.min_confidence and proposal.action in {
            ProposalAction.ADD,
            ProposalAction.UPDATE,
            ProposalAction.SUPERSEDE,
        }:
            reasons.append("low_confidence")
        if self.quarantine_sensitive and _SENSITIVE_RE.search(proposal.fact or ""):
            reasons.append("sensitive_content")
        if (
            self.quarantine_destructive
            and proposal.action is ProposalAction.SUPERSEDE
            and len(proposal.affected_record_ids) > 1
        ):
            # Replacing several current facts at once is the destructive
            # shape: one wrong proposal would retire a whole slot's history.
            reasons.append("destructive_multi_record_change")
        if self.quarantine_ambiguous and "ambiguous_referent" in proposal.reason_codes:
            reasons.append("ambiguous_referent")
        if self.quarantine_non_durable and proposal.memory_class.value not in {
            "durable_fact"
        }:
            reasons.append("non_durable_class")
        return tuple(dict.fromkeys(reasons))


class ReviewService:
    """The one place a proposal's fate is decided by a person."""

    def __init__(self, memory: Any, *, policy: ReviewPolicy | None = None) -> None:
        self.memory = memory
        self.policy = policy or ReviewPolicy()

    def queue(
        self, subject_id: str | None = None, *, limit: int = 100
    ) -> dict[str, Any]:
        """Everything awaiting a decision, with its evidence and allowed acts."""
        rows = self.memory.list_extraction_proposals(
            subject_id, review_states=("pending_review",), limit=limit
        )
        return {
            "format": "atmem-extraction-review-queue-v1",
            "count": len(rows),
            "allowed_decisions": list(DECISIONS),
            "proposals": [self._view(row) for row in rows],
        }

    def inspect(self, proposal_id: str) -> dict[str, Any]:
        """One proposal with the exact evidence a reviewer needs to judge it."""
        stored = self.memory.store.get_memory_proposal(proposal_id)
        if stored is None:
            raise ValueError(f"unknown proposal: {proposal_id}")
        view = self._view(stored)
        view["reviews"] = self.memory.store.list_memory_reviews(proposal_id)
        return view

    def decide(
        self,
        proposal_id: str,
        decision: str,
        *,
        actor: str,
        reason: str = "",
        edited_fact: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Approve, edit-and-approve, or reject exactly once.

        The store settles the proposal under a pending-only guard, so two
        reviewers racing on the same item produce one decision and one clear
        conflict rather than two commits.
        """
        if decision not in DECISIONS:
            raise ValueError(f"decision must be one of {DECISIONS}")
        if decision == "edit_and_approve" and not (edited_fact or "").strip():
            raise ValueError("edit_and_approve requires the edited fact text")

        stored = self.memory.store.get_memory_proposal(proposal_id)
        if stored is None:
            raise ValueError(f"unknown proposal: {proposal_id}")
        if stored["review_state"] != "pending_review":
            raise ValueError(
                f"proposal {proposal_id} was already decided: {stored['review_state']}"
            )
        return self._settle(
            stored,
            decision,
            actor=actor,
            reason=reason,
            edited_fact=edited_fact,
            session_id=session_id,
        )

    def _settle(
        self,
        stored: dict[str, Any],
        decision: str,
        *,
        actor: str,
        reason: str,
        edited_fact: str | None,
        session_id: str | None,
    ) -> dict[str, Any]:
        from atmem.extract.context import build_resolution_context

        proposal = _rehydrate(stored["proposal"])
        subject_id = stored["subject_id"]
        record_ids: list[str] = []
        superseded_ids: list[str] = []
        lineage_ids: list[str] = []
        reason_codes: list[str] = list(stored.get("reason_codes") or ())
        edited_digest: str | None = None

        with self.memory.store.transaction():
            if decision == "reject":
                state = "rejected"
                reason_codes.append("rejected_by_reviewer")
            else:
                fact = (
                    edited_fact.strip()
                    if decision == "edit_and_approve" and edited_fact
                    else proposal.fact
                )
                if decision == "edit_and_approve":
                    edited_digest = f"sha256:{sha256_hex(str(fact))}"
                context = build_resolution_context(
                    self.memory.store, subject_id, scope=proposal.scope
                )
                drift = _precondition_drift(self.memory.store, subject_id, proposal)
                if drift:
                    # The world moved under the reviewer. Fail closed and keep
                    # the reason so the queue can explain why nothing changed.
                    state = "stale"
                    reason_codes.extend(drift)
                elif proposal.action in {
                    ProposalAction.ADD,
                    ProposalAction.UPDATE,
                    ProposalAction.SUPERSEDE,
                }:
                    state = "committed"
                    reason_codes.append(
                        "approved_by_reviewer"
                        if decision == "approve"
                        else "edited_and_approved_by_reviewer"
                    )
                    (
                        record_ids,
                        superseded_ids,
                        lineage_ids,
                    ) = self.memory._commit_extraction(
                        proposal,
                        context=context,
                        session_id=session_id,
                        turn=None,
                        fact=fact,
                    )
                else:
                    state = "noop"
                    reason_codes.append("approved_without_mutation")

            outcome = {
                **(stored.get("outcome") or {}),
                "state": state,
                "reason_codes": list(dict.fromkeys(reason_codes)),
                "record_ids": record_ids,
                "superseded_record_ids": superseded_ids,
                "lineage_ids": lineage_ids,
                "decided_by": actor,
                "decision": decision,
                "decided_at": utc_now(),
            }
            settled = self.memory.store.settle_memory_proposal(
                stored["proposal_id"], review_state=state, outcome=outcome
            )
            if settled is None:
                raise ValueError(
                    f"proposal {stored['proposal_id']} was decided concurrently"
                )
            event_id = self.memory.store.append_audit_event(
                subject_id=subject_id,
                event_type="memory.proposal_reviewed",
                actor=actor,
                session_id=session_id,
                turn_id=None,
                record_id=(record_ids or [None])[0],
                payload={
                    "proposal_id": stored["proposal_id"],
                    "decision": decision,
                    "review_state": state,
                    "reason": reason,
                    "reason_codes": outcome["reason_codes"],
                    "edited_fact_sha256": edited_digest,
                    "record_ids": record_ids,
                    "superseded_record_ids": superseded_ids,
                    "lineage_ids": lineage_ids,
                },
            )
            self.memory.store.insert_memory_review(
                proposal_id=stored["proposal_id"],
                subject_id=subject_id,
                decision=(
                    "rejected"
                    if decision == "reject"
                    else "edited_approved"
                    if decision == "edit_and_approve"
                    else "approved"
                ),
                actor=actor,
                reason=reason,
                edited_fact_sha256=edited_digest,
                record_ids=record_ids,
                audit_event_id=event_id,
            )
        return self.inspect(stored["proposal_id"])

    def _view(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = row.get("proposal") or {}
        outcome = row.get("outcome") or {}
        # A settled proposal's reasons live on its outcome, which carries the
        # reviewer's codes as well as the ones submission recorded.
        reason_codes = outcome.get("reason_codes") or row.get("reason_codes") or ()
        return {
            "proposal_id": row["proposal_id"],
            "subject_id": row["subject_id"],
            "agent_id": row.get("agent_id"),
            "workspace_id": row.get("workspace_id"),
            "action": row["action"],
            "memory_class": row["memory_class"],
            "confidence": row["confidence"],
            "fact": payload.get("fact"),
            "fact_key": row.get("fact_key"),
            "review_state": row["review_state"],
            "reason_codes": list(reason_codes),
            "evidence": list(payload.get("evidence") or ()),
            "affected_record_ids": list(payload.get("affected_record_ids") or ()),
            "preconditions": list(payload.get("preconditions") or ()),
            "allowed_decisions": (
                list(DECISIONS) if row["review_state"] == "pending_review" else []
            ),
            "record_ids": list(outcome.get("record_ids") or ()),
            "superseded_record_ids": list(
                outcome.get("superseded_record_ids") or ()
            ),
            "decision": outcome.get("decision"),
            "decided_by": outcome.get("decided_by"),
            "created_at": row.get("created_at"),
            "decided_at": row.get("decided_at"),
        }


def _rehydrate(payload: dict[str, Any]) -> Any:
    from atmem.contracts import AuthorityScope
    from atmem.extract.models import (
        ExtractionProposal,
        MemoryClass,
        ProposalEvidence,
        ProposalPrecondition,
    )

    scope = payload["scope"]
    return ExtractionProposal(
        proposal_id=payload["proposal_id"],
        idempotency_key=payload["idempotency_key"],
        scope=AuthorityScope(
            subject_id=scope["subject_id"],
            agent_id=scope["agent_id"],
            workspace_id=scope["workspace_id"],
        ),
        action=ProposalAction(payload["action"]),
        memory_class=MemoryClass(payload["memory_class"]),
        confidence=float(payload["confidence"]),
        reason_codes=tuple(payload.get("reason_codes") or ()),
        evidence=tuple(
            ProposalEvidence(**item) for item in payload.get("evidence") or ()
        ),
        fact=payload.get("fact"),
        fact_key=payload.get("fact_key"),
        affected_record_ids=tuple(payload.get("affected_record_ids") or ()),
        preconditions=tuple(
            ProposalPrecondition(**item) for item in payload.get("preconditions") or ()
        ),
        review_required=bool(payload.get("review_required")),
    )


def _precondition_drift(store: Any, subject_id: str, proposal: Any) -> tuple[str, ...]:
    """Reason codes for state that moved between submission and decision.

    Evidence digests were re-derived at submission, when the raw source text
    was still in hand; AtMem does not retain that text on the proposal row.
    What can still change while a proposal waits is the memory it targets, so
    review re-checks exactly that before any commit.
    """
    reasons: list[str] = []
    current = store.record_preconditions(
        subject_id,
        list(
            dict.fromkeys(
                [item.record_id for item in proposal.preconditions]
                + list(proposal.affected_record_ids)
            )
        ),
    )
    for precondition in proposal.preconditions:
        state = current.get(precondition.record_id)
        if state is None:
            reasons.append("precondition_record_not_eligible")
            continue
        if state["generation"] != precondition.generation:
            reasons.append("stale_proposal_generation")
        if state["status"] != precondition.status:
            reasons.append("precondition_status_changed")
        if state["content_sha256"] != precondition.content_sha256:
            reasons.append("precondition_content_changed")
    for record_id in proposal.affected_record_ids:
        state = current.get(record_id)
        if state is None or state["status"] != "active":
            reasons.append("affected_record_not_eligible")
    return tuple(dict.fromkeys(reasons))
