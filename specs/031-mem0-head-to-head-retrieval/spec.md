# Feature Specification: 2.3.3 Beta Retrieval and Mem0 Comparison

**Feature directory:** `specs/031-mem0-head-to-head-retrieval`
**Created:** 2026-09-16
**Status:** Specified; implementation and release evidence pending
**Target:** AtMem `2.3.3b1`; matching OpenClaw bridge `2.3.3-beta.1` if released. AtBot retains its independent version unless changed.

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

- **SC-001:** Pre-change and post-change benchmark reports are reproducible from immutable manifests and contain no silent skips or mismatched configurations.
- **SC-002:** On the declared held-out native-path workload, zero unauthorized injections, stale deliveries, wrong-scope hits or changed exact context bytes occur; existing deterministic and adapter conformance gates pass.
- **SC-003:** On a matched, statistically adequate warm workload, p95 reaches the FR-006 2× target with noninferior quality. If it fails, a 2.3.3b1 release candidate is not cleared for tagging; the measured result and blocker are reported. A 10× result may be reported only if measured under the same rules.
- **SC-004:** Independent nonanswer, multilingual, correction and ambiguous-relation fixtures improve or retain quality; topical overlap alone no longer produces direct support in the specified nonanswer fixture.
- **SC-005:** Counting-embedder and failpoint tests prove unchanged records are not redundantly embedded on a one-record update, and no partial index result becomes canonical success.
- **SC-006:** Dashboard and CLI present the same authenticated benchmark summary and case evidence on desktop and mobile; a viewer never sees protected plaintext.
- **SC-007:** Documentation and spec audit has no unresolved contradiction affecting 2.3.3's scope, installed behavior or release claims; links and version/pin checks pass.

## Scope limits and compatibility

Base install stays local-first and Python 3.10–3.13 compatible. Optional models and Mem0 stay out of default dependencies. No new automatic admission, hidden egress, semantic deletion, causal inference or migration of live memory is authorized by this feature. Existing SQLite Home, evidence and delegated contracts must remain readable. Any new persisted derivative needs versioned migration and verified deletion; prefer a no-schema beta slice if equivalent quality/speed can be obtained safely.

**Benchmark interpretation:** A 2× quality improvement cannot be claimed for a bounded metric already near 1.0; the numerical multiplier is a speed target. Quality is a noninferiority and per-category improvement gate. If the speed or quality gate is unmet, the beta release is blocked pending more work or an explicit scope revision. No “beats Mem0” claim is permitted without the specific comparable profile result.
