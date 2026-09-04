from __future__ import annotations

from pathlib import Path

import pytest

from atmem import Memory
from atmem.semantic import SemanticIndex


class CountingEmbedder:
    def __init__(self) -> None:
        self.documents: list[str] = []

    @property
    def identity(self) -> dict[str, str]:
        return {
            "provider": "test",
            "model": "checkpointed",
            "version": "1",
            "normalization": "l2",
        }

    def embed_documents(self, texts):
        self.documents.extend(texts)
        return [[1.0, float(index + 1)] for index, _ in enumerate(texts)]

    def embed_query(self, _text):
        return [1.0, 1.0]


def _memory(path: Path) -> Memory:
    memory = Memory(path, auto_vectors=False)
    memory.remember(
        "u1",
        "First durable preference.",
        interpreted_fact="First durable preference.",
        interpreted_fact_key="test.first",
    )
    memory.remember(
        "u1",
        "Second durable preference.",
        interpreted_fact="Second durable preference.",
        interpreted_fact_key="test.second",
    )
    return memory


def test_interrupted_epoch_resumes_without_reembedding_checkpointed_records(
    tmp_path: Path,
) -> None:
    memory = _memory(tmp_path / "memory.db")
    index = SemanticIndex(tmp_path / "vectors.db")
    embedder = CountingEmbedder()
    interrupted_epoch = None

    def interrupt(phase, evidence):
        nonlocal interrupted_epoch
        if phase == "batch_checkpointed":
            interrupted_epoch = evidence["epoch_id"]
            raise RuntimeError("simulated interruption")

    try:
        with pytest.raises(RuntimeError, match="interruption"):
            index.build(memory, "u1", embedder, batch_size=1, fault_hook=interrupt)
        assert index.active_epoch("u1") is None
        assert len(embedder.documents) == 1

        result = index.build(memory, "u1", embedder, batch_size=1)
        assert result["resumed"] is True
        assert result["epoch_id"] == interrupted_epoch
        assert len(embedder.documents) == 2
        assert index.verify(memory, "u1")["valid"] is True
    finally:
        index.close()
        memory.close()


@pytest.mark.parametrize("mutation", ["add", "delete"])
def test_concurrent_canonical_change_never_activates_partial_epoch(
    tmp_path: Path, mutation: str
) -> None:
    memory = _memory(tmp_path / "memory.db")
    index = SemanticIndex(tmp_path / "vectors.db")
    original = CountingEmbedder()
    replacement = CountingEmbedder()
    try:
        first = index.build(memory, "u1", original)

        def mutate(phase, _evidence):
            if phase != "before_activation":
                return
            if mutation == "add":
                memory.remember(
                    "u1",
                    "A concurrently added preference.",
                    interpreted_fact="A concurrently added preference.",
                    interpreted_fact_key="test.concurrent",
                )
            else:
                record_id = memory.store.list_records("u1", statuses=("active",))[0]["id"]
                memory.forget_record("u1", record_id)

        with pytest.raises(RuntimeError, match="canonical memory changed"):
            index.build(memory, "u1", replacement, batch_size=1, fault_hook=mutate)
        assert index.active_epoch("u1")["epoch_id"] == first["epoch_id"]
    finally:
        index.close()
        memory.close()


def test_dimension_and_disk_failures_preserve_prior_active_epoch(tmp_path: Path) -> None:
    memory = _memory(tmp_path / "memory.db")
    index = SemanticIndex(tmp_path / "vectors.db")
    good = CountingEmbedder()
    try:
        first = index.build(memory, "u1", good)

        class ChangingDimensions(CountingEmbedder):
            def embed_documents(self, texts):
                self.documents.extend(texts)
                size = 2 if len(self.documents) == 1 else 3
                return [[1.0] * size for _ in texts]

        with pytest.raises(ValueError, match="inconsistent dimensions"):
            index.build(memory, "u1", ChangingDimensions(), batch_size=1)
        assert index.active_epoch("u1")["epoch_id"] == first["epoch_id"]

        def disk_failure(phase, _evidence):
            if phase == "before_activation":
                raise OSError("simulated disk full")

        with pytest.raises(OSError, match="disk full"):
            index.build(memory, "u1", CountingEmbedder(), fault_hook=disk_failure)
        assert index.active_epoch("u1")["epoch_id"] == first["epoch_id"]
    finally:
        index.close()
        memory.close()
