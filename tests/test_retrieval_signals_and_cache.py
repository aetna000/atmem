from __future__ import annotations

import pytest

from atmem import Memory
from atmem.retrieve import RetrievalCacheKey, RetrievalDecisionCache, final_reload
from atmem.retrieve.signals import SIGNAL_REGISTRY_VERSION, contribution, semantic_contribution


def test_signal_registry_is_versioned_bounded_and_marks_hashing_diagnostic() -> None:
    assert SIGNAL_REGISTRY_VERSION == "atmem-retrieval-signals-v1"
    assert contribution("lexical_support", 8).normalized_score == 1.0
    assert contribution("candidate_prior", float("nan")).normalized_score == 0.0
    assert semantic_contribution(0.99, "hashing-diagnostic").eligible_for_support is False
    assert semantic_contribution(0.81, "sentence-transformers").eligible_for_support is True


def test_cache_key_separates_scope_generation_epoch_calibration_query_and_policy() -> None:
    values = dict(
        subject_id="u1", agent_id="a1", workspace_id="w1", generation=2,
        epoch_id="epoch-1", calibration_version="calibration-v1",
        policy_sha256="policy-1",
    )
    first = RetrievalCacheKey.for_query(query="favorite lunch", **values)
    assert first.query_sha256 != "favorite lunch"
    assert first.digest != RetrievalCacheKey.for_query(query="favorite car", **values).digest
    assert first.digest != RetrievalCacheKey.for_query(
        query="favorite lunch", **{**values, "workspace_id": "w2"}
    ).digest
    cache = RetrievalDecisionCache(max_entries=1)
    cache.put(first, "first")
    second = RetrievalCacheKey.for_query(query="favorite car", **values)
    cache.put(second, "second")
    assert cache.get(first) is None
    assert cache.get(second) == "second"


def test_cached_ids_require_final_generation_and_lifecycle_reload(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    try:
        record_id = memory.remember("u1", "I prefer aisle seats.")["records"][0]["id"]
        key = RetrievalCacheKey.for_query(
            query="seat preference", subject_id="u1", agent_id="a1",
            workspace_id="w1", generation=memory.store.record_generation("u1"),
            epoch_id="none", calibration_version="calibration-v1",
            policy_sha256="policy-1",
        )
        assert [row["id"] for row in final_reload(memory, key, [record_id])] == [record_id]
        memory.forget_record("u1", record_id)
        with pytest.raises(ValueError, match="invalidated"):
            final_reload(memory, key, [record_id])
    finally:
        memory.close()
