"""Scope-safe keys and final-reload checks for retrieval caches."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class RetrievalCacheKey:
    subject_id: str
    agent_id: str
    workspace_id: str
    generation: int
    epoch_id: str
    calibration_version: str
    query_sha256: str
    policy_sha256: str
    support_policy: str = "direct-only"
    topology_generation: int = 0
    model_sha256: str = "none"
    index_generation: str = "none"
    lifecycle_generation: int = 0
    deletion_generation: int = 0

    @classmethod
    def for_query(cls, *, query: str, **values: Any) -> "RetrievalCacheKey":
        return cls(query_sha256=sha256(query.encode("utf-8")).hexdigest(), **values)

    @property
    def digest(self) -> str:
        value = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(value.encode("utf-8")).hexdigest()


class RetrievalDecisionCache:
    """Small process-local cache; callers must final-reload selected records."""

    def __init__(self, max_entries: int = 256) -> None:
        self.max_entries = max(1, int(max_entries))
        self._values: dict[RetrievalCacheKey, Any] = {}

    def get(self, key: RetrievalCacheKey) -> Any | None:
        return self._values.get(key)

    def put(self, key: RetrievalCacheKey, value: Any) -> None:
        self._values[key] = value
        while len(self._values) > self.max_entries:
            self._values.pop(next(iter(self._values)))

    def invalidate(
        self,
        *,
        subject_id: str | None = None,
        workspace_id: str | None = None,
    ) -> int:
        """Invalidate a bounded scope, or the whole process cache.

        Mutation, policy, topology, model, index, lifecycle and deletion
        changes normally produce a different key. This method handles eager
        invalidation and prevents old generations consuming bounded capacity.
        """
        selected = [
            key
            for key in self._values
            if (subject_id is None or key.subject_id == subject_id)
            and (workspace_id is None or key.workspace_id == workspace_id)
        ]
        for key in selected:
            self._values.pop(key, None)
        return len(selected)

    def clear(self) -> int:
        return self.invalidate()

    def __len__(self) -> int:
        return len(self._values)


def final_reload(memory: Any, key: RetrievalCacheKey, record_ids: list[str]) -> list[dict[str, Any]]:
    """Revalidate generation, scope, lifecycle, and exclusion before delivery."""
    if memory.store.record_generation(key.subject_id) != key.generation:
        raise ValueError("cached retrieval was invalidated by a memory change")
    lifecycle_generation = getattr(memory.store, "lifecycle_generation", None)
    if key.lifecycle_generation and callable(lifecycle_generation):
        if lifecycle_generation(key.subject_id) != key.lifecycle_generation:
            raise ValueError("cached retrieval was invalidated by a lifecycle change")
    unique_ids = list(dict.fromkeys(record_ids))
    records = memory.store.get_records(key.subject_id, unique_ids)
    excluded = memory.store.excluded_record_ids(key.subject_id)
    result: list[dict[str, Any]] = []
    for record_id in unique_ids:
        record = records.get(record_id)
        if record is None or record.get("status") != "active" or record_id in excluded:
            raise ValueError("cached retrieval contains an ineligible record")
        authority = (record.get("raw") or {}).get("authority_scope") or {}
        if authority and (
            authority.get("subject_id") != key.subject_id
            or authority.get("workspace_id") != key.workspace_id
        ):
            raise ValueError("cached retrieval record is outside the authority scope")
        result.append(record)
    return result
