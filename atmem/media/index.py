"""Generation-bound in-memory multimodal candidate index."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from .models import DerivedObservation


@dataclass(frozen=True, slots=True)
class MediaIndexGeneration:
    generation_id: str; observation_sha256: str; model_sha256: str; active: bool


class MediaIndex:
    def __init__(self) -> None: self._generations: dict[str, tuple[MediaIndexGeneration, tuple[str, ...]]] = {}
    def rebuild(self, subject_id: str, observations: Iterable[DerivedObservation], *, model_sha256: str) -> MediaIndexGeneration:
        ids=tuple(sorted(item.observation_id for item in observations)); source=sha256("\n".join(ids).encode()).hexdigest(); generation=MediaIndexGeneration("midx_"+sha256(f"{subject_id}:{source}:{model_sha256}".encode()).hexdigest()[:24], source, model_sha256, True); self._generations[subject_id]=(generation,ids); return generation
    def active_generation(self, subject_id: str) -> MediaIndexGeneration | None: return self._generations.get(subject_id, (None, ()))[0]
    def invalidate(self, subject_id: str, observation_ids: set[str]) -> dict[str, object]:
        current=self._generations.get(subject_id)
        if current is None: return {"verified": True, "removed": 0}
        generation, ids=current; kept=tuple(item for item in ids if item not in observation_ids); self._generations[subject_id]=(MediaIndexGeneration(generation.generation_id,generation.observation_sha256,generation.model_sha256,False),kept); return {"verified": not (set(ids)-set(kept)-observation_ids), "removed": len(ids)-len(kept)}
