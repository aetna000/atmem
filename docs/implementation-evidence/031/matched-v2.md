# Corrected matched-input AtMem–Mem0 calibration comparison

**Date:** 2026-09-17. **Status:** development evidence, not a release or leaderboard claim.

The earlier profile accidentally passed `limit` to Mem0 2.0.20's `search`,
which accepts `top_k`; it silently used its default 20 results. This corrected
profile passes `top_k=100`. It also gives all systems exactly the same
canonical-deduplicated document strings and `nomic-embed-text:latest` query and
document prefixes. Independent reads of the AtMem canonical database and both
Mem0 Qdrant collections found identical sorted strings and counts for all 12
cases (338–359 records per case). Mem0 hybrid's Qdrant collection had an active
`bm25` sparse-vector slot. No timed searches overlapped between systems.

| Metric | AtMem, optional NumPy | Mem0 OSS 2.0.20, semantic-only | Mem0 OSS 2.0.20, spaCy + BM25 |
| --- | ---: | ---: | ---: |
| Evidence-session recall-any@5 | 1.000 | 1.000 | 1.000 |
| Evidence-session recall-all@5 | 1.000 | 1.000 | 1.000 |
| Evidence-session MRR@5 | 1.000 | 1.000 | 1.000 |
| First unique search p50 | 56.85 ms | 63.52 ms | 154.93 ms |
| First unique search p95 | 161.09 ms | **69.39 ms** | 568.88 ms |
| Ten exact repeats per question, p50 | **5.96 ms** | 52.65 ms | 146.68 ms |
| Ten exact repeats per question, p95 | **14.73 ms** | 65.66 ms | 220.20 ms |
| Corpus admission + index p50, different persistence work | 39.39 s | 48.42 s | 63.32 s |

The answer session ranked first in every case for all three systems. The full
top-five session order matched AtMem in 10/12 semantic-only cases and 2/12
hybrid cases. The primary quality metrics tie at the ceiling; the result does
not establish general answer quality or noninferiority on hard/held-out cases.
The semantic-only repeated-search p95 ratio is 65.66/14.73 = **4.46×** in
AtMem's favor, but those 120 timings are correlated repeats of just 12
calibration questions. Against enabled-hybrid Mem0 the repeated-query p95
ratio is 14.95×, comparing different ranking feature sets. Mem0 has the better
first-search p95 in the semantic-only comparison: 69.39 vs 161.09 ms. With
12 first-query samples, the nearest-rank p95 is the maximum; AtMem's first
case includes lazy initialization, and the other 11 first searches were
42–66 ms. None of these figures establishes the Spec 031 matched warm
**full-preparation** 2× acceptance criterion.

## Exact measurement boundary and limits

Both paths ingest public LongMemEval-S cleaned data with automatic inference
disabled, select the frozen 12 calibration IDs, use 1,600-character chunks,
the same local Ollama model, 100 returned chunk nominations, five evidence
sessions and the same scorer. Search timing starts immediately before each
backend call and ends at its result. It includes query embedding, vector
search and that backend's built-in ranking/validation, but **excludes** corpus
admission/indexing, AtMem's native `control_prepare`, final context packing,
delivery, model answer generation, and cold process startup before the first
search call. AtMem's scoped 60-second query-vector cache explains much of its
exact-repeat advantage; Mem0 was left on its stock search behavior. The
canonical governance work done by AtMem and the BM25/entity work done by Mem0
hybrid are not identical. The ingestion row is descriptive, not a comparable
performance verdict. Twelve calibration questions are not statistically
adequate for a general p95 or quality claim. Unique-query held-out and native
preparation runs remain required.

**Pinned inputs:** LongMemEval-S cleaned commit
`98d7416c24c778c2fee6e6f3006e7a073259d48f`; dataset SHA-256
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`;
manifest SHA-256
`6dfe8fba9bf810576e191bc5de6bd472dc36dbce4ed4815b9a198fdeaefd8481`;
Mem0 package 2.0.20 / inspected source
`0df3e4b87df20785f0741370c75e44428796193e`. Host and Ollama model
identity are in [baseline.md](baseline.md). The three full per-case JSON
reports are currently local temporary artifacts:
`/tmp/atmem-mem0-research.6BAkC2/matched-v2-{atmem,mem0-base,mem0-hybrid}-calibration.json`.
They need durable archiving and a quiet-host replication before release claims.
