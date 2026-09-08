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


def final_reload(memory: Any, key: RetrievalCacheKey, record_ids: list[str]) -> list[dict[str, Any]]:
    """Revalidate generation, scope, lifecycle, and exclusion before delivery."""
    if memory.store.record_generation(key.subject_id) != key.generation:
        raise ValueError("cached retrieval was invalidated by a memory change")
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
