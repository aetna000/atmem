"""The host-boundary write path: observations, deltas, and lifecycle requests.

Spec 007 Amendment A, FR-044 through FR-046, FR-049, FR-051, FR-054.

Before this existed a host adapter could read governed task state and not
change it, so an agent received a checklist it had no way to tick. This module
is the write half, and it is deliberately narrow.

Four gates run in a fixed order, and the order is the design:

1. **Enablement.** A disabled scope refuses immediately, before identity is
   resolved or content is looked at, so a refusal discloses nothing about
   whether any task exists. Shadow evaluates fully and commits nothing.
2. **Session binding.** Every submission resolves through its own conversation
   and must name the task that conversation is bound to. Scope alone is not
   enough: one authorized scope routinely holds several tasks, so a submission
   naming a sibling would otherwise pass every scope and capability check.
3. **Capability ceiling.** Operator-only actions are refused on capability
   grounds *before* delta content is evaluated, so a malformed privileged
   request and a well-formed one produce the same answer and leak nothing.
4. **Policy.** Only then does the ordinary transition path run, unchanged.

Actor role is derived here and never received. A request carrying one is
rejected at parse time by its contract, not quietly ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    HostSessionIdentity,
    HostTaskLifecycleRequest,
    HostTaskObservationRequest,
    HostTaskProposalRequest,
    OperationKind,
    StepOutcome,
    TaskStateProposal,
    TransitionDecision,
)
from atmem.task_state.binding import SessionBindingService
from atmem.task_state.enablement import ScopeEnablement
from atmem.task_state.governance import capability_for
from atmem.task_state.service import TaskStateError


# Operations a host agent may never request. These are the operator-only
# actions of the Governance Matrix expressed as delta shapes: locking a schema
# and adding constraints change the rules of the task rather than its progress,
# and a party that may propose progress is not thereby allowed to rewrite the
# rules it is judged against.
OPERATOR_ONLY_OPERATIONS = frozenset(
    {OperationKind.LOCK_SCHEMA, OperationKind.ADD_CONSTRAINT}
)


@dataclass(frozen=True, slots=True)
class HostRefusal:
    """A refusal carrying one stable reason code and no task content."""

    reason_code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "atmem-task-unavailable-v1",
            "reason_code": self.reason_code,
            "message": self.message,
        }


class HostBoundary:
    """One gate sequence, shared by all three host-boundary operations."""

    def __init__(self, service: Any, store: Any) -> None:
        self._service = service
        self._store = store
        self._bindings = SessionBindingService(store, service.clock)

    # --- gates -------------------------------------------------------------

    def _enablement(self, scope: AuthorityScope) -> tuple[HostRefusal | None, bool]:
        """Refuse when disabled; report shadow so the caller evaluates without commit.

        Disabled and shadow are different code paths on purpose. Collapsing
        them would either leak task existence from a disabled scope or make
        shadow untestable as a rehearsal for the active path.
        """
        mode = ScopeEnablement(self._store).mode(scope)
        if not mode.enabled:
            return (
                HostRefusal(
                    "task_state_disabled",
                    "Governed task state is disabled for this scope.",
                ),
                False,
            )
        return None, bool(mode.shadow)

    def _bound_task(
        self, scope: AuthorityScope, identity: HostSessionIdentity, task_id: str
    ) -> HostRefusal | None:
        """FR-054. The submitted task id is checked, never trusted.

        Read and write end up on one resolution path, so a host can only write
        to the task it is currently allowed to read.
        """
        resolved = self._bindings.resolve(scope, identity=identity)
        if not resolved.resolution.delivers:
            return HostRefusal(
                resolved.reason_code or "task_context_selection_required",
                "This conversation is not bound to a governed task.",
            )
        if resolved.task_id != task_id:
            # Non-disclosing on purpose: naming tasks at random must not become
            # an existence oracle, so this reads the same whether the named
            # task exists in another session or does not exist at all.
            return HostRefusal(
                "host_task_not_bound_to_session",
                "This conversation is not bound to that task.",
            )
        return None

    def _ceiling(self, operations: tuple[Any, ...]) -> HostRefusal | None:
        """Capability first, content second, so a refusal leaks nothing."""
        capability = capability_for(ActorRole.HOST_AGENT)
        if not capability.propose_delta:
            return HostRefusal(
                "capability_denied", "This actor may not propose task changes."
            )
        forbidden = sorted(
            {
                operation.kind.value
                for operation in operations
                if operation.kind in OPERATOR_ONLY_OPERATIONS
            }
        )
        if forbidden:
            return HostRefusal(
                "capability_denied",
                f"A host agent may not request {', '.join(forbidden)}; "
                "that is an operator action.",
            )
        return None

    # --- operations --------------------------------------------------------

    def observe(
        self, scope: AuthorityScope, request: HostTaskObservationRequest
    ) -> dict[str, Any]:
        """Admit one observed workflow step (FR-049 path (a)).

        The adapter submits what it saw; interpretation happens in the
        authorized companion path and AtMem revalidates the result against the
        current head before commit. With AtBot unavailable this records a
        deterministic `no_change` rather than inventing progress.
        """
        refusal, shadow = self._enablement(scope)
        if refusal:
            return refusal.to_dict()
        refusal = self._bound_task(scope, request.identity, request.task_id)
        if refusal:
            return refusal.to_dict()
        if shadow:
            return self._shadow(request.task_id, "observation evaluated, not committed")
        try:
            decision = self._service.submit_atbot_observation(
                scope, request.task_id, request.observation, evidence=request.evidence
            )
        except TaskStateError as exc:
            return HostRefusal(exc.reason_code, str(exc)).to_dict()
        return decision.to_dict()

    def propose(
        self, scope: AuthorityScope, request: HostTaskProposalRequest
    ) -> dict[str, Any]:
        """Admit one typed delta already in delta form (FR-049 path (b))."""
        refusal, shadow = self._enablement(scope)
        if refusal:
            return refusal.to_dict()
        refusal = self._bound_task(scope, request.identity, request.task_id)
        if refusal:
            return refusal.to_dict()
        refusal = self._ceiling(request.operations)
        if refusal:
            return refusal.to_dict()
        if shadow:
            return self._shadow(request.task_id, "proposal evaluated, not committed")

        proposal = TaskStateProposal(
            proposal_id=f"proposal_host_{request.idempotency_key[:96]}",
            task_id=request.task_id,
            scope=scope,
            base_revision=request.base_revision,
            # Namespaced so a host key and an operator key cannot collide.
            idempotency_key=f"host:{request.adapter}:{request.idempotency_key}",
            actor=request.adapter,
            # Derived, never received. The request contract has no field for it.
            actor_role=ActorRole.HOST_AGENT,
            operations=request.operations,
            evidence=request.evidence,
            interpreter=request.adapter_version or None,
            # A host reporting its own tool outcome is asserting, not verifying.
            assurance=Assurance.ASSERTED,
            reason=request.reason or None,
        )
        try:
            return self._service.submit(
                proposal, step_kind="host_proposal"
            ).to_dict()
        except TaskStateError as exc:
            return HostRefusal(exc.reason_code, str(exc)).to_dict()

    def request_lifecycle(
        self, scope: AuthorityScope, request: HostTaskLifecycleRequest
    ) -> dict[str, Any]:
        """A request, never a command. Existing gates decide it."""
        refusal, shadow = self._enablement(scope)
        if refusal:
            return refusal.to_dict()
        refusal = self._bound_task(scope, request.identity, request.task_id)
        if refusal:
            return refusal.to_dict()
        if shadow:
            return self._shadow(request.task_id, "lifecycle request evaluated, not committed")

        from atmem.task_state.service import TaskCompletionDenied

        try:
            current = self._service.get(scope, request.task_id).state.revision
            if int(request.expected_revision) != current:
                return {
                    "format": "atmem-task-conflict-v1",
                    "task_id": request.task_id,
                    "reason_code": "stale_base_revision",
                    "expected_revision": int(request.expected_revision),
                    "current_revision": current,
                    "message": (
                        f"This task is at revision {current}, not "
                        f"{request.expected_revision}. Re-read it and submit a "
                        "fresh request."
                    ),
                }
            view = getattr(self._service, request.action)(
                scope,
                request.task_id,
                actor=request.adapter,
                actor_role=ActorRole.HOST_AGENT,
                reason=request.reason or request.action,
            )
            return {"format": "atmem-task-lifecycle-result-v1", **view.to_dict()}
        except TaskCompletionDenied as exc:
            return {
                "format": "atmem-task-unavailable-v1",
                "task_id": request.task_id,
                "reason_code": exc.reason_code,
                "message": str(exc),
                "guard": exc.guard.to_dict(),
            }
        except TaskStateError as exc:
            return HostRefusal(exc.reason_code, str(exc)).to_dict()

    def _shadow(self, task_id: str, message: str) -> dict[str, Any]:
        """Evaluated, recorded as a decision, committed nowhere."""
        return {
            "format": "atmem-task-decision-v1",
            "task_id": task_id,
            "outcome": StepOutcome.NO_CHANGE.value,
            "reason_codes": ["task_state_shadow_mode"],
            "resulting_revision": None,
            "message": message,
        }


__all__ = ["HostBoundary", "HostRefusal", "OPERATOR_ONLY_OPERATIONS"]
