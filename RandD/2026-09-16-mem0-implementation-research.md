# Mem0 implementation research and AtMem adoption plan

**Date:** 16 September 2026. **Status:** research and proposed engineering work, not a shipped feature or comparative performance result.

## Decision in brief

AtMem should adopt Mem0's emphasis on self-contained extracted facts, contextual extraction, batched indexing, complementary retrieval signals and optional reranking. It should **not** copy Mem0's current algorithm wholesale. Preserve AtMem's canonical authority, corrections, source evidence, access checks and exact-delivery proof.

The immediate opportunity is not another always-on large model. It is a better-connected, measured retrieval pipeline: strong embeddings when configured, independent candidate generation, calibrated answer support, cheap common-case execution, incremental indexing and an actually integrated cache. Some of these components already exist in AtMem, but existence in the repository does not establish that the production path uses them efficiently.

The research reproduced three AtMem classifier behaviors and four Mem0 scoring properties using synthetic, offline probes. Thirty existing focused AtMem tests pass. **No full Mem0-versus-AtMem benchmark was run, and neither faster retrieval nor superior answer quality is established.**

## 1. Evidence boundary and exact versions

| Item | Examined baseline |
| --- | --- |
| Mem0 source | Commit `0df3e4b87df20785f0741370c75e44428796193e`; package declares `mem0ai==2.0.20` |
| Algorithm terminology | The code calls its additive ingestion/hybrid retrieval design **V3**; this is not a claim that the Python package major version is 3 |
| AtMem source | Branch `benchmark`, HEAD `00f36abe0381edcb6040de2d17b491bdbb19791f`, plus existing untracked MemoryBench integration inspected separately |
| Video | Hugging Face / Alejandro AO, *Agent Memory EXPLAINED – Complete Architecture*, user-supplied link; English caption track read |
| Execution | Offline scoring/classification probes and four focused AtMem test modules; no paid model calls, live-memory migration or production configuration changes |

Mem0 was cloned under `/tmp/atmem-mem0-research.6BAkC2/mem0`. Runtime paths below were inspected in that checkout. The Python version and license are directly recorded in [Mem0's pinned package metadata](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/pyproject.toml).

Three products/evidence sets must remain separate:

1. The historical algorithm and experiments in the [2025 Mem0 paper](https://arxiv.org/abs/2504.19413).
2. The current open-source implementation pinned here.
3. The managed platform, whose internal execution and current performance were not independently inspected.

Old descriptions of extraction followed by an LLM choosing ADD/UPDATE/DELETE do not describe the examined default additive write path. Hosted temporal capabilities also cannot be assumed to exist in the OSS SDK: its `search(reference_date=...)` explicitly rejects that parameter as platform-only. [Pinned search implementation](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L1379).

## 2. The supplied video: useful architecture, checked against code

The [video](https://www.youtube.com/watch?v=aYfZN8t6AQs) distinguishes conversation state from persistent memory; covers the main memory, entity and history stores around **4:26**; ingestion around **8:06**; retrieval around **15:30**; and keyword/entity boosts around **19:19**. Its key limitation is explicit: those boosts only reorder the initial semantic pool. The local-model discussion around **25:38** is guidance, not an AtMem hardware benchmark.

Two qualifications matter. The extraction prompt supports more context fields than the examined call actually supplies. The scoring denominator is 2.5 only when both additional signals are present; it adapts otherwise. For AtMem, persistence requires independence from the agent session's lifecycle—not necessarily separate physical database files. One portable AtMem Home can still contain logically separate evidence, canonical memory and rebuildable indexes.

## 3. Mem0 ingestion: where the useful work happens

### Actual default path

The synchronous `_add_to_vector_store` path performs:

`new messages → recent session messages + retrieved memories → one extraction LLM call → batch embeddings → exact deduplication → batch memory/history writes → entity linking → save messages`

It loads the last ten messages, embeds the flattened new messages and retrieves ten existing memories. These provide context for extraction, including pronoun resolution and avoiding repeated facts. The extractor emits self-contained facts instead of storing the whole conversation as the primary searchable unit. The `infer=False` route is different: it stores individual non-system messages directly and should be benchmarked as a separate ingestion policy. [Pinned write implementation](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L879).

### Prompt quality is a substantial part of the system

The additive prompt emphasizes specific, independently understandable statements, preserving useful detail, resolving references and avoiding conversational filler. It distinguishes recommendations made to the user from the user's own preferences. This is more valuable than simply increasing vector dimensions: an embedding cannot reliably recover a fact that extraction dropped or misattributed. [Pinned extraction prompt](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/configs/prompts.py#L468).

The prompt builder accepts summary, recently extracted memories and timestamp/date inputs, but the inspected OSS call passes existing memories, new messages, recent messages and custom instructions. Do not credit an unused argument as a completed feature. Similarly, prompt-mentioned relationship IDs are not evidence of a maintained causal graph; actual entity-to-memory links are constructed separately. [Prompt builder](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/configs/prompts.py#L1016), [call site](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L945).

**AtMem adaptation:** extend the proposal package with bounded, authorized prior messages and relevant canonical facts, each with immutable source identity. Keep the extractor proposal-only. Dates must come from trusted source timestamps, not the model's guessed current date. “She prefers it now” should resolve only when authorized context establishes both referents; otherwise preserve uncertainty.

AtBot already has structured fact proposals and validation; `propose_memories` currently supplies one message and deliberately returns no related record IDs because it has not received existing records. Build on that contract instead of inventing a second canonical writer. [AtBot runtime](../packages/atbot/src/atbot/companion.py), [proposal validation](../packages/atbot/src/atbot/extraction.py).

### Batching is valuable; current deduplication is limited

Mem0 batches extracted-text embeddings, main vector inserts, history writes and unique entity embeddings. Its OpenAI embedder retains a client, chunks batches at 100 and checks response cardinality. Its Qdrant adapter supports batch queries with a sequential fallback. These reduce per-item overhead; they do not prove a particular end-to-end speed advantage. [Embedder](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/embeddings/openai.py), [Qdrant adapter](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/vector_stores/qdrant.py#L437).

The examined deduplication uses MD5 of the extracted text, against retrieved existing memories and the current batch. It occurs **after embedding**. It is neither global semantic deduplication nor an integrity/security claim. Rephrased duplicates can survive, and exact deduplication needlessly spends embedding work when done this late.

**AtMem adaptation:** perform scope-bound exact deduplication before embedding; batch genuinely new work; reuse embeddings only when content, model/revision, preprocessing and applicable policy identity match. Treat semantic near-duplicates as proposals, not automatic permission to merge distinct facts or erase evidence.

### Do not copy additive semantics or failure ambiguity

Add-only extraction simplifies ingestion, but “I moved from Paris to Berlin” cannot leave both assertions eligible as undifferentiated present truth. AtMem's supersession, historical evidence and conflict handling are strengths to preserve.

The examined Mem0 code raises an `LLMError` for provider failures, but a parse failure can become an empty extraction. Batch vector insertion failures fall back per item; individual insert failures are logged, yet the eventual result is built from the original prepared record list. History and entity work are separate. This is a **source-observed partial-failure risk**, not a reproduced live data-loss incident. [Failure and return paths](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L1045).

AtMem should distinguish `no_facts`, `extraction_failed`, `canonical_committed`, `index_pending` and `index_failed`. Use a durable outbox for rebuildable derivatives and test crash/retry boundaries. Never describe preparation as durable successful storage.

## 4. Mem0 retrieval: three signals, one candidate pool

The inspected search defaults are `top_k=20`, `threshold=0.1`, `rerank=False`. It lemmatizes the query, extracts entities, embeds the query, obtains semantic candidates, performs keyword search, computes entity boosts and fuses scores. Its internal semantic pool is `max(top_k × 4, 60)`. [Search stages](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L1628).

### Keyword matching

Stored lemmatized text and query lemmatization reduce word-form mismatch. Backend keyword results are normalized with a query-length-dependent sigmoid. For Qdrant, keyword support depends on a BM25 sparse slot and encoder being available; it is not guaranteed merely by importing Mem0. Missing spaCy causes the lemmatizer to return original text, while entity extraction can return no entities. Thus degraded behavior is configuration-dependent, not universally “all three signals work” or “only vectors work.” [Lemmatization](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/utils/lemmatization.py), [keyword implementation](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/vector_stores/qdrant.py#L454).

### Entity boosts

The extractor combines named entities, selected noun phrases and technical identifiers, with generic-term rejection. Entity vectors link to memory IDs. Query processing is bounded to a small entity set; matching entities boost linked semantic candidates. The boost discounts highly connected entities approximately as:

`similarity × 0.5 / (1 + 0.001 × (linked_memory_count − 1)²)`

The maximum matching entity boost is used per memory. This can favor a specific project or person over a generic hub. It is an associative retrieval mechanism, **not causal inference**. A separate entity vector collection is not a counterfactual model. [Entity extraction](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/utils/entity_extraction.py), [boost implementation](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L1732).

AtMem should reuse its governed graph/entity identities, distinguish same-name entities and compute degree statistics within the authorized view. An inaccessible record must not change visible rankings through a hidden shared count.

### Scoring limitations, reproduced

Mem0 loops only over semantic candidates. Keyword-only and entity-only hits cannot introduce a missing candidate. The raw semantic threshold applies **before** boosts. The score is then divided by 1, 1.5, 2 or 2.5 depending on available signal maps; it is not a calibrated probability of relevance. [Scoring source](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/utils/scoring.py).

Our pure-function probes establish:

| Synthetic input | Observed behavior |
| --- | --- |
| Strong keyword hit absent from semantic pool | Never returned |
| Semantic 0.09, keyword 1.0, entity 0.5; threshold 0.1 | Excluded before fusion |
| Semantic 0.8; add a keyword map containing only a different ID | Returned score changes from 0.8 to 0.4 |
| Semantic 0.15 and an unrelated keyword score; threshold 0.1 | Returned combined score is 0.075 |

These properties may be intentional, but they make blindly transplanting thresholds incorrect. AtMem should use an authorized **union** of independently nominated lexical, semantic, fact-key and bounded graph candidates, then evaluate reciprocal-rank fusion (RRF) against calibrated score fusion. Keep original-query relevance separate from authority and from popularity/trust.

### Reranking and concurrency

Mem0's optional reranker is applied after the first top-k selection. It cannot recover a candidate already removed by that cut. A local cross-encoder processes pairs in batches; the alternative LLM reranker scores documents sequentially and should not be presented as a speed optimization. [Cross-encoder](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/reranker/sentence_transformer_reranker.py), [LLM reranker](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/reranker/llm_reranker.py).

The synchronous top-level retrieval stages are sequential. The async version awaits successive stages as well; entity lookups have internal concurrency. Also, the slow-search timer is stopped before optional reranking. Measure full request wall time externally instead of treating this internal timer as complete latency. [Sync timing](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L1490), [async retrieval](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/memory/main.py#L3293).

## 5. AtMem's concrete gaps, not generic feature suggestions

### 5.1 Retrieval and admission are being confused in the classifier

AtMem already combines lexical, semantic and graph candidates. Its native manager then runs `decide_retrieval` before AtBot selection. This is valuable for withholding unsupported context, but the current deterministic label is stronger than the evidence behind it.

The classifier uses English/ASCII concept tokens, manually maintained aliases and fixed thresholds. Lexical support of 0.5 can establish “direct support.” Production semantic support is gated at 0.72. Trust/recency are priors, not proof of relevance; that separation should stay. [Classifier](../atmem/retrieve/rank.py), [calibration](../atmem/retrieve/calibration-v1.json).

Offline observations:

| Question / candidate | Result | Interpretation |
| --- | --- | --- |
| “How old is my daughter?” / “My daughter likes drawing.” | `direct_support`, relevance 0.5 | Topic overlap does not answer the age question |
| Persian age question / Persian age statement, lexical-only input | No selected memory | ASCII tokenization loses this lexical signal |
| “Where do I reside?” / “Home: Paris.” with synthetic production similarity 0.71 versus 0.73 | Withhold versus select | Fixed threshold discontinuity; synthetic scores, not measured embedding outputs |

The first result proves a classifier defect, not that every downstream agent necessarily gives a wrong answer; a later model may reject the candidate. The multilingual example does not claim configured multilingual embeddings fail. Add these cases to independent held-out fixtures and distinguish topical relevance from relation/attribute support.

### 5.2 Some latency is avoidable orchestration

Native `prepare` calls AtBot query expansion before candidate retrieval, then calls AtBot again for eligible-candidate selection. Expansion is **rule-based** in the examined companion—not generative—but still crosses HTTP. The client performs health checks and has an expansion request timeout up to 10 seconds; query handling has a default timeout of 90 seconds. These are failure-path timeout settings, not observed normal latency. The no-companion/fallback path remains available. [Manager](../atmem/control/manager.py), [client](../atmem/control/atbot_companion.py), [companion](../packages/atbot/src/atbot/companion.py).

Candidate generation loops through up to six expanded queries sequentially. Duplicate rows retain one score and final ordering prioritizes expansion order; this is not a global fusion of all query/result ranks. **Recommendation:** keep cheap expansion local, batch query embeddings where needed, cap total work and retain original-query evaluation. Invoke model selection only for calibrated ambiguity or multi-hop needs. Query rewriting should not become a mandatory expensive step merely because a tutorial recommends it.

### 5.3 Exact semantic scan is safe but has a scaling cost

`SemanticIndex.search` fetches the active subject/epoch vector set and computes exact similarities, with an optional NumPy block at scale. This is not an ANN index. Preserve it as a correctness oracle and a good small-corpus mode. For larger stores, test an optional local approximate index with scoped candidate selection and canonical final validation; do not replace it just to claim ANN support. [Semantic index](../atmem/semantic/index.py).

`SQLiteStore.recall_candidates` also fetches active fact-key rows and checks matches in Python. A bounded returned result list does not bound that scan. An indexed normalized fact lookup is a high-value experiment, subject to the same encryption and authorized-query requirements. [SQLite retrieval](../atmem/store/sqlite.py).

### 5.4 Batch rebuild is not incremental indexing

AtMem already batches document embeddings in `SemanticIndex.build`. However, `Memory.close` can synchronize dirty subjects by calling that rebuild path. A fresh build creates a new epoch; resumption reuses only an unfinished matching build, not unchanged entries from the active epoch. A normal completed previous epoch is therefore not an embedding reuse cache. This is a source-level opportunity to measure: use a counting embedder to prove whether a one-record update causes N embeddings on each affected public path. [Synchronization](../atmem/memory.py), [build and checkpoint selection](../atmem/semantic/index.py).

Adopt content/model/policy-bound reuse and incremental derivative updates, while retaining staged activation, crash recovery and final generation checks. Do not trade correctness for in-place unversioned vector mutations.

### 5.5 A cache component exists but is not on the runtime path

`RetrievalDecisionCache` has careful scope/generation/epoch/calibration keys and final reload behavior. Repository search found definitions and exports, but no production caller. Its unit tests and Spec 008 T009 being checked do not establish a runtime cache speedup. Integrate and instrument it rather than adding a second cache. [Cache](../atmem/retrieve/cache.py), [Spec 008 task history](../specs/008-retrieval-quality-and-reranking/tasks.md).

Cache IDs and decision metadata where possible, not indefinitely retained plaintext. Bind membership/policy, evaluation-time semantics and model identity; revalidate before delivery. Repeated exact queries and query embeddings are safer initial targets than semantic answer caching.

### 5.6 Production and benchmark paths differ

The existing untracked MemoryBench adapter builds session chunks, uses lexical/semantic RRF and a substantially larger context budget. It does not exercise the native manager's complete expansion/classification/AtBot/default-budget path. The native `prepare` defaults include three records and 1,200 characters; the adapter has a 16,000-character budget. Neither a tiny successful pilot nor raw-chunk retrieval establishes the quality of normal AtMem injection. [Adapter](../atmem/benchmark/memorybench.py), [native manager](../atmem/control/manager.py).

Benchmark both explicitly. Upgrade context packing to a declared token budget with deduplication, diversity and source coverage; avoid spending the entire budget on redundant variants of one fact. Preserve all exact-delivery and context-envelope evidence.

## 6. Architecture to adopt

| Layer | Adopt or strengthen | Preserve / avoid |
| --- | --- | --- |
| Capture | Independent full-fidelity host-observed evidence | Extraction must not replace raw multimodal evidence |
| Extraction | Bounded prior context, self-contained facts, source/time/attribution, batch proposals | No assistant claim silently promoted to a user fact |
| Admission | Scope-bound dedup, explicit correction and historical validity | No automatic destructive LLM reconciliation |
| Indexing | Incremental, batched, versioned lexical/vector/entity projections | Canonical DB remains authority; indexes are rebuildable |
| Candidate generation | Independent lexical, semantic, fact and bounded graph nominations | No semantic-only bottleneck; no unauthorized aggregate influence |
| Ranking | Measured fusion and relation-aware support; optional small reranker | Scores are not probabilities; do not always call a generative model |
| Delivery | Token-budget packing and canonical final reload | Exact authorized bytes, current grants and flight evidence |

Keep three distinct objects: **source evidence**, **accepted memory assertions**, and **derived retrieval indexes**. Text from image OCR/audio transcription is a sourced derivative, not the original media or an automatically true user assertion. Entity/vector search over such derivatives is not by itself multimodal retrieval; a future image/audio embedding profile needs its own measured contract.

Delegation remains compatible: a Mem0-backed provider can select context and AtMem can authenticate, authorize and verify exact delivery. Provider-owned bytes must not be rewritten, mixed with native context or retained contrary to the agreed provider contract. Native retrieval improvements and provider composition are distinct workstreams. Neither Mem0's identity filters nor an entity collection replace AtMem's authenticated scope boundary.

Mem0 uses Apache-2.0; this research copies no Mem0 implementation into production. Prefer independently implemented techniques with attribution. If later copying code or prompts, retain the applicable license/notice obligations and review every bundled model's separate license. [License](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/LICENSE).

## 7. Proposed implementation sequence and acceptance gates

These are **new proposed work packages**, not retroactively completed Spec Kit tasks or changed release commitments.

| Order | Work package / main files | Required evidence before enabling |
| --- | --- | --- |
| P0-A | Native-path benchmark and stage timers: `control/manager.py`, `benchmark/` | Search, policy, packing and delivery timed separately; installed host path represented; fixed corpus/model/budget manifests |
| P0-B | Classifier regression suite: `retrieve/rank.py`, `calibration*`, quality tests | Daughter-age nonanswer, multilingual, negation, pronouns, corrections, absent facts; held-out evaluation, no benchmark-specific aliases |
| P1-A | Cheap deterministic fast path: manager and companion client | No companion request for proven unambiguous direct facts; bounded fallback; identical authority/delivery checks; measure p95 with companion unavailable |
| P1-B | Integrate existing decision/query-embedding caches | Hits actually avoid upstream work; revocation, policy, epoch, membership, expiry and correction invalidate; race tests prove final reload |
| P1-C | Incremental embedding reuse and batch extraction/index outbox | Counting embedder: one new fact does not re-embed unchanged corpus; replay/crash tests; no successful receipt for failed canonical write |
| P2-A | Candidate union + measured fusion + indexed fact lookup | Keyword-only and graph-only relevant candidates can reach ranking; bounded per-channel quotas; inaccessible records cannot affect selection |
| P2-B | Optional bounded cross-encoder, before final context cut | Quality/latency ablation versus deterministic path and AtBot; no widening scope; clean fallback on timeout/malformed output |
| P2-C | Contextual extraction package | Pronoun/date/attribution fixtures; referenced IDs restricted to authorized package; per-source provenance; correction lineage preserved |
| P3-A | Scoped entity rarity, aliases and typed retrieval signals | Same-name separation, common-hub noise tests, delete/unlink and membership races; no causal claims |
| P3-B | Optional ANN and token-aware packing | Exact-search oracle comparison, recoverable index builds, measurable scale benefit, budget/source-coverage tests |

Dependencies: P0 precedes performance claims; P1-B depends on correct invalidation contracts, not on a cached happy path; P2-C consumes canonical admission, not a second store; P3-A needs scoped entity identity. P1-A must not shortcut P0-B's support-quality work.

Suggested first implementation slice: **measurement + classifier regressions + local cheap expansion + guarded cache integration**. Next address incremental indexing and candidate fusion. This gives a testable improvement without turning the next release into a rewrite of all memory, graph and evidence subsystems.

### Fit with the existing roadmap

Specs [001](../specs/001-memory-quality-benchmarks/spec.md), [006](../specs/006-memory-extraction-and-updating/spec.md), [008](../specs/008-retrieval-quality-and-reranking/spec.md) and [009](../specs/009-entity-relationship-memory/spec.md) already own the relevant quality, extraction, retrieval and graph foundations. New tasks should extend those contracts, preserving completion history. Spec [026](../specs/026-temporal-memory-consolidation/tasks.md) separates 2.4 temporal foundations from later background consolidation; contextual date handling must respect that distinction.

The [roadmap](../docs/release-roadmap.md) currently prioritizes authenticated private/shared spaces for 2.4. Add a bounded retrieval-quality/performance track alongside that foundation rather than postponing all improvements to 2.8, or silently removing the access work. This is a recommended scope amendment, **not a modification of the approved roadmap in this research**. Full scheduled consolidation and causal simulation are not prerequisites for fixing today's search path.

## 8. How to determine whether the adopted strategy actually wins

Run two complementary comparisons, with immutable manifests:

1. **Controlled retrieval:** same accepted memories, embedding model/revision, hardware, query set and context-token budget. This isolates candidate generation/ranking from extraction.
2. **End-to-end memory:** same chronological conversations, ingestion opportunities, answer model and evaluator. Each product uses its stated extraction pipeline; report resulting storage, tokens, cost and source coverage as well as answers.

Record native AtMem separately from the experimental raw-chunk MemoryBench adapter. Record Mem0 OSS configuration separately from any managed-service comparison. Pin BM25/NLP/reranker availability; otherwise “Mem0 hybrid” may actually be a degraded configuration. Warm local model loading before warm-cache runs, but publish cold start too. Mem0's spaCy loader can attempt to download a missing language model; pre-provision approved assets and disable surprise downloads in offline test profiles. [Loader](https://github.com/mem0ai/mem0/blob/0df3e4b87df20785f0741370c75e44428796193e/mem0/utils/spacy_models.py).

Measure:

- Relevant-source recall@k, ranking quality, useful-context precision and context-token efficiency.
- Answer accuracy, attribution, current/historical correctness and appropriate abstention, including unanswerable questions.
- p50/p95/p99 full retrieval-to-prepared-context latency, cold/warm state, throughput under concurrent users, RSS and CPU.
- Ingestion latency, model/API tokens, embeddings per new fact, write amplification and index catch-up delay.
- Scope leakage, stale grant delivery, poisoned-memory influence and false durable-success reports.

Stratify by personal facts, preferences, entity relations, multi-hop questions, temporal changes, exact identifiers, multilingual input and noisy sessions. Use small/medium/large corpora—for example 1k, 10k and 100k memories—as planned scale profiles, not claims already tested. Keep calibration and evaluation users/conversations separate; do not tune rules against leaderboard answers.

Run ablations: lexical; semantic; their union; +fact keys; +entities; +optional reranker; +cache. Measure caches with realistic repeat rates and also unique-query workloads. Quality improvement must not merely be a larger context budget. Faster cached queries must not hide slower cache misses.

Pre-register a non-inferiority margin for answer quality and a practically meaningful latency improvement, report paired confidence intervals and per-category regressions. “Beats Mem0” requires the named version/configuration and reproducible held-out results; a five-question pilot or vendor headline cannot support it. Benchmark results do not prove zero security risk, and passing synthetic scope cases is only the start of that assurance.

## 9. Reproduction and observed results

Run the research-only probe against the pinned checkout:

```sh
.venv/bin/python RandD/mem0_retrieval_probes.py /tmp/atmem-mem0-research.6BAkC2/mem0
```

It checks the Mem0 revision, imports only its dependency-free scoring module and runs synthetic AtMem classification. It does not create a memory database or call external models. Assertions passed; the output reports the cases detailed above. The companion script intentionally documents current shortcomings—it is not a production regression suite whose expectations should remain unchanged after fixes.

Existing focused checks:

```sh
.venv/bin/python -m pytest -q \
  tests/test_retrieval_quality.py \
  tests/test_retrieval_signals_and_cache.py \
  tests/test_retrieval_cache.py \
  tests/test_atbot_companion.py
```

**Observed:** 30 passed in 3.74 seconds. This is not the full AtMem suite, an installed-host acceptance run or the Mem0 suite. No production implementation changes, package upgrades, deployment, commit or publication were performed for this research. Existing untracked benchmark work was preserved.

## Bottom line

Adopt the retrieval and ingestion disciplines that survive source review and measurement, not the Mem0 name or its defaults. AtMem can pursue **useful retrieval with low common-case latency plus independent evidence and governance**. The next engineering goal is to prove that combination on the actual shipping injection path—not to add more components or declare superiority before testing.
