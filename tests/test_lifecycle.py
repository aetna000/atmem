from datetime import datetime, timezone

import pytest

from atmem import Memory
from atmem.lifecycle import LifecycleService, LifecycleState, LifecycleTransition
from atmem.lifecycle.invalidation import InvalidationRegistry


def test_transition_matrix_generation_and_invalidation() -> None:
    memory = Memory(":memory:")
    record = memory.remember("u", "My city is Sydney.")["records"][0]
    registry = InvalidationRegistry()
    registry.register("cache", lambda subject, record_id: {"verified": True, "subject_id": subject, "record_id": record_id})
    service = LifecycleService(memory.store, invalidators=registry)
    view = service.inspect("u", record["id"], evaluated_at="2026-09-09T00:00:00Z")
    assert view["eligible"]
    receipt = service.transition(LifecycleTransition(record["id"], "u", LifecycleState.ARCHIVED, 1, "owner", "retention", occurred_at="2026-09-09T00:00:01Z"))
    assert receipt.invalidations["verified"]
    assert not service.inspect("u", record["id"])["eligible"]
    with pytest.raises(RuntimeError, match="precondition"):
        service.transition(LifecycleTransition(record["id"], "u", LifecycleState.ACTIVE, 1, "owner", "stale"))
    memory.close()


def test_timezone_is_required() -> None:
    memory = Memory(":memory:")
    record = memory.remember("u", "My city is Sydney.")["records"][0]
    with pytest.raises(ValueError, match="timezone"):
        LifecycleService(memory.store).inspect("u", record["id"], evaluated_at="2026-09-09T00:00:00")
    memory.close()
