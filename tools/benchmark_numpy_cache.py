"""Synthetic matrix/search ablation; no model calls or Mem0 comparison."""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from atmem import Memory
from atmem.semantic import HashingEmbedder, SemanticIndex
from atmem.semantic.index import _MatrixCache, _exact_similarities


def summary(times):
    return {'n': len(times), 'median_ms': statistics.median(times),
            'p95_ms': sorted(times)[math.ceil(len(times) * .95) - 1]}


def main():
    rng = np.random.default_rng(31)
    report = {'numpy': np.__version__, 'profile': 'synthetic-distinct-query',
              'kernel': [], 'backend': 'plaintext', 'encrypted': 'not measured'}
    for n in (350, 4000):
        blobs = [row.tobytes() for row in rng.normal(size=(n, 384)).astype('<f4')]
        queries = rng.normal(size=(61, 384))
        queries /= np.linalg.norm(queries, axis=1)[:, None]
        for mode in ('uncached', 'reuse', 'alternating', 'oversized-bypass'):
            cache = None if mode == 'uncached' else _MatrixCache(1 if mode == 'oversized-bypass' else 32 * 1024 * 1024)
            times = []
            for i, q in enumerate(queries):
                fresh_blobs = [memoryview(blob).tobytes() for blob in blobs]
                start = time.perf_counter()
                actual = _exact_similarities(q, fresh_blobs, 384, cache=cache,
                                            identity=str(i % 2) if mode == 'alternating' else 'u')
                times.append((time.perf_counter() - start) * 1000)
                assert actual == _exact_similarities(q, blobs, 384)
            report['kernel'].append({'rows': n, 'mode': mode, 'first_ms': times[0],
                                     'retained_bytes': (cache.entry[1].nbytes + sys.getsizeof(cache.entry[0][3]) + sum(sys.getsizeof(b) for b in cache.entry[0][3])) if cache and cache.entry else 0,
                                     **summary(times[1:])})
    with tempfile.TemporaryDirectory(prefix='atmem-numpy-') as directory:
        memory = Memory(Path(directory) / 'memory.db', auto_vectors=False)
        index = SemanticIndex(Path(directory) / 'vectors.db', policy=memory.policy, cache_vectors=True)
        try:
            for i in range(350):
                memory.remember('u', f'My numbered preference is item {i}.')
            embedder = HashingEmbedder()
            index.build(memory, 'u', embedder)
            searches = {}
            outputs = {}
            for mode in ('uncached', 'reuse', 'single-use'):
                index._matrix_cache = _MatrixCache(0 if mode == 'uncached' else 32 * 1024 * 1024)
                times, results = [], []
                for i in range(61):
                    if mode == 'single-use':
                        index.close()
                        index = SemanticIndex(Path(directory) / 'vectors.db', policy=memory.policy, cache_vectors=True)
                    start = time.perf_counter()
                    rows = index.search(memory, 'u', f'preference {i}', embedder, min_similarity=0)
                    times.append((time.perf_counter() - start) * 1000)
                    results.append(rows)
                outputs[mode] = results
                searches[mode] = {'first_ms': times[0], **summary(times[1:])}
            assert outputs['uncached'] == outputs['reuse']
            assert outputs['uncached'] == outputs['single-use']
            report['search'] = searches
        finally:
            index.close()
            memory.close()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
