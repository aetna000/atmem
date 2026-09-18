"""Research dispatch policies; service units are seconds, never task counts.

All tasks are atomic/non-preemptible. This module provides queue order only:
it makes no authorization, delivery, deadline-enforcement or rollback promise.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Work:
    ordinal: int
    arrival: float
    kind: str
    size: int
    deadline: float | None = None

    def __post_init__(self):
        if self.kind not in ("recall", "write", "artifact"):
            raise ValueError("unknown work kind")
        if type(self.ordinal) is not int or self.ordinal < 0 or type(self.size) is not int or self.size < 0:
            raise ValueError("ordinal and size must be nonnegative integers")
        if not math.isfinite(self.arrival) or self.arrival < 0:
            raise ValueError("invalid arrival")
        if self.deadline is not None and (not math.isfinite(self.deadline) or self.deadline < self.arrival):
            raise ValueError("invalid deadline")

    @property
    def bulk(self) -> bool:
        return self.kind != "recall"

    @property
    def cost_key(self) -> str:
        return f"{self.kind}:{'large' if self.size >= 65536 else 'small'}"


class Scheduler:
    """Shortest estimated job with measured-service debt for oldest work.

    Debt accrues only for known queued contenders at dispatch. Arrivals during
    an atomic task are seen at the next dispatch. Overservice credit is capped
    at 5ms to prevent one large operation buying a long starvation interval.
    Debt payments precede deadline preferences. No finite wall-time bound follows
    without a bound on task service and offered load.
    """
    POLICIES = ("fifo", "legacy", "homa", "fair")

    def __init__(self, policy: str, estimates: dict[str, float], *,
                 fifo_fraction: float = .05, bulk_fraction: float = .4,
                 credit_cap_s: float = .005):
        if policy not in self.POLICIES:
            raise ValueError("unknown policy")
        for value in (fifo_fraction, bulk_fraction):
            if not math.isfinite(value) or not 0 < value < 1:
                raise ValueError("fractions must be finite and inside (0,1)")
        if not math.isfinite(credit_cap_s) or credit_cap_s <= 0:
            raise ValueError("credit cap must be positive and finite")
        if not estimates or any(not math.isfinite(v) or v <= 0 for v in estimates.values()):
            raise ValueError("estimates must be positive and finite")
        self.policy, self.estimates = policy, dict(estimates)
        self.fifo_fraction, self.bulk_fraction = fifo_fraction, bulk_fraction
        self.credit_cap = credit_cap_s
        self.oldest_debt = self.bulk_debt = 0.0
        self.count = 0
        self._active: tuple[int, bool, bool, bool] | None = None

    def estimate(self, job: Work) -> float:
        return self.estimates.get(job.cost_key, self.estimates.get(job.kind, .02))

    def pick(self, queue: list[Work], now: float) -> tuple[int, str]:
        if not queue or self._active is not None:
            raise ValueError("dispatch needs queued work and no active task")
        oldest = min(range(len(queue)), key=lambda i: (queue[i].arrival, queue[i].ordinal))
        bulk = [i for i, task in enumerate(queue) if task.bulk]
        contended = len(queue) > 1
        mixed = bool(bulk) and len(bulk) != len(queue)
        if not contended:
            self.oldest_debt = 0
        if not mixed:
            self.bulk_debt = 0
        reason = self.policy
        if self.policy == "fifo":
            selected = oldest
        elif self.policy == "legacy":
            candidates = bulk if self.count % 5 == 4 and bulk else list(range(len(queue)))
            fixed = {"artifact": .004, "recall": .012, "write": .040}
            selected = min(candidates, key=lambda i: (
                queue[i].deadline is None, queue[i].deadline or math.inf,
                fixed[queue[i].kind], queue[i].arrival, queue[i].ordinal))
        elif self.oldest_debt > 0:
            selected, reason = oldest, "oldest_service_debt"
        elif self.policy == "fair" and mixed and self.bulk_debt > 0:
            selected = min(bulk, key=lambda i: (queue[i].arrival, queue[i].ordinal))
            reason = "bulk_service_debt"
        else:
            # Only trusted fixture deadlines near predicted completion override
            # shortest-job ordering; unlike legacy, size normally determines rank.
            urgent = [i for i, task in enumerate(queue)
                      if task.deadline is not None and task.deadline - now <= self.estimate(task)]
            if urgent:
                selected = min(urgent, key=lambda i: (queue[i].deadline, queue[i].ordinal))
                reason = "urgent_deadline"
            else:
                selected = min(range(len(queue)), key=lambda i: (
                    self.estimate(queue[i]), queue[i].arrival, queue[i].ordinal))
                reason = "estimated_service"
        self._active = (queue[selected].ordinal, selected == oldest, contended, mixed)
        return selected, reason

    def finish(self, job: Work, service_s: float) -> None:
        if self._active is None or self._active[0] != job.ordinal:
            raise ValueError("completion does not match active task")
        if not math.isfinite(service_s) or service_s < 0:
            raise ValueError("invalid measured service")
        _, paid_oldest, contended, mixed = self._active
        if contended:
            self.oldest_debt = max(-self.credit_cap, self.oldest_debt +
                                   (self.fifo_fraction - int(paid_oldest)) * service_s)
        if mixed:
            self.bulk_debt = max(-self.credit_cap, self.bulk_debt +
                                 (self.bulk_fraction - int(job.bulk)) * service_s)
        # Same past-only estimator for every policy; no duration oracle.
        self.estimates[job.cost_key] = .8 * self.estimate(job) + .2 * max(service_s, .000001)
        self._active = None
        self.count += 1
