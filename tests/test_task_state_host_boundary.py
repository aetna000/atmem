"""The host-boundary write path, gate by gate.

Spec 007 Amendment A, T068, T071 and T074.

The gates run in a fixed order and the order is the design, so the tests are
organised the same way: enablement, then session binding, then capability
ceiling, then policy. The cases worth the most are the ones a weaker
implementation would still pass -- a submission naming a sibling task in the
same authorized scope, and a refusal that leaks whether the named task exists.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    HostSessionIdentity,
    TaskItem,
    TaskStartRequest,
)
from atmem.control.manager import ControlPlaneManager
from atmem.task_state.binding import SessionBindingService
from atmem.task_state.enablement import ScopeEnablement


SUBJECT = "local-user"
SCOPE = AuthorityScope(SUBJECT, "default-agent", "default-workspace")
IDENTITY = {"host_type": "openclaw", "session_key": "session-1", "session_epoch": "epoch-1"}
OTHER_IDENTITY = {**IDENTITY, "session_key": "session-2"}


@pytest.fixture()
def manager(tmp_path: Path) -> ControlPlaneManager:
    return ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "control.json",
        control_root=tmp_path / "migrations",
        subject_id=SUBJECT,
        memory_db=tmp_path / "memories.db",
    )


def enable(manager: ControlPlaneManager, *, shadow: bool = False) -> None:
    service, memory = manager._task_service()
    try:
        ScopeEnablement(memory.store).enable(SCOPE, actor="operator", shadow=shadow)
    finally:
        memory.close()


def start_task(manager: ControlPlaneManager, task_id: str, *, required: bool = True) -> None:
    service, memory = manager._task_service()
    try:
        service.start(
            TaskStartRequest(
                task_id=task_id, scope=SCOPE, profile_id="general",
                profile_version="general-v1", goal=f"Goal for {task_id}",
                actor="operator", actor_role=ActorRole.OPERATOR,
                idempotency_key=f"start-{task_id}",
            ),
            items=(
                TaskItem(item_id="step-1", kind="step", title="First step",
                         required=required),
            ),
        )
    finally:
        memory.close()


def bind(manager: ControlPlaneManager, task_id: str, identity: dict) -> None:
    service, memory = manager._task_service()
    try:
        SessionBindingService(memory.store, service.clock).register(
            SCOPE, HostSessionIdentity(**identity), task_id=task_id,
            actor="operator", reason="drive this task here",
        )
    finally:
        memory.close()


def proposal(task_id: str = "migrate", *, identity: dict | None = None, **overrides) -> dict:
    return {
        "identity": identity or IDENTITY,
        "task_id": task_id,
        "base_revision": 1,
        "idempotency_key": "run-1:tool-1",
        "operations": [{"kind": "set_item_status", "item_id": "step-1", "status": "running"}],
        "adapter": "openclaw",
        **overrides,
    }


def observation(task_id: str = "migrate", *, identity: dict | None = None, **overrides) -> dict:
    return {
        "identity": identity or IDENTITY,
        "task_id": task_id,
        "idempotency_key": "run-1:tool-1",
        "observation": "the migration script exited zero",
        "adapter": "openclaw",
        **overrides,
    }


def lifecycle(task_id: str = "migrate", *, identity: dict | None = None, **overrides) -> dict:
    return {
        "identity": identity or IDENTITY,
        "task_id": task_id,
        "action": "complete",
        "expected_revision": 1,
        "idempotency_key": "run-1:end",
        "adapter": "openclaw",
        **overrides,
    }


ALL_OPERATIONS = (
    ("propose_task_delta", proposal),
    ("observe_task_step", observation),
    ("request_task_lifecycle", lifecycle),
)


def call(manager: ControlPlaneManager, method: str, payload: dict) -> dict:
    return getattr(manager, method)(payload)


# --- gate 1: enablement, and disabled is not shadow --------------------------


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_a_disabled_scope_refuses_before_anything_else(manager, method, build) -> None:
    """Refused before identity resolution or content evaluation.

    Nothing about the task surface is disclosed, including whether the named
    task exists -- which is why this gate runs first rather than after binding.
    """
    result = call(manager, method, build())
    assert result["reason_code"] == "task_state_disabled"


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_a_disabled_scope_answers_identically_for_real_and_invented_tasks(
    manager, method, build
) -> None:
    real = call(manager, method, build("migrate"))
    invented = call(manager, method, build("no-such-task"))
    assert real["reason_code"] == invented["reason_code"]
    assert real["message"] == invented["message"]


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_shadow_evaluates_and_commits_nothing(manager, method, build) -> None:
    """Shadow is a rehearsal for the active path, not a silent no-op."""
    enable(manager, shadow=True)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    result = call(manager, method, build())
    assert result["reason_codes"] == ["task_state_shadow_mode"]
    assert result["outcome"] == "no_change"

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.revision == 1
    finally:
        memory.close()


# --- gate 2: session binding (FR-054) ---------------------------------------


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_an_unbound_conversation_may_not_write(manager, method, build) -> None:
    enable(manager)
    start_task(manager, "migrate")
    result = call(manager, method, build())
    assert result["reason_code"] == "task_context_selection_required"


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_a_session_may_not_write_to_another_sessions_task(manager, method, build) -> None:
    """The case scope and capability checks both let through.

    One authorized scope routinely holds several tasks. Without FR-054 a model
    in the first conversation could advance the second conversation's work
    while passing every other check.
    """
    enable(manager)
    start_task(manager, "migrate")
    start_task(manager, "docs-audit")
    bind(manager, "migrate", IDENTITY)
    bind(manager, "docs-audit", OTHER_IDENTITY)

    result = call(manager, method, build("docs-audit"))
    assert result["reason_code"] == "host_task_not_bound_to_session"

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.revision == 1
        assert service.get(SCOPE, "docs-audit").state.revision == 1
    finally:
        memory.close()


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_naming_another_session_task_reads_the_same_as_naming_a_fiction(
    manager, method, build
) -> None:
    """Non-disclosing, so guessing task names is not an existence oracle."""
    enable(manager)
    start_task(manager, "migrate")
    start_task(manager, "docs-audit")
    bind(manager, "migrate", IDENTITY)
    bind(manager, "docs-audit", OTHER_IDENTITY)

    real_elsewhere = call(manager, method, build("docs-audit"))
    pure_fiction = call(manager, method, build("never-existed"))
    assert real_elsewhere["reason_code"] == pure_fiction["reason_code"]
    assert real_elsewhere["message"] == pure_fiction["message"]


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
def test_a_recycled_session_may_not_write(manager, method, build) -> None:
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    result = call(
        manager, method, build(identity={**IDENTITY, "session_epoch": "epoch-2"})
    )
    assert result["reason_code"] == "task_binding_stale_session"


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
@pytest.mark.parametrize("dropped", ["host_type", "session_key", "session_epoch"])
def test_a_partial_identity_is_refused_not_resolved(manager, method, build, dropped) -> None:
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    identity = {k: v for k, v in IDENTITY.items() if k != dropped}
    result = call(manager, method, build(identity=identity))
    assert result["reason_code"] == "session_identity_required"


# --- gate 3: capability ceiling ---------------------------------------------


@pytest.mark.parametrize("forbidden", ["lock_schema", "add_constraint"])
def test_operator_only_operations_are_refused_on_capability_grounds(
    manager, forbidden
) -> None:
    """Refused before delta content is evaluated, so nothing leaks."""
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    operation = {"kind": forbidden}
    if forbidden == "add_constraint":
        operation |= {"constraint_id": "c-1", "text": "no downtime"}
    result = call(manager, "propose_task_delta", proposal(operations=[operation]))
    assert result["reason_code"] == "capability_denied"

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.revision == 1
    finally:
        memory.close()


def test_a_host_cannot_cancel_a_task(manager) -> None:
    """Cancellation is operator-only and is not an action the contract admits."""
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    result = call(manager, "request_task_lifecycle", lifecycle(action="cancel"))
    assert result["reason_code"] in {"capability_denied", "session_identity_required"}

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.lifecycle.value == "open"
    finally:
        memory.close()


@pytest.mark.parametrize("method,build", ALL_OPERATIONS)
@pytest.mark.parametrize("smuggled", ["actor_role", "capability", "authority"])
def test_a_smuggled_authority_field_is_refused(manager, method, build, smuggled) -> None:
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    result = call(manager, method, build(**{smuggled: "operator"}))
    assert result["reason_code"] == "capability_denied"
    assert "authority" in result["message"]


# --- gate 4: policy, unchanged ----------------------------------------------


def test_a_bound_session_advances_its_own_task(manager) -> None:
    """The point of all of it: a host can finally report progress."""
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    result = call(manager, "propose_task_delta", proposal())
    assert result["outcome"] == "accepted"
    assert result["resulting_revision"] == 2


def test_a_stale_base_revision_conflicts(manager) -> None:
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)
    call(manager, "propose_task_delta", proposal())

    result = call(
        manager, "propose_task_delta",
        proposal(base_revision=1, idempotency_key="run-1:tool-2"),
    )
    assert result["outcome"] == "conflict"


def test_a_replayed_idempotency_key_makes_no_second_revision(manager) -> None:
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    first = call(manager, "propose_task_delta", proposal())
    replay = call(manager, "propose_task_delta", proposal())

    # A replay resolves to the decision already recorded rather than a fresh
    # one. Returning the original outcome is what makes a retried hook safe:
    # the caller sees what happened the first time, and the head does not move.
    assert first["outcome"] == "accepted"
    assert replay["resulting_revision"] == first["resulting_revision"]

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.revision == 2
        proposals = memory.store.list_task_proposals(task_id="migrate")
        assert len({row["idempotency_key"] for row in proposals}) == len(proposals)
    finally:
        memory.close()


def test_premature_completion_is_denied_with_the_blocking_items(manager) -> None:
    enable(manager)
    start_task(manager, "migrate", required=True)
    bind(manager, "migrate", IDENTITY)

    result = call(manager, "request_task_lifecycle", lifecycle())
    assert result["reason_code"] == "required_items_incomplete"

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.lifecycle.value == "open"
    finally:
        memory.close()


def test_host_idempotency_keys_cannot_collide_with_operator_keys(manager) -> None:
    """Namespaced, so a host replay cannot masquerade as an operator action."""
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)
    call(manager, "propose_task_delta", proposal())

    service, memory = manager._task_service()
    try:
        keys = [
            row["idempotency_key"]
            for row in memory.store.list_task_proposals(task_id="migrate")
        ]
    finally:
        memory.close()
    assert any(key.startswith("host:openclaw:") for key in keys)


# --- concurrency (T074) -----------------------------------------------------


def test_concurrent_host_proposals_produce_one_successor(manager) -> None:
    """The SC-002 guarantee, exercised through the host path."""
    enable(manager)
    start_task(manager, "migrate")
    bind(manager, "migrate", IDENTITY)

    attempts = 40
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda index: call(
                    manager, "propose_task_delta",
                    proposal(idempotency_key=f"run-1:tool-{index}"),
                ),
                range(attempts),
            )
        )

    accepted = [row for row in results if row.get("outcome") == "accepted"]
    assert len(accepted) == 1, "one base revision admitted more than one successor"

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.revision == 2
    finally:
        memory.close()


def test_two_sessions_advance_only_their_own_tasks(manager) -> None:
    """Concurrency plus FR-054: neither conversation can touch the other's work."""
    enable(manager)
    start_task(manager, "migrate")
    start_task(manager, "docs-audit")
    bind(manager, "migrate", IDENTITY)
    bind(manager, "docs-audit", OTHER_IDENTITY)

    plan = [
        ("migrate", IDENTITY),
        ("docs-audit", OTHER_IDENTITY),
        ("docs-audit", IDENTITY),      # cross-session, must be refused
        ("migrate", OTHER_IDENTITY),   # cross-session, must be refused
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda row: call(
                    manager, "propose_task_delta",
                    proposal(row[0], identity=row[1],
                             idempotency_key=f"k-{row[0]}-{row[1]['session_key']}"),
                ),
                plan,
            )
        )

    refused = [r for r in results if r.get("reason_code") == "host_task_not_bound_to_session"]
    assert len(refused) == 2

    service, memory = manager._task_service()
    try:
        assert service.get(SCOPE, "migrate").state.revision == 2
        assert service.get(SCOPE, "docs-audit").state.revision == 2
    finally:
        memory.close()
