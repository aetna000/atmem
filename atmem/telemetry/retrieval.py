"""Per-stage retrieval profiling that never retains query or context bytes."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Iterator


@dataclass(frozen=True, slots=True)
class StageSample:
    stage: str
    elapsed_ms: float
    candidate_count: int
    result_count: int


@dataclass(slots=True)
class RetrievalProfile:
    run_id: str
    samples: list[StageSample] = field(default_factory=list)
    format: str = "atmem-retrieval-profile-v1"

    def to_dict(self) -> dict[str, object]:
        return {"format": self.format, "run_id": self.run_id, "samples": [asdict(item) for item in self.samples]}


@contextmanager
def profile_stage(profile: RetrievalProfile, stage: str, *, candidate_count: int = 0) -> Iterator[dict[str, int]]:
    start = perf_counter()
    result = {"result_count": 0}
    try:
        yield result
    finally:
        profile.samples.append(StageSample(stage, round((perf_counter() - start) * 1000, 3), max(0, candidate_count), max(0, int(result["result_count"]))))
