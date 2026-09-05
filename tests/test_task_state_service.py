"""The committing authority: acceptance, refusal, concurrency, and lifecycle.

Policy decides in memory; this suite proves the service writes exactly what
policy approved, exactly once, and nothing else — including under concurrent
writers, replayed keys, restarts, and crashes mid-transaction.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    EvidenceRef,
    ItemStatus,
    OperationKind,
    StepOutcome,
    TaskItem,
    TaskLifecycle,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.core.time import FixedUtcClock
from atmem.store.sqlite import SQLiteStore
from atmem.task_state.governance import CapabilityDenied
from atmem.task_state.service import (
    TaskCompletionDenied,
    TaskStateError,
    TaskStateService,
)


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
OTHER_SCOPE = AuthorityScope("subject-2", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/task_state/general-v1.json").read_text()
)


@pytest.fixture()
def clock() -> FixedUtcClock:
    return FixedUtcClock(MOMENT)


@pytest.fixture()
def service(tmp_path: Path, clock: FixedUtcClock) -> TaskStateService:
    store = SQLiteStore(tmp_path / "tasks.db")
    engine = TaskStateService(store, clock=clock)
    try:
        yield engine
    finally:
        store.close()


def start(
    service: TaskStateService, *, items=None, scope: AuthorityScope = SCOPE, **overrides
):
    base = dict(
        task_id="task-1", scope=scope, profile_id="general",
        profile_version="general-v1", goal="Ship the migration",
        actor="operator@example.com", actor_role=ActorRole.OPERATOR,
        idempotency_key="start-1",
    )
    base.update(overrides)
    return service.start(
        TaskStartRequest(**base),
        items=items
        if items is not None
        else (
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
            TaskItem(item_id="item-3", kind="step", title="Third"),
        ),
    )


def propose(*operations, revision=1, key="delta-1", scope=SCOPE, **overrides):
    base = dict(
        proposal_id=f"proposal-{key}", task_id="task-1", scope=scope,
        base_revision=revision, idempotency_key=key, actor="agent",
        actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
    )
    base.update(overrides)
    return TaskStateProposal(operations=tuple(operations), **base)


# --- start ------------------------------------------------------------------


def test_starting_a_task_creates_revision_one_with_full_identity(
    service: TaskStateService,
) -> None:
    view = start(service, constraints=("Stay under one hour",))

    assert view.state.revision == 1
    assert view.state.lifecycle is TaskLifecycle.OPEN
    assert view.state.phase == "plan"
    assert view.state.goal == "Ship the migration"
    assert view.state.profile_version == "general-v1"
    assert view.state.scope == SCOPE
    assert [row.text for row in view.state.constraints] == ["Stay under one hour"]
    assert view.task["clock_source"] == "fixed-utc-v1"


def test_starting_twice_with_the_same_key_returns_the_same_task(
    service: TaskStateService,
) -> None:
    first = start(service)
    second = start(service, goal="A different goal")

    assert second.state.revision == first.state.revision
    assert second.state.goal == "Ship the migration", (
        "an idempotent start replays; it does not silently rewrite the goal"
    )
    assert service.list(SCOPE)["count"] == 1


def test_starting_records_provenance_for_the_task_and_every_item(
    service: TaskStateService,
) -> None:
    start(service)
    rows = service.store.list_task_provenance("task-1")

    kinds = {row["target_kind"] for row in rows}
    assert kinds == {"task", "item"}
    assert {row["target_id"] for row in rows if row["target_kind"] == "item"} == {
        "item-1", "item-2", "item-3",
    }
    assert all(row["actor"] == "operator@example.com" for row in rows)


def test_an_unknown_profile_version_is_refused(service: TaskStateService) -> None:
    with pytest.raises(TaskStateError) as error:
        start(service, profile_version="not-a-profile")
    assert error.value.reason_code == "task_not_eligible"


def test_a_role_without_lifecycle_capability_cannot_start_a_task(
    service: TaskStateService,
) -> None:
    with pytest.raises(CapabilityDenied):
        start(service, actor_role=ActorRole.ATBOT_INTELLIGENCE)


# --- reads and scope --------------------------------------------------------


def test_a_task_is_not_readable_from_another_scope(
    service: TaskStateService,
) -> None:
    start(service)

    with pytest.raises(TaskStateError) as error:
        service.get(OTHER_SCOPE, "task-1")
    assert error.value.reason_code == "task_not_eligible"


def test_an_unknown_task_and_an_unauthorized_task_look_identical(
    service: TaskStateService,
) -> None:
    """A caller must not be able to probe for the existence of another's task."""
    start(service)

    with pytest.raises(TaskStateError) as unauthorized:
        service.get(OTHER_SCOPE, "task-1")
    with pytest.raises(TaskStateError) as unknown:
        service.get(OTHER_SCOPE, "task-does-not-exist")

    assert str(unauthorized.value) == str(unknown.value)
    assert unauthorized.value.reason_code == unknown.value.reason_code


def test_listing_is_scoped_and_paginates_deterministically(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    for index in range(4):
        clock.advance(minutes=1)
        start(service, task_id=f"task-{index}", idempotency_key=f"start-{index}")
    start(
        service, task_id="other", idempotency_key="start-other", scope=OTHER_SCOPE,
    )

    first = service.list(SCOPE, limit=2)
    second = service.list(SCOPE, limit=2, cursor=first["next_cursor"])

    assert [row["task_id"] for row in first["tasks"]] == ["task-0", "task-1"]
    assert [row["task_id"] for row in second["tasks"]] == ["task-2", "task-3"]
    assert all(row["task_id"] != "other" for row in first["tasks"] + second["tasks"])


# --- authorization before intelligence --------------------------------------


def test_a_proposal_from_another_scope_never_reaches_the_task(
    service: TaskStateService,
) -> None:
    start(service)

    with pytest.raises(TaskStateError) as error:
        service.submit(
            propose(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
                scope=OTHER_SCOPE,
            )
        )
    assert error.value.reason_code == "task_not_eligible"
    assert service.get(SCOPE, "task-1").state.revision == 1


def test_atbot_may_propose_but_never_commits(service: TaskStateService) -> None:
    from atmem.task_state.governance import permits

    assert permits(ActorRole.ATBOT_INTELLIGENCE, "propose_delta") is True
    assert permits(ActorRole.ATBOT_INTELLIGENCE, "commit_state") is False

    start(service)
    decision = service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            actor_role=ActorRole.ATBOT_INTELLIGENCE,
            assurance=Assurance.MODEL_INTERPRETED,
        )
    )
    # AtMem, not AtBot, decided and wrote the revision.
    assert decision.outcome is StepOutcome.ACCEPTED
    assert decision.decided_by == "atmem-authority"


# --- the four outcomes ------------------------------------------------------


def test_an_accepted_transition_advances_the_head_exactly_once(
    service: TaskStateService,
) -> None:
    start(service)
    decision = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )

    assert decision.outcome is StepOutcome.ACCEPTED
    assert decision.resulting_revision == 2
    assert service.get(SCOPE, "task-1").state.revision == 2
    assert len(service.store.list_task_revisions("task-1")) == 2


def test_a_rejected_proposal_leaves_the_head_untouched(
    service: TaskStateService,
) -> None:
    start(service)
    decision = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="teatime"))
    )

    assert decision.outcome is StepOutcome.REJECTED
    assert decision.resulting_revision is None
    assert service.get(SCOPE, "task-1").state.revision == 1
    assert len(service.store.list_task_revisions("task-1")) == 1


def test_a_stale_base_revision_conflicts_without_changing_anything(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )
    stale = service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="execute"),
            revision=1, key="delta-stale",
        )
    )

    assert stale.outcome is StepOutcome.CONFLICT
    assert stale.reason_codes == ("stale_base_revision",)
    assert service.get(SCOPE, "task-1").state.phase == "collect"


def test_a_no_change_step_is_recorded_without_a_new_revision(
    service: TaskStateService,
) -> None:
    start(service)
    decision = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="plan"))
    )

    assert decision.outcome is StepOutcome.NO_CHANGE
    assert len(service.store.list_task_revisions("task-1")) == 1
    steps = service.store.list_task_steps("task-1")
    assert steps[-1]["outcome"] == "no_change"


def test_every_observed_step_produces_exactly_one_recorded_outcome(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect")))
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="teatime"),
                revision=2, key="delta-2")
    )
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
                revision=2, key="delta-3")
    )
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="execute"),
                revision=1, key="delta-4")
    )

    outcomes = [row["outcome"] for row in service.store.list_task_steps("task-1")]
    assert outcomes == ["accepted", "accepted", "rejected", "no_change", "conflict"]


# --- replay and concurrency -------------------------------------------------


def test_replaying_an_idempotency_key_returns_the_original_decision(
    service: TaskStateService,
) -> None:
    start(service)
    first = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )
    second = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )

    assert second.replayed is True
    assert second.resulting_revision == first.resulting_revision
    assert len(service.store.list_task_revisions("task-1")) == 2, (
        "a replayed key must not create a second revision"
    )


def test_reusing_a_key_with_a_different_delta_fails_closed(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect")))

    with pytest.raises(TaskStateError) as error:
        service.submit(
            propose(
                TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                              status=ItemStatus.COMPLETED),
                key="delta-1",
            )
        )
    assert error.value.reason_code == "task_not_eligible"


def test_one_base_revision_accepts_only_one_successor(
    tmp_path: Path, clock: FixedUtcClock
) -> None:
    """Two workers race on the same head; exactly one wins, the other conflicts."""
    path = tmp_path / "tasks.db"
    store = SQLiteStore(path)
    service = TaskStateService(store, clock=clock)
    try:
        start(service)
    finally:
        store.close()

    def worker(index: int) -> str:
        own_store = SQLiteStore(path)
        own = TaskStateService(own_store, clock=FixedUtcClock(MOMENT))
        try:
            decision = own.submit(
                propose(
                    TaskOperation(
                        kind=OperationKind.SET_ITEM_STATUS, item_id=f"item-{index + 1}",
                        status=ItemStatus.BLOCKED, reason=f"worker {index}",
                    ),
                    revision=1, key=f"delta-{index}",
                )
            )
            return decision.outcome.value
        finally:
            own_store.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = list(pool.map(worker, range(3)))

    verifier = SQLiteStore(path)
    try:
        assert outcomes.count("accepted") == 1, outcomes
        assert all(row in {"accepted", "conflict"} for row in outcomes), outcomes
        revisions = verifier.list_task_revisions("task-1")
        assert [row["revision"] for row in revisions] == [1, 2]
        assert verifier.get_task(
            subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
            workspace_id=SCOPE.workspace_id, task_id="task-1",
        )["head_revision"] == 2
    finally:
        verifier.close()


def test_a_thousand_replays_create_no_duplicate_revision(
    service: TaskStateService,
) -> None:
    start(service)
    proposal = propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    outcomes = [service.submit(proposal) for _ in range(1_000)]

    assert all(row.outcome is StepOutcome.ACCEPTED for row in outcomes)
    assert sum(1 for row in outcomes if row.replayed) == 999
    assert len(service.store.list_task_revisions("task-1")) == 2
    assert service.get(SCOPE, "task-1").state.revision == 2


# --- lifecycle --------------------------------------------------------------


def test_pause_and_resume_are_distinct_authorized_revisions(
    service: TaskStateService, clock: FixedUtcClock
) -> None:
    start(service)
    clock.advance(minutes=5)
    paused = service.pause(
        SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR, reason="waiting"
    )
    clock.advance(minutes=5)
    resumed = service.resume(
        SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR
    )

    assert paused.state.lifecycle is TaskLifecycle.PAUSED
    assert resumed.state.lifecycle is TaskLifecycle.OPEN
    assert resumed.state.revision == 3
    assert [row["revision"] for row in service.store.list_task_revisions("task-1")] == [
        1, 2, 3,
    ]


def test_a_paused_task_refuses_ordinary_transitions(
    service: TaskStateService,
) -> None:
    start(service)
    service.pause(
        SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR, reason="waiting"
    )
    decision = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"), revision=2)
    )

    assert decision.outcome is StepOutcome.REJECTED
    assert decision.reason_codes == ("task_is_paused",)


def test_completion_is_denied_while_required_work_remains(
    service: TaskStateService,
) -> None:
    start(service)

    with pytest.raises(TaskCompletionDenied) as error:
        service.complete(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)

    assert error.value.reason_code == "required_items_incomplete"
    assert "item-1" in error.value.guard.blocking_item_ids
    assert error.value.guard.enforced is False
    assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.OPEN


def test_completion_succeeds_once_required_work_is_settled(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                          status=ItemStatus.COMPLETED),
        )
    )
    view = service.complete(
        SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR
    )

    assert view.state.lifecycle is TaskLifecycle.COMPLETED
    assert view.task["terminal_reason"] == "completed"


def test_cancellation_requires_a_reason(service: TaskStateService) -> None:
    start(service)

    with pytest.raises(TaskStateError) as error:
        service.cancel(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
                       reason="   ")
    assert error.value.reason_code == "reason_required"


@pytest.mark.parametrize("terminal", ["completed", "cancelled"])
def test_a_terminal_task_cannot_be_mutated_or_reopened(
    service: TaskStateService, terminal: str
) -> None:
    start(service, items=())
    if terminal == "completed":
        service.complete(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)
    else:
        service.cancel(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR,
                       reason="no longer needed")

    decision = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"), revision=2)
    )
    assert decision.outcome is StepOutcome.REJECTED
    assert decision.reason_codes == ("task_is_terminal",)

    with pytest.raises(TaskStateError) as error:
        service.resume(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)
    assert error.value.reason_code == "task_is_terminal"


def test_continuing_terminal_work_requires_a_new_linked_task(
    service: TaskStateService,
) -> None:
    start(service, items=())
    service.complete(SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR)

    successor = start(
        service, task_id="task-2", idempotency_key="start-2",
        goal="Finish what task-1 started", continues_task_id="task-1",
    )

    assert successor.task["continues_task_id"] == "task-1"
    assert successor.state.lifecycle is TaskLifecycle.OPEN
    assert service.get(SCOPE, "task-1").state.lifecycle is TaskLifecycle.COMPLETED


# --- correction -------------------------------------------------------------


def test_an_operator_correction_appends_a_revision_and_keeps_the_prior_one(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-3",
                          status=ItemStatus.BLOCKED, reason="Wrong reason recorded"),
        )
    )
    corrected = service.correct(
        SCOPE, "task-1",
        propose(
            TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-3",
                          status=ItemStatus.READY, reason="Unblocked after review"),
            revision=2, key="correction-1",
            actor="operator@example.com", actor_role=ActorRole.OPERATOR,
            assurance=Assurance.OPERATOR_CONFIRMED,
        ),
        reason="The blocker was resolved offline",
    )

    assert corrected.outcome is StepOutcome.ACCEPTED
    assert corrected.resulting_revision == 3
    revisions = service.store.list_task_revisions("task-1")
    assert [row["revision"] for row in revisions] == [1, 2, 3]
    assert revisions[1]["state"]["items"][2]["status"] == "blocked", (
        "the prior revision is preserved, not overwritten"
    )
    assert service.get(SCOPE, "task-1").state.item("item-3").status is ItemStatus.READY


def test_a_correction_requires_a_reason(service: TaskStateService) -> None:
    start(service)

    with pytest.raises(TaskStateError) as error:
        service.correct(
            SCOPE, "task-1",
            propose(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
                actor_role=ActorRole.OPERATOR, assurance=Assurance.OPERATOR_CONFIRMED,
            ),
            reason="",
        )
    assert error.value.reason_code == "reason_required"


def test_a_host_agent_cannot_issue_an_operator_correction(
    service: TaskStateService,
) -> None:
    start(service)

    with pytest.raises(CapabilityDenied):
        service.correct(
            SCOPE, "task-1",
            propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect")),
            reason="trying to self-authorize",
        )


def test_a_correction_is_recorded_as_its_own_step_kind(
    service: TaskStateService,
) -> None:
    start(service)
    service.correct(
        SCOPE, "task-1",
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            actor_role=ActorRole.OPERATOR, assurance=Assurance.OPERATOR_CONFIRMED,
        ),
        reason="Phase was recorded wrongly",
    )
    assert service.store.list_task_steps("task-1")[-1]["step_kind"] == (
        "operator_correction"
    )


# --- provenance -------------------------------------------------------------


def test_a_transition_records_field_and_status_provenance(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                          status=ItemStatus.COMPLETED),
            evidence=(EvidenceRef(kind="tool_call", reference_id="call-1"),),
        )
    )
    rows = service.store.list_task_provenance("task-1")
    at_two = [row for row in rows if row["revision"] == 2]

    assert {row["target_kind"] for row in at_two} == {"transition", "field", "status"}
    status_row = next(row for row in at_two if row["target_kind"] == "status")
    assert status_row["target_id"] == "item-1"
    assert status_row["superseded_revision"] == 1
    assert status_row["evidence"][0]["reference_id"] == "call-1"


def test_an_honest_assurance_is_carried_into_provenance(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                          status=ItemStatus.COMPLETED,
                          assurance=Assurance.HOST_REPORTED),
        )
    )
    status_row = next(
        row
        for row in service.store.list_task_provenance("task-1", target_kind="status")
        if row["target_id"] == "item-1"
    )
    assert status_row["assurance"] == "host_reported", (
        "a host-reported tool result is not independently verified"
    )


# --- crash recovery ---------------------------------------------------------


def test_a_failure_mid_commit_leaves_no_partial_revision(
    tmp_path: Path, clock: FixedUtcClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(tmp_path / "tasks.db")
    service = TaskStateService(store, clock=clock)
    try:
        start(service)
        original = store.insert_task_step

        def explode(*args, **kwargs):
            raise RuntimeError("simulated crash after the revision was written")

        monkeypatch.setattr(store, "insert_task_step", explode)
        with pytest.raises(RuntimeError):
            service.submit(
                propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
            )
        monkeypatch.setattr(store, "insert_task_step", original)

        # The whole commit rolled back: no orphan revision, head unchanged.
        assert [row["revision"] for row in store.list_task_revisions("task-1")] == [1]
        assert service.get(SCOPE, "task-1").state.revision == 1
        assert store.find_task_proposal("task-1", "delta-1") is None
    finally:
        store.close()


def test_state_survives_a_restart_byte_for_byte(
    tmp_path: Path, clock: FixedUtcClock
) -> None:
    path = tmp_path / "tasks.db"
    store = SQLiteStore(path)
    service = TaskStateService(store, clock=clock)
    try:
        start(service)
        service.submit(
            propose(
                TaskOperation(kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                              status=ItemStatus.COMPLETED),
            )
        )
        before = service.get(SCOPE, "task-1").state
    finally:
        store.close()

    reopened_store = SQLiteStore(path)
    try:
        after = TaskStateService(
            reopened_store, clock=FixedUtcClock(MOMENT)
        ).get(SCOPE, "task-1").state
        assert after.canonical_bytes() == before.canonical_bytes()
        assert after.state_digest() == before.state_digest()
    finally:
        reopened_store.close()


# --- the checked-in fixture -------------------------------------------------


def test_the_deterministic_fixture_workflow_behaves_as_recorded(
    tmp_path: Path, clock: FixedUtcClock
) -> None:
    """Replays `tests/fixtures/task_state/general-v1.json` step by step."""
    from atmem.task_state.policy import evaluate_completion

    path = tmp_path / "tasks.db"
    store = SQLiteStore(path)
    service = TaskStateService(store, clock=clock)
    scope = AuthorityScope(**FIXTURE["scope"])
    task = FIXTURE["task"]

    try:
        view = service.start(
            TaskStartRequest(
                task_id=task["task_id"], scope=scope, profile_id="general",
                profile_version=FIXTURE["profile_version"], goal=task["goal"],
                actor="operator@example.com", actor_role=ActorRole.OPERATOR,
                idempotency_key="fixture-start",
                constraints=tuple(task["constraints"]),
                sources_to_inspect=tuple(task["sources_to_inspect"]),
            ),
            items=tuple(
                TaskItem(
                    item_id=row["item_id"], kind=row["kind"], title=row["title"],
                    depends_on=tuple(row.get("depends_on") or ()),
                    required=bool(row.get("required")),
                )
                for row in FIXTURE["items"]
            ),
        )

        for index, step in enumerate(FIXTURE["sequence"]):
            expect = step["expect"]
            if step.get("completion_request"):
                allowed, _, guard = evaluate_completion(view.state, view.profile)
                assert allowed is expect["completion_allowed"], step["label"]
                blockers = list(guard.blocking_item_ids) if guard else []
                assert blockers == expect["completion_blockers"], step["label"]
                continue

            clock.advance(minutes=1)
            decision = service.submit(
                TaskStateProposal(
                    proposal_id=f"proposal-{index}", task_id=task["task_id"],
                    scope=scope, base_revision=view.state.revision,
                    idempotency_key=f"fixture-delta-{index}", actor="agent",
                    actor_role=ActorRole.HOST_AGENT,
                    assurance=Assurance.HOST_REPORTED,
                    operations=tuple(
                        TaskOperation(
                            kind=OperationKind(row["kind"]),
                            item_id=row.get("item_id"),
                            constraint_id=row.get("constraint_id"),
                            source_id=row.get("source_id"),
                            phase=row.get("phase"),
                            status=(
                                ItemStatus(row["status"]) if row.get("status") else None
                            ),
                            reason=row.get("reason"),
                        )
                        for row in step["operations"]
                    ),
                )
            )
            assert decision.outcome.value == expect["outcome"], step["label"]
            if "reason_codes" in expect:
                assert list(decision.reason_codes) == expect["reason_codes"], step["label"]
            view = service.get(scope, task["task_id"])
            assert view.state.revision == expect["revision"], step["label"]
            for key in ("ready_items", "blocked_items", "remaining_items"):
                if key in expect:
                    assert view.summary[key] == expect[key], (step["label"], key)
    finally:
        store.close()

    reopened_store = SQLiteStore(path)
    try:
        restarted = TaskStateService(
            reopened_store, clock=FixedUtcClock(MOMENT)
        ).get(scope, task["task_id"])
        expected = FIXTURE["after_restart"]
        assert restarted.state.revision == expected["revision"]
        assert restarted.state.lifecycle.value == expected["lifecycle"]
        assert restarted.summary["completed_items"] == expected["completed_items"]
        assert restarted.summary["blocked_items"] == expected["blocked_items"]
        assert restarted.summary["remaining_items"] == expected["remaining_items"]
    finally:
        reopened_store.close()


# --- deletion ---------------------------------------------------------------


def test_forgetting_a_task_removes_it_and_returns_a_receipt(
    service: TaskStateService,
) -> None:
    start(service)
    service.submit(propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect")))

    receipt = service.forget(
        SCOPE, "task-1", actor="admin", actor_role=ActorRole.ADMINISTRATOR
    )

    assert receipt["deleted"] is True
    assert receipt["revisions_removed"] == 2
    assert receipt["goal_sha256"].startswith("sha256:")
    assert "goal" not in receipt, "a receipt keeps a digest, not the content"
    with pytest.raises(TaskStateError):
        service.get(SCOPE, "task-1")


def test_only_a_role_with_deletion_capability_may_forget(
    service: TaskStateService,
) -> None:
    start(service)

    with pytest.raises(CapabilityDenied):
        service.forget(
            SCOPE, "task-1", actor="op", actor_role=ActorRole.OPERATOR
        )
    assert service.get(SCOPE, "task-1").state.revision == 1
