"""Generation-bound pgvector derived-index adapter."""

from __future__ import annotations

from typing import Any

from atmem.core.storage import BackendCapabilities, DerivedGeneration


class PgVectorIndex:
    def __init__(self, connection: Any, *, table: str = "atmem_vectors") -> None:
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe pgvector table name")
        self.connection, self.table = connection, table
        self._active: dict[str, DerivedGeneration] = {}

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities("pgvector-v1", "derived", True, True, True, True, True, True, True)

    def activate(self, subject_id: str, generation: DerivedGeneration) -> None:
        if not generation.source_sha256 or generation.canonical_generation < 0:
            raise ValueError("derived generation is not canonically bound")
        self._active[subject_id] = DerivedGeneration(generation.generation_id, generation.canonical_generation, generation.source_sha256, generation.configuration_sha256, True)

    def active_generation(self, subject_id: str) -> DerivedGeneration | None:
        return self._active.get(subject_id)

    def discard_generation(self, subject_id: str, generation_id: str) -> None:
        active = self._active.get(subject_id)
        if active and active.generation_id == generation_id:
            raise ValueError("cannot discard an active derived generation")
        with self.connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {self.table} WHERE subject_id=%s AND generation_id=%s", (subject_id, generation_id))
        self.connection.commit()
