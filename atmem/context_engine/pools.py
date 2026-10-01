"""Independent evidence-pool definitions and quotas."""

from __future__ import annotations

from dataclasses import dataclass


POOL_KINDS = (
    "raw_state", "transition", "fact", "entity", "procedure", "rule", "gotcha", "premise"
)


@dataclass(frozen=True, slots=True)
class PoolBudget:
    per_pool: int = 3
    total_units: int = 24

    def __post_init__(self) -> None:
        if self.per_pool <= 0 or self.total_units <= 0:
            raise ValueError("pool budgets must be positive")
