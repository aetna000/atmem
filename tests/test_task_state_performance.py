"""Local transition and context overhead, measured rather than asserted.

SC-007 claims a p95 below 25 ms for single-writer transition and context work
on the supported SQLite profile, excluding model, tool, and verifier execution.
That is a claim about AtMem's own overhead, so this suite measures exactly
that: no concurrency, no network, no optional providers.

Contended correctness is a different property and is measured separately in
`test_task_state_service.py`; nothing here makes a timing claim about it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time

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
from atmem.core.time import FixedUtcClock, to_iso
from atmem.store.sqlite import SQLiteStore
from atmem.task_state import GENERAL_V1
from atmem.task_state.context import prepare
from atmem.task_state.service import TaskStateService


SCOPE = AuthorityScope("subject-1", "agent-1", "workspace-1")
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
SAMPLES = 1_000
P95_BUDGET_MS = 25.0


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _report(name: str, durations: list[float]) -> dict[str, float]:
    return {
        "operation": name,
        "samples": len(durations),
        "p50_ms": round(_percentile(durations, 0.50), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "max_ms": round(max(durations), 3),
    }


@pytest.fixture()
def service(tmp_path: Path) -> TaskStateService:
    store = SQLiteStore(tmp_path / "tasks.db")
    engine = TaskStateService(store, clock=FixedUtcClock(MOMENT))
    try:
        yield engine
    finally:
        store.close()


def _start(service: TaskStateService, *, items: int = 5) -> None:
    service.start(
        TaskStartRequest(
            task_id="task-1", scope=SCOPE, profile_id="general",
            profile_version="general-v1", goal="Measure the overhead",
            actor="operator", actor_role=ActorRole.OPERATOR,
            idempotency_key="start-1",
        ),
        items=tuple(
            TaskItem(item_id=f"item-{index}", kind="step", title=f"Step {index}")
            for index in range(items)
        ),
    )


def test_transition_commit_p95_is_within_budget(
    service: TaskStateService, capsys: pytest.CaptureFixture[str]
) -> None:
    """Single writer, no contention: this is AtMem's own commit overhead."""
    _start(service, items=5)
    durations: list[float] = []

    for index in range(SAMPLES):
        revision = service.get(SCOPE, "task-1", evaluate_expiry=False).state.revision
        proposal = TaskStateProposal(
            proposal_id=f"proposal-{index}", task_id="task-1", scope=SCOPE,
            base_revision=revision, idempotency_key=f"delta-{index}",
            actor="agent", actor_role=ActorRole.HOST_AGENT,
            assurance=Assurance.HOST_REPORTED,
            operations=(
                TaskOperation(
                    kind=OperationKind.SET_ITEM_STATUS,
                    item_id=f"item-{index % 5}",
                    status=(
                        ItemStatus.RUNNING if index % 2 == 0 else ItemStatus.READY
                    ),
                ),
            ),
        )
        started = time.perf_counter()
        decision = service.submit(proposal)
        durations.append((time.perf_counter() - started) * 1000)
        assert decision.outcome in {StepOutcome.ACCEPTED, StepOutcome.NO_CHANGE}

    report = _report("transition_commit", durations)
    with capsys.disabled():
        print(f"\n{report}")
    assert report["samples"] == SAMPLES
    assert report["p95_ms"] < P95_BUDGET_MS, report


def test_context_preparation_p95_is_within_budget(
    service: TaskStateService, capsys: pytest.CaptureFixture[str]
) -> None:
    _start(service, items=20)
    view = service.get(SCOPE, "task-1")
    durations: list[float] = []

    for index in range(SAMPLES):
        started = time.perf_counter()
        package = prepare(
            view.state, GENERAL_V1, scope=SCOPE,
            context_id=f"context-{index}", prepared_at=to_iso(MOMENT),
            budget_chars=8_000,
        )
        durations.append((time.perf_counter() - started) * 1000)
        assert package.context_sha256

    report = _report("context_preparation", durations)
    with capsys.disabled():
        print(f"\n{report}")
    assert report["p95_ms"] < P95_BUDGET_MS, report


def test_reading_a_task_stays_cheap_as_history_grows(
    service: TaskStateService, capsys: pytest.CaptureFixture[str]
) -> None:
    """A long-running task must not get slower to read every revision."""
    _start(service, items=5)
    for index in range(200):
        revision = service.get(SCOPE, "task-1", evaluate_expiry=False).state.revision
        service.submit(
            TaskStateProposal(
                proposal_id=f"proposal-{index}", task_id="task-1", scope=SCOPE,
                base_revision=revision, idempotency_key=f"delta-{index}",
                actor="agent", actor_role=ActorRole.HOST_AGENT,
                assurance=Assurance.HOST_REPORTED,
                operations=(
                    TaskOperation(
                        kind=OperationKind.SET_ITEM_STATUS,
                        item_id=f"item-{index % 5}",
                        status=(
                            ItemStatus.RUNNING if index % 2 == 0 else ItemStatus.READY
                        ),
                    ),
                ),
            )
        )

    durations: list[float] = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        service.get(SCOPE, "task-1", evaluate_expiry=False)
        durations.append((time.perf_counter() - started) * 1000)

    report = _report("task_read_after_200_revisions", durations)
    with capsys.disabled():
        print(f"\n{report}")
    assert report["p95_ms"] < P95_BUDGET_MS, report


def test_the_head_read_uses_an_index_rather_than_a_scan(
    service: TaskStateService,
) -> None:
    """A query plan check, so a regression shows up as a plan change."""
    _start(service)
    plan = service.store._conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM governed_tasks "
        "WHERE task_id = ? AND subject_id = ? AND agent_id = ? AND workspace_id = ?",
        ("task-1", SCOPE.subject_id, SCOPE.agent_id, SCOPE.workspace_id),
    ).fetchall()
    detail = " ".join(str(row["detail"]) for row in plan)

    assert "SCAN" not in detail.upper(), detail
    assert "governed_tasks" in detail


def test_the_revision_lookup_uses_its_primary_key(
    service: TaskStateService,
) -> None:
    _start(service)
    plan = service.store._conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM governed_task_revisions "
        "WHERE task_id = ? AND revision = ?",
        ("task-1", 1),
    ).fetchall()
    detail = " ".join(str(row["detail"]) for row in plan)

    assert "SCAN" not in detail.upper(), detail


def test_the_expiry_scan_uses_its_index(service: TaskStateService) -> None:
    _start(service)
    plan = service.store._conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM governed_tasks "
        "WHERE lifecycle IN ('open', 'paused') "
        "ORDER BY created_at_utc ASC, task_id ASC LIMIT 200"
    ).fetchall()
    detail = " ".join(str(row["detail"]) for row in plan).upper()

    assert "IDX_GOVERNED_TASKS_EXPIRY" in detail or "USING INDEX" in detail, detail


def test_the_repeat_counter_uses_its_fingerprint_index(
    service: TaskStateService,
) -> None:
    _start(service)
    plan = service.store._conn.execute(
        "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM governed_task_steps "
        "WHERE task_id = ? AND action_fingerprint = ? AND recorded_at_utc >= ?",
        ("task-1", "sha256:x", to_iso(MOMENT)),
    ).fetchall()
    detail = " ".join(str(row["detail"]) for row in plan).upper()

    assert "SCAN" not in detail, detail
