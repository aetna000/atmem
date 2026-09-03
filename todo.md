# AtMem product todo

Goal: close the practical memory-quality, scale, and ecosystem gaps with Mem0
without weakening AtMem's authority, provenance, privacy, deletion, shadow mode,
or exact-delivery guarantees.

## P0 — Prove and improve memory quality

### 1. Memory benchmarks

- [x] Add LongMemEval and small deterministic regression datasets.
- [x] Measure extraction accuracy, contradiction handling, recall, incorrect
      injection, privacy leakage, poisoning, latency, tokens, and model cost.
- [x] Test deterministic fallback separately.
- [x] Test local embeddings separately.
- [ ] Test the local AtBot profile end to end with a configured local model.
- [ ] Test the hosted AtBot profile end to end with recorded provider, model,
      token, cost, and egress evidence.
- [x] Compare with a pinned Mem0 OSS setup using the same models and data.
- [x] Publish reproducible commands, configurations, results, and limitations.

**Done when:** every memory-quality claim is backed by a repeatable release gate.

### 2. Easy high-quality semantic retrieval

- [ ] Keep dependency-free hashing as the safe base fallback.
- [ ] Add one-command setup for a strong local embedding model.
- [ ] Detect weak, missing, stale, or incompatible indexes in CLI and dashboard.
- [ ] Rebuild indexes safely after model changes.
- [ ] Show model identity, dimensions, epoch, digest, and health.
- [ ] Recommend local models based on available hardware.

**Done when:** a new user can enable and verify paraphrase recall in minutes.

### 3. Better automatic extraction and updating

- [ ] Distinguish durable facts, temporary state, episodes, procedures, and
      content that should not be remembered.
- [ ] Resolve pronouns and entities using bounded recent context and eligible
      existing memory.
- [ ] Detect duplicates, refinements, contradictions, corrections, and
      superseding facts.
- [ ] Produce typed `ADD`, `UPDATE`, `SUPERSEDE`, `REJECT`, and `NOOP`
      proposals with reasons and source evidence.
- [ ] Send uncertain or sensitive proposals to review.
- [ ] Detect poisoning and instruction-as-memory before admission.

**Done when:** changing statements produce one clear current memory with a
complete history instead of polluted duplicates.

### 4. Better retrieval and ranking

- [ ] Evaluate lexical, fact-key, vector, entity, graph, trust, recency, and
      AtBot ranking signals independently.
- [ ] Add calibrated thresholds and a reliable “no useful memory” result.
- [ ] Prevent a generally related memory from being presented as a direct
      answer.
- [ ] Add optional local cross-encoder reranking with deterministic fallback.
- [ ] Explain every result by signal, score, scope, policy, and final rank.
- [ ] Test paraphrases, aliases, multi-hop and temporal questions, conflicts,
      unrelated queries, and privacy boundaries.

**Done when:** correct paraphrases recall, unrelated queries inject nothing, and
every selection is explainable.

## P1 — Storage, scale, and relationships

### 5. Entity and relationship memory

- [ ] Extract canonical entities, aliases, types, and evidence-bound relations.
- [ ] Link every entity and relation to canonical memory and source.
- [ ] Add authorized bounded multi-hop retrieval.
- [ ] Handle entity merge, split, rename, deletion, and supersession.
- [ ] Add graph-quality and cross-scope leakage tests.

**Done when:** relationship questions work across memories and every traversed
edge remains authorized and auditable.

### 6. Production storage backends

- [ ] Define versioned canonical-store and derived-index interfaces.
- [ ] Add PostgreSQL as a canonical storage option.
- [ ] Add pgvector and Qdrant as derived vector-index options.
- [ ] Preserve SQLite and the local sidecar as the default.
- [ ] Test transactional mutation, rebuild, backup, restore, migration, and
      verified deletion for every backend.
- [ ] Define dataset-size, concurrency, and p95 latency targets.

**Done when:** AtMem scales beyond one local process without making a vector or
graph database authoritative.

### 7. Safe performance improvements

- [ ] Profile candidate generation, indexes, graph search, reranking, context
      preparation, and evidence recording separately.
- [ ] Add database indexes from measured query plans.
- [ ] Cache only scope-bound, generation-bound, byte-stable results.
- [ ] Invalidate caches on memory, policy, topology, model, or index changes.
- [ ] Publish cold, warm, and degraded-path latency measurements.

**Done when:** target-scale retrieval is fast and caches cannot return stale or
unauthorized context.

## P1 — Ecosystem

### 8. Framework adapters

- [ ] OpenAI Agents SDK.
- [ ] Microsoft Agent Framework.
- [ ] Google ADK.
- [ ] Hugging Face smolagents.
- [ ] CrewAI.
- [ ] Hermes or a verified generic integration recipe.
- [ ] Keep MCP as the universal tool-only fallback.

Every automatic adapter must cover capture, prepare, exact injection, exposure
confirmation, model input/output, tools, terminal events, failures, and
multi-agent scope.

**Done when:** every advertised adapter passes the same conformance suite and
states exactly what its host can prove.

### 9. Stable application APIs and SDKs

- [ ] Publish a versioned local HTTP API for memory, query, review, audit,
      configuration, and health.
- [ ] Publish a supported TypeScript SDK alongside Python and MCP.
- [ ] Add idempotency, pagination, filtering, timeouts, and structured errors.
- [ ] Separate agent-facing and administrative operations.

**Done when:** applications integrate without importing internal Python modules
or depending on the OpenClaw bridge.

### 10. Migration and interoperability

- [ ] Import Mem0 memories with scope, metadata, source, and import evidence.
- [ ] Export memory and provenance in a documented neutral format.
- [ ] Add dry-run, conflict review, resumability, counts, and digest receipts.
- [ ] Test upgrades and rollback for every import format.

**Done when:** users can evaluate AtMem without locking memory into either
product.

## P2 — Product and deployment

### 11. Production self-hosted service

- [ ] Authentication and scoped API keys.
- [ ] Tenant, user, workspace, and agent isolation.
- [ ] Secret management, TLS, encryption, retention, and quotas.
- [ ] Workers, health checks, metrics, backup, and disaster recovery.
- [ ] Administrative audit separated from agent access.

**Done when:** AtMem can honestly support a multi-user server, not only a local
loopback dashboard.

### 12. Memory lifecycle controls

- [ ] Expiry, retention, archival, and review policies.
- [ ] Learned-at, valid-from/to, replaced-at, and last-used timestamps.
- [ ] Optional evidence-based decay and promotion.
- [ ] Clear correction, merge, split, exclude, approve, reject, and forget.
- [ ] Verify lifecycle changes across canonical, graph, vector, cache, and
      backup policy.

**Done when:** stale memory does not accumulate silently and every transition is
understandable and controllable.

### 13. Governed multimodal memory

- [ ] Contracts for images, audio, video, files, and tool artifacts.
- [ ] Keep original bytes host-controlled by default.
- [ ] Store derived observations, references, model identity, confidence, and
      consent state.
- [ ] Add optional multimodal embeddings as derived, deletable indexes.
- [ ] Test sensitive content, retention, egress, and deletion.

**Done when:** multimodal recall works without silently copying private media.

### 14. Simpler onboarding

- [ ] One guided setup for host, shadow mode, AtBot, embeddings, test memory,
      retrieval verification, activation, and restore readiness.
- [ ] Dashboard health summaries with direct corrective actions.
- [ ] Clear “why remembered,” “why retrieved,” and “why withheld” explanations.
- [ ] Examples for OpenClaw, Pydantic AI, LangGraph, and the HTTP API.

**Done when:** a new user can install, test semantic recall, understand shadow
mode, and activate safely without reading internal architecture documents.

## Do not weaken existing AtMem advantages

- [ ] AtMem remains the only canonical authority.
- [ ] Authorization happens before intelligence sees candidate content.
- [ ] Rankings are revalidated against record scope and lifecycle.
- [ ] Shadow mode and activation remain explicit.
- [ ] Context construction remains byte-stable and receipt-bound.
- [ ] Provenance and memory history remain human-readable.
- [ ] Deletion covers canonical, graph, vector, and derived copies.
- [ ] Agent Black Box retains honest proof boundaries.
- [ ] OpenClaw migration remains reversible.
- [ ] Local operation and deterministic fallback remain available.
- [ ] Persisted-data upgrades remain backward compatible.

## Suggested Spec Kit order

1. `specs/001-memory-quality-benchmarks`
2. `specs/002-supporting-evidence-ranking`
3. `specs/003-storizon-delegated-context-provider`
4. `specs/004-semantic-setup-and-health`
5. `specs/005-memory-extraction-lifecycle`
6. `specs/006-retrieval-quality-and-reranking`
7. `specs/007-entity-relationship-memory`
8. `specs/008-production-storage-backends`
9. `specs/009-framework-adapter-conformance`
10. `specs/010-http-api-and-typescript-sdk`
11. `specs/011-production-service-profile`
