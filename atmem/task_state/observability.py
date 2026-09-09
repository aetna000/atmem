"""What is happening across governed tasks, without leaking what they say.

Observability here is deliberately content-free. Counts, reason codes, latency,
ages, and integrity are enough to run the system; goals, item titles, blocker
text, prompts, and tool payloads are not, and none of them appear in any
snapshot this module produces.

Everything is scope-filtered at the source, so an aggregate can never blend one
subject's work into another's totals.
"""

from __future__ import annotations

from typing import Any

from atmem.contracts import AuthorityScope
from atmem.contracts.task_state import (
    GuardType,
    ItemStatus,
    StepOutcome,
    TaskLifecycle,
)
from atmem.core.time import DEFAULT_CLOCK, TrustedUtcClock, elapsed_ms, from_iso, to_iso


class TaskObservability:
    """A read-only projection over governed task state."""

    def __init__(self, store: Any, *, clock: TrustedUtcClock | None = None) -> None:
        self.store = store
        self.clock = clock or DEFAULT_CLOCK

    def snapshot(
        self,
        scope: AuthorityScope | None = None,
        *,
        limit: int = 500,
    ) -> dict[str, Any]:
        """The overview level: counts, guards, fallback, integrity, freshness."""
        now = self.clock.now()
        tasks = self.store.list_tasks(
            subject_id=scope.subject_id if scope else None,
            agent_id=scope.agent_id if scope else None,
            workspace_id=scope.workspace_id if scope else None,
            lifecycles=None,
            limit=limit,
        )
        lifecycle_counts = {value.value: 0 for value in TaskLifecycle}
        outcome_counts = {value.value: 0 for value in StepOutcome}
        reason_counts: dict[str, int] = {}
        guard_counts = {value.value: 0 for value in GuardType}
        durations: list[int] = []
        prepared = exposed = withheld = 0
        stale_conflicts = 0
        fallback_steps = 0
        last_progress: str | None = None
        overdue: list[dict[str, Any]] = []

        for task in tasks:
            lifecycle_counts[str(task["lifecycle"])] += 1
            task_id = str(task["task_id"])

            for step in self.store.list_task_steps(task_id, limit=1000):
                outcome_counts[str(step["outcome"])] += 1
                durations.append(int(step["duration_ms"]))
                for reason in step["reason_codes"] or ():
                    reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
                    if reason == "stale_base_revision":
                        stale_conflicts += 1
                if str(step["step_kind"]).endswith("_fallback"):
                    fallback_steps += 1

            for delivery in self.store.list_task_deliveries(task_id, limit=1000):
                prepared += 1
                if str(delivery["disposition"]) == "injected":
                    if delivery["exposed"]:
                        exposed += 1
                else:
                    withheld += 1
                    for reason in delivery["reason_codes"] or ():
                        reason_counts[str(reason)] = (
                            reason_counts.get(str(reason), 0) + 1
                        )

            progressed = str(task["last_progress_at_utc"])
            if last_progress is None or progressed > last_progress:
                last_progress = progressed

            status = self._expiry_status(task, now)
            if status["overdue"]:
                overdue.append(
                    {
                        "task_id": task_id,
                        "reason": status["reason"],
                        "absolute_age_ms": status["absolute_age_ms"],
                        "no_progress_age_ms": status["no_progress_age_ms"],
                    }
                )

        bindings_active = bindings_revoked = 0
        if scope is not None:
            for row in self.store.list_session_bindings(
                subject_id=scope.subject_id,
                agent_id=scope.agent_id,
                workspace_id=scope.workspace_id,
                include_revoked=True,
            ):
                if row.get("revoked_at_utc"):
                    bindings_revoked += 1
                else:
                    bindings_active += 1

        return {
            "format": "atmem-task-observability-v1",
            "observed_at_utc": to_iso(now),
            "scope": scope.to_dict() if scope else None,
            "tasks": {
                "total": len(tasks),
                "by_lifecycle": lifecycle_counts,
                "open_or_paused": lifecycle_counts["open"] + lifecycle_counts["paused"],
            },
            "transitions": {
                "by_outcome": outcome_counts,
                "by_reason_code": dict(sorted(reason_counts.items())),
                "stale_revision_conflicts": stale_conflicts,
                "fallback_steps": fallback_steps,
            },
            "guards": guard_counts,
            "context": {
                "prepared": prepared,
                "exposed": exposed,
                "withheld": withheld,
            },
            "latency_ms": {
                "p50": _percentile(durations, 0.50),
                "p95": _percentile(durations, 0.95),
                "samples": len(durations),
            },
            "freshness": {
                "last_progress_at_utc": last_progress,
                "no_progress_age_ms": (
                    elapsed_ms(from_iso(last_progress), now) if last_progress else None
                ),
            },
            "overdue_tasks": overdue,
            # Bindings decide which conversations can reach a task at all, so
            # an operator asking "why is my agent getting nothing?" needs them
            # beside the delivery counters rather than in a separate view.
            "bindings": {
                "active": bindings_active,
                "revoked": bindings_revoked,
            },
            "integrity": self._integrity(tasks),
        }

    def task_detail(
        self, scope: AuthorityScope, task_id: str, *, limit: int = 200
    ) -> dict[str, Any]:
        """The task level: recent decisions and delivery dispositions."""
        task = self.store.get_task(
            subject_id=scope.subject_id, agent_id=scope.agent_id,
            workspace_id=scope.workspace_id, task_id=task_id,
        )
        if task is None:
            return {
                "format": "atmem-task-observability-detail-v1",
                "task_id": task_id,
                "found": False,
            }
        steps = self.store.list_task_steps(task_id, limit=limit)
        deliveries = self.store.list_task_deliveries(task_id, limit=limit)
        return {
            "format": "atmem-task-observability-detail-v1",
            "task_id": task_id,
            "found": True,
            "lifecycle": task["lifecycle"],
            "revision": task["head_revision"],
            "last_progress_at_utc": task["last_progress_at_utc"],
            "expiry": self._expiry_status(task, self.clock.now()),
            "recent_decisions": [
                {
                    "sequence": row["sequence"],
                    "step_kind": row["step_kind"],
                    "outcome": row["outcome"],
                    "reason_codes": row["reason_codes"],
                    "base_revision": row["base_revision"],
                    "resulting_revision": row["resulting_revision"],
                    "duration_ms": row["duration_ms"],
                    "recorded_at_utc": row["recorded_at_utc"],
                }
                for row in steps[-20:]
            ],
            "deliveries": [
                {
                    "sequence": row["sequence"],
                    "revision": row["revision"],
                    "disposition": row["disposition"],
                    "reason_codes": row["reason_codes"],
                    "exposed": row["exposed"],
                    "prepared_at_utc": row["prepared_at_utc"],
                }
                for row in deliveries[-20:]
            ],
        }

    def _expiry_status(self, task: dict[str, Any], now: Any) -> dict[str, Any]:
        rule = dict(task.get("expiry_rule") or {})
        created = from_iso(str(task["created_at_utc"]))
        progressed = from_iso(str(task["last_progress_at_utc"]))
        absolute_ms = elapsed_ms(created, now)
        paused_ms = int(task.get("no_progress_paused_ms") or 0)
        if task.get("paused_at_utc"):
            paused_ms += elapsed_ms(from_iso(str(task["paused_at_utc"])), now)
        no_progress_ms = max(0, elapsed_ms(progressed, now) - paused_ms)

        terminal = TaskLifecycle(str(task["lifecycle"])).terminal
        max_absolute = rule.get("max_absolute_age_ms")
        max_no_progress = rule.get("max_no_progress_age_ms")
        reason: str | None = None
        if not terminal:
            if max_absolute is not None and absolute_ms >= int(max_absolute):
                reason = "expired_absolute_age"
            elif max_no_progress is not None and no_progress_ms >= int(max_no_progress):
                reason = "expired_no_progress"
        return {
            "rule": rule,
            "absolute_age_ms": absolute_ms,
            "no_progress_age_ms": no_progress_ms,
            "paused_ms": paused_ms,
            "overdue": reason is not None,
            "reason": reason,
        }

    def _integrity(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """Check that every head has a revision and the chain has no gaps."""
        problems: list[str] = []
        for task in tasks:
            task_id = str(task["task_id"])
            revisions = self.store.list_task_revisions(task_id, limit=1000)
            numbers = [int(row["revision"]) for row in revisions]
            if not numbers:
                problems.append(f"{task_id}: no revisions")
                continue
            if numbers != list(range(1, len(numbers) + 1)):
                problems.append(f"{task_id}: revision chain has a gap")
            if int(task["head_revision"]) != max(numbers):
                problems.append(f"{task_id}: head does not match the latest revision")
        return {
            "valid": not problems,
            "checked_tasks": len(tasks),
            "problems": problems,
        }


def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]
