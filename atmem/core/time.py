"""One injectable source of trusted UTC time.

Expiry is a policy decision with real consequences: a task that passes its
threshold becomes terminal and stops informing the agent. That decision must be
reproducible and testable, which rules out scattered `datetime.now()` calls.

Every task-state timestamp flows through a `TrustedUtcClock`. Production uses
`SystemUtcClock`; tests inject `FixedUtcClock` and advance it deliberately.
Naive and non-UTC values are rejected at the boundary rather than silently
reinterpreted, because a timestamp that is wrong by a timezone offset is the
kind of bug that only shows up in someone else's timezone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class TrustedUtcClock(Protocol):
    """A source of aware UTC time that callers cannot silently substitute."""

    def now(self) -> datetime:
        """Return the current time as an aware UTC datetime."""
        ...


@dataclass(frozen=True, slots=True)
class SystemUtcClock:
    """The wall clock, read as aware UTC."""

    source: str = "system-utc-v1"

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(slots=True)
class FixedUtcClock:
    """A deterministic clock for tests; time moves only when told to."""

    current: datetime
    source: str = "fixed-utc-v1"

    def __post_init__(self) -> None:
        self.current = require_utc("current", self.current)

    def now(self) -> datetime:
        return self.current

    def advance(self, **delta: float) -> datetime:
        """Move the clock forward. Time never runs backwards here."""
        step = timedelta(**delta)
        if step < timedelta(0):
            raise ValueError("a trusted clock cannot move backwards")
        self.current = self.current + step
        return self.current

    def set(self, moment: datetime) -> datetime:
        value = require_utc("moment", moment)
        if value < self.current:
            raise ValueError("a trusted clock cannot move backwards")
        self.current = value
        return self.current


def require_utc(name: str, value: datetime) -> datetime:
    """Accept only an aware UTC datetime.

    A naive datetime is refused rather than assumed to be UTC: assuming is how
    a task silently expires hours early or late for a user in another zone.
    """
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be timezone-aware UTC, not naive")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be UTC, not offset {value.utcoffset()}")
    return value.astimezone(timezone.utc)


def to_iso(value: datetime) -> str:
    """Serialize an aware UTC datetime to a stable, sortable string."""
    return require_utc("value", value).isoformat().replace("+00:00", "+00:00")


def from_iso(value: str) -> datetime:
    """Parse a stored timestamp back into aware UTC, refusing naive text."""
    text = str(value).strip()
    if not text:
        raise ValueError("timestamp is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return require_utc("value", parsed)


def elapsed_ms(start: datetime, end: datetime) -> int:
    """Whole milliseconds between two trusted instants, never negative."""
    delta = require_utc("end", end) - require_utc("start", start)
    return max(0, int(delta.total_seconds() * 1000))


DEFAULT_CLOCK: TrustedUtcClock = SystemUtcClock()
