"""Independent evidence-pool definitions and quotas."""

from __future__ import annotations

from dataclasses import dataclass


POOL_KINDS = (
    "raw_state", "transition", "fact", "entity", "procedure", "rule", "gotcha", "premise"
)


@dataclass(frozen=True, slots=True)
class PoolBudget:
    # Full histories need enough independent nominations to keep a relevant
    # episode in play before semantic/temporal fusion and packing.  This is a
    # candidate budget, not a context budget: packing still enforces the
    # request's single byte ceiling.
    per_pool: int = 32
    total_units: int = 200

    def __post_init__(self) -> None:
        if self.per_pool <= 0 or self.total_units <= 0:
            raise ValueError("pool budgets must be positive")
