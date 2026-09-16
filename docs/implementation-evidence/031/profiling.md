# Retrieval bottlenecks and narrow speed observations

**Date:** 2026-09-17. **Status:** development measurements, not release claims.

**Correction:** The earlier runner passed `limit` to Mem0 2.0.20, whose search
API requires `top_k`. Mem0 silently used its default 20 returned results while
AtMem nominated 100. All historical latency ratios below are **withdrawn as
apple-to-apple comparisons**. Corrected results with `top_k=100`, exactly
matching canonical document bytes and Nomic prefixes are in
[matched-v2.md](matched-v2.md). The old measurements remain for audit only.

The pinned calibration workload has 12 LongMemEval-S questions, roughly
338–367 raw chunks per case, 768-dimensional local `nomic-embed-text` vectors,
100 nominated chunks and five scored evidence sessions. Source dataset and
hardware are in [baseline.md](baseline.md). The installed Mem0 package is
2.0.20; its base profile lacks optional spaCy and fastembed, so BM25/entity
behavior must not be attributed to that run.

| Profile | AtMem p95 | Mem0 base p95 | Interpretation |
| --- | ---: | ---: | --- |
| Pre-change first search, 12 cases | 259.6 ms | 135.7 ms | exploratory, contention affected Mem0 |
| New compiled-vector path, first search, 12 cases | 492.8 ms | 62.7 ms | AtMem had a cold import/outlier; no cold win |
| New compiled-vector path, one repeated query per case | 88.0 ms | 54.4 ms | cache not yet integrated in this run |
| Process-only query cache plus compiled vectors, 10 repeats per case on prebuilt indexes | 7.85 ms | 58.71 ms | historical trace; Mem0 used only 20 returned results |
| Scope-bound cache after independent review, same repeated profile | 7.41 ms | 58.71 ms | historical trace; ratio withdrawn because candidate pools differed |

The old comparison used the same frozen dataset manifest, ordered case IDs,
local embedding model and 10 repeated requests per question, but **not** the
same effective candidate pool or embedding-input preprocessing.
Both systems scored recall-any@5, recall-all@5 and MRR@5 at 1.0. The query
cache in the **subsequently tightened source** stores only normalized vectors behind SHA-256 keys bound to Ollama model
digest, endpoint, preprocessing profile and the requesting index/memory instance,
subject, epoch, policy and canonical/index generations. Unscoped direct embedder
calls bypass the cache. The cache is bounded to 128 process-local entries with
expiry on access. AtMem still checks the model identity and reloads
canonical record status/content digests before returning nominations. It does
not cache delivered context or authorization decisions. The initial ratio
measurement predates that scope tightening. The AtMem rerun on the tightened
source returned warm p50 6.24 ms and p95 7.41 ms; first-search p95 was
1009.43 ms due a lazy import/outlier, versus 82.82 ms in the earlier Mem0 base
run. These remain development observations, not candidate evidence.

The repeat profile reopens previously built indexes. Early development reports
used `indexing_ms=0` as a sentinel for excluded work; the runner now emits
`null` for **not measured**, not instant indexing. It checks AtMem's source
session IDs and benchmark fact-key range but is not a cryptographic proof that
all original corpus bytes were stored; the fresh-build report binds the source
dataset digest. The first-search AtMem result in this profile includes lazy
NumPy import and was not faster. Cold, unique-query, native `control_prepare`
and held-out results are separate required gates. A fresh
fully enabled Mem0 2.0.20 hybrid run (spaCy model and fastembed/BM25 installed)
retained recall-any/all@5 and MRR@5 of 1.0 on the same 12 calibration cases;
its warm p95 was 180.45 ms. A separate prebuilt ten-repeat hybrid run returned
warm p95 165.92 ms, still not a matched native-preparation or held-out result.

One profiled uncached search spent about 69 ms in Ollama query embedding and
about 193 ms under Python vector unpacking/dot products with profiler overhead.
The optional NumPy path moved those vector operations to compiled code. A
profiled cached search then spent about 3 ms checking Ollama model identity,
2 ms reloading 100 canonical validation rows, and the remainder reading and
scoring encrypted vector entries. These are sample traces, not universal costs.

After a single new record was admitted to a 338-record temporary case, a
staged semantic rebuild reused 338 content/status/model/policy-compatible
vectors, embedded only the new record, activated a verified epoch and finished
in 227 ms. Initial corpus admission plus indexing was tens of seconds, but
that aggregate is a **different boundary**; no 100× rebuild claim is made
without measuring a matched full-rebuild control.

**Decision:** keep exact search on current small indexes. An ANN/HNSW sidecar
would be a rebuildable nominee only, never an authority source; it is deferred
until exact-search recall, lifecycle, encryption and cross-scope tests can
prove noninferior results at a scale where ANN has a real benefit. The corrected
raw repeated-search p95 ratio is 4.46× against semantic-only Mem0; the 10×
stretch remains unmet, and no 2× full native
preparation or general Mem0 win is claimed.

An independent read-only Claude CLI review flagged per-vector payload validation
before incremental reuse and before NumPy scoring, plus process-global unscoped
query-cache sharing. Those paths were tightened and regression tests added.
It agreed that the old repeated-query result cannot satisfy the full-preparation acceptance
gate: 120 repeats are correlated within only 12 calibration questions, and the
cache-ideal profile omits native support, revalidation and packing. The next
priority is unique-query cold latency and a matched native-path benchmark.
