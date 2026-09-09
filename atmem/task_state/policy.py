"""What AtMem will and will not accept as a change to task state.

This is the decision layer. It takes a current snapshot, a profile, and an
untrusted proposal, and returns exactly one outcome — accepted, rejected,
conflict, or no_change — with stable reason codes. It performs no I/O and
commits nothing, which makes it exhaustively testable and makes the committing
layer's job narrow: apply what policy already approved.

The refusals here are the product. A proposer that invents an item, widens
scope, unlocks a schema, or claims a completion it cannot evidence gets a
reasoned rejection, not a silent partial application.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    GuardSignal,
    GuardType,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskState,
    TaskStateProposal,
)
from atmem.task_state.models import (
    allows_status_transition,
    apply_operations,
    completion_blockers,
    dependencies_satisfied,
    is_progress,
)


# Only these roles may nominate a change at all. AtMem itself commits; the
# policy evaluator owns expiry and nothing else.
PROPOSING_ROLES = frozenset(
    {
        ActorRole.ATBOT_INTELLIGENCE,
        ActorRole.HOST_AGENT,
        ActorRole.OPERATOR,
        ActorRole.ADMINISTRATOR,
        ActorRole.VERIFIER,
    }
)

# The strongest assurance each role may claim for an outcome. A model saying
# an action succeeded is an interpretation; only a registered verifier may
# assert independent verification.
ASSURANCE_CEILING: dict[ActorRole, Assurance] = {
    ActorRole.ATBOT_INTELLIGENCE: Assurance.MODEL_INTERPRETED,
    ActorRole.HOST_AGENT: Assurance.HOST_REPORTED,
    ActorRole.OPERATOR: Assurance.OPERATOR_CONFIRMED,
    ActorRole.ADMINISTRATOR: Assurance.OPERATOR_CONFIRMED,
    ActorRole.VERIFIER: Assurance.INDEPENDENTLY_VERIFIED,
    ActorRole.POLICY_EVALUATOR: Assurance.RULE_EXTRACTED,
    ActorRole.ATMEM_AUTHORITY: Assurance.RULE_EXTRACTED,
}

# Operations only a person with the right permission may request. Skipping
# required work and unlocking structure are not ordinary agent moves.
PRIVILEGED_OPERATIONS = frozenset({OperationKind.LOCK_SCHEMA})

# Operations that change the structure of the task rather than its progress.
SCHEMA_OPERATIONS = frozenset(
    {OperationKind.ADD_ITEM, OperationKind.ADD_CONSTRAINT}
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """The outcome of evaluating one proposal, before anything is written."""

    outcome: StepOutcome
    reason_codes: tuple[str, ...]
    next_state: TaskState | None = None
    is_progress: bool = False
    guards: tuple[GuardSignal, ...] = ()
    effective_assurance: Assurance = Assurance.ASSERTED

    @property
    def accepted(self) -> bool:
        return self.outcome is StepOutcome.ACCEPTED


def evaluate(
    *,
    state: TaskState,
    profile: TaskProfile,
    proposal: TaskStateProposal,
    now_iso: str,
    known_evidence_ids: frozenset[str] | None = None,
    allow_privileged: bool = False,
) -> PolicyDecision:
    """Decide what one proposal does to one task. No I/O, no commit."""
    reasons: list[str] = []

    # --- authority and eligibility ---------------------------------------
    if proposal.scope.to_dict() != state.scope.to_dict():
        return _reject("scope_mismatch")
    if proposal.task_id != state.task_id:
        return _reject("task_not_eligible")
    if proposal.actor_role not in PROPOSING_ROLES:
        return _reject("capability_denied")
    if state.lifecycle.terminal:
        return _reject("task_is_terminal")
    if state.lifecycle is TaskLifecycle.PAUSED:
        return _reject("task_is_paused")

    # --- concurrency -------------------------------------------------------
    if proposal.base_revision != state.revision:
        # Not a rejection: the proposal may be perfectly valid against a state
        # that has since moved. The caller re-reads and decides.
        return PolicyDecision(
            outcome=StepOutcome.CONFLICT,
            reason_codes=("stale_base_revision",),
        )

    # --- assurance honesty --------------------------------------------------
    ceiling = ASSURANCE_CEILING.get(proposal.actor_role, Assurance.ASSERTED)
    if proposal.assurance.rank > ceiling.rank:
        return _reject("assurance_ceiling_exceeded")

    # --- evidence -----------------------------------------------------------
    if known_evidence_ids is not None:
        unknown = [
            ref.reference_id
            for ref in proposal.evidence
            if ref.reference_id not in known_evidence_ids
        ]
        if unknown:
            return _reject("unknown_evidence")

    # --- structural validation, one operation at a time --------------------
    working = state
    progressed = False
    for operation in proposal.operations:
        failure = _validate_operation(
            operation,
            state=working,
            profile=profile,
            proposal=proposal,
            allow_privileged=allow_privileged,
        )
        if failure:
            return _reject(*failure)
        if is_progress(operation, working):
            progressed = True
        # Apply incrementally so later operations see earlier ones, which is
        # how a proposal that adds an item and then advances it stays legal.
        working = apply_operations(
            working, [operation], revision=working.revision,
            updated_at=working.updated_at,
        )

    if not proposal.operations:
        return _reject("empty_delta")

    next_state = apply_operations(
        state,
        proposal.operations,
        revision=state.revision + 1,
        updated_at=now_iso,
        last_progress_at=now_iso if progressed else state.last_progress_at,
    )

    # --- no_change: the honest answer when nothing actually differs --------
    if next_state.semantic_digest() == state.semantic_digest():
        return PolicyDecision(
            outcome=StepOutcome.NO_CHANGE,
            reason_codes=("state_already_matches",),
            effective_assurance=proposal.assurance,
        )

    guards = tuple(_completion_guards(next_state, profile))
    return PolicyDecision(
        outcome=StepOutcome.ACCEPTED,
        reason_codes=("transition_accepted",),
        next_state=next_state,
        is_progress=progressed,
        guards=guards,
        effective_assurance=proposal.assurance,
    )


def evaluate_completion(
    state: TaskState, profile: TaskProfile
) -> tuple[bool, tuple[str, ...], GuardSignal | None]:
    """May this task be completed right now, and if not, what is blocking?"""
    blockers = completion_blockers(state, profile)
    if not blockers:
        return True, (), None
    guard = GuardSignal(
        guard_type=GuardType.COMPLETION_NOT_ALLOWED,
        task_id=state.task_id,
        revision=state.revision,
        message=(
            "Completion is not allowed yet: "
            f"{len(blockers)} requirement(s) are unsatisfied."
        ),
        blocking_item_ids=blockers,
    )
    return False, ("required_items_incomplete",), guard


def _validate_operation(
    operation: TaskOperation,
    *,
    state: TaskState,
    profile: TaskProfile,
    proposal: TaskStateProposal,
    allow_privileged: bool,
) -> tuple[str, ...] | None:
    """Return reason codes when this operation may not be applied."""
    if not profile.allows_operation(operation.kind):
        return ("operation_not_permitted_by_profile",)
    if operation.kind in PRIVILEGED_OPERATIONS and not allow_privileged:
        return ("capability_denied",)

    if operation.kind in SCHEMA_OPERATIONS and state.schema_locked:
        return ("schema_is_locked",)
    if (
        operation.kind in SCHEMA_OPERATIONS
        and profile.allow_schema_extension_phases
        and state.phase not in profile.allow_schema_extension_phases
    ):
        return ("schema_is_locked",)

    if operation.kind is OperationKind.SET_PHASE:
        target = str(operation.phase)
        if target not in profile.phases:
            return ("illegal_phase_transition",)
        if target != state.phase and not profile.allows_phase_transition(
            state.phase, target
        ):
            return ("illegal_phase_transition",)
        if target == profile.terminal_phase:
            blockers = completion_blockers(state, profile)
            if blockers:
                return ("required_items_incomplete",)
        return None

    if operation.kind is OperationKind.ADD_ITEM:
        if state.item(str(operation.item_id)) is not None:
            return ("duplicate_item_id",)
        unknown = set(operation.depends_on or ()) - {
            item.item_id for item in state.items
        }
        if unknown:
            return ("unknown_item",)
        return None

    if operation.kind in {
        OperationKind.SET_ITEM_STATUS,
        OperationKind.SET_ITEM_CONTENT,
        OperationKind.SET_ITEM_BLOCKER,
    }:
        item = state.item(str(operation.item_id))
        if item is None:
            return ("unknown_item",)
        if operation.kind is OperationKind.SET_ITEM_STATUS:
            target = operation.status
            assert target is not None
            if not allows_status_transition(item.status, target):
                return ("illegal_status_transition",)
            if target in {ItemStatus.RUNNING, ItemStatus.COMPLETED} and not (
                dependencies_satisfied(state, item)
            ):
                return ("dependency_unsatisfied",)
            if target is ItemStatus.SKIPPED and not operation.reason:
                return ("reason_required",)
            if target is ItemStatus.BLOCKED and not operation.reason:
                return ("reason_required",)
            claimed = max(
                operation.assurance.rank, proposal.assurance.rank
            )
            if target is ItemStatus.COMPLETED and not (
                proposal.evidence or claimed >= Assurance.HOST_REPORTED.rank
            ):
                # Claiming work is done is exactly where unevidenced optimism
                # does damage, so completion needs either cited evidence or an
                # actor whose assurance class can carry the claim on its own.
                return ("evidence_required",)
            if item.required and target is ItemStatus.SKIPPED and not allow_privileged:
                return ("capability_denied",)
        return None

    if operation.kind is OperationKind.SATISFY_CONSTRAINT:
        if state.constraint(str(operation.constraint_id)) is None:
            return ("unknown_constraint",)
        return None

    if operation.kind is OperationKind.ADD_CONSTRAINT:
        if state.constraint(str(operation.constraint_id)) is not None:
            return ("unknown_constraint",)
        return None

    if operation.kind is OperationKind.MARK_SOURCE_INSPECTED:
        if str(operation.source_id) not in set(state.sources_to_inspect):
            return ("unknown_source",)
        return None

    return None


def _completion_guards(
    state: TaskState, profile: TaskProfile
) -> list[GuardSignal]:
    guards: list[GuardSignal] = []
    unmet = [
        item.item_id
        for item in state.items
        if item.status in {ItemStatus.PENDING, ItemStatus.READY}
        and not dependencies_satisfied(state, item)
    ]
    if unmet:
        guards.append(
            GuardSignal(
                guard_type=GuardType.DEPENDENCY_UNSATISFIED,
                task_id=state.task_id,
                revision=state.revision,
                message=(
                    f"{len(unmet)} item(s) are waiting on unfinished dependencies."
                ),
                blocking_item_ids=tuple(unmet),
            )
        )
    return guards


def _reject(*reason_codes: str) -> PolicyDecision:
    return PolicyDecision(
        outcome=StepOutcome.REJECTED, reason_codes=tuple(reason_codes)
    )
