"""The Governance Matrix, proved exhaustively rather than described.

Every actor role is checked against every action. A capability that quietly
widens — an agent gaining the ability to correct state, a model gaining the
ability to commit — fails here before it can ship.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskItem,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock
from atmem.store.sqlite import SQLiteStore
from atmem.task_state.governance import (
    GOVERNANCE_ACTIONS,
    GOVERNANCE_MATRIX,
    CapabilityDenied,
    capability_for,
    matrix_rows,
    permits,
    require,
)
from atmem.task_state.service import TaskStateService

from conftest_task_state import MOMENT, SCOPE


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/task_state/governance-v1.json").read_text()
)


@pytest.fixture()
def service(tmp_path: Path) -> TaskStateService:
    store = SQLiteStore(tmp_path / "tasks.db")
    engine = TaskStateService(store, clock=FixedUtcClock(MOMENT))
    try:
        yield engine
    finally:
        store.close()


# --- the matrix is exhaustive and matches its fixture ----------------------


def test_every_role_and_action_appears_in_the_matrix() -> None:
    assert set(GOVERNANCE_MATRIX) == set(ActorRole), (
        "a role with no matrix row would silently hold nothing or everything"
    )
    for role in ActorRole:
        capability = capability_for(role)
        for action in GOVERNANCE_ACTIONS:
            assert isinstance(capability.permits(action), bool), (role, action)


def test_the_runtime_matrix_matches_the_checked_in_fixture() -> None:
    assert matrix_rows() == FIXTURE["matrix"]
    assert list(GOVERNANCE_ACTIONS) == FIXTURE["actions"]


@pytest.mark.parametrize("row", FIXTURE["matrix"], ids=lambda row: row["actor_role"])
def test_each_fixture_row_matches_the_derived_capability(row: dict) -> None:
    role = ActorRole(row["actor_role"])
    for action in GOVERNANCE_ACTIONS:
        assert permits(role, action) is row[action], (role.value, action)


def test_an_unknown_action_is_a_programming_error_not_a_silent_allow() -> None:
    with pytest.raises(ValueError, match="unknown governance action"):
        permits(ActorRole.OPERATOR, "do_whatever")


# --- the invariants the matrix exists to protect ---------------------------


def test_only_atmem_commits_canonical_state() -> None:
    committing = [role for role in ActorRole if permits(role, "commit_state")]
    assert committing == [ActorRole.ATMEM_AUTHORITY]


def test_expiry_is_held_by_exactly_one_role() -> None:
    expiring = [role for role in ActorRole if permits(role, "expire_task")]
    assert expiring == [ActorRole.POLICY_EVALUATOR], (
        "expiry is a policy operation, never an agent or operator cancellation"
    )


def test_the_policy_evaluator_holds_nothing_but_expiry() -> None:
    capability = capability_for(ActorRole.POLICY_EVALUATOR)
    for action in GOVERNANCE_ACTIONS:
        assert capability.permits(action) is (action == "expire_task"), action


def test_atbot_may_propose_and_nothing_more() -> None:
    capability = capability_for(ActorRole.ATBOT_INTELLIGENCE)
    allowed = {action for action in GOVERNANCE_ACTIONS if capability.permits(action)}
    assert allowed == {"read_state", "propose_delta"}


def test_a_host_agent_cannot_correct_register_or_delete() -> None:
    for action in ("correct_state", "register_profile", "delete_state",
                   "commit_state", "expire_task"):
        assert permits(ActorRole.HOST_AGENT, action) is False, action


def test_administrative_permission_is_distinct_from_operator_access() -> None:
    for action in ("register_profile", "delete_state"):
        assert permits(ActorRole.ADMINISTRATOR, action) is True, action
        assert permits(ActorRole.OPERATOR, action) is False, action


def test_a_delegated_context_provider_holds_no_task_capability() -> None:
    capability = capability_for(ActorRole.DELEGATED_PROVIDER)
    assert not any(capability.permits(action) for action in GOVERNANCE_ACTIONS)


def test_an_auditor_can_read_and_change_nothing() -> None:
    capability = capability_for(ActorRole.AUDITOR)
    allowed = {action for action in GOVERNANCE_ACTIONS if capability.permits(action)}
    assert allowed == {"read_state"}


def test_a_verifier_supplies_evidence_but_owns_no_state() -> None:
    capability = capability_for(ActorRole.VERIFIER)
    allowed = {action for action in GOVERNANCE_ACTIONS if capability.permits(action)}
    assert allowed == {"read_state", "propose_delta"}


# --- a label is not a capability -------------------------------------------


def test_an_actor_string_cannot_grant_a_capability(
    service: TaskStateService,
) -> None:
    """Calling yourself an administrator changes nothing."""
    with pytest.raises(CapabilityDenied):
        service.start(
            TaskStartRequest(
                task_id="task-1", scope=SCOPE, profile_id="general",
                profile_version="general-v1", goal="Sneak in",
                actor="administrator@example.com",
                actor_role=ActorRole.ATBOT_INTELLIGENCE,
                idempotency_key="start-1",
            )
        )


def test_require_names_the_role_and_the_action_it_denied() -> None:
    with pytest.raises(CapabilityDenied) as error:
        require(ActorRole.HOST_AGENT, "delete_state")

    assert error.value.actor_role is ActorRole.HOST_AGENT
    assert error.value.action == "delete_state"
    assert error.value.reason_code == "capability_denied"
    assert "host_agent" in str(error.value)


# --- enforcement at the service boundary -----------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (ActorRole.HOST_AGENT, "accepted"),
        (ActorRole.ATBOT_INTELLIGENCE, "accepted"),
        (ActorRole.OPERATOR, "accepted"),
        (ActorRole.VERIFIER, "accepted"),
        (ActorRole.AUDITOR, "rejected"),
        (ActorRole.DELEGATED_PROVIDER, "rejected"),
        (ActorRole.POLICY_EVALUATOR, "rejected"),
    ],
)
def test_only_permitted_roles_can_move_task_state(
    service: TaskStateService, role: ActorRole, expected: str
) -> None:
    _seed(service)
    decision = service.submit(
        TaskStateProposal(
            proposal_id=f"proposal-{role.value}", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key=f"delta-{role.value}",
            actor="someone", actor_role=role, assurance=Assurance.ASSERTED,
            operations=(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            ),
        )
    )
    assert decision.outcome.value == expected, role
    if expected == "rejected":
        assert decision.reason_codes == ("capability_denied",)


def test_a_denied_action_leaves_state_completely_unchanged(
    service: TaskStateService,
) -> None:
    _seed(service)
    before = service.get(SCOPE, "task-1").state

    service.submit(
        TaskStateProposal(
            proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key="delta-1", actor="auditor",
            actor_role=ActorRole.AUDITOR, assurance=Assurance.ASSERTED,
            operations=(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            ),
        )
    )

    after = service.get(SCOPE, "task-1").state
    assert after.canonical_bytes() == before.canonical_bytes()
    assert len(service.store.list_task_revisions("task-1")) == 1


def test_every_denial_still_records_a_reasoned_decision(
    service: TaskStateService,
) -> None:
    _seed(service)
    service.submit(
        TaskStateProposal(
            proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key="delta-1", actor="auditor",
            actor_role=ActorRole.AUDITOR, assurance=Assurance.ASSERTED,
            operations=(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            ),
        )
    )
    step = service.store.list_task_steps("task-1")[-1]

    assert step["outcome"] == "rejected"
    assert step["reason_codes"] == ["capability_denied"]


def test_the_fixture_records_the_invariants_it_protects() -> None:
    """The fixture is documentation as well as data."""
    assert FIXTURE["invariants"], "a governance fixture must say what it protects"
    for text in FIXTURE["invariants"]:
        assert isinstance(text, str) and text.strip()


def _seed(service: TaskStateService) -> None:
    service.start(
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="general-v1", goal="Ship it", actor="op",
            actor_role=ActorRole.OPERATOR, idempotency_key="start-1",
        ),
        items=(TaskItem(item_id="item-1", kind="step", title="First"),),
    )
