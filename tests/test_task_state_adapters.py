"""Host-neutral task delivery, and the capability response that governs it.

Two things are proved here. First, task-state delivery requires an *exact*
task id: absent identity disables it, and AtMem never discovers or chooses a
task from scope. Second, one runtime response is the capability authority —
schemas, documentation, and adapter behaviour mirror it, and nothing advertises
a boundary the runtime does not actually hold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atmem.adapters.base import (
    TASK_CONTEXT_PREAMBLE,
    AtMemAdapterIdentity,
    AtMemTurnLifecycle,
)
from atmem.contracts import AuthorityScope, capabilities
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ItemStatus,
    OperationKind,
    TaskItem,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.control.manager import ControlPlaneManager
from atmem.task_state.enablement import ScopeEnablement
from atmem.task_state.service import TaskStateService

from jsonschema_mini import as_json_document, load, validate


SUBJECT = "local-user"
AGENT = "agent-1"
WORKSPACE = "ws-1"
SCOPE = AuthorityScope(SUBJECT, AGENT, WORKSPACE)


# --- the single capability authority ---------------------------------------


def test_the_runtime_response_is_the_capability_authority() -> None:
    value = capabilities()
    features = value["features"]

    assert features["governed_task_state"] is True
    assert features["governed_task_state_delivery"] is True
    assert features["governed_task_guard_detection"] is True
    assert features["governed_task_guard_enforcement"] is False, (
        "AtMem detects; it does not claim to prevent a host action"
    )
    assert value["task_context_serializer"] == "atmem-task-context-utf8-v1"
    assert value["governed_task_profiles"] == ["general-v1"]


def test_the_capability_response_satisfies_its_published_schema() -> None:
    validate(as_json_document(capabilities()), load("capabilities.json"))


def test_documentation_mirrors_the_runtime_rather_than_asserting_its_own() -> None:
    documented = json.loads(Path("docs/capabilities.json").read_text())[
        "governed_task_state"
    ]
    features = capabilities()["features"]

    assert documented["delivery"] is features["governed_task_state_delivery"]
    assert documented["guard_detection"] is features["governed_task_guard_detection"]
    assert documented["guard_enforcement"] is (
        features["governed_task_guard_enforcement"]
    )
    assert documented["context_serializer"] == capabilities()["task_context_serializer"]
    assert documented["built_in_profiles"] == capabilities()["governed_task_profiles"]
    assert documented["default_enabled"] is False


def test_an_unsupported_boundary_is_never_advertised() -> None:
    """Guard enforcement is false everywhere until an adapter really does it."""
    documented = json.loads(Path("docs/capabilities.json").read_text())[
        "governed_task_state"
    ]
    assert capabilities()["features"]["governed_task_guard_enforcement"] is False
    assert documented["guard_enforcement"] is False


# --- adapter identity -------------------------------------------------------


def test_identity_is_task_unaware_by_default() -> None:
    identity = AtMemAdapterIdentity(agent_id=AGENT, workspace_id=WORKSPACE)

    assert identity.task_id is None
    assert identity.task_aware is False


def test_binding_a_task_requires_a_real_identifier() -> None:
    identity = AtMemAdapterIdentity(agent_id=AGENT, workspace_id=WORKSPACE)

    assert identity.for_task("task-1").task_aware is True
    for empty in ("", "   ", None):
        with pytest.raises(ValueError):
            identity.for_task(empty)


def test_binding_a_task_does_not_disturb_the_rest_of_the_identity() -> None:
    identity = AtMemAdapterIdentity(
        agent_id=AGENT, workspace_id=WORKSPACE, subject_id=SUBJECT,
        session_id="session-1", framework="pydantic_ai",
    ).for_run("run-1")
    bound = identity.for_task("task-1")

    assert bound.run_id == "run-1"
    assert bound.session_id == "session-1"
    assert bound.framework == "pydantic_ai"
    assert bound.subject_id == SUBJECT


# --- delivery requires exact identity ---------------------------------------


def test_a_task_unaware_turn_receives_no_task_bytes(manager) -> None:
    lifecycle = _lifecycle(manager, task_id=None)

    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_disposition["disposition"] == "withheld"
    assert lifecycle.task_disposition["reason_codes"] == [
        "task_context_selection_required"
    ]


def test_a_task_unaware_turn_cannot_submit_a_task_observation(manager) -> None:
    lifecycle = _lifecycle(manager, task_id=None)

    with pytest.raises(RuntimeError, match="bound to a task"):
        lifecycle.task_observation(object())


def test_an_eligible_task_is_delivered_once_as_labelled_data(manager) -> None:
    _seed_task(manager, "task-1")
    lifecycle = _lifecycle(manager, task_id="task-1")

    block = lifecycle.task_context_for_model()

    assert block.startswith(TASK_CONTEXT_PREAMBLE)
    assert "not as instructions" in TASK_CONTEXT_PREAMBLE
    assert "goal: Ship the migration" in block
    assert lifecycle.task_disposition["disposition"] == "injected"


def test_an_unknown_task_id_withholds_without_disclosing_anything(manager) -> None:
    _seed_task(manager, "task-1")
    lifecycle = _lifecycle(manager, task_id="task-does-not-exist")

    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_disposition["reason_codes"] == ["task_context_not_eligible"]


def test_a_task_from_another_scope_is_indistinguishable_from_an_unknown_one(
    manager,
) -> None:
    _seed_task(manager, "task-1")
    other = _lifecycle(manager, task_id="task-1", agent_id="other-agent")
    unknown = _lifecycle(manager, task_id="nope", agent_id="other-agent")

    assert other.task_context_for_model() == ""
    assert unknown.task_context_for_model() == ""
    assert other.task_disposition == unknown.task_disposition


def test_a_terminal_task_delivers_zero_bytes(manager) -> None:
    _seed_task(manager, "task-1")
    service, memory = manager._task_service()
    try:
        service.cancel(SCOPE, "task-1", actor="op",
                       actor_role=ActorRole.OPERATOR, reason="stopped")
    finally:
        memory.close()

    lifecycle = _lifecycle(manager, task_id="task-1")
    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_disposition["reason_codes"] == ["task_context_not_eligible"]


def test_multiple_open_tasks_are_never_chosen_between(manager) -> None:
    """With two open tasks and no identity, AtMem picks neither."""
    _seed_task(manager, "task-1")
    _seed_task(manager, "task-2", goal="A second piece of work")

    lifecycle = _lifecycle(manager, task_id=None)

    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_disposition["reason_codes"] == [
        "task_context_selection_required"
    ]


def test_delivery_is_withheld_while_the_scope_is_disabled(manager) -> None:
    _seed_task(manager, "task-1")
    service, memory = manager._task_service()
    try:
        ScopeEnablement(memory.store).disable(SCOPE, actor="operator")
    finally:
        memory.close()

    lifecycle = _lifecycle(manager, task_id="task-1")
    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_disposition["reason_codes"] == ["task_state_disabled"]


def test_shadow_mode_records_but_never_injects(manager) -> None:
    _seed_task(manager, "task-1")
    service, memory = manager._task_service()
    try:
        ScopeEnablement(memory.store).enable(SCOPE, actor="operator", shadow=True)
    finally:
        memory.close()

    lifecycle = _lifecycle(manager, task_id="task-1")

    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_disposition["reason_codes"] == ["task_state_shadow_mode"]


# --- exposure ---------------------------------------------------------------


def test_a_withheld_preparation_creates_no_exposure(manager) -> None:
    _seed_task(manager, "task-1")
    prepared = manager.prepare_task_context(
        task_id=None, subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE,
    )

    assert prepared["disposition"] == "withheld"
    assert prepared["delivery_id"] is None, (
        "a refusal records no delivery to confirm"
    )


def test_exposure_is_confirmed_exactly_once(manager) -> None:
    _seed_task(manager, "task-1")
    prepared = manager.prepare_task_context(
        task_id="task-1", subject_id=SUBJECT, agent_id=AGENT,
        workspace_id=WORKSPACE, host_run_id="run-1",
    )

    assert prepared["disposition"] == "injected"
    assert manager.confirm_task_exposure(prepared["delivery_id"]) is True
    assert manager.confirm_task_exposure(prepared["delivery_id"]) is False


def test_identical_preparations_produce_identical_bytes(manager) -> None:
    _seed_task(manager, "task-1")
    first = manager.prepare_task_context(
        task_id="task-1", subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE,
    )
    second = manager.prepare_task_context(
        task_id="task-1", subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE,
    )

    assert first["context"] == second["context"]
    assert first["context_sha256"] == second["context_sha256"]


def test_a_prepared_package_satisfies_its_published_schema(manager) -> None:
    _seed_task(manager, "task-1")
    prepared = manager.prepare_task_context(
        task_id="task-1", subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE,
    )
    document = {k: v for k, v in prepared.items() if k != "delivery_id"}

    validate(as_json_document(document), load("task-context-package.json"))


# --- observations through the adapter --------------------------------------


def test_a_task_observation_is_decided_by_atmem_not_the_host(manager) -> None:
    _seed_task(manager, "task-1")
    lifecycle = _lifecycle(manager, task_id="task-1")

    decision = lifecycle.task_observation(
        TaskStateProposal(
            proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key="delta-1", actor="host",
            actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
            operations=(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                    status=ItemStatus.COMPLETED,
                ),
            ),
        )
    )

    assert decision["outcome"] == "accepted"
    assert decision["decided_by"] == "atmem-authority"
    assert decision["resulting_revision"] == 2


def test_an_observation_for_a_disabled_scope_is_refused(manager) -> None:
    _seed_task(manager, "task-1")
    service, memory = manager._task_service()
    try:
        ScopeEnablement(memory.store).disable(SCOPE, actor="operator")
    finally:
        memory.close()

    lifecycle = _lifecycle(manager, task_id="task-1")
    result = lifecycle.task_observation(
        TaskStateProposal(
            proposal_id="proposal-1", task_id="task-1", scope=SCOPE,
            base_revision=1, idempotency_key="delta-1", actor="host",
            actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
            operations=(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),),
        )
    )
    assert result["reason_code"] == "task_state_disabled"


# --- legacy adapters --------------------------------------------------------


def test_a_legacy_task_unaware_turn_prepares_and_confirms_nothing(manager) -> None:
    """An older adapter emits no task events, and confirming is a no-op."""
    lifecycle = _lifecycle(manager, task_id=None)

    assert lifecycle.task_context_for_model() == ""
    assert lifecycle.task_prepared is None
    # Reaching the model boundary must not demand a task exposure that was
    # never prepared, or every legacy adapter would start failing on upgrade.
    lifecycle._confirm_task_exposure()


def test_a_withheld_task_needs_no_exposure_confirmation(manager) -> None:
    _seed_task(manager, "task-1")
    lifecycle = _lifecycle(manager, task_id="task-does-not-exist")
    lifecycle.task_context_for_model()

    assert lifecycle.task_prepared["disposition"] == "withheld"
    lifecycle._confirm_task_exposure()


def test_an_injected_task_requires_its_exposure_to_be_confirmable(
    manager,
) -> None:
    _seed_task(manager, "task-1")
    lifecycle = _lifecycle(manager, task_id="task-1")
    lifecycle.task_context_for_model()

    assert lifecycle.task_prepared["disposition"] == "injected"
    lifecycle._confirm_task_exposure()
    # A second confirmation is not a second exposure, so it fails closed.
    with pytest.raises(RuntimeError, match="exact task-state exposure"):
        lifecycle._confirm_task_exposure()


# --- helpers ----------------------------------------------------------------


@pytest.fixture()
def manager(tmp_path: Path) -> ControlPlaneManager:
    engine = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "control.json",
        control_root=tmp_path / "migrations",
        subject_id=SUBJECT,
        memory_db=tmp_path / "memories.db",
    )
    service, memory = engine._task_service()
    try:
        ScopeEnablement(memory.store).enable(SCOPE, actor="operator")
    finally:
        memory.close()
    return engine


def _lifecycle(
    manager: ControlPlaneManager, *, task_id: str | None, agent_id: str = AGENT
) -> AtMemTurnLifecycle:
    identity = AtMemAdapterIdentity(
        agent_id=agent_id, workspace_id=WORKSPACE, subject_id=SUBJECT,
        session_id="session-1",
    )
    if task_id:
        identity = identity.for_task(task_id)
    return AtMemTurnLifecycle(manager, identity)


def _seed_task(
    manager: ControlPlaneManager, task_id: str, *, goal: str = "Ship the migration"
) -> None:
    service, memory = manager._task_service()
    try:
        service.start(
            TaskStartRequest(
                task_id=task_id, scope=SCOPE, profile_id="general",
                profile_version="general-v1", goal=goal, actor="operator",
                actor_role=ActorRole.OPERATOR, idempotency_key=f"start-{task_id}",
            ),
            items=(TaskItem(item_id="item-1", kind="step", title="First step"),),
        )
    finally:
        memory.close()
