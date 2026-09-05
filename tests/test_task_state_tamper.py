"""Adversarial paths: forged scope, stale revisions, and overclaimed outcomes.

These are the attempts that would matter if they worked. Each one is checked
for two things: the refusal itself, and that the head is byte-for-byte unchanged
afterwards. A refusal that still moved something is not a refusal.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
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
from atmem.task_state.policy import evaluate
from atmem.task_state.service import TaskStateError, TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def service(tmp_path: Path) -> TaskStateService:
    store = SQLiteStore(tmp_path / "tasks.db")
    engine = TaskStateService(store, clock=FixedUtcClock(MOMENT))
    engine.start(
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="general-v1", goal="Ship the migration",
            actor="operator", actor_role=ActorRole.OPERATOR,
            idempotency_key="start-1",
        ),
        items=(
            TaskItem(item_id="item-1", kind="step", title="First", required=True),
            TaskItem(item_id="item-2", kind="step", title="Second",
                     depends_on=("item-1",)),
        ),
    )
    try:
        yield engine
    finally:
        store.close()


def propose(*operations, **overrides) -> TaskStateProposal:
    base = dict(
        proposal_id="proposal-1", task_id="task-1", scope=SCOPE, base_revision=1,
        idempotency_key="delta-1", actor="attacker",
        actor_role=ActorRole.HOST_AGENT, assurance=Assurance.HOST_REPORTED,
    )
    base.update(overrides)
    return TaskStateProposal(operations=tuple(operations), **base)


def unchanged(service: TaskStateService) -> bytes:
    return service.get(SCOPE, "task-1").state.canonical_bytes()


# --- forged scope -----------------------------------------------------------


@pytest.mark.parametrize(
    "forged",
    [
        AuthorityScope("subject-2", "agent-1", "workspace-1"),
        AuthorityScope("subject-1", "agent-2", "workspace-1"),
        AuthorityScope("subject-1", "agent-1", "workspace-2"),
    ],
)
def test_a_forged_scope_never_reaches_the_task(
    service: TaskStateService, forged: AuthorityScope
) -> None:
    before = unchanged(service)

    with pytest.raises(TaskStateError) as error:
        service.submit(
            propose(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
                scope=forged,
            )
        )

    assert error.value.reason_code == "task_not_eligible"
    assert unchanged(service) == before


def test_a_proposal_naming_a_different_task_is_refused(
    service: TaskStateService,
) -> None:
    before = unchanged(service)
    with pytest.raises(TaskStateError):
        service.submit(
            propose(
                TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
                task_id="task-elsewhere",
            )
        )
    assert unchanged(service) == before


# --- stale and out-of-order -------------------------------------------------


def test_a_stale_proposal_cannot_overwrite_newer_work(
    service: TaskStateService,
) -> None:
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )
    after_first = unchanged(service)

    stale = service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="execute"),
            proposal_id="proposal-2", idempotency_key="delta-2", base_revision=1,
        )
    )

    assert stale.outcome is StepOutcome.CONFLICT
    assert unchanged(service) == after_first


def test_a_proposal_claiming_a_future_revision_is_refused(
    service: TaskStateService,
) -> None:
    before = unchanged(service)
    result = service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            base_revision=99,
        )
    )
    assert result.outcome is StepOutcome.CONFLICT
    assert unchanged(service) == before


def test_a_delayed_tool_result_arriving_after_a_task_ended_is_refused(
    service: TaskStateService,
) -> None:
    service.cancel(SCOPE, "task-1", actor="operator",
                   actor_role=ActorRole.OPERATOR, reason="abandoned")
    before = unchanged(service)

    late = service.submit(
        propose(
            TaskOperation(
                kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                status=ItemStatus.COMPLETED,
            ),
            base_revision=2,
        )
    )

    assert late.outcome is StepOutcome.REJECTED
    assert late.reason_codes == ("task_is_terminal",)
    assert unchanged(service) == before


# --- forged payloads --------------------------------------------------------


def test_reusing_an_idempotency_key_with_a_different_delta_fails_closed(
    service: TaskStateService,
) -> None:
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )
    after = unchanged(service)

    with pytest.raises(TaskStateError, match="different delta"):
        service.submit(
            propose(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                    status=ItemStatus.COMPLETED,
                ),
                base_revision=2, idempotency_key="delta-1",
            )
        )
    assert unchanged(service) == after


def test_a_proposal_cannot_widen_a_locked_schema(
    service: TaskStateService,
) -> None:
    service.submit(
        propose(
            TaskOperation(kind=OperationKind.LOCK_SCHEMA),
            actor_role=ActorRole.ADMINISTRATOR,
            assurance=Assurance.OPERATOR_CONFIRMED,
        ),
        allow_privileged=True,
    )
    before = unchanged(service)

    result = service.submit(
        propose(
            TaskOperation(
                kind=OperationKind.ADD_ITEM, item_id="smuggled",
                kind_label="step", text="An item nobody approved",
            ),
            proposal_id="proposal-2", idempotency_key="delta-2", base_revision=2,
        )
    )

    assert result.outcome is StepOutcome.REJECTED
    assert result.reason_codes == ("schema_is_locked",)
    assert unchanged(service) == before


def test_an_ordinary_agent_cannot_lock_the_schema_itself(
    service: TaskStateService,
) -> None:
    result = service.submit(propose(TaskOperation(kind=OperationKind.LOCK_SCHEMA)))
    assert result.reason_codes == ("capability_denied",)


def test_a_dependency_cannot_be_bypassed_by_ordering(
    service: TaskStateService,
) -> None:
    """Completing a dependent before its dependency is refused, not reordered."""
    before = unchanged(service)
    result = service.submit(
        propose(
            TaskOperation(
                kind=OperationKind.SET_ITEM_STATUS, item_id="item-2",
                status=ItemStatus.COMPLETED,
            )
        )
    )

    assert result.reason_codes == ("dependency_unsatisfied",)
    assert unchanged(service) == before


def test_required_work_cannot_be_skipped_without_permission(
    service: TaskStateService,
) -> None:
    before = unchanged(service)
    result = service.submit(
        propose(
            TaskOperation(
                kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                status=ItemStatus.SKIPPED, reason="I would rather not",
            )
        )
    )

    assert result.reason_codes == ("capability_denied",)
    assert unchanged(service) == before


def test_completion_cannot_be_reached_by_jumping_the_phase(
    service: TaskStateService,
) -> None:
    before = unchanged(service)
    result = service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="complete"))
    )

    assert result.outcome is StepOutcome.REJECTED
    assert unchanged(service) == before


# --- overclaimed outcomes ---------------------------------------------------


@pytest.mark.parametrize(
    ("role", "claim"),
    [
        (ActorRole.ATBOT_INTELLIGENCE, Assurance.INDEPENDENTLY_VERIFIED),
        (ActorRole.ATBOT_INTELLIGENCE, Assurance.OPERATOR_CONFIRMED),
        (ActorRole.ATBOT_INTELLIGENCE, Assurance.HOST_REPORTED),
        (ActorRole.HOST_AGENT, Assurance.INDEPENDENTLY_VERIFIED),
        (ActorRole.HOST_AGENT, Assurance.OPERATOR_CONFIRMED),
        (ActorRole.OPERATOR, Assurance.INDEPENDENTLY_VERIFIED),
    ],
)
def test_an_actor_cannot_claim_assurance_above_its_ceiling(
    service: TaskStateService, role: ActorRole, claim: Assurance
) -> None:
    before = unchanged(service)
    result = service.submit(
        propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            actor_role=role, assurance=claim,
        )
    )

    assert result.reason_codes == ("assurance_ceiling_exceeded",)
    assert unchanged(service) == before


def test_a_model_cannot_complete_work_on_its_own_say_so(
    service: TaskStateService,
) -> None:
    before = unchanged(service)
    result = service.submit(
        propose(
            TaskOperation(
                kind=OperationKind.SET_ITEM_STATUS, item_id="item-1",
                status=ItemStatus.COMPLETED,
            ),
            actor_role=ActorRole.ATBOT_INTELLIGENCE,
            assurance=Assurance.MODEL_INTERPRETED,
            evidence=(),
        )
    )

    assert result.reason_codes == ("evidence_required",)
    assert unchanged(service) == before


def test_unknown_evidence_is_refused_by_policy() -> None:
    from atmem.task_state import GENERAL_V1
    from atmem.contracts.task_state import TaskState

    state = TaskState(
        task_id="task-1", scope=SCOPE, revision=1, lifecycle=TaskLifecycle.OPEN,
        phase="plan", goal="G", profile_id="general", profile_version="general-v1",
    )
    result = evaluate(
        state=state, profile=GENERAL_V1,
        proposal=propose(
            TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"),
            evidence=(EvidenceRef(kind="tool_call", reference_id="never-happened"),),
        ),
        now_iso="2026-09-05T12:00:00+00:00",
        known_evidence_ids=frozenset({"call-1"}),
    )
    assert result.reason_codes == ("unknown_evidence",)


# --- tampering with what is already stored ---------------------------------


def test_a_committed_revision_cannot_be_rewritten(
    service: TaskStateService,
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        service.store._conn.execute(
            "UPDATE governed_task_revisions SET state = '{}' WHERE task_id = 'task-1'"
        )


def test_provenance_cannot_be_rewritten(service: TaskStateService) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        service.store._conn.execute(
            "UPDATE governed_task_provenance "
            "SET assurance = 'independently_verified'"
        )


def test_a_forked_revision_chain_is_impossible(service: TaskStateService) -> None:
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="collect"))
    )

    with pytest.raises(sqlite3.IntegrityError):
        service.store.insert_task_revision(
            task_id="task-1", revision=99, parent_revision=1,
            state={"forked": True}, state_sha256="sha256:" + "f" * 64,
            semantic_sha256="sha256:" + "e" * 64, actor="attacker",
            actor_role="host_agent", reason_codes=["transition_accepted"],
            evidence=[], created_at_utc="2026-09-05T12:00:00+00:00",
        )


def test_tampering_with_the_head_is_visible_to_integrity_checks(
    service: TaskStateService,
) -> None:
    from atmem.task_state.observability import TaskObservability

    service.store._conn.execute(
        "UPDATE governed_tasks SET head_revision = 42 WHERE task_id = 'task-1'"
    )
    integrity = TaskObservability(
        service.store, clock=service.clock
    ).snapshot(SCOPE)["integrity"]

    assert integrity["valid"] is False
    assert any("head does not match" in row for row in integrity["problems"])


def test_every_refusal_is_still_recorded_as_a_decision(
    service: TaskStateService,
) -> None:
    """A rejected attempt leaves evidence that it was attempted."""
    service.submit(
        propose(TaskOperation(kind=OperationKind.SET_PHASE, phase="complete"))
    )
    step = service.store.list_task_steps("task-1")[-1]

    assert step["outcome"] == "rejected"
    assert step["actor"] == "attacker"
    assert step["reason_codes"]
    assert step["resulting_revision"] is None
