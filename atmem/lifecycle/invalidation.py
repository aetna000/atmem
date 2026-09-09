"""Ordered registry for graph/vector/cache/context/media invalidation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Invalidator = Callable[[str, str], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class RegisteredInvalidator:
    name: str
    order: int
    callback: Invalidator


class InvalidationRegistry:
    def __init__(self) -> None:
        self._items: dict[str, RegisteredInvalidator] = {}

    def register(self, name: str, callback: Invalidator, *, order: int = 100) -> None:
        if not name.strip() or name in self._items:
            raise ValueError(f"invalid or duplicate invalidator: {name!r}")
        self._items[name] = RegisteredInvalidator(name, int(order), callback)

    def unregister(self, name: str) -> None:
        self._items.pop(name, None)

    def invalidate(self, subject_id: str, record_id: str) -> dict[str, Any]:
        outcomes: dict[str, Any] = {}
        verified = True
        for item in sorted(self._items.values(), key=lambda value: (value.order, value.name)):
            try:
                outcome = dict(item.callback(subject_id, record_id))
            except Exception as exc:
                outcome = {"verified": False, "reason": f"{type(exc).__name__}: {exc}"}
            outcomes[item.name] = outcome
            verified = verified and outcome.get("verified") is True
        return {"format": "atmem-invalidation-result-v1", "verified": verified, "consumers": outcomes}

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))


invalidation_registry = InvalidationRegistry()
