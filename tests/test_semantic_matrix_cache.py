"""Exact matrix reuse: derived acceleration never replaces canonical authority."""
import builtins
import struct

import pytest

from atmem.semantic.index import _MatrixCache, _exact_similarities


def vectors():
    return [struct.pack('<fff', 0.5, i / 256, -0.25) for i in range(256)]


def test_reuse_matches_uncached_and_is_immutable():
    pytest.importorskip('numpy')
    cache = _MatrixCache()
    blobs = vectors()
    for query in ([1., 0., 0.], [0., 1., 0.], [0.5, 1e-14, -0.5]):
        expected = _exact_similarities(query, blobs, 3)
        actual = _exact_similarities(query, blobs, 3, cache=cache, identity='a')
        assert actual == expected
        previous = cache.entry
        assert _exact_similarities(query, blobs, 3, cache=cache, identity='a') == expected
        assert cache.entry is previous
        assert not cache.entry[1].flags.writeable
        assert cache.entry[1].dtype.name == 'float64'


@pytest.mark.parametrize('change', ['identity', 'bytes', 'order'])
def test_invalidation(change):
    pytest.importorskip('numpy')
    cache = _MatrixCache()
    blobs = vectors()
    _exact_similarities([1, 0, 0], blobs, 3, cache=cache, identity='a')
    previous = cache.entry
    identity = 'b' if change == 'identity' else 'a'
    if change == 'bytes':
        blobs[0] = struct.pack('<fff', 0.7, 0., 0.)
    if change == 'order':
        blobs.reverse()
    assert _exact_similarities([1, 0, 0], blobs, 3, cache=cache, identity=identity) == _exact_similarities([1, 0, 0], blobs, 3)
    assert cache.entry is not previous


def test_realistic_dimensions_and_fresh_blob_objects():
    np = pytest.importorskip('numpy')
    rng = np.random.default_rng(31)
    blobs = [row.tobytes() for row in rng.normal(size=(350, 384)).astype('<f4')]
    cache = _MatrixCache()
    for query in rng.normal(size=(10, 384)):
        fresh = [memoryview(blob).tobytes() for blob in blobs]
        assert _exact_similarities(query, fresh, 384, cache=cache) == _exact_similarities(query, blobs, 384)


@pytest.mark.parametrize('bad', [b'x', struct.pack('<fff', float('nan'), 0., 0.)])
def test_corruption_after_hit_fails_and_clears(bad):
    pytest.importorskip('numpy')
    cache = _MatrixCache()
    blobs = vectors()
    _exact_similarities([1, 0, 0], blobs, 3, cache=cache, identity='a')
    blobs[0] = bad
    with pytest.raises(ValueError):
        _exact_similarities([1, 0, 0], blobs, 3, cache=cache, identity='a')
    assert cache.entry is None


def test_size_bypass_and_absent_numpy(monkeypatch):
    cache = _MatrixCache(max_bytes=1)
    blobs = vectors()
    expected = _exact_similarities([1, 0, 0], blobs, 3)
    assert _exact_similarities([1, 0, 0], blobs, 3, cache=cache) == expected
    assert cache.entry is None
    original = builtins.__import__
    def without_numpy(name, *args, **kwargs):
        if name == 'numpy':
            raise ImportError('test without optional dependency')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_numpy)
    assert _exact_similarities([1, 0, 0], blobs, 3, cache=cache) == [0.5] * 256
    assert cache.entry is None


def test_search_revalidates_and_close_clears(tmp_path):
    pytest.importorskip('numpy')
    from atmem import Memory
    from atmem.semantic import HashingEmbedder, SemanticIndex
    memory = Memory(tmp_path / 'memory.db', auto_vectors=False)
    index = SemanticIndex(tmp_path / 'vectors.db', policy=memory.policy, cache_vectors=True)
    try:
        for i in range(256):
            memory.remember('u', f'My numbered preference is item {i}.')
        embedder = HashingEmbedder()
        index.build(memory, 'u', embedder)
        before = index.search(memory, 'u', 'preference', embedder, min_similarity=0)
        assert index._matrix_cache.entry is not None
        entry = index._matrix_cache.entry
        assert index.search(memory, 'u', 'preference', embedder, min_similarity=0) == before
        assert index._matrix_cache.entry is entry
        index.purge('u', [])
        assert index._matrix_cache.entry is None
        index.search(memory, 'u', 'preference', embedder, min_similarity=0)
        index.invalidate_for_policy_change('u')
        assert index._matrix_cache.entry is None
        index.search(memory, 'u', 'preference', embedder, min_similarity=0)
        index.discard_generation('u', 'missing')
        assert index._matrix_cache.entry is None
        memory.forget_record('u', before[0]['record_id'])
        after = index.search(memory, 'u', 'preference', embedder, min_similarity=0)
        assert before[0]['record_id'] not in {r['record_id'] for r in after}
        assert index._matrix_cache.entry is not entry
    finally:
        index.close()
        assert index._matrix_cache.entry is None
        memory.close()


def test_default_does_not_enable_matrix_retention(tmp_path):
    from atmem.semantic import SemanticIndex
    index = SemanticIndex(tmp_path / 'vectors.db')
    try:
        assert index._cache_vectors is False
        assert index._matrix_cache.entry is None
    finally:
        index.close()
