"""Closed parsing, bounds, and canonical bytes for the task-state contracts."""

from __future__ import annotations

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ContextDisposition,
    EvidenceRef,
    ExpiryPolicy,
    GuardSignal,
    GuardType,
    ItemStatus,
    OperationKind,
    Provenance,
    REASON_CODES,
    SERIALIZER_VERSION,
    StepOutcome,
    TaskConstraint,
    TaskContextPackage,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskProfile,
    TaskStartRequest,
    TaskState,
    TaskStateProposal,
    TransitionDecision,
)
from atmem.task_state import GENERAL_V1


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
DIGEST = f"sha256:{'a' * 64}"


def _state(**overrides) -> TaskState:
    base = dict(
        task_id="task-1",
        scope=SCOPE,
        revision=1,
        lifecycle=TaskLifecycle.OPEN,
        phase="plan",
        goal="Ship the migration",
        profile_id="general",
        profile_version="general-v1",
    )
    base.update(overrides)
    return TaskState(**base)


# --- lifecycle and status vocabularies -------------------------------------


def test_lifecycle_has_exactly_five_values_with_three_terminal() -> None:
    assert [item.value for item in TaskLifecycle] == [
        "open",
        "paused",
        "completed",
        "cancelled",
        "expired",
    ]
    assert [item.value for item in TaskLifecycle if item.terminal] == [
        "completed",
        "cancelled",
        "expired",
    ]


def test_item_status_has_exactly_seven_values() -> None:
    assert [item.value for item in ItemStatus] == [
        "pending",
        "ready",
        "running",
        "blocked",
        "completed",
        "skipped",
        "failed",
    ]
    assert [item.value for item in ItemStatus if item.settled] == [
        "completed",
        "skipped",
    ]


def test_every_observed_step_resolves_to_one_of_four_outcomes() -> None:
    assert {item.value for item in StepOutcome} == {
        "accepted",
        "rejected",
        "conflict",
        "no_change",
    }


def test_assurance_is_ordered_weakest_to_strongest() -> None:
    assert Assurance.ASSERTED.rank < Assurance.HOST_REPORTED.rank
    assert Assurance.HOST_REPORTED.rank < Assurance.INDEPENDENTLY_VERIFIED.rank
    # A host saying a tool succeeded is not independent proof.
    assert Assurance.HOST_REPORTED.rank < Assurance.OPERATOR_CONFIRMED.rank


# --- closed parsing and bounds ---------------------------------------------


def test_profile_parsing_rejects_unknown_fields() -> None:
    payload = GENERAL_V1.to_dict()
    payload["surprise_field"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        TaskProfile.from_dict(payload)


def test_profile_round_trips_through_its_canonical_form() -> None:
    restored = TaskProfile.from_dict(GENERAL_V1.to_dict())

    assert restored == GENERAL_V1
    assert restored.profile_digest() == GENERAL_V1.profile_digest()


def test_profile_refuses_transitions_naming_unknown_phases() -> None:
    with pytest.raises(ValueError, match="unknown phases"):
        TaskProfile(
            profile_id="custom",
            version="custom-v1",
            phases=("start", "finish"),
            phase_transitions=(("start", "nowhere"),),
        )


def test_profile_refuses_duplicate_phases_and_bad_thresholds() -> None:
    with pytest.raises(ValueError, match="unique"):
        TaskProfile(
            profile_id="custom", version="custom-v1", phases=("a", "a"),
            phase_transitions=(),
        )
    with pytest.raises(ValueError, match="at least 1"):
        TaskProfile(
            profile_id="custom", version="custom-v1", phases=("a",),
            phase_transitions=(), no_progress_action_threshold=0,
        )


def test_expiry_policy_requires_positive_thresholds() -> None:
    assert ExpiryPolicy().enabled is False
    assert ExpiryPolicy(max_absolute_age_ms=1).enabled is True
    for bad in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            ExpiryPolicy(max_absolute_age_ms=bad)
        with pytest.raises(ValueError, match="positive"):
            ExpiryPolicy(max_no_progress_age_ms=bad)


def test_goal_and_text_bounds_are_enforced() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="general-v1", goal="x" * 2_001, actor="op",
            actor_role=ActorRole.OPERATOR, idempotency_key="key-1",
        )
    with pytest.raises(ValueError, match="required"):
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="general-v1", goal="   ", actor="op",
            actor_role=ActorRole.OPERATOR, idempotency_key="key-1",
        )


def test_item_identities_must_be_unique_and_dependencies_must_exist() -> None:
    item = TaskItem(item_id="item-1", kind="step", title="First")
    with pytest.raises(ValueError, match="unique"):
        _state(items=(item, item))
    with pytest.raises(ValueError, match="unknown items"):
        _state(
            items=(
                TaskItem(
                    item_id="item-1", kind="step", title="First",
                    depends_on=("missing",),
                ),
            )
        )


def test_an_item_cannot_depend_on_itself() -> None:
    with pytest.raises(ValueError, match="depend on itself"):
        TaskItem(item_id="item-1", kind="step", title="First", depends_on=("item-1",))


def test_blocked_and_skipped_items_must_say_why() -> None:
    with pytest.raises(ValueError, match="why it is blocked"):
        TaskItem(item_id="i", kind="step", title="T", status=ItemStatus.BLOCKED)
    with pytest.raises(ValueError, match="why it was skipped"):
        TaskItem(item_id="i", kind="step", title="T", status=ItemStatus.SKIPPED)


def test_revisions_start_at_one() -> None:
    with pytest.raises(ValueError, match="revisions start at 1"):
        _state(revision=0)


# --- operations and proposals ----------------------------------------------


@pytest.mark.parametrize(
    ("kind", "kwargs", "message"),
    [
        (OperationKind.SET_ITEM_STATUS, {}, "requires item_id"),
        (
            OperationKind.SET_ITEM_STATUS,
            {"item_id": "item-1"},
            "requires status",
        ),
        (OperationKind.SET_PHASE, {}, "requires phase"),
        (OperationKind.ADD_CONSTRAINT, {}, "requires constraint_id"),
        (OperationKind.SATISFY_CONSTRAINT, {}, "requires constraint_id"),
        (OperationKind.MARK_SOURCE_INSPECTED, {}, "requires source_id"),
        (
            OperationKind.ADD_ITEM,
            {"item_id": "item-1"},
            "requires kind_label",
        ),
    ],
)
def test_operation_shapes_are_enforced(kind, kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        TaskOperation(kind=kind, **kwargs)


def test_there_is_no_full_replacement_operation() -> None:
    """A proposer may only request bounded changes it can name."""
    values = {item.value for item in OperationKind}
    for forbidden in ("replace_state", "set_state", "overwrite", "replace_items"):
        assert forbidden not in values


def test_a_proposal_requires_at_least_one_bounded_operation() -> None:
    with pytest.raises(ValueError, match="at least one operation"):
        TaskStateProposal(
            proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key="key-1", actor="atbot",
            actor_role=ActorRole.ATBOT_INTELLIGENCE, operations=(),
        )


def test_a_proposal_is_bounded_in_size() -> None:
    operation = TaskOperation(kind=OperationKind.LOCK_SCHEMA)
    with pytest.raises(ValueError, match="at most 50 operations"):
        TaskStateProposal(
            proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key="key-1", actor="atbot",
            actor_role=ActorRole.ATBOT_INTELLIGENCE,
            operations=tuple(operation for _ in range(51)),
        )


def test_proposal_payload_digest_ignores_its_own_identity() -> None:
    """Two proposals asking for the same change have the same payload."""
    def build(proposal_id: str, key: str) -> TaskStateProposal:
        return TaskStateProposal(
            proposal_id=proposal_id, task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key=key, actor="atbot",
            actor_role=ActorRole.ATBOT_INTELLIGENCE,
            operations=(TaskOperation(kind=OperationKind.LOCK_SCHEMA),),
        )

    assert build("p-1", "k-1").payload_digest() == build("p-2", "k-2").payload_digest()


# --- decisions and reason codes --------------------------------------------


def test_reason_codes_are_a_closed_vocabulary() -> None:
    with pytest.raises(ValueError, match="unknown reason codes"):
        TransitionDecision(
            decision_id="decision-1", proposal_id="proposal-1", task_id="task-1",
            scope=SCOPE, outcome=StepOutcome.REJECTED,
            reason_codes=("something_invented",), base_revision=1,
        )
    assert "task_context_budget_exceeded" in REASON_CODES
    assert "task_context_selection_required" in REASON_CODES
    assert "task_context_not_eligible" in REASON_CODES


def test_only_an_accepted_decision_may_advance_the_revision() -> None:
    with pytest.raises(ValueError, match="must name its resulting revision"):
        TransitionDecision(
            decision_id="d", proposal_id="p", task_id="t", scope=SCOPE,
            outcome=StepOutcome.ACCEPTED, reason_codes=("transition_accepted",),
            base_revision=1,
        )
    with pytest.raises(ValueError, match="only an accepted transition"):
        TransitionDecision(
            decision_id="d", proposal_id="p", task_id="t", scope=SCOPE,
            outcome=StepOutcome.REJECTED, reason_codes=("scope_mismatch",),
            base_revision=1, resulting_revision=2,
        )


def test_a_no_change_decision_may_keep_the_same_revision() -> None:
    decision = TransitionDecision(
        decision_id="d", proposal_id="p", task_id="t", scope=SCOPE,
        outcome=StepOutcome.NO_CHANGE, reason_codes=("state_already_matches",),
        base_revision=4, resulting_revision=4,
    )
    assert decision.to_dict()["outcome"] == "no_change"


# --- canonical bytes and semantic identity ---------------------------------


def test_identical_states_serialize_to_identical_bytes() -> None:
    first = _state(items=(TaskItem(item_id="a", kind="step", title="A"),))
    second = _state(items=(TaskItem(item_id="a", kind="step", title="A"),))

    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.state_digest() == second.state_digest()


def test_semantic_digest_ignores_timestamps_and_revision_bookkeeping() -> None:
    """This is what makes an honest `no_change` outcome possible."""
    first = _state(revision=1, updated_at="2026-09-05T10:00:00+00:00")
    second = _state(
        revision=7,
        parent_revision=6,
        updated_at="2026-09-05T11:00:00+00:00",
        last_progress_at="2026-09-05T11:00:00+00:00",
    )

    assert first.semantic_digest() == second.semantic_digest()
    assert first.state_digest() != second.state_digest()


def test_semantic_digest_changes_when_meaning_changes() -> None:
    first = _state(items=(TaskItem(item_id="a", kind="step", title="A"),))
    second = _state(
        items=(
            TaskItem(
                item_id="a", kind="step", title="A", status=ItemStatus.COMPLETED
            ),
        )
    )
    assert first.semantic_digest() != second.semantic_digest()


def test_state_ordering_is_stable_across_construction_order() -> None:
    items = (
        TaskItem(item_id="a", kind="step", title="A"),
        TaskItem(item_id="b", kind="step", title="B"),
    )
    assert _state(items=items).canonical_bytes() == _state(items=items).canonical_bytes()


# --- evidence and provenance -----------------------------------------------


def test_evidence_refs_are_typed_and_digest_checked() -> None:
    assert EvidenceRef(kind="source", reference_id="source-1", sha256=DIGEST)
    with pytest.raises(ValueError, match="unsupported evidence kind"):
        EvidenceRef(kind="rumour", reference_id="source-1")
    with pytest.raises(ValueError, match="sha256"):
        EvidenceRef(kind="source", reference_id="source-1", sha256="nope")


def test_provenance_records_where_a_value_came_from() -> None:
    provenance = Provenance(
        actor="atbot",
        actor_role=ActorRole.ATBOT_INTELLIGENCE,
        method="model_delta",
        assurance=Assurance.MODEL_INTERPRETED,
        observed_at="2026-09-05T10:00:00+00:00",
        introduced_in_revision=2,
        evidence=(EvidenceRef(kind="source", reference_id="source-1"),),
    )
    payload = provenance.to_dict()

    assert payload["actor_role"] == "atbot_intelligence"
    assert payload["assurance"] == "model_interpreted"
    with pytest.raises(ValueError, match="starts at 1"):
        Provenance(
            actor="a", actor_role=ActorRole.OPERATOR, method="m",
            assurance=Assurance.ASSERTED, observed_at="t", introduced_in_revision=0,
        )


# --- context package --------------------------------------------------------


def test_a_withheld_package_carries_no_task_state_bytes() -> None:
    package = TaskContextPackage(
        context_id="context-1", task_id="task-1", scope=SCOPE, revision=3,
        disposition=ContextDisposition.WITHHELD,
        reason_codes=("task_context_not_eligible",),
    )
    assert package.context == ""
    with pytest.raises(ValueError, match="no task-state bytes"):
        TaskContextPackage(
            context_id="c", task_id="t", scope=SCOPE, revision=1,
            disposition=ContextDisposition.WITHHELD, context="leaked",
            reason_codes=("task_context_not_eligible",),
        )


def test_an_injected_package_must_carry_the_authorized_bytes() -> None:
    with pytest.raises(ValueError, match="must carry the authorized bytes"):
        TaskContextPackage(
            context_id="c", task_id="t", scope=SCOPE, revision=1,
            disposition=ContextDisposition.INJECTED, context="",
        )


def test_cache_identity_is_bound_to_everything_that_changes_the_bytes() -> None:
    def build(**overrides) -> TaskContextPackage:
        base = dict(
            context_id="context-1", task_id="task-1", scope=SCOPE, revision=3,
            disposition=ContextDisposition.INJECTED, context="body",
            profile_version="general-v1", policy_generation=1,
        )
        base.update(overrides)
        return TaskContextPackage(**base)

    baseline = build().cache_key()
    assert build(context_id="context-2").cache_key() == baseline, (
        "the context id is bookkeeping, not part of cache identity"
    )
    for changed in (
        {"revision": 4},
        {"task_id": "task-2"},
        {"profile_version": "general-v2"},
        {"policy_generation": 2},
        {"serializer_version": "other-v9"},
        {"scope": AuthorityScope("subject-2", "agent-1", "workspace-1")},
        {"scope": AuthorityScope("subject-1", "agent-2", "workspace-1")},
        {"scope": AuthorityScope("subject-1", "agent-1", "workspace-2")},
    ):
        assert build(**changed).cache_key() != baseline, changed


def test_the_serializer_version_is_pinned() -> None:
    assert SERIALIZER_VERSION == "atmem-task-context-utf8-v1"


# --- guards -----------------------------------------------------------------


def test_a_guard_defaults_to_detection_not_enforcement() -> None:
    guard = GuardSignal(
        guard_type=GuardType.NO_PROGRESS, task_id="task-1", revision=3,
        message="Three equivalent actions produced no accepted progress.",
        repeated_action_count=3,
    )
    assert guard.enforced is False, (
        "AtMem detects; only an adapter that reports enforcement may claim it"
    )
    assert guard.to_dict()["guard_type"] == "no_progress"


def test_constraints_are_identified_and_bounded() -> None:
    assert TaskConstraint(constraint_id="c-1", text="Stay under budget")
    with pytest.raises(ValueError):
        TaskConstraint(constraint_id="c-1", text="")
