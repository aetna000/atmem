"""Authenticated application boundary shared by feedback, RAG, CLI and MCP.

Owner configuration is deliberately separate from model-facing operations.
Credentials are re-read on every call; agent capabilities are encrypted records
inside the same authoritative evidence vault, not model-provided role flags.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import time
from typing import Callable

from atmem.contracts.feedback import FeedbackScope, OutcomeRecord, identifier
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, FeedbackStore, snapshot
from atmem.feedback.observability import FeedbackObservability, measured


OPERATIONS = frozenset({"read", "report", "propose", "search", "inspect", "execute", "verify"})


@dataclass(frozen=True)
class FeedbackSession:
    """Application-bound scope; never reconstructed from MCP tool arguments."""

    scope: FeedbackScope
    credential: str = field(repr=False, compare=False)


class FeedbackService:
    def __init__(self, evidence, *, clock: Callable[[], float] = time.time, memory=None, observability=None):
        self.evidence = evidence
        self.store = FeedbackStore(evidence)
        self.clock = clock
        self.memory = memory
        self.observability = observability if observability is not None else FeedbackObservability()

    def _principal(self, credential):
        if type(credential) is not str or not 16 <= len(credential) <= 512:
            raise FeedbackError("denied")
        try:
            principal = self.evidence.authenticate(credential)
        except (ValueError, OSError, RuntimeError):
            raise FeedbackError("denied") from None
        if principal is None:
            raise FeedbackError("denied")
        return principal

    def _scope(self, principal, agent_id: str, workspace_id: str) -> FeedbackScope:
        scope = FeedbackScope(principal.scope.tenant_id, principal.scope.subject_id,
                              agent_id, workspace_id)
        try:
            principal.authorize(EvidenceOperation.VIEW, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        return scope

    def bind(self, credential: str, *, agent_id: str, workspace_id: str) -> FeedbackSession:
        principal = self._principal(credential)
        session = FeedbackSession(self._scope(principal, agent_id, workspace_id), credential)
        # Any enabled operation is sufficient to establish the application binding.
        with self._authorized(session, None):
            pass
        return session

    @contextmanager
    def owner_transaction(self, credential, scope, *, operation=EvidenceOperation.GRANT):
        """Check privileged authority before decryption and again under lock."""
        principal = self._principal(credential)
        try:
            principal.authorize(operation, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        with self.store.transaction(scope) as tx:
            principal = self._principal(credential)
            try:
                principal.authorize(operation, scope.evidence_scope())
            except PermissionError:
                raise FeedbackError("denied") from None
            yield tx, principal

    def grant_agent(self, owner_credential: str, scope: FeedbackScope, *,
                    principal_id: str, operations: tuple[str, ...], expires_at: int) -> dict:
        """Trusted owner API, not a model tool. Changes take effect on the next call."""
        principal = self._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        identifier(principal_id)
        if (type(operations) is not tuple or not operations or len(set(operations)) != len(operations)
                or any(type(op) is not str or op not in OPERATIONS for op in operations)
                or type(expires_at) is not int or not self.clock() < expires_at <= self.clock() + 31_536_000):
            raise ValueError("bounded explicit operations and grant expiry required")
        with self.owner_transaction(owner_credential, scope) as (tx, principal):
            value = {"principal_id": principal_id, "operations": sorted(operations),
                     "expires_at": expires_at, "active": True}
            receipt = tx.put("agent_grant", principal_id, value,
                             expected_revision=tx.revision("agent_grant", principal_id))
            tx.audit(principal.principal_id, "grant_agent", allowed=True)
            return receipt

    def revoke_agent(self, owner_credential: str, scope: FeedbackScope, *, principal_id: str) -> dict:
        principal = self._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        with self.owner_transaction(owner_credential, scope) as (tx, principal):
            grant = tx.get("agent_grant", principal_id)
            if grant is None:
                raise FeedbackError("denied")
            grant["active"] = False
            result = tx.put("agent_grant", principal_id, grant,
                            expected_revision=tx.revision("agent_grant", principal_id))
            tx.audit(principal.principal_id, "revoke_agent", allowed=True)
            return result

    @contextmanager
    def _authorized(self, session: FeedbackSession, operation: str | None):
        if type(session) is not FeedbackSession or type(session.scope) is not FeedbackScope:
            raise FeedbackError("denied")
        if operation is not None and operation not in OPERATIONS:
            raise FeedbackError("denied")
        principal = self._principal(session.credential)
        scope = self._scope(principal, session.scope.agent_id, session.scope.workspace_id)
        if scope != session.scope:
            raise FeedbackError("denied")
        # The authenticated evidence scope is checked before the scoped key is used.
        denied = False
        with self.store.transaction(scope) as tx:
            principal = self._principal(session.credential)
            if self._scope(principal, scope.agent_id, scope.workspace_id) != scope:
                raise FeedbackError("denied")
            grant = tx.get("agent_grant", principal.principal_id)
            if (not grant or not grant["active"] or grant["expires_at"] <= self.clock()
                    or not grant["operations"] or operation is not None and operation not in grant["operations"]):
                # Denied inspection creates only an access record, not returned data.
                tx.audit(principal.principal_id, operation or "bind", allowed=False)
                denied = True
            else:
                yield tx, principal
                tx.audit(principal.principal_id, operation or "bind", allowed=True)
        if denied:
            raise FeedbackError("denied")

    def capabilities(self, session: FeedbackSession) -> dict:
        with self._authorized(session, None) as (tx, principal):
            grant = tx.get("agent_grant", principal.principal_id)
            return {"format": "atmem-feedback-capabilities-v1", "scope": session.scope.to_dict(),
                    "operations": grant["operations"], "expires_at": grant["expires_at"],
                    "external_host_tools": "advisory", "rule_activation": False}

    def authorize_review(self, session: FeedbackSession, stored: dict, authorization) -> str:
        """Verify the existing core-issued review identity, not a caller's actor label."""
        with self._authorized(session, "propose") as (_, principal):
            if self.memory is None or getattr(authorization, "principal_id", None) != principal.principal_id:
                raise FeedbackError("denied")
            expected = session.scope.authority_scope().to_dict()
            if any(stored.get(k) != expected[k] for k in ("subject_id", "agent_id", "workspace_id")):
                raise FeedbackError("denied")
            try:
                return self.memory.verify_review_authorization(authorization, stored,
                                                              required_scopes=("procedure:review",))
            except PermissionError:
                raise FeedbackError("denied") from None

    @measured("context.retain")
    def retain_context(self, session, *, confirmation_id: str) -> dict:
        """Copy an actual core exposure and its exact prepared bytes into evidence.

        A caller's delivery assertion or receipt-shaped dictionary is not accepted.
        The core receipt establishes host-confirmed exposure, not model use.
        """
        identifier(confirmation_id)
        with self._authorized(session, "report") as (tx, principal):
            if self.memory is None:
                raise FeedbackError("missing_evidence")
            exposure = self.memory.store.get_protocol_exposure(confirmation_id)
            if exposure is None:
                raise FeedbackError("missing_evidence")
            receipt = exposure["receipt"]
            expected_scope = {k: getattr(session.scope, k) for k in ("subject_id", "agent_id", "workspace_id")}
            if receipt.get("scope") != expected_scope:
                raise FeedbackError("denied")
            prepared = self.memory.store.get_protocol_preparation(receipt["preparation_id"])
            if prepared is None:
                raise FeedbackError("missing_evidence")
            package = prepared["value"]
            event = self.memory.store.get_audit_event(session.scope.subject_id, receipt["audit_event_id"])
            if not event or event.get("event_type") != "memory.context_injected":
                raise FeedbackError("missing_evidence")
            from hashlib import sha256
            text = package.get("context")
            if (type(text) is not str or "sha256:" + sha256(text.encode()).hexdigest() != receipt["context_sha256"]
                    or package.get("scope") != receipt["scope"]):
                raise FeedbackError("missing_evidence")
            value = {"format": "atmem-feedback-context-evidence-v1", "receipt": receipt,
                     "package": package, "confirmation_id": confirmation_id,
                     "assurance": "host_confirmed_exposure", "model_use": "unknown",
                     "actor_id": principal.principal_id, "run_id": event["payload"]["host_run_id"]}
            return tx.once("retain_context", confirmation_id, {"receipt": receipt},
                           lambda: self._put_context(tx, receipt["receipt_id"], value))

    @staticmethod
    def _put_context(tx, key, value):
        tx.put("context_evidence", key, value, expected_revision=0)
        return value

    @measured("outcome.report")
    def report_outcome(self, session, outcome: OutcomeRecord, *, idempotency_key: str) -> dict:
        outcome = OutcomeRecord.from_dict(outcome.to_dict())
        identifier(idempotency_key)
        if outcome.scope != session.scope:
            raise FeedbackError("denied")
        with self._authorized(session, "report") as (tx, principal):
            payload = {"outcome": outcome.to_dict(), "actor_id": principal.principal_id}
            def publish():
                if outcome.context_receipt_id is not None:
                    context = tx.get("context_evidence", outcome.context_receipt_id)
                    if context is None or context["run_id"] != outcome.run_id:
                        raise FeedbackError("missing_evidence")
                old = tx.get("outcome", outcome.outcome_id)
                if old:
                    previous = OutcomeRecord.from_dict(old["outcome"])
                    if (outcome.revision != previous.revision + 1 or outcome.predecessor_id != previous.outcome_id
                            or outcome.run_id != previous.run_id or outcome.turn_id != previous.turn_id
                            or outcome.required != previous.required
                            or previous.context_receipt_id is not None and outcome.context_receipt_id != previous.context_receipt_id
                            or previous.delivery == "delivered" and outcome.delivery != "delivered"):
                        raise FeedbackError("stale_revision")
                    prior_calls = {v.invocation_id: v for v in previous.observations}
                    new_calls = {v.invocation_id: v for v in outcome.observations}
                    if any(new_calls.get(k) != v for k, v in prior_calls.items()):
                        raise FeedbackError("immutable_observation")
                elif outcome.revision != 1 or outcome.predecessor_id is not None:
                    raise FeedbackError("stale_revision")
                value = {"outcome": outcome.to_dict(), "outcome_sha256": outcome.content_digest,
                         "actor_id": principal.principal_id, "assurance": "host_report",
                         "verified_success": False}
                tx.put("outcome", outcome.outcome_id, value, expected_revision=outcome.revision-1)
                tx.put("outcome_revision", outcome.content_digest, value, expected_revision=0)
                return value
            return tx.once("report_outcome", idempotency_key, payload, publish)

    def outcome(self, session, outcome_id: str, *, revision_sha256: str | None = None) -> dict:
        identifier(outcome_id)
        with self._authorized(session, "read") as (tx, _):
            value = tx.get("outcome_revision", revision_sha256) if revision_sha256 else tx.get("outcome", outcome_id)
            if value is None or value["outcome"]["outcome_id"] != outcome_id:
                raise FeedbackError("denied")
            return value

    def schedule(self, owner_credential, scope, *, schedule_id: str, tasks: tuple[dict, ...]) -> dict:
        """Owner freezes eligible tasks before observations; no execution implied."""
        from atmem.feedback.metrics import summarize
        principal = self._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        identifier(schedule_id)
        if type(tasks) is not tuple or not 0 < len(tasks) <= 128:
            raise ValueError("bounded frozen schedule required")
        tasks = snapshot(list(tasks))
        summarize(scope, tasks, [])
        with self.owner_transaction(owner_credential, scope) as (tx, principal):
            value = {"schedule_id": schedule_id, "tasks": tasks, "actor_id": principal.principal_id}
            old = tx.get("schedule", schedule_id)
            if old is not None:
                if old != value:
                    raise FeedbackError("conflicting_retry")
                return old
            if any(tx.get("outcome", item["outcome_id"]) is not None for item in tasks):
                raise FeedbackError("schedule_after_observation")
            tx.put("schedule", schedule_id, value, expected_revision=0)
            tx.audit(principal.principal_id, "schedule", allowed=True)
            return value

    def quality(self, session, *, schedule_id: str) -> dict:
        from atmem.feedback.metrics import summarize
        with self._authorized(session, "read") as (tx, _):
            schedule = tx.get("schedule", identifier(schedule_id))
            if schedule is None:
                raise FeedbackError("denied")
            receipts = list(tx.iter_kind("verification"))
            records = []
            assessments = []
            for task in schedule["tasks"]:
                row = tx.get("outcome", task["outcome_id"])
                if row is not None:
                    outcome = OutcomeRecord.from_dict(row["outcome"])
                    records.append((outcome, receipts))
                    for receipt in receipts:
                        if (receipt["outcome_sha256"] != outcome.content_digest or receipt["assurance"] != "independent_readback"
                                or receipt.get("binding", "state_only") != "effect_receipt"):
                            continue
                        evidence = tx.get("readback_evidence", receipt["evidence_id"])
                        if evidence:
                            assessments.extend({"outcome_id": outcome.outcome_id, **item}
                                               for item in evidence.get("assessments", []))
            report = summarize(session.scope, schedule["tasks"], records, assessments=assessments)
            run_ids = {outcome.run_id for outcome, _ in records}
            usage = [row for row in tx.iter_kind("reported_usage") if row["run_id"] in run_ids]
            totals, subtotals, unknown, overflow = {}, {}, {}, {}
            for key in ("usd_micros", "input_tokens", "output_tokens", "model_calls"):
                known = [row[key] for row in usage if row[key] is not None]
                subtotal = sum(known)
                unknown[key] = len(usage)-len(known)
                overflow[key] = subtotal > 2**53
                subtotals[key] = subtotal if known and not overflow[key] else None
                totals[key] = subtotal if usage and not unknown[key] and not overflow[key] else None
            report["usage"] = {"assurance":"host_report", "status":"partial" if usage else "not_captured",
                               "receipt_count":len(usage), "complete_billing_verified":False,
                               **totals, "reported_subtotals":subtotals, "unknown_receipts":unknown, "overflow":overflow}
            return report

    def operational_metrics(self, session):
        with self._authorized(session, "read"):
            return self.observability.snapshot(session.scope)

    def record_usage(self, owner_credential, scope, *, receipt_id, run_id, usd_micros=None, input_tokens=None, output_tokens=None, model_calls=None):
        """Retain application-reported provider usage, never fabricate billed cost.

        This owner-only SDK records an already observed receipt. It invokes no
        model and cannot approve a budget, qualify a candidate or verify billing.
        A provider receipt may not be reassigned to another run on retry.
        """
        identifier(receipt_id)
        identifier(run_id)
        counts = {"usd_micros":usd_micros, "input_tokens":input_tokens,
                  "output_tokens":output_tokens, "model_calls":model_calls}
        if any(v is not None and (type(v) is not int or not 0 <= v <= 2**53) for v in counts.values()):
            raise ValueError("bounded nonnegative usage counts or explicit unknown required")
        with self.owner_transaction(owner_credential, scope) as (tx, principal):
            value = {"receipt_id":receipt_id, "run_id":run_id, **counts, "assurance":"host_report",
                     "actor_id":principal.principal_id}
            old = tx.get("reported_usage", receipt_id)
            if old is not None:
                if old != value:
                    raise FeedbackError("conflicting_retry")
                return old
            tx.put("reported_usage", receipt_id, value, expected_revision=0)
            tx.audit(principal.principal_id, "record_usage", allowed=True)
            return value
