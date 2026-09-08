"""Generation-bound Qdrant derived-index adapter."""

from __future__ import annotations

from typing import Any

from atmem.core.storage import BackendCapabilities, DerivedGeneration


class QdrantIndex:
    def __init__(self, client: Any, *, collection: str = "atmem_vectors") -> None:
        self.client, self.collection = client, collection
        self._active: dict[str, DerivedGeneration] = {}

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities("qdrant-v1", "derived", False, True, True, True, True, True, True)

    def activate(self, subject_id: str, generation: DerivedGeneration) -> None:
        if not generation.source_sha256:
            raise ValueError("derived generation is not canonically bound")
        self._active[subject_id] = DerivedGeneration(generation.generation_id, generation.canonical_generation, generation.source_sha256, generation.configuration_sha256, True)

    def active_generation(self, subject_id: str) -> DerivedGeneration | None:
        return self._active.get(subject_id)

    def discard_generation(self, subject_id: str, generation_id: str) -> None:
        active = self._active.get(subject_id)
        if active and active.generation_id == generation_id:
            raise ValueError("cannot discard an active derived generation")
        self.client.delete(collection_name=self.collection, points_selector={"filter": {"must": [{"key": "subject_id", "match": {"value": subject_id}}, {"key": "generation_id", "match": {"value": generation_id}}]}})
