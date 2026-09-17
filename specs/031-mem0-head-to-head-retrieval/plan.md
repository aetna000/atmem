# Implementation Plan: 2.3.3 Beta Retrieval and Mem0 Comparison

**Spec:** [spec.md](spec.md)
**Constitution:** [AtMem Constitution](../../.specify/memory/constitution.md)
**Research input:** [pinned Mem0 2.0.20 source](https://github.com/mem0ai/mem0/tree/0df3e4b87df20785f0741370c75e44428796193e) and [benchmark baseline](../../docs/implementation-evidence/031/baseline.md)
**Target:** stable `2.3.3`, matching bridge `2.3.3`, unchanged AtBot `0.1.0`, under the approved stable scope amendment in spec.md. Original beta research planning below remains future work where not completed; it is not the stable release completion checklist.

## Technical context and baseline

AtMem 2.3.2 uses Python 3.10–3.13, SQLite canonical memory, an encrypted portable Home, a rebuildable SQLite vector sidecar, optional local or hosted embedders, AtBot as a proposal/ranking companion, and OpenClaw plus framework adapters. The OpenClaw bridge is a separate npm package; AtBot `0.1.0` is independently versioned. The benchmark runner is Python; the UI is the existing control dashboard. Mem0 stays in a separate temporary Python environment.

The previously published 12-case LongMemEval-S raw-retrieval comparison used Mem0 OSS 2.0.19 and `nomic-embed-text:latest`. AtMem and Mem0 tied on recall@5; Mem0 won MRR@5 (1.000 vs 0.958) and reported search p95 (57.9 ms vs 193.1 ms). Preserve that dated report. Before code changes, run the checked-in deterministic gate and rerun the pinned raw-retrieval campaign on this machine, recording the source/dataset hashes, complete timing boundary and any changed environment. A new comparison should pin current Mem0 `2.0.20` separately; a changed opponent version is a new experiment, not a revision of the old report.

The full native preparation path has a different budget, support gate and optional companion behavior from the raw benchmark. Build a native AtMem workload and a comparable Mem0 search plus bounded context assembly profile. If its authenticated delivery semantics cannot be matched, name only the common timed segment and leave full-preparation comparison unavailable. Raw retrieval, native context, end-to-end extraction/answer and host-observed delivery receive separate labels.

## Design and ownership

### Benchmark contract and evaluation

Extend `atmem/benchmark/` contracts and `tools/` runners, reusing the existing external result validator and comparison logic. Create immutable `benchmarks/2.3.3b1/` manifests or a new append-only evidence entry under `docs/implementation-evidence/031/`; user supplied datasets remain in temporary storage. The raw runner must record full mode, package versions, content hashes, cases, index parameters, retrieval limit, context budget, hardware/CPU, cold/warm state, independent timing boundaries, per-case source rank and the exact scorer. The native runner calls the service/control path used by adapters, checks the prepared context bytes and records authorization/exposure evidence separately. Mem0 uses only its public OSS APIs under a pinned environment with telemetry disabled and model endpoint declared. An external LLM answer judge is optional, declared and never silently substituted.

Freeze a calibration partition and a distinct held-out partition before adjusting relevance weights. Deterministic fixtures cover cases that LongMemEval does not: scope denial, model failure, corrections, media-derived text, misleading topical matches and non-Latin scripts. Report Pareto quality directions, paired case deltas and latency ratios. Do not combine sampling noise, different corpus sizes or different context budgets in one multiplier.

### Retrieval quality

In `atmem/retrieve/rank.py`, separate topical matching from requested relation/attribute support. Start with general question-intent slots and an explicit abstain on unsupported relations, then use a bounded optional verifier only when measured necessary. Any slot rule must be generic and tested on a held-out category. Unicode-aware lexical normalization must preserve useful letters/numbers across supported languages. Keep original-query scoring, direct/background/no-useful classes and diagnostic-embedding exclusion.

In `atmem/memory.py` and `atmem/store/sqlite.py`, nominate lexical, fact-key, semantic and bounded graph candidates independently. Fuse only after the same authority and lifecycle filters. Bound each channel and record its contribution. Do not allow an inaccessible record or count to influence visible ranking. Preserve the final `prepare_context_v1` reload and context digest.

### Fast path and derived state

Mirror AtBot 0.1.0's existing deterministic query expansion in a local pure function used by the AtMem client, with a parity test against the companion's versioned behavior. AtBot remains independently packaged; its existing endpoint remains compatible. For common direct facts, avoid companion health/request round trips, but retain the exact decision and delivery contracts. AtBot remains optional for ambiguous or complex ranking. Time the fallback and compare quality before enabling it broadly.

Integrate the existing `RetrievalDecisionCache` only after adding missing key identities and race tests. Cache selected identifiers and decisions, not long-lived plaintext; on hit verify generation, policy, membership, lifecycle, index and current record eligibility. Do not cache an unverified provider response or a prepared envelope across turns.

Implement embedding reuse in `atmem/semantic/index.py` by copying or referencing a prior compatible epoch's vector only after validating object ID, content hash, scope, model and preprocessing identity, and policy fingerprint. A changed record is re-embedded; a missing or incompatible prior entry is not reused. Stage a new epoch and activate after whole-source and generation validation. Preserve deletion and rebuild recovery semantics. Avoid schema changes if possible; if unavoidable, use the Spec 010 migration registry and real upgrade fixtures.

### User interface and documentation

Keep the dashboard's existing navigation. Add a compact diagnostic summary for semantic quality, last declared benchmark profile and withheld/direct support, with a click-through case view if a benchmark report is present. Reuse the same authenticated service read model as the CLI. Restrict plaintext to the existing investigator/evidence collector role policy; viewer sees aggregate metrics and hashes. No oversized settings panel or long scrolling report. Case evidence should fit keyboard and narrow screens.

Audit all tracked Markdown for live version and status claims, stale beta pins, broken relative links and contradictory current-scope text. Classify historical releases/reviews separately from current product docs; never rewrite a prior measurement. Update README, benchmarks guide, current status, roadmap, relevant active specs and beta release notes only with measured outcomes. A failed speed target remains a recorded failure, not a polished claim.

## Files and contracts

| Area | Intended changes |
| --- | --- |
| Benchmark | `atmem/benchmark/`, `tools/run_longmemeval_retrieval.py`, new matched native runner, versioned result schema, tests and manifests |
| Selection | `atmem/retrieve/rank.py`, `atmem/retrieve/calibration*.json`, `atmem/memory.py`, `atmem/store/sqlite.py` |
| Intelligence | `atmem/control/manager.py`, `atmem/control/atbot_companion.py`, `packages/atbot/src/atbot/companion.py` only if shared expansion contract needs it |
| Derived state | `atmem/retrieve/cache.py`, `atmem/semantic/index.py` |
| Host boundary | OpenClaw, Pydantic AI, LangChain/LangGraph and MCP contract tests; production adapter code only if a real regression appears |
| UI | Existing `atmem/control/assets/` diagnostics and accessible drilldown; common service read model |
| Docs/release | `docs/benchmarks.md`, `docs/current-status.md`, `docs/release-roadmap.md`, README, `docs/releases/v2.3.3b1.md` when candidate gates are met |

## Sequencing and validation

1. Freeze benchmark manifest, pre-change results and held-out cases; verify dataset and Mem0 source hashes.
2. Add failing independent quality, cache-race, index-reuse and cross-adapter tests. Run Spec Kit analysis before production edits.
3. Implement relation-aware/Unicode support and independent candidate nomination; rerun deterministic gate.
4. Optimize deterministic expansion, guarded cache and index reuse one at a time; measure each ablation. Revert any optimization that regresses safety or held-out quality.
5. Add stage timing and benchmark/CLI/UI read model, then rerun on the same hardware and pinned external configuration.
6. Run full Python, AtBot, OpenClaw build/typecheck/hooks, framework/MCP contracts, dashboard, docs, build metadata and installed-artifact gates. Audit persisted upgrade if a schema changed.
7. Prepare aligned beta version constants and release note only for a reviewed passing candidate. Under the repository release rule, no tag/push/publication occurs merely because a plan or candidate is complete.

Quality gate: zero unauthorized, stale or cross-scope exposures; existing deterministic and adapter floors do not regress. Keep retrieval defaults unchanged. The owner approved moving the FR-006 2× target to future work on 2026-09-17; it is not a stable 2.3.3 tagging gate. Held-out comparative quality and native full-preparation performance remain required before general superiority claims or default promotion. Never tune on held-out questions after looking at the results. Stable publication uses T040–T044 below in tasks.md, including all ordinary regression and artifact gates.

## Consistency decisions

### Core lexical–semantic fusion amendment

Implement a deterministic normalized RRF helper in `atmem/retrieve/fusion.py`:
one contribution per channel per ID, reciprocal rank constant 60, stable ID ties,
and explicit versioned evidence. Normalize by the maximum possible contribution
for participating channels, yielding a bounded nomination prior, not confidence.
Preserve raw semantic similarity as a separate signal for original-query support.

Integrate through `Memory.eligible_candidates`, the native adapter/control path.
Before ranking, load active records for the subject and filter existing workspace,
exclusion and egress rules. Build an ephemeral in-memory FTS5 corpus from only
authorized content so BM25 statistics cannot be changed by hidden records. This
prioritizes correctness; measure the corpus preparation cost and do not claim a
speed win. No persistent plaintext index is introduced. FTS unavailable falls back
to deterministic lexical overlap on the same authorized corpus. Fact-key matches
nominate independently. Semantic search gains an optional allowed-ID restriction
applied before the top-k quota, with normal epoch/model/canonical validation.

Fusion runs for explicit `RecallRequest.retrieval_strategy="core-rrf-v1"`
requests with lexical, semantic or (under the amendment below) graph enabled. Default `legacy` and all adapters
remain unchanged pending graph integration and comparative quality clearance.
The new validated additive request field exposes a core engine, not just a
benchmark adapter. Never call legacy `recall_candidates` to construct lexical ranks: it
backfills nonmatching recent rows and synthesizes fact scores. Lexical nominations
require actual content matches; fact-key nominations require separate key matches.
Initial fused channels are lexical, fact-key and semantic; the amendment below
adds an independently scoped graph channel without reusing global graph ranks.
Legacy graph-only requests and `Memory.recall`
keep legacy behavior. This is a declared opt-in candidate ordering/graph-coverage
change, not full graph feature parity. Broad T006/T009 remain open for independent
authorized graph integration. Retain trust/recency only on the authorized corpus.

Apply `min_score` to the existing `rank_records` 0–1 composite on authorized
content-only lexical matches or fact-only matches (never raw BM25). Semantic
nominations use a separately versioned 0.0 cosine floor; the existing 0.72
production support gate remains downstream and is not a nomination threshold.
Diagnostic hashing never
nominates via the semantic channel. Record both thresholds and channel status
(active/no_epoch/incompatible/unavailable/diagnostic/disabled). Never threshold
raw RRF. Allowed semantic IDs mean all authorized active records, not lexical
nominees. Preserve legacy unscoped-record visibility explicitly in tests.
Across expanded queries in the manager, retain the earliest query's candidate
and append matched_queries instead of comparing incomparable RRF scores.
This merge change belongs to future adapter activation (T035); existing legacy
expansion behavior is not changed by this opt-in slice.
After fusion, batch
reload canonical rows, reject changed/deleted/denied content, attach channel
evidence to candidate signals and publish through the existing receipt contract.
Use no new model calls, dependencies or matrix-cache activation. First run a
read-only Claude design loop and Spec Kit coverage analysis, then fixtures,
implementation, latency/quality checks and a second read-only Claude code review.
Stream active subject records and authorize before collecting the scoped corpus.
Cap authorized corpus at 10,000 records and 8 MiB UTF-8 content plus fact keys;
above either cap, fail explicitly with a corpus-limit error rather than truncate
or claim a complete result. This bounds retained corpus, not the time needed to
scan denied records. Build FTS once per opted-in call, close it in finally. No
adapter expansion loop is enabled on this strategy in this slice; cross-call
corpus reuse remains separate work with its own invalidation requirements.
Record fusion version, thresholds and actual channel ranks in both candidate
signals and audit payload. This scoped slice does not claim legacy graph-only
ranking has the new noninterference property. Tests use file-backed semantic
indexes and assert participation rather than silently exercising lexical only.

Publish pure RRF scores without the separate session-support aggregation bonus;
record `support_aggregation_version: null` for this path. The graph amendment makes
explicit graph-only core requests valid. Distinguish semantic integrity failures, egress denials and model
incompatibility. Extend the bounded age support guard for explicit self-versus-
relative questions; regression tests include a valid self-age statement too.

### Scoped graph nomination implementation

Execute T036–T039 with the revised design. On 2026-09-17 the user waived further
Claude reviews after its session limit; retain its first-review findings and
perform local implementation review and tests instead. Add
`atmem/retrieve/graph.py`, consuming only the already-authorized record list.
Reuse `extract_graph_fact`; normalize entity text locally, create one edge per
extractable record and adjacency lists. Do not read global entities, aliases,
merges or graph FTS. Seed from query/entity token matches and query/relationship
matches (including relation aliases such as my boss); root `you` is never a seed
or intermediate fanout. Relationship matches nominate their edge directly and
seed its non-root endpoints. Two-edge breadth-first traversal records the full
support path, with depth decay, stable record-ID ties and no repeated edge/node
within a path. Bound seeds to 16 and unique visited edges to 256; output quota is
min(request.candidate_limit, 256). Expose disabled/empty/active status plus a separate truncation flag, extracted
edge count and paths. Counts use only authorized records. No raw query logging.

Integrate as the fourth independent RRF channel in `hybrid.collect`; preserve
non-graph results and lexical min_score/semantic floor semantics. Graph scores
are deterministic nomination priors, not support confidence; no min_score reuse.
Batch revalidate all path supporting records for content, scope, lifecycle and
generation before publishing. Existing final preparation authorization remains.
Paths with canonical entity/relation text are in authorized candidate signals;
audit graph metadata contains only counts, bounds, status and supporting record
IDs, never query text or matched seed tokens. Graph extraction/traversal creates
no persistent derivative.

Claude design clarifications: explicitly update graph-only contract validation;
populate `raw_scores['graph']` for every nominated ID. Reload the union of fused
IDs and all path-support IDs, rejecting any missing/changed/denied record rather
than silently dropping a path. Nodes use existing `_normalize(surface)` only,
not kind-keyed identity. The two-edge fixture joins at Sarah, not the user-root.
Record graph status disabled/empty/active separately from `graph_truncated`,
`graph_extracted_edges`, `graph_seeds_used`, `graph_visited_edges` and
`graph_min_score_applied: false`. Count adjacency examinations as well as unique
visited edges under the 256-work budget to bound repeated traversals. Prefix
edges from relation seeds count toward two-edge path length. Truncation includes
seed, work and output caps. Return one deterministic best path per record.

Extend `tools/benchmark_core_hybrid.py` to three named profiles, rotate profile
order by case/repetition, report graph edge/candidate coverage and retain raw
results separately from earlier reports. Test graph-specific recovery outside
lexical quota, invisible bridge removal, bounds and mutations. Frozen calibration
is diagnostic; held-out and matched end-to-end remain future default-promotion and comparative-claim gates, not stable 2.3.3 tagging gates.
Review implementation locally after tests; record review, measurements
and recommendation in `docs/implementation-evidence/031/graph-nomination.md`.

### NumPy amendment implementation

Execute T024–T028 independently of unfinished broader beta work. Keep the
current full-sort selection algorithm. Add a private one-entry matrix cache to
`SemanticIndex`, passed into `_exact_similarities`. Cache immutable float64
matrix storage, removing the implicit per-query float32-to-float64 conversion;
use the same float64 query and matrix.dot operation as today and test equality.
The cache is opt-in via `cache_vectors=True`; default native one-shot instances
pass no cache and incur no key comparison/publication cost. Explicit purge,
policy invalidation and generation discard clear the local cache immediately.
Key by existing search identity, dimensions and exact ordered immutable vector blobs;
check every blob length before lookup. Compare tuples of bytes directly, avoiding
the measured SHA-256 bottleneck and repeated finite-value scanning on reuse. All SQLite reads,
model identity checks and final canonical validation remain unchanged. Use the
existing 256-row threshold and a 32 MiB cache ceiling; clear old entries on misses,
oversized inputs and close. No process-global cache or changes to service lifetime.
Publish a tuple containing identity, source-blob tuple and read-only matrix only after finite-value
validation, by a single assignment; bind locally on read. This does not make the
SQLite-backed index thread-safe or introduce a new concurrent-use contract.
Keep the one-entry design for minimal retention and explicitly measure alternating
subjects. Count matrix bytes, retained blob objects and tuple overhead against the
ceiling before allocating the float64 matrix; transient query and score storage
are excluded. Blob equality checks every byte even if generation counters lie.

Tests compare cached and uncached NumPy results exactly, force absent NumPy,
exercise malformed/nonfinite data after a hit, subject/generation isolation,
close cleanup and size bypass. Benchmark fixed deterministic vectors with distinct
queries; report first-call import separately and no new external model expenditure.
Keep review history in `numpy-review.md` and measurements in `numpy-benchmark.md`.
Report fetch/decrypt contribution for full-search profiles where measured, and
label unavailable backend evidence rather than implying coverage.
If reuse is slower, report it and do not claim acceleration; broader matrix lifetime
and top-k changes remain deferred. Native preparation creates short-lived index
instances, so this slice must not promise cross-turn cache hits there.

- Spec 001 owns benchmark contracts and intentionally forbids production retrieval changes **within that spec**; Spec 031 owns the new production changes and consumes Spec 001 result formats.
- Spec 008's checked tasks document its earlier implementation; new regression cases and calibration revisions belong here without rewriting completed history. Spec 002 supporting evidence remains a ranking signal, not causal proof.
- Spec 005 owns semantic model/epoch identity. Spec 010 owns large-scale storage and migration contracts. This beta measures small/local and declared medium workloads; it does not claim Spec 010's million-record service target.
- Spec 009's entity graph is associative. Spec 026's temporal foundation and consolidation remain scheduled separately. This beta must not advertise historical temporal reasoning or causal what-if answers.
- Spec 003/004 delegated providers and signatures remain separate authority profiles. New native ranking must not alter provider-owned exact context or claim provider content was stored in canonical AtMem memory.
- Spec 022 owns broad dashboard navigation. This beta adds retrieval diagnostics within the existing information architecture, not a competing workspace design.
- The published 2.3.2 baseline remains true; beta 2.3.3 is an intervening maintenance/quality feature. The 2.4 multi-agent scope remains planned and unclaimed.
