"""Deterministic graph materialization generations over canonical memory."""

from __future__ import annotations

import uuid
from typing import Any

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.store.sqlite import utc_now
from . import GraphIndex


class DerivedGraphStore:
    def __init__(self, store: Any) -> None: self.store, self.index = store, GraphIndex(store)

    def materialize(self, memory: Any, subject_id: str, *, rebuild: bool = False) -> dict[str, Any]:
        if rebuild:
            self.index.clear(subject_id)
        result = self.index.backfill(subject_id)
        graph = self.index.inspect(subject_id)
        body = {"entities": graph["entities"], "aliases": graph["aliases"], "edges": graph["edges"]}
        graph_sha = sha256_hex(canonical_json(body)); canonical_generation = self.store.record_generation(subject_id)
        generation_id = f"ggen_{sha256_hex(canonical_json({'subject_id': subject_id, 'canonical_generation': canonical_generation, 'graph_sha256': graph_sha}))[:24]}"
        with self.store.transaction():
            self.store._conn.execute("UPDATE graph_generations SET status='retired' WHERE subject_id=? AND status='active' AND generation_id<>?", (subject_id, generation_id))
            self.store._conn.execute("INSERT INTO graph_generations VALUES(?,?,?,?,?,?) ON CONFLICT(generation_id) DO UPDATE SET status='active'", (generation_id, subject_id, canonical_generation, graph_sha, "active", utc_now()))
        return {"format": "atmem-graph-generation-v1", "generation_id": generation_id, "canonical_generation": canonical_generation, "graph_sha256": graph_sha, "status": "active", "materialization": result}

    def active_generation(self, subject_id: str) -> dict[str, Any] | None:
        row = self.store._conn.execute("SELECT * FROM graph_generations WHERE subject_id=? AND status='active'", (subject_id,)).fetchone()
        return dict(row) if row else None
