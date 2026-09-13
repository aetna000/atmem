"""Retention helpers that never silently turn deleted evidence into certainty."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def retention_cutoff(*, days: int, now: datetime | None = None) -> str:
    if days < 1:
        raise ValueError("retention days must be positive")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("retention time must be timezone-aware")
    return (current.astimezone(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
