# Feature Specification: 2.3.3 Retrieval Improvements and Continuing Research

**Feature directory:** `specs/031-mem0-head-to-head-retrieval`
**Created:** 2026-09-16
**Status:** Stable release scope approved on 2026-09-17; broader research remains open.
**Target:** Stable AtMem `2.3.3`, OpenClaw bridge `2.3.3`, unchanged AtBot `0.1.0`.

## Approved stable scope amendment — 2026-09-17

The owner explicitly approved moving the 2× full-preparation target to future
work and publishing stable 2.3.3. This amendment supersedes the original beta
tagging condition below, not the measured results or safety requirements.
The release includes validated local expansion, exact-search/index reuse,
bounded support corrections, responsive archive layout, and developer opt-in
fusion, scoped graph nominations and matrix reuse. Existing retrieval defaults
remain unchanged and matrix reuse remains off by default. No general speed or
quality superiority is claimed. Broader native/held-out comparative research,
benchmark dashboard integration and default promotion remain future work.
Python, companion, host/framework, security, UI, build, metadata and installed
upgrade gates remain mandatory for the released scope. Historical beta names
and experiment identities below describe the original research campaign, not
the published package version. This amendment does not mark all Spec 031 tasks
complete or weaken the quality gate for future default promotion.

## Overview

The next beta must make useful memory easier and faster to find while preserving AtMem's independent evidence store, canonical memory authority, encrypted storage, scoped access, lifecycle, exact delivery and agent neutrality. A repeatable comparison with a pinned Mem0 OSS implementation must establish the 2.3.2 baseline **before** production retrieval changes and then compare the same workloads after them. Any 2× speed claim must name the measured workload and comparable boundary. A 10× improvement is a stretch goal, never a default product claim.

This is a 2.3.3 beta scope between the published 2.3.2 baseline and the existing planned 2.4 private/shared memory foundation. It does not bring the 2.4 or 2.8 roadmap work forward by implication.

## User scenarios and independent acceptance

### US1 — Receive a relevant memory or an honest withhold (P1)

An agent user asks a personal question through any supported native adapter. AtMem supplies memory that actually answers it, or explicitly withholds. Topical overlap, diagnostic hashing, untrusted rankers and an expansion alone cannot establish answer support.

**Independent test:** Run answerable paraphrases, topical nonanswers, negation, spelling errors, entity ambiguity, changed facts, multilingual text and no-memory controls through the common preparation contract and supported host adapters. Compare selected record IDs and final bytes with canonical scope and lifecycle state.

### US2 — Investigate retrieval performance and quality (P1)

An operator runs a documented benchmark with a fixed dataset, models, hardware declaration and scope. The report shows the baseline and candidate results for AtMem and pinned Mem0 OSS, including quality, latency, ingestion cost, tokens when measurable, and scope failures. A failure, skip or absent measurement is visible and never counted as a win.

**Independent test:** Repeat on clean temporary state. Tamper with one manifest identity and verify comparison rejection. Run the shipping native `control_prepare` path separately from raw chunk retrieval, then reconcile selected context and exposure evidence.

### US3 — See what changed in the product (P2)

The dashboard and CLI explain whether strong semantic search is configured, whether a result was relevant or withheld, and the measured benchmark identity and limits in readable language. The UI does not imply that a search hit was injected or that a benchmark sample establishes a general victory.

**Independent test:** Check desktop and narrow layouts, keyboard navigation, empty/error states, role restrictions, and CLI/UI agreement against the same service response. The user can move from the summary to case-level evidence without an excessively long single page.

## Functional requirements

- **FR-001:** Preserve the constitution's canonical admission, authorization-before-intelligence, final revalidation, generation/epoch invalidation, exact bytes, encrypted evidence, role controls and source provenance on every optimized path.
- **FR-002:** Capture the pre-change baseline with exact AtMem commit/version, Mem0 package/source revision, dataset hash, ordered cases, selected corpus, embedding and answer model identities, hardware, software, configuration, warm/cold state, per-case outputs and timing boundaries. Preserve prior published results as historical, never overwrite them.
- **FR-003:** Provide at least two labeled comparison profiles: controlled raw retrieval with equal inputs, and native AtMem preparation/injection. Do not call a raw retrieval win an end-to-end memory win. A full end-to-end extraction/answer comparison is required before claiming superiority in memory quality overall.
- **FR-004:** Run Mem0 OSS in an isolated environment and pin the exact version, revision, dependencies and optional NLP/BM25/reranker status. The same question set, source chronology, embedding model, context budget, answer/judge model and scorer must be used for a matched comparison, or the metric must be marked incomparable.
- **FR-005:** Report recall@k, MRR@k, useful-context precision, answer correctness/abstention where evaluated, full prepare-to-context p50/p95/p99, cold and warm latency, ingestion/indexing latency, model calls and cost where observable, with per-case records and confidence intervals where samples permit. Unknown values are unknown, not zero.
- **FR-006:** The 2× target means AtMem's **matched warm full-preparation p95** is at most half Mem0's equivalent authorized retrieval-to-context boundary, with noninferior answer/source quality and zero authorization regressions. If equivalent Mem0 boundaries cannot be measured, report the p95 ratio only on a clearly named common substage and withhold the full-preparation claim. The 10× target uses the same conditions and is stretch only.
- **FR-007:** Establish a separate held-out test partition before tuning. Never add case-specific answer rules, alter the competitor configuration to make AtMem win, compare different budgets without labeling them, or use a tiny sample as a general claim.
- **FR-008:** Native candidate generation must allow authorized lexical, fact-key, semantic and graph/entity nominations to reach ranking independently within bounded quotas; the original query, not an expansion, determines support. Inaccessible records must not affect visible scores through hidden aggregate counts.
- **FR-009:** Direct support must require evidence that the candidate answers the requested relation/attribute, not merely shared topic tokens. Calibrated background and no-useful-memory remain available. Local and strong semantic profiles remain distinct; diagnostic hashing never independently authorizes injection.
- **FR-010:** Cheap query expansion should avoid a companion HTTP/model round trip when deterministic rules suffice. Optional reranking sees only authorized bounded candidates and must be skipped or fail safely when unavailable; no false completed delivery may be recorded.
- **FR-011:** If a cache is activated, its key includes principal/scope and canonical, membership, policy, lifecycle, index, model, calibration and relevant time identities. Cache hits must revalidate authorized current records and produce the same receipt-bound bytes; plaintext must not escape the existing encryption/retention profile.
- **FR-012:** Incremental embeddings may reuse unchanged vectors only for identical content, scope, policy and embedding/preprocessing identities. Correction, forget, key rotation, model change and stale epoch must invalidate as applicable. Staged activation and recoverable rebuilds remain intact.
- **FR-013:** Versioned metric/stage events must expose counts and timings without leaking private query text, semantic metadata or content into logs; at least the candidate, support, optional intelligence, final revalidation and context-packing stages are distinguishable.
- **FR-014:** The benchmark and UI read models must expose aggregate and case-level results with declared profile and limitations, provide readable drilldown, honor viewer/investigator/evidence collector/administrator authorization, and never display inaccessible memory text.
- **FR-015:** Supported OpenClaw, Pydantic AI, LangChain/LangGraph and MCP native context boundaries must consume the same decision and final validation contract. Delegated provider/HMAC/Ed25519 behavior must remain unaffected unless separately specified.
- **FR-016:** This beta's release notes, README, benchmark guide, current-status, roadmap and relevant spec cross-links must agree on shipped versus proposed features, beta install/upgrade/rollback, Mem0 comparison profile and honest limitations. Existing dated historical evidence must retain its date and not be rewritten as a new result.
- **FR-017:** The beta is only ready to publish after relevant Python, AtBot, adapter/OpenClaw, UI, package build, installed-artifact and benchmark gates pass on the exact candidate; release creation follows repository `AGENTS.md`. Preparation alone creates no tag or published package.

## Success criteria

### NumPy acceleration amendment (2026-09-17)

- **FR-018:** Optionally reuse an immutable float64 process-memory vector matrix and immutable source blobs within one open semantic-index instance, bounded to one entry and 32 MiB of retained matrix data, blob objects and blob-tuple storage (not peak working memory). Never persist this cache or share it across instances. Replace the immutable entry atomically and bind it locally before reading. Close releases references before releasing the household lock; oversized matrices use the existing uncached path. Both representations extend decrypted process-memory residency until replacement/close and must never appear in status or logs. No new base dependency, schema, model call or native wheel build is required.
- **FR-019:** Matrix reuse must verify exact ordered vector bytes and dimensions on every search, in addition to the existing subject, epoch, model, policy and canonical/index generation identities. Canonical validation remains per-query. Cached computation must return identical scores and ordered results to the existing NumPy path, including thresholds and ties. Missing NumPy retains the existing fallback. Invalid payloads must fail equally on cold and reused paths.
- **FR-020:** Measure matrix preparation separately from complete search on different queries, including first use, reuse, invalidation and oversized bypass. Report memory and limitations. Do not claim a full-path or Mem0 speedup from a kernel benchmark. Partial top-k selection is deferred until separate evidence justifies its numerical/tie and rejected-candidate complexity.

Validate finite values before publishing a cache entry. Benchmark repeated distinct
queries and alternating subjects with median/p95 and sample counts; report any
single-entry thrashing cost. Distinguish plaintext and encrypted backend evidence;
an unmeasured backend is explicitly unmeasured, never covered by another result.

Measured amendment revision: retain the ordered immutable source-blob tuple for
exact byte comparison instead of hashing on reuse. The 32 MiB ceiling includes
float64 matrix bytes, blob objects and tuple overhead. No digest substitution is
needed for identity: equal ordered bytes are a stronger equality check.

Enable reuse only with explicit `SemanticIndex(cache_vectors=True)` for long-lived
callers. Default one-shot/native retrieval remains unchanged. Local purge,
generation discard and policy invalidation clear retained references immediately;
external mutations are detected on the next search, not by a background watcher.
Dropping references is not guaranteed memory zeroization.

This amendment is an independently executable slice (T024–T028); it does not
complete the broader beta tasks or authorize release. Re-reading vector bytes
is deliberately retained so cache reuse cannot mask direct sidecar corruption.

- **SC-001:** Pre-change and post-change benchmark reports are reproducible from immutable manifests and contain no silent skips or mismatched configurations.
- **SC-002:** On the declared held-out native-path workload, zero unauthorized injections, stale deliveries, wrong-scope hits or changed exact context bytes occur; existing deterministic and adapter conformance gates pass.
- **SC-003 (future research):** On a matched, statistically adequate warm workload, p95 reaches the FR-006 2× target with noninferior quality. This remains unachieved and is not a 2.3.3 tagging gate under the approved scope amendment. A 10× result may be reported only if measured under the same rules.
- **SC-004:** Independent nonanswer, multilingual, correction and ambiguous-relation fixtures improve or retain quality; topical overlap alone no longer produces direct support in the specified nonanswer fixture.
- **SC-005:** Counting-embedder and failpoint tests prove unchanged records are not redundantly embedded on a one-record update, and no partial index result becomes canonical success.
- **SC-006:** Dashboard and CLI present the same authenticated benchmark summary and case evidence on desktop and mobile; a viewer never sees protected plaintext.
- **SC-007:** Documentation and spec audit has no unresolved contradiction affecting 2.3.3's scope, installed behavior or release claims; links and version/pin checks pass.

## Scope limits and compatibility

### Core hybrid retrieval amendment (2026-09-17)

- **FR-021:** The host-neutral `eligible_candidates` path must rank independent authorized lexical and semantic nominations using a versioned deterministic fusion rule, rather than mixing raw lexical and cosine scores. A lexical-only result must be able to enter even when absent from semantic nominations, and vice versa. `Memory.recall` remains the legacy lexical/graph API; this amendment must not silently market it as semantic retrieval.
- **FR-022:** Authorization and lifecycle filtering must precede channel limits and fusion. Excluded, inactive, other-subject, other-workspace or remote-egress-denied records must not affect returned ranks or scores. Scoped lexical corpus statistics must not include denied records. Revalidate canonical content before candidate publication and retain the existing final context validation. Diagnostic hashing never establishes semantic answer support.
- **FR-023:** Rank evidence must name the fusion version, channel ranks and raw channel signals separately. Rank fusion is a nomination prior, never an answer-support probability. Existing `min_score` must not be applied to tiny raw RRF values as though they were cosine similarity. Missing or incompatible semantic indexes must preserve useful lexical retrieval without fabricating semantic evidence.
- **FR-024:** Test exact identifiers, semantic paraphrases, complementary matches, duplicate candidates, empty results, contradictory/stale facts, denied scopes and media-derived text. Compare pre-change ordering and core hybrid ordering on frozen fixtures; report quality and latency separately. Mem0 parity/superiority remains an empirical target; historical semantic-only timing results are not transferable to this new path.

The independently executable core-hybrid slice is T029–T033. Existing NumPy
matrix caching remains off by default. No schema, package dependency, external
egress or release change is authorized. New fusion must not change delegated
provider-owned context or pretend to understand raw multimodal bytes.

Compatibility: add validated `RecallRequest.retrieval_strategy="core-rrf-v1"`.
Default `legacy` preserves existing graph and adapter behavior. Opted-in mixed
requests use new lexical/fact/semantic fusion;
requested graph was initially deferred; the graph amendment below replaces that
deferral. Legacy graph-only and `Memory.recall` retain their
existing behavior, outside FR-022's new fusion guarantees. This changes candidate
ordering and may reduce graph-only coverage on mixed requests; it must be tested
and disclosed rather than called complete feature parity. `min_score` gates native
lexical/fact 0–1 composite priors; semantic nomination uses a versioned 0.0 floor
and the existing calibrated production threshold still governs answer support.
Cap the authorized corpus at 10,000 records / 8 MiB content-plus-fact-key bytes;
overflow is an explicit error, never silent truncation or success. Streaming
authorization precedes this cap, and the ephemeral index closes after each call.

An explicit self-age query must not become directly supported solely by a
relative's age. A bounded original-query subject guard is covered by the core
fixtures; it is not a general semantic entailment or negation guarantee.

Base install stays local-first and Python 3.10–3.13 compatible. Optional models and Mem0 stay out of default dependencies. No new automatic admission, hidden egress, semantic deletion, causal inference or migration of live memory is authorized by this feature. Existing SQLite Home, evidence and delegated contracts must remain readable. Any new persisted derivative needs versioned migration and verified deletion; prefer a no-schema beta slice if equivalent quality/speed can be obtained safely.

**Benchmark interpretation:** A 2× quality improvement cannot be claimed for a bounded metric already near 1.0; the numerical multiplier is a future speed target. Quality remains a noninferiority and per-category improvement gate for default promotion. The approved stable scope does not claim the outstanding comparative gates passed. No “beats Mem0” claim is permitted without the specific comparable profile result.

### Scoped graph nomination amendment (2026-09-17)

- **FR-025:** Opted-in core fusion must accept graph-only and mixed graph requests. Derive an ephemeral associative graph exclusively from the authorized canonical corpus using the existing conservative fact extractor. Hidden edges, aliases, entity merges and global graph statistics must not affect nominations, scores or paths. Persisted alias/merge support is explicitly not included in this slice; legacy graph remains unchanged.
- **FR-026:** Graph nomination must independently discover connected records within two edges, with deterministic seeds, stable ties, cycle prevention and no traversal back through the user-root supernode. Bound seeds to 16, edge visits to 256 and output to min(candidate_limit, 256). Report budget truncation rather than imply exhaustive traversal. Path evidence must identify canonical supporting records, normalized entities and relations. Revalidate all supporting records before publication; path connectivity is not answer support or causal proof.
- **FR-027:** Prove independent two-edge discovery, denied-bridge/alias noninterference, scope/egress/lifecycle isolation, cycles/root-fanout bounds, deterministic truncation and stale-path rejection. Compare legacy, fusion without graph and fusion with graph on frozen calibration plus explicit graph fixtures. Report extraction coverage and latency; no graph-quality claim from a corpus with no extracted edges. Keep defaults and matrix caching unchanged until broader quality/release gates pass.

T036–T039 execute this bounded amendment independently. T035 remains open for
reuse/scaling and adapter activation. Graph-only core requests now become valid;
non-graph core requests retain their existing ordering. No persisted schema,
dependency, egress, delegated-provider or release-version changes are included.
