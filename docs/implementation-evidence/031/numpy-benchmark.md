# NumPy matrix cache experiment — 2026-09-17

Command: `./.venv/bin/python tools/benchmark_numpy_cache.py`

Local Python 3.12 / NumPy 2.5.3, deterministic seed 31. Each profile has one
first invocation and 60 distinct-query samples; p95 is nearest rank. Matrix
fixtures are 384-dimensional float32, queried using float64. Each call receives
fresh byte objects (not the same objects retained in the cache). Equality with
the original uncached scorer is asserted outside the timed interval. Profiles
run sequentially, not randomized; these exploratory results have no confidence
interval and establish no general speedup.

| Matrix rows | Profile | Median ms | p95 ms | First ms | Retained bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| 350 | Uncached | 0.244 | 0.310 | 1.091 | 0 |
| 350 | Reuse | 0.252 | 0.279 | 0.329 | 1,627,190 |
| 350 | Alternating identities | 0.326 | 0.349 | 0.323 | 1,627,190 |
| 350 | Oversized bypass | 0.306 | 1.001 | 0.310 | 0 |
| 4000 | Uncached | 2.665 | 3.333 | 3.952 | 0 |
| 4000 | Reuse | 2.923 | 3.626 | 3.516 | 18,596,040 |
| 4000 | Alternating identities | 3.733 | 3.975 | 3.457 | 18,596,040 |
| 4000 | Oversized bypass | 3.423 | 3.719 | 3.472 | 0 |

Complete `SemanticIndex.search` on 350 synthetic memories, local diagnostic
HashingEmbedder (not semantic quality evaluation), plaintext backend:

| Profile | Median ms | p95 ms | First ms |
| --- | ---: | ---: | ---: |
| Reused index, cache disabled | 2.863 | 3.056 | 3.152 |
| Reused index, cache enabled | 2.853 | 2.985 | 2.846 |
| Fresh index each call, cache enabled | 3.115 | 3.271 | 3.217 |

All search outputs are identical. Index open/close is outside the search timer;
the single-use profile is not full native preparation. SQL fetch is included in
search but its separate share was not measured. Encrypted backend latency,
NumPy import/process startup, external embeddings, adapter delivery and Mem0
comparison were not measured. No 2x or 10x claim is justified. Median search
improvement is approximately 0.4%, within plausible run noise; kernel results
regress at 4000 rows. Therefore cache reuse remains experimental and opt-in,
not enabled on the native/default path.

Earlier SHA-256-based prototype failed: 350-row kernel median 0.235 ms uncached
versus 2.510 ms reused; plaintext search p95 3.528 versus 4.416 ms. It was replaced
after review. An intermediate same-object kernel probe overstated potential
benefit; fresh byte objects are required to model SQLite BLOB reads faithfully.

Retained accounting includes float64 data, source byte objects and tuple overhead;
it is not peak RSS. Clearing drops references, not guaranteed zeroization. External
index changes are detected at the next search. A local purge/policy invalidation/
generation discard clears immediately. The 32 MiB limit fits fewer rows when both
source and converted representations are retained.

## Use and packaging

No default dependency, version, schema or wheel build changes. Existing optional
extra remains `pip install 'atmem[semantic-accelerated]'` (installing the published
version does not install this uncommitted source change). In this source,
long-lived callers can opt in with `SemanticIndex(path, cache_vectors=True)`;
keep the default unless workload-specific measurements justify the extra memory.
Without NumPy, existing Python scoring remains available. Partial top-k selection
was deliberately not implemented.

Validation: 74 focused tests passed in 12.25 seconds, covering semantic search,
rebuild, matrix cache, retrieval quality, companion and benchmark contracts.
This is not full beta release clearance; remaining Spec 031 tasks remain open.
