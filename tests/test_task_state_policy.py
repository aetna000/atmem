"""Transition policy: what AtMem accepts, refuses, and why.

Policy performs no I/O, so this suite can be exhaustive about the edges that
actually protect a user: illegal transitions, unmet dependencies, unevidenced
completion claims, assurance overclaims, schema locks, and the honest
`no_change` answer.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    EvidenceRef,
    GuardType,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskConstraint,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskState,
    TaskStateProposal,
)
from atmem.task_state import GENERAL_V1
from atmem.task_state.models import LEGAL_STATUS_TRANSITIONS, allows_status_transition
from atmem.task_state.policy import (
    ASSURANCE_CEILING,
    PROPOSING_ROLES,
    evaluate,
    evaluate_completion,
)


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
NOW = "2026-09-05T12:00:00+00:00"
EVIDENCE = (EvidenceRef(kind="tool_call", reference_id="call-1"),)


def state(**overrides) -> TaskState:
    base = dict(
        task_id="task-1",
        scope=SCOPE,
        revision=1,
        lifecycle=TaskLifecycle.OPEN,
        phase="plan",
        goal="Ship the migration",
        profile_id="general",
        profile_version="general-v1",
        items=(
            TaskItem(item_id="item-1", kind="step", title="First"),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        ),
        created_at="2026-09-05T10:00:00+00:00",
        updated_at="2026-09-05T10:00:00+00:00",
        last_progress_at="2026-09-05T10:00:00+00:00",
    )
    base.update(overrides)
    return TaskState(**base)


def proposal(*operations, **overrides) -> TaskStateProposal:
    base = dict(
        proposal_id="proposal-1",
        task_id="task-1",
        scope=SCOPE,
        base_revision=1,
        idempotency_key="delta-1",
        actor="agent",
        actor_role=ActorRole.HOST_AGENT,
        assurance=Assurance.HOST_REPORTED,
        evidence=EVIDENCE,
    )
    base.update(overrides)
    return TaskStateProposal(operations=tuple(operations), **base)


def decide(*operations, current=None, profile=GENERAL_V1, **overrides):
    return evaluate(
        state=current or state(),
        profile=profile,
        proposal=proposal(*operations, **overrides),
        now_iso=NOW,
    )


# --- authority and scope ----------------------------------------------------


def test_a_proposal_from_another_scope_is_rejected() -> None:
    other = AuthorityScope("subject-2", "agent-1", "workspace-1")
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"), scope=other
    )

    assert result.outcome is StepOutcome.REJECTED
    assert result.reason_codes == ("scope_mismatch",)
    assert result.next_state is None


def test_a_proposal_naming_another_task_is_rejected() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        task_id="task-2",
    )
    assert result.reason_codes == ("task_not_eligible",)


@pytest.mark.parametrize(
    "role",
    [
        ActorRole.AUDITOR,
        ActorRole.DELEGATED_PROVIDER,
        ActorRole.ATMEM_AUTHORITY,
        ActorRole.POLICY_EVALUATOR,
    ],
)
def test_roles_outside_the_proposing_set_cannot_propose(role: ActorRole) -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        actor_role=role,
        assurance=Assurance.ASSERTED,
    )
    assert result.reason_codes == ("capability_denied",)
    assert role not in PROPOSING_ROLES


def test_a_delegated_context_provider_has_no_task_access() -> None:
    """The Governance Matrix gives it no task capability at all."""
    assert ActorRole.DELEGATED_PROVIDER not in PROPOSING_ROLES
    assert ActorRole.DELEGATED_PROVIDER not in ASSURANCE_CEILING


# --- lifecycle --------------------------------------------------------------


@pytest.mark.parametrize(
    "lifecycle",
    [TaskLifecycle.COMPLETED, TaskLifecycle.CANCELLED, TaskLifecycle.EXPIRED],
)
def test_a_terminal_task_cannot_be_mutated(lifecycle: TaskLifecycle) -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        current=state(lifecycle=lifecycle),
    )
    assert result.reason_codes == ("task_is_terminal",)
    assert result.next_state is None


def test_a_paused_task_does_not_accept_ordinary_transitions() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        current=state(lifecycle=TaskLifecycle.PAUSED),
    )
    assert result.reason_codes == ("task_is_paused",)


# --- concurrency ------------------------------------------------------------


def test_a_stale_base_revision_is_a_conflict_not_a_rejection() -> None:
    """The proposal may be fine; the world moved. That is a different answer."""
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        current=state(revision=5),
    )

    assert result.outcome is StepOutcome.CONFLICT
    assert result.reason_codes == ("stale_base_revision",)
    assert result.next_state is None


def test_a_proposal_from_the_future_is_also_a_conflict() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        base_revision=9,
    )
    assert result.outcome is StepOutcome.CONFLICT


# --- assurance honesty ------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "ceiling"),
    [
        (ActorRole.ATBOT_INTELLIGENCE, Assurance.MODEL_INTERPRETED),
        (ActorRole.HOST_AGENT, Assurance.HOST_REPORTED),
        (ActorRole.OPERATOR, Assurance.OPERATOR_CONFIRMED),
        (ActorRole.VERIFIER, Assurance.INDEPENDENTLY_VERIFIED),
    ],
)
def test_each_role_has_an_assurance_ceiling(role, ceiling) -> None:
    assert ASSURANCE_CEILING[role] is ceiling
    ok = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        actor_role=role, assurance=ceiling,
    )
    assert ok.outcome is StepOutcome.ACCEPTED


def test_a_model_cannot_claim_independent_verification() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        actor_role=ActorRole.ATBOT_INTELLIGENCE,
        assurance=Assurance.INDEPENDENTLY_VERIFIED,
    )
    assert result.reason_codes == ("assurance_ceiling_exceeded",)


def test_a_host_tool_result_cannot_claim_more_than_host_reported() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
        actor_role=ActorRole.HOST_AGENT,
        assurance=Assurance.INDEPENDENTLY_VERIFIED,
    )
    assert result.reason_codes == ("assurance_ceiling_exceeded",)


# --- evidence ---------------------------------------------------------------


def test_evidence_naming_something_atmem_does_not_hold_is_rejected() -> None:
    result = evaluate(
        state=state(),
        profile=GENERAL_V1,
        proposal=proposal(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            evidence=(EvidenceRef(kind="tool_call", reference_id="invented"),),
        ),
        now_iso=NOW,
        known_evidence_ids=frozenset({"call-1"}),
    )
    assert result.reason_codes == ("unknown_evidence",)


def test_completing_work_without_any_evidence_is_refused() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.COMPLETED,
        ),
        actor_role=ActorRole.ATBOT_INTELLIGENCE,
        assurance=Assurance.MODEL_INTERPRETED,
        evidence=(),
    )
    assert result.reason_codes == ("evidence_required",)


def test_a_model_completion_with_cited_evidence_is_accepted() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.COMPLETED,
        ),
        actor_role=ActorRole.ATBOT_INTELLIGENCE,
        assurance=Assurance.MODEL_INTERPRETED,
    )
    assert result.outcome is StepOutcome.ACCEPTED
    assert result.is_progress is True


# --- item status transitions ------------------------------------------------


def test_settled_items_do_not_silently_reopen() -> None:
    assert LEGAL_STATUS_TRANSITIONS[ItemStatus.COMPLETED] == frozenset()
    assert LEGAL_STATUS_TRANSITIONS[ItemStatus.SKIPPED] == frozenset()
    for target in ItemStatus:
        if target is ItemStatus.COMPLETED:
            continue
        assert not allows_status_transition(ItemStatus.COMPLETED, target), target


def test_reopening_completed_work_is_an_illegal_transition() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First",
                     status=ItemStatus.COMPLETED),
        )
    )
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.READY,
        ),
        current=current,
    )
    assert result.reason_codes == ("illegal_status_transition",)


def test_work_can_be_completed_directly_from_pending() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.COMPLETED,
        )
    )
    assert result.outcome is StepOutcome.ACCEPTED


def test_an_item_whose_dependency_is_unfinished_cannot_complete() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
            status=ItemStatus.COMPLETED,
        )
    )
    assert result.reason_codes == ("dependency_unsatisfied",)


def test_a_dependency_can_be_satisfied_and_used_in_one_proposal() -> None:
    """Operations inside a delta see each other, in order."""
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.COMPLETED,
        ),
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
            status=ItemStatus.COMPLETED,
        ),
    )
    assert result.outcome is StepOutcome.ACCEPTED
    assert all(item.status.settled for item in result.next_state.items)


def test_blocking_and_skipping_require_a_reason() -> None:
    for status in (ItemStatus.BLOCKED, ItemStatus.SKIPPED):
        result = decide(
            TaskOperation(
                kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                status=status,
            )
        )
        assert result.reason_codes == ("reason_required",), status


def test_a_blocked_item_records_the_reason_it_was_given() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.BLOCKED, reason="Waiting on approval",
        )
    )
    assert result.outcome is StepOutcome.ACCEPTED
    assert result.next_state.item("item-1").blocker_reason == "Waiting on approval"


def test_skipping_required_work_needs_permission() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
        )
    )
    denied = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.SKIPPED, reason="Not needed",
        ),
        current=current,
    )
    assert denied.reason_codes == ("capability_denied",)

    allowed = evaluate(
        state=current, profile=GENERAL_V1,
        proposal=proposal(
            TaskOperation(
                kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                status=ItemStatus.SKIPPED, reason="Not needed",
            ),
            actor_role=ActorRole.OPERATOR, assurance=Assurance.OPERATOR_CONFIRMED,
        ),
        now_iso=NOW, allow_privileged=True,
    )
    assert allowed.outcome is StepOutcome.ACCEPTED


def test_an_operation_naming_an_unknown_item_is_rejected() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="invented",
            status=ItemStatus.COMPLETED,
        )
    )
    assert result.reason_codes == ("unknown_item",)


def test_adding_an_item_that_already_exists_is_rejected() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.ADD_ITEM, item_id="item-1", kind_label="step",
            text="Duplicate",
        )
    )
    assert result.reason_codes == ("duplicate_item_id",)


def test_a_new_item_cannot_depend_on_something_that_does_not_exist() -> None:
    result = decide(
        TaskOperation(
            kind=OperationKind.ADD_ITEM, item_id="item-3", kind_label="step",
            text="Third", depends_on=("invented",),
        )
    )
    assert result.reason_codes == ("unknown_item",)


# --- phases -----------------------------------------------------------------


def test_a_phase_outside_the_profile_is_rejected() -> None:
    result = decide(TaskOperation(kind=OperationKind.SET_PHASE, phase="teatime"))
    assert result.reason_codes == ("illegal_phase_transition",)


def test_a_phase_jump_the_profile_does_not_allow_is_rejected() -> None:
    result = decide(TaskOperation(kind=OperationKind.SET_PHASE, phase="verify"))
    assert result.reason_codes == ("illegal_phase_transition",)


def test_an_allowed_phase_transition_is_accepted_and_counts_as_progress() -> None:
    result = decide(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))

    assert result.outcome is StepOutcome.ACCEPTED
    assert result.next_state.phase == "collect"
    assert result.is_progress is True
    assert result.next_state.last_progress_at == NOW


def test_reaching_the_terminal_phase_requires_the_work_to_be_done() -> None:
    current = state(
        phase="verify",
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
        ),
    )
    blocked = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="complete"), current=current
    )
    assert blocked.reason_codes == ("required_items_incomplete",)

    done = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="complete"),
        current=replace(
            current,
            items=(
                TaskItem(item_id="item-1", kind="step", title="First",
                         required=True, status=ItemStatus.COMPLETED),
            ),
        ),
    )
    assert done.outcome is StepOutcome.ACCEPTED


# --- schema locking ---------------------------------------------------------


def test_a_locked_schema_refuses_structural_changes() -> None:
    current = state(schema_locked=True)
    for operation in (
        TaskOperation(kind=OperationKind.ADD_ITEM, item_id="item-9",
                      kind_label="step", text="New"),
        TaskOperation(kind=OperationKind.ADD_CONSTRAINT, constraint_id="c-9",
                      text="New rule"),
    ):
        result = decide(operation, current=current)
        assert result.reason_codes == ("schema_is_locked",), operation.kind


def test_structure_may_only_be_extended_in_profile_permitted_phases() -> None:
    """`general-v1` allows extension while planning and collecting, not later."""
    assert GENERAL_V1.allow_schema_extension_phases == ("plan", "collect")

    allowed = decide(
        TaskOperation(kind=OperationKind.ADD_ITEM, item_id="item-3",
                      kind_label="step", text="Third"),
        current=state(phase="collect"),
    )
    assert allowed.outcome is StepOutcome.ACCEPTED

    refused = decide(
        TaskOperation(kind=OperationKind.ADD_ITEM, item_id="item-3",
                      kind_label="step", text="Third"),
        current=state(phase="execute"),
    )
    assert refused.reason_codes == ("schema_is_locked",)


def test_locking_the_schema_is_a_privileged_operation() -> None:
    denied = decide(TaskOperation(kind=OperationKind.LOCK_SCHEMA))
    assert denied.reason_codes == ("capability_denied",)

    allowed = evaluate(
        state=state(), profile=GENERAL_V1,
        proposal=proposal(
            TaskOperation(kind=OperationKind.LOCK_SCHEMA),
            actor_role=ActorRole.ADMINISTRATOR,
            assurance=Assurance.OPERATOR_CONFIRMED,
        ),
        now_iso=NOW, allow_privileged=True,
    )
    assert allowed.outcome is StepOutcome.ACCEPTED
    assert allowed.next_state.schema_locked is True


def test_a_profile_may_forbid_an_operation_entirely() -> None:
    narrow = replace(
        GENERAL_V1,
        permitted_operations=(OperationKind.SET_ITEM_STATUS,),
    )
    result = decide(
        TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"), profile=narrow
    )
    assert result.reason_codes == ("operation_not_permitted_by_profile",)


# --- constraints and sources ------------------------------------------------


def test_satisfying_an_unknown_constraint_is_rejected() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.SATISFY_CONSTRAINT, constraint_id="c-9")
    )
    assert result.reason_codes == ("unknown_constraint",)


def test_satisfying_a_known_constraint_is_progress() -> None:
    current = state(
        constraints=(TaskConstraint(constraint_id="c-1", text="Stay under budget"),)
    )
    result = decide(
        TaskOperation(kind=OperationKind.SATISFY_CONSTRAINT, constraint_id="c-1"),
        current=current,
    )
    assert result.outcome is StepOutcome.ACCEPTED
    assert result.next_state.constraint("c-1").satisfied is True
    assert result.is_progress is True


def test_marking_an_unlisted_source_inspected_is_rejected() -> None:
    result = decide(
        TaskOperation(kind=OperationKind.MARK_SOURCE_INSPECTED, source_id="unknown")
    )
    assert result.reason_codes == ("unknown_source",)


def test_marking_a_listed_source_inspected_is_accepted() -> None:
    current = state(sources_to_inspect=("runbook",))
    result = decide(
        TaskOperation(kind=OperationKind.MARK_SOURCE_INSPECTED, source_id="runbook"),
        current=current,
    )
    assert result.outcome is StepOutcome.ACCEPTED
    assert result.next_state.completed_sources == ("runbook",)


# --- no_change --------------------------------------------------------------


def test_setting_a_value_to_what_it_already_is_reports_no_change() -> None:
    result = decide(TaskOperation(kind=OperationKind.SET_PHASE, phase="plan"))

    assert result.outcome is StepOutcome.NO_CHANGE
    assert result.reason_codes == ("state_already_matches",)
    assert result.next_state is None, "no_change must not write a new revision"


def test_no_change_is_reported_even_for_item_status(tmp_path=None) -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First",
                     status=ItemStatus.RUNNING),
        )
    )
    result = decide(
        TaskOperation(
            kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
            status=ItemStatus.RUNNING,
        ),
        current=current,
    )
    assert result.outcome is StepOutcome.NO_CHANGE


def test_marking_an_already_inspected_source_is_no_change() -> None:
    current = state(
        sources_to_inspect=("runbook",), completed_sources=("runbook",)
    )
    result = decide(
        TaskOperation(kind=OperationKind.MARK_SOURCE_INSPECTED, source_id="runbook"),
        current=current,
    )
    assert result.outcome is StepOutcome.NO_CHANGE


# --- completion gates -------------------------------------------------------


def test_completion_is_denied_while_required_work_remains() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
        )
    )
    allowed, reasons, guard = evaluate_completion(current, GENERAL_V1)

    assert allowed is False
    assert reasons == ("required_items_incomplete",)
    assert guard.guard_type is GuardType.COMPLETION_NOT_ALLOWED
    assert guard.blocking_item_ids == ("item-1",)
    assert guard.enforced is False, "AtMem denies; the host executes"


def test_completion_is_denied_while_a_required_constraint_is_unsatisfied() -> None:
    current = state(
        items=(),
        constraints=(TaskConstraint(constraint_id="c-1", text="Sign off required"),),
    )
    allowed, _, guard = evaluate_completion(current, GENERAL_V1)

    assert allowed is False
    assert guard.blocking_item_ids == ("constraint:c-1",)


def test_completion_is_allowed_once_everything_required_is_settled() -> None:
    current = state(
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True,
                     status=ItemStatus.COMPLETED),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     status=ItemStatus.PENDING),
        ),
        constraints=(
            TaskConstraint(constraint_id="c-1", text="Sign off", satisfied=True),
        ),
    )
    allowed, reasons, guard = evaluate_completion(current, GENERAL_V1)

    assert allowed is True
    assert reasons == ()
    assert guard is None


def test_a_profile_may_require_a_whole_kind_of_work() -> None:
    profile = replace(GENERAL_V1, required_item_kinds=("verification",))
    current = state(items=(TaskItem(item_id="item-1", kind="step", title="First"),))
    allowed, _, guard = evaluate_completion(current, profile)

    assert allowed is False
    assert "kind:verification" in guard.blocking_item_ids


# --- guards -----------------------------------------------------------------


def test_an_accepted_transition_reports_dependency_guards() -> None:
    result = decide(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))

    assert result.outcome is StepOutcome.ACCEPTED
    [guard] = result.guards
    assert guard.guard_type is GuardType.DEPENDENCY_UNSATISFIED
    assert guard.blocking_item_ids == ("item-2",)
