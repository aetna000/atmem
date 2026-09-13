# AtMem vs Mem0: implementation comparison

## Archive metadata

| Field | Value |
| --- | --- |
| Analysis date | 9 September 2026 (Australia/Sydney) |
| AtMem repository | `aetna000/atmem` local working tree |
| AtMem version declared by repository | `2.2.6b11` release candidate |
| Git branch | `storizon` |
| Base commit | `f5b5eca048fdfd3b5af89d1f0cbf9ec130669091` |
| Tracked working-tree diff SHA-256 | `dd6c50625d904d333eb0e2ad74219cfcbb9444079f5809fd7da941b22f7aa437` |
| Mem0 version checked | `mem0ai 2.0.20`, published 2 September 2026 |

### Reproducibility warning

The AtMem repository was **not clean** when this analysis was made. The base
commit therefore does not identify the analyzed source by itself. The analysis
used the base commit plus the tracked working-tree changes represented by the
diff digest above. Untracked `.vscode/sessions.json` and `tmp/` content was not
used as evidence.

Relevant modified files at analysis time included `pyproject.toml`, the Mem0
provider tests, delegated-context services and documentation, and the OpenClaw
bridge. To reproduce the exact state, preserve both the commit and the working
tree patch.

## Executive conclusion

AtMem and Mem0 overlap in long-term agent memory, but optimize for different
outcomes:

- **Mem0 is primarily a mature, developer-friendly memory engine and managed
  memory platform.**
- **AtMem is primarily a governed memory authority and agent-observability
  control plane.**

Mem0 is currently stronger for production scale, retrieval performance,
provider choice, ecosystem breadth, hosted operation, and fast adoption. AtMem
is stronger where explicit authorization, provenance, review, reversible
activation, exact context-delivery evidence, governed task state, and complete
agent-run investigation matter.

This is not a pure replacement comparison. AtMem can delegate context selection
to Mem0 and retain responsibility for scoped delivery and evidence.

## Side-by-side comparison

| Area | AtMem | Mem0 |
| --- | --- | --- |
| Primary purpose | Governed memory, context authorization, task state, and agent-flight evidence | Adaptive memory for personalization and cross-session recall |
| Memory operations | Capture, remember, recall, review, promote, supersede, forget, audit, verify | Add, search, get, list, update, delete, history |
| Extraction | AtBot or deterministic extractor proposes typed changes | LLM extracts and updates memories |
| Write authority | Proposer cannot directly write canonical memory; AtMem validates and commits | Extraction and persistence operate as one application memory workflow |
| Review workflow | First-class quarantine, approve, edit-and-approve, reject | CRUD and memory history; broader administration in Mem0 Platform |
| Contradictions | Explicit `UPDATE`, `SUPERSEDE`, `NOOP`, and `REJECT`, with immutable lineage | Memory update/supersession and linked history |
| Retrieval | Lexical, fact-key, graph, semantic, trust, recency, supporting evidence, optional AtBot reranking | Vector/hybrid search, metadata filters, optional reranking and graph enrichment |
| Graph | Rebuildable candidate source; edges cite eligible canonical evidence | Optional graph backend for extracted entities and relationships |
| Context injection | Bounded deterministic block with exposure receipt | Application or integration injects returned memories |
| Shadow mode | Native observe-without-influencing rollout state | No directly equivalent memory-authority rollout mode |
| Agent-run evidence | Black Box records context, model, tool, and turn boundaries | Request audit logs and memory-operation history |
| Governed task state | Revisioned goals, work items, dependencies, blockers, guards, and expiry | Session/working memory, but no equivalent governed task authority |
| OpenClaw | Managed install, migration, takeover verification, evidence, and restore | Official plugin with triage, recall, consolidation, and memory tools |
| LangGraph | Native middleware with model/tool lifecycle evidence | Official integration patterns and tools |
| Pydantic AI | Purpose-built capability adapter | Can be connected through application integration |
| Generic integration | Python, MCP, HTTP, TypeScript client, host-neutral control contract | Python, TypeScript, REST, MCP, and broad framework integrations |
| Default deployment | Local SQLite and derived vector sidecar; local inference options | OSS library defaults to OpenAI, Qdrant, and SQLite history |
| Hosted service | Not provided | Fully managed Mem0 Platform |
| Server authentication | Local/loopback single-user default; SaaS supplies tenant boundary | Self-hosted JWT sessions and per-user API keys |
| Storage choices | SQLite/PostgreSQL canonical; local sidecar, pgvector, or Qdrant | Larger vector-store, LLM, embedder, reranker, and graph ecosystem |
| Multimodal | Host retains bytes; AtMem stores governed observations and references | Direct image, audio, and video memory processing |
| Maturity | Beta release candidate | Stable published package and established hosted service |
| License | Apache 2.0 | Apache 2.0 |

## Where AtMem is stronger

### 1. Memory changes have an authority boundary

AtMem separates intelligence from authority:

```text
User or model observation
        |
        v
AtBot/rule engine proposes a typed change
        |
        v
AtMem checks source, scope, policy, and current generation
        |
        v
Accept, quarantine, reject, conflict, or no-change
        |
        v
Canonical memory and audit event
```

AtBot cannot directly commit, delete, promote, or inject memories. This reduces
the chance of an extraction model silently changing authoritative memory. The
cost is a larger state model and a steeper integration learning curve.

### 2. Stronger provenance and correction semantics

AtMem records source spans and digests, proposing and reviewing actors,
assurance, predecessor/successor relationships, immutable lineage, and
hash-chained audit evidence. Corrections create new state and preserve the old
lineage rather than silently overwriting it.

Mem0 provides history and linked supersession behavior. AtMem's distinctive
focus is independently inspectable provenance and integrity verification.

### 3. Context-delivery evidence

AtMem distinguishes retrieval from actual model exposure. It records which
records were eligible, the context block prepared, the authorization decision,
the exact block digest, and whether the host confirmed exposure at the model
boundary.

This makes it easier to diagnose cases where a memory existed but did not reach
the model. It does not prove that the model understood or followed the context.

### 4. Agent Black Box

AtMem records a content-minimizing timeline of turn input, context disposition,
model boundaries, tool requests and completions, errors, missing evidence,
termination, and optional externally verified outcomes.

It can distinguish a tool failure from an observation gap. A verified flight
proves retained-chain integrity and closure of reported boundaries; it does not
prove that a host hook was truthful or that an external real-world result
occurred.

### 5. Governed Task State

AtMem has a separate task authority plane for goals, phases, required and
optional items, dependencies, blockers, immutable revisions, optimistic
concurrency, idempotency, evidence, assurance, completion guards, and expiry.

Mem0's conversation, session, working, and long-term memory layers organize
context, but they are not a revisioned workflow authority with guarded
lifecycle transitions.

### 6. Reversible OpenClaw rollout

AtMem can discover OpenClaw workspaces, copy native memory, start in shadow
mode, verify its bridge and indexes, explicitly activate takeover, protect
native memory paths, and restore the preserved configuration and files.

Mem0's OpenClaw integration is easier to start and provides automatic triage,
recall, consolidation, and agent tools. AtMem's differentiator is controlled
migration, evidence, and reversibility.

## Where Mem0 is stronger

### 1. Simpler adoption

Mem0's ordinary application interface is a small `add`/`search` loop. AtMem
requires understanding scopes, topology, shadow and active modes, admission,
proposals, exposure, and evidence. For a conventional personalized chatbot,
Mem0 is easier to adopt.

### 2. Mature managed platform

Mem0 Platform supplies managed scaling, infrastructure, workspace governance,
webhooks, audit features, and support. AtMem does not currently ship a hosted
multi-tenant service. Its embedding SaaS must provide authentication,
authorization, tenant isolation, encryption, retention, quotas, and credential
management.

### 3. Broader provider ecosystem

Mem0 supports a wider selection of vector stores, embedding models, LLMs,
rerankers, graph stores, SDKs, and framework examples. AtMem intentionally has a
narrower governed backend surface: SQLite or PostgreSQL as canonical storage,
with local vectors, pgvector, or Qdrant as derived candidate sources.

### 4. Better measured retrieval result in AtMem's checked-in comparison

AtMem's own 12-question LongMemEval-S retrieval campaign against Mem0 OSS
2.0.19 reports:

| Metric | AtMem | Mem0 OSS 2.0.19 | Result |
| --- | ---: | ---: | --- |
| Any evidence-session recall@5 | 1.000 | 1.000 | Tie |
| All evidence-session recall@5 | 1.000 | 1.000 | Tie |
| Evidence-session MRR@5 | 0.958 | 1.000 | Mem0 |
| Search latency p50 | 130.0 ms | 47.8 ms | Mem0 |
| Search latency p95 | 193.1 ms | 57.9 ms | Mem0 |

The honest result is that Mem0 performed better on this benchmark. The test is
small, measures retrieval rather than end-to-end answer quality, and used Mem0
2.0.19 rather than the current 2.0.20.

### 5. Ecosystem and production experience

Mem0 offers Python and TypeScript SDKs, hosted and self-hosted APIs, MCP,
OpenClaw and LangGraph integrations, many provider adapters, and a much larger
public community. AtMem currently has greater first-party governance depth than
ecosystem breadth.

### 6. Direct multimodal handling

Mem0 directly processes multimodal memories. AtMem deliberately leaves source
media bytes under host custody and stores typed observations, digests, and
references. AtMem's approach is stronger for custody control but less
convenient for direct multimodal memory ingestion.

## AtMem limitations and risks

- The analyzed version is a beta release candidate, while Mem0 2.0.20 is a
  published stable package.
- Governance adds more concepts and operational complexity.
- Generic Black Box accuracy depends on truthful, complete host hooks.
- Only OpenClaw has fully automated discovery, migration, activation, and
  restoration.
- Governed Task State is disabled by default and requires an exact task ID;
  prompt text alone never selects a task.
- The dependency-free hashing index is diagnostic quality, not a
  production-quality semantic embedding model.
- AtMem does not semantically prove that an assistant answer is correct.
- It cannot prove external outcomes without a system-of-record verifier.
- Raw prompts, responses, tool arguments, and results are intentionally absent
  from Black Box evidence, protecting privacy but limiting forensic detail.
- Hosted identity, tenancy, retention, and production operations remain the
  embedding application's responsibility.
- Retrieval evidence currently favors Mem0 for ranking and latency.

## Mem0 adapter compatibility issue found

AtMem advertises an optional delegated Mem0 context-provider adapter, but the
analyzed `pyproject.toml` declares:

```toml
mem0ai>=1,<2
```

The current Mem0 release is `2.0.20`. Therefore `pip install atmem[mem0]`
cannot currently resolve the latest Mem0 2.x SDK without changing the AtMem
dependency range and validating the adapter. The separate checked-in benchmark
environment pins Mem0 2.0.19 and is not evidence that the optional AtMem
provider extra supports Mem0 2.x.

## Selection guidance

Choose **Mem0** when the priority is fast implementation, managed scaling,
broad provider support, mature retrieval, production API authentication, or
personalization without a strict evidence-governance requirement.

Choose **AtMem** when the priority is explicit memory authorization, review of
sensitive or ambiguous memory, proof of context placement, agent/tool run
investigation, reversible OpenClaw takeover, governed task state, local-first
operation, or content-minimizing audit evidence.

## Combined architecture

The systems can be complementary:

```text
Mem0
  selects and ranks relevant memories
        |
        v  signed delegated decision
AtMem
  verifies scope and replay protection
  delivers the exact accepted context
  records exposure and agent-flight evidence
```

AtMem already implements this delegated-provider architecture. The immediate
integration issue is its current `mem0ai>=1,<2` dependency constraint.

## AtMem source evidence

- [README](../README.md)
- [Current implementation status](../docs/current-status.md)
- [Memory extraction and updating](../docs/memory-extraction.md)
- [Semantic search](../docs/semantic-search.md)
- [Entity and relationship memory](../docs/entity-relationship-memory.md)
- [Governed Task State](../docs/governed-task-state.md)
- [Agent Black Box](../docs/agent-blackbox.md)
- [Framework adapters](../docs/framework-adapters.md)
- [Storage performance](../docs/storage-performance.md)
- [SaaS integration boundaries](../docs/saas-integration.md)
- [Benchmark methodology and recorded comparison](../docs/benchmarks.md)
- [Python packaging metadata](../pyproject.toml)
- [Mem0 delegated provider adapter](../atmem/provider_adapters/mem0.py)

## Mem0 sources checked

- [Mem0 OSS overview](https://docs.mem0.ai/open-source/overview)
- [Mem0 Platform overview](https://docs.mem0.ai/platform/overview)
- [Mem0 OSS configuration](https://docs.mem0.ai/open-source/configuration)
- [Mem0 REST API server](https://docs.mem0.ai/open-source/features/rest-api)
- [Mem0 graph memory](https://docs.mem0.ai/open-source/features/graph-memory)
- [Mem0 reranker-enhanced search](https://docs.mem0.ai/open-source/features/reranker-search)
- [Mem0 memory types](https://docs.mem0.ai/core-concepts/memory-types)
- [Mem0 OpenClaw integration](https://docs.mem0.ai/integrations/openclaw)
- [Mem0 LangGraph integration](https://docs.mem0.ai/integrations/langgraph)
- [Mem0 Python package](https://pypi.org/project/mem0ai/)
- [Mem0 source repository](https://github.com/mem0ai/mem0)

## Evidence file digests

These SHA-256 values identify the principal local files used during analysis:

```text
22932d48a77730bf2a357a7bcbb384a8877ce1a1920320879cd3bff5b7712c2c  README.md
0048a51f8e5b94e53afc24c8b096f654b47f52b1328d7504eba13aac309bfe6e  docs/current-status.md
9bd52f9905a71bd3b21a864f4687949866e510ba48126f3d686a3d912001048c  docs/benchmarks.md
3340fb3e80b801851c0a679271b43e1bc2f086147e3713d792142d8fd29af1fb  docs/governed-task-state.md
45ba99b137093f1b4973a6413789ee5f868d9cca0796112250bd671eddfb77ef  docs/memory-extraction.md
7c27726b989fe6afa2d5719179e517a9ecc1e8b1421aab99c21daed5b47e4923  docs/agent-blackbox.md
c649289a45b244902eb1b40b498abc88fa398739de76432980729d5a23d56af9  docs/storage-performance.md
b2ab6798a651e3b6d77bd61321d76bd53cd53373664d9b30feb02e966852d1f8  docs/framework-adapters.md
fb9f39ad0bf96b1c237295cf343b4b3020a763bd878344fee83bb746448a4a75  pyproject.toml
c31863853ced348533cec38406bf8da1528f9c33618f03bda57e7b58edbb5ba9  atmem/provider_adapters/mem0.py
```
