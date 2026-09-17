# Core hybrid experiment — 2026-09-17

**Historical snapshot:** graph deferral and graph-only rejection described below
apply to this initial experiment. The subsequent
[graph amendment](graph-nomination.md) implements scoped graph nominations and
accepts graph-only core requests; it remains experimental. These original
measurements are unchanged.

**Not a rollout or a Mem0 superiority claim.** The opt-in core engine now supports
independent lexical, fact-key and production-semantic nominations, scoped BM25,
deterministic normalized RRF and final canonical revalidation. Default legacy
and graph behavior are unchanged. Graph contributions in opted-in requests are
explicitly marked deferred. NumPy matrix caching remains off.

## Frozen calibration check

Command:

```bash
./.venv/bin/python tools/benchmark_core_hybrid.py \
  --dataset /tmp/atmem-mem0-research.6BAkC2/longmemeval_s_cleaned.json \
  --source /tmp/atmem-mem0-research.6BAkC2/matched-v2-atmem-calibration
```

The tool copies prebuilt fixture databases to temporary storage, validates exact
canonical content/session sets against the frozen dataset and uses the existing
Nomic model. It does not read live user memory. Twelve calibration cases, 338–364
records each; three calls per case/strategy, lexical and semantic requested,
100 candidates/channel, 100 returned records. Source sessions are deduplicated
in candidate order and truncated at five. No query/content tuning was performed
after inspecting these results. No answer generation or judge was run.

Raw case/timing evidence: [core-hybrid-calibration.json](core-hybrid-calibration.json).
Manifest SHA-256: `6dfe8fba9bf810576e191bc5de6bd472dc36dbce4ed4815b9a198fdeaefd8481`.
Model digest observed: `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`.

| Metric | Legacy core candidates | Opt-in pure RRF core |
| --- | ---: | ---: |
| Session recall-any@5 | 1.000 | 1.000 |
| Session recall-all@5 | 0.917 | 0.917 |
| Session MRR@5 | 0.938 | 0.892 |
| Candidate call median | 61.02 ms | 59.71 ms |
| Candidate call p95 | 65.66 ms | 69.80 ms |

This is **not an accuracy improvement**: MRR regressed and p95 rose. Keep opt-in;
do not enable adapters by default or declare the release quality gate passed.
It demonstrates wiring and usable independent channels, not best fusion weights.
Further calibration and then unseen held-out evaluation are required.

The timed boundary is `eligible_candidates`, including scoped corpus creation,
semantic retrieval, canonical validation and candidate-set evidence writes.
It excludes final answer-support decisions, context packing and host delivery.
The 36 timings/profile mix first and repeated queries; they are correlated, small
and order-biased (legacy before new per case), not a statistically adequate
latency study. No confidence intervals or encrypted-backend timing are claimed.

The historical 4.46x result was repeated **semantic-index** search versus Mem0
semantic-only with a different source-session aggregation. Its numbers cannot be
reused here. Mem0 was not rerun in this experiment; no head-to-head conclusion is
drawn. The new corpus-limit behavior fails explicitly above 10,000 authorized
records or 8 MiB of content/fact-key bytes; larger-scale performance is unmeasured.

## Using the unreleased source profile

Set `retrieval_strategy="core-rrf-v1"` on `RecallRequest` passed to
`Memory.eligible_candidates`. Omit it for unchanged legacy behavior and wire
serialization. Explicit core graph-only requests are rejected, not reported as
successful empty searches. `min_score` gates normalized lexical/fact priors,
not fused scores; the versioned semantic nomination floor is 0.0. Existing
original-query support checks remain responsible for context eligibility.
Published scores can be below `min_score`: the threshold applies before fusion
to lexical/fact priors only. RRF normalization uses nonempty channels, so priors
are not comparable across queries or when a channel becomes unavailable. A
channel failure can raise a surviving candidate's normalized prior; it cannot
by itself establish direct answer support. Authorization-withheld active counts
are recorded in audit metadata only, never candidate/reranker signals. Runtime
contract validation rejects core graph-only requests; JSON schema alone does not
enforce that cross-field rule. Scoped vector integrity checks cover authorized
rows only, not a whole-index verification claim.

No dependency, persistent schema or release version changes are needed. Text
derived from media participates like other authorized text; raw media embedding
or understanding is not added by this change.

The shared answer-support gate also now rejects a relative's age as direct support
for an explicit self-age query. This bounded correctness fix applies to both
strategies; it does not activate core fusion or change legacy graph nomination.
