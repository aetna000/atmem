"""Per-edge authorized, cycle-safe, hard-bounded graph traversal."""

from __future__ import annotations

from typing import Any

from . import GraphIndex
from .models import AuthorizedPath


def traverse_authorized(store: Any, subject_id: str, query: str, *, max_hops: int = 2, max_candidates: int = 32, max_bytes: int = 16_384) -> list[AuthorizedPath]:
    if not 1 <= max_hops <= 4 or not 1 <= max_candidates <= 256 or not 1 <= max_bytes <= 1_048_576:
        raise ValueError("graph traversal budget is outside hard bounds")
    recall = GraphIndex(store).recall(subject_id, query, max_depth=max_hops, frontier_cap=max_candidates)
    excluded = store.excluded_record_ids(subject_id); paths: list[AuthorizedPath] = []; used = 0
    for candidate in recall.candidates:
        record_id = str(candidate["record_id"]); record = store.get_record(subject_id, record_id)
        if record is None or record.get("status") != "active" or record_id in excluded: continue
        encoded = str(record.get("content") or "").encode("utf-8")
        if used + len(encoded) > max_bytes: break
        steps = tuple(candidate.get("path") or ()); edge_ids = tuple(str(step.get("edge_id") or "") for step in steps)
        if len(edge_ids) != len(set(edge_ids)): continue
        entities = tuple(str(step.get("from_entity") or "") for step in steps)
        paths.append(AuthorizedPath(entities, tuple(str(step.get("relation") or "") for step in steps), (record_id,), len(encoded), ("authorized",)))
        used += len(encoded)
    return paths
