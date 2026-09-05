"""The trusted clock every task-state timestamp flows through."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from atmem.core.time import (
    DEFAULT_CLOCK,
    FixedUtcClock,
    SystemUtcClock,
    TrustedUtcClock,
    elapsed_ms,
    from_iso,
    require_utc,
    to_iso,
)


UTC = timezone.utc
MOMENT = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


def test_system_clock_returns_aware_utc() -> None:
    value = SystemUtcClock().now()

    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)
    assert isinstance(SystemUtcClock(), TrustedUtcClock)
    assert isinstance(DEFAULT_CLOCK, TrustedUtcClock)


def test_fixed_clock_only_moves_when_told() -> None:
    clock = FixedUtcClock(MOMENT)

    assert clock.now() == MOMENT
    assert clock.now() == MOMENT, "a fixed clock must not drift between reads"
    assert clock.advance(hours=2) == MOMENT + timedelta(hours=2)
    assert clock.now() == MOMENT + timedelta(hours=2)
    assert isinstance(clock, TrustedUtcClock)


def test_a_trusted_clock_cannot_run_backwards() -> None:
    clock = FixedUtcClock(MOMENT)

    with pytest.raises(ValueError, match="backwards"):
        clock.advance(hours=-1)
    with pytest.raises(ValueError, match="backwards"):
        clock.set(MOMENT - timedelta(seconds=1))
    assert clock.now() == MOMENT


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 9, 5, 12, 0),
        datetime(2026, 9, 5, 12, 0, tzinfo=timezone(timedelta(hours=10))),
        datetime(2026, 9, 5, 12, 0, tzinfo=timezone(timedelta(hours=-5))),
    ],
)
def test_naive_and_offset_times_are_refused(value: datetime) -> None:
    with pytest.raises(ValueError):
        require_utc("value", value)
    with pytest.raises(ValueError):
        FixedUtcClock(value)


def test_non_datetime_values_are_refused() -> None:
    with pytest.raises(TypeError):
        require_utc("value", "2026-09-05T12:00:00+00:00")


def test_iso_round_trip_preserves_the_instant() -> None:
    text = to_iso(MOMENT)

    assert text == "2026-09-05T12:00:00+00:00"
    assert from_iso(text) == MOMENT
    assert from_iso("2026-09-05T12:00:00Z") == MOMENT


def test_parsing_refuses_a_naive_stored_timestamp() -> None:
    with pytest.raises(ValueError, match="naive"):
        from_iso("2026-09-05T12:00:00")
    with pytest.raises(ValueError):
        from_iso("")


def test_elapsed_milliseconds_are_whole_and_never_negative() -> None:
    later = MOMENT + timedelta(milliseconds=1500)

    assert elapsed_ms(MOMENT, later) == 1500
    assert elapsed_ms(later, MOMENT) == 0, "clock skew must not produce negative age"
    assert elapsed_ms(MOMENT, MOMENT) == 0
