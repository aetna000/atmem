from atmem import Memory
from atmem.retrieve.cache import RetrievalCacheKey, RetrievalDecisionCache, final_reload


def _key(memory: Memory, *, lifecycle_generation: int = 0) -> RetrievalCacheKey:
    return RetrievalCacheKey.for_query(subject_id="u", agent_id="main", workspace_id="w", generation=memory.store.record_generation("u"), epoch_id="epoch", calibration_version="v1", query="city", policy_sha256="p", topology_generation=2, model_sha256="m", index_generation="i", lifecycle_generation=lifecycle_generation, deletion_generation=3)


def test_scope_bound_cache_and_invalidation() -> None:
    cache = RetrievalDecisionCache(2)
    memory = Memory(":memory:")
    record = memory.remember("u", "My city is Sydney.")["records"][0]
    key = _key(memory)
    cache.put(key, [record["id"]])
    assert final_reload(memory, key, [record["id"]])[0]["id"] == record["id"]
    assert cache.invalidate(subject_id="other") == 0
    assert cache.invalidate(subject_id="u") == 1
    memory.close()


def test_cache_revalidates_memory_and_lifecycle_generation() -> None:
    memory = Memory(":memory:")
    record = memory.remember("u", "My city is Sydney.")["records"][0]
    lifecycle = memory.store.lifecycle_generation("u")
    key = _key(memory, lifecycle_generation=lifecycle)
    memory.remember("u", "My timezone is UTC.")
    try:
        final_reload(memory, key, [record["id"]])
    except ValueError as exc:
        assert "memory change" in str(exc)
    else:
        raise AssertionError("stale cache was accepted")
    memory.close()
