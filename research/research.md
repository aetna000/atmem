# AtMem 2.2: AtBot-readiness research

Status: proposed research and implementation contract

This document defines the work required for AtMem 2.2 to serve as the
authoritative memory and evidence engine beneath AtBot. It is not a commitment
to reproduce Mem0's internal storage architecture. The objective is to support
Mem0-level extraction and retrieval intelligence without moving model-specific
reasoning, prompts, or agent orchestration into AtMem.

## Naming and release baseline

AtMem is the public product name, Python package, and CLI name used by this
repository. The current `main` branch ships AtMem 2.1.0; “AtMem 2.2” in this
document means the planned next authority-contract release. AtBot is a separate
consumer product, not a rename of AtMem.

## Product boundary

AtMem owns truth:

- canonical memory records and source episodes;
- subject, agent, and workspace scope enforcement;
- admission, quarantine, promotion, supersession, rejection, and forgetting;
- provenance, audit chains, retrieval evidence, and context-exposure receipts;
- canonical lexical and graph state plus verified derived-index bindings;
- deterministic, versioned serialization of authorized context blocks;
- host-neutral capture, prepare, exposure, model, tool, and turn contracts.

AtBot owns intelligence:

- recent-conversation context assembly;
- local and remote model providers;
- model-backed fact and entity extraction;
- ambiguity and contradiction analysis;
- semantic reranking and model routing;
- agent loops, tools, skills, workers, and user interaction.

AtMem must not depend on Pydantic AI, LangChain, LangGraph, or a particular
model provider. AtBot must not write directly to AtMem SQLite tables.

### Approved product direction

AtBot is only the intelligent companion of AtMem. It supplies extraction,
entity and relationship proposals, query expansion, reranking, and bounded
memory maintenance. It is not an independent customer-facing agent, even if
its internal framework retains agent capabilities for memory work.

AtMem and AtBot form one agent-agnostic memory product. The AtBot interface is
merged into the AtMem dashboard as natural-language memory query. The unified
dashboard adopts AtBot's simple dark chat language while preserving AtMem's
shadow mode, multi-agent topology, storage, review, provenance, deletion,
audit, Safe Switch, and restore functionality.

OpenClaw remains the first maintained adapter. Hermes and other runtimes use
the same host-neutral contracts. Adapter-specific behavior must not enter the
AtMem core or AtBot intelligence policy.

## Identity and scope semantics

Every authority decision uses the complete scope tuple:

- `subject_id`: the person, team, project, or other entity the memory is about;
- `agent_id`: the authenticated runtime identity making or receiving a request;
- `workspace_id`: the hard administrative sharing and isolation boundary.

Session, run, and turn IDs correlate activity but grant no authority. Equality
of subject or agent IDs never implies cross-workspace access. Shared memory
requires explicit workspace membership and policy; omitted or ambiguous scope
fails closed. AtMem owns the canonical identity mappings and authorization
decision. Adapters may report host identities, but must record their assurance
and cannot create a stronger binding by assertion.

## Current foundation

AtMem 2.1 already provides most authority-plane primitives:

- canonical SQLite memory with source episodes;
- deterministic extraction and trusted host-interpreted facts;
- duplicate detection and fact-key supersession;
- quarantine, promotion, rejection, tombstoning, and purge;
- hash-chained mutation and retrieval audit evidence;
- lexical recall, bounded graph recall, and optional semantic investigation;
- generic shadow/active control contracts;
- persistent agent and workspace topology;
- context-preparation and exposure confirmation;
- OpenClaw automation and Agent Black Box evidence.

The gap is not the absence of another database. The gap is a stable authority
contract through which AtBot can submit model-derived proposals and request
governed hybrid recall.

The existing Safe Switch and OpenClaw integration remain supported. OpenClaw
becomes the first reference host adapter for the versioned runtime hooks in
capability 8: its copy, shadow, verify, activate, and restore guarantees are
preserved while its host-specific calls move behind the generic contract.

## Normative OpenClaw companion flows

The existing OpenClaw–AtMem adapter remains the host boundary. OpenClaw remains
the primary agent, AtMem remains the memory authority, and AtBot runs as AtMem's
intelligence companion. AtBot must not replace the adapter, become a second
authority, or become a required dependency for safe baseline recall.

There are two distinct paths: automatic storage, and retrieval with return
injection.

### Automatic storage

```text
OpenClaw user message
  -> existing OpenClaw–AtMem adapter
  -> AtMem captures the authenticated source
  -> AtBot extracts proposed facts, entities, and relationships
  -> AtBot submits typed proposals to AtMem
  -> AtMem admits, quarantines, or rejects each proposal
  -> AtMem projects admitted memory into canonical, graph, and vector storage
```

The model used by AtBot cannot approve its own extraction. AtMem binds every
proposal to the authenticated source, applies scope and lifecycle policy, and
owns the resulting canonical state.

### Retrieval, injection, and return path

Retrieval requires an explicit return path to the primary agent:

```text
User asks OpenClaw
  -> existing OpenClaw–AtMem adapter sends:
       query + subject + agent + workspace
  -> AtMem checks scope and permissions
  -> AtMem searches lexical + graph + vector storage
  -> AtMem removes inaccessible, deleted, excluded, and sensitive candidates
  -> AtBot receives only eligible candidates
  -> AtBot reranks, expands relationships, and selects useful memories
  -> AtMem revalidates AtBot's selected record IDs
  -> AtMem creates a byte-stable authorized context package
  -> existing adapter injects that context into OpenClaw
  -> OpenClaw generates the answer
  -> adapter confirms which exact context was delivered
  -> AtMem records retrieval, exposure, and response evidence
  -> answer returns to the user
```

The critical security boundary is:

```text
AtMem authorization
  before
AtBot sees candidate content
```

AtBot cannot introduce a memory that AtMem did not provide. AtBot returns
rankings and selections over eligible record IDs only:

```text
AtMem -> [memory A, memory B, memory C]
AtBot -> [memory C, memory A]
AtMem -> verifies C and A are still eligible
AtMem -> produces final authorized context
```

AtMem must revalidate scope, lifecycle, sensitivity, egress, membership,
generation, exclusion, and budget after AtBot returns a ranking. A stale or
hostile AtBot response must not introduce an ineligible record.

### Query expansion before content access

AtBot may help before candidate retrieval without receiving private memory
content. For example:

```text
Original query: "What cars do I like?"

AtBot query expansion:
  - car preference
  - preferred vehicle
  - favorite automobile
```

AtMem runs those expansions under its own scope and authority policy. Query
expansion grants no additional access and does not bypass candidate filtering.

### AtBot-unavailable fallback

AtBot improves inference and retrieval quality but is not a single point of
failure. If AtBot is unavailable, times out, or returns an invalid result, the
adapter and AtMem continue through the safe degraded path:

```text
OpenClaw query
  -> existing adapter
  -> AtMem lexical + graph + local-vector ranking
  -> AtMem authorized byte-stable context
  -> existing adapter injects context into OpenClaw
  -> OpenClaw returns the answer
  -> AtMem records the exposure receipt
```

Failure of AtBot must reduce intelligence, not weaken authorization, switch to
an undeclared remote provider, corrupt canonical memory, or stop OpenClaw from
using AtMem's verified baseline capabilities.

### Mandatory semantic query path

Natural-language memory questions must not depend on literal word overlap. The
dashboard and every agent adapter use the same governed hybrid path:

1. AtBot receives only the query and returns bounded, content-free expansions.
2. AtMem resolves subject, agent, and workspace authority.
3. AtMem searches lexical text, canonical fact keys, graph relationships, and
   the active local vector index for the original query and its expansions.
4. AtMem removes inaccessible, inactive, excluded, and sensitive candidates.
5. AtBot receives only that eligible union and ranks the useful records.
6. AtMem revalidates returned IDs before producing an answer or context.

The always-present hashing index is a safe local fallback and plumbing
guarantee, not a claim of model-quality embeddings. When a verified local
embedding model is configured, the same authority path uses it. Query expansion
and canonical fact-key matching must still work when no embedding model is
installed. A `favorite food` query retrieving `likes burgers` is a release gate.

The dashboard must report which semantic epoch is active. Once a verified local
embedding model replaces the hashing fallback, memory mutation and OpenClaw
mirror refresh must rebuild that same model epoch and must never silently
downgrade semantic retrieval back to token hashing.

## 2.2 required capabilities

### 1. Versioned memory-proposal contract

Add a public, provider-neutral proposal type that can be transported through
Python, CLI JSON, and MCP without importing an agent framework.

Minimum request shape:

```json
{
  "format": "atmem-memory-proposal-v1",
  "proposal_id": "proposal_...",
  "idempotency_key": "sha256:...",
  "subject_id": "user-1",
  "agent_id": "assistant-1",
  "workspace_id": "private",
  "session_id": "session-1",
  "turn_id": "turn-1",
  "fact": "User prefers aisle seats.",
  "fact_key": "travel::seat-preference",
  "confidence": 0.94,
  "source_episode_ids": ["episode_..."],
  "source_message_ids": ["message_..."],
  "entities": [
    {"label": "aisle seat", "kind": "preference"}
  ],
  "suggested_action": "add",
  "related_record_ids": [],
  "sensitivity": "personal",
  "interpreter": {
    "provider": "ollama",
    "model": "qwen",
    "prompt_version": "atbot-extract-v1",
    "calibration_id": "uncalibrated",
    "assurance": "model_interpreted"
  },
  "source_binding": {
    "method": "host_authenticated_turn",
    "source_sha256": "..."
  }
}
```

Required properties:

- proposal IDs and idempotency keys are caller supplied and validated;
- idempotency is retry identity, not semantic deduplication: AtMem computes and
  stores a canonical proposal-payload digest independently of the supplied key;
- the canonical payload digest uses RFC 8785 JSON canonicalization over the
  schema-listed semantic fields, excluding `idempotency_key` and transport-only
  metadata, with strings normalized according to the schema version;
- a `sha256:` idempotency key, when used, must match that canonical payload
  digest; other allowed key schemes remain opaque but are bound to the digest;
- the fact cannot claim stronger provenance than its source binding supports;
- every proposal is attached to an existing or atomically created source
  episode;
- source, fact, interpreter, prompt-version, and scope digests are audited;
- replaying the same proposal returns the original decision;
- conflicting reuse of an idempotency key fails closed;
- entities are suggestions until canonical validation/indexing completes;
- an interpreter can propose an action but cannot authorize it;
- `confidence` is a model self-report in `[0, 1]`, not a probability of truth;
- admission cannot threshold on confidence unless the named model, prompt
  version, fact category, and `calibration_id` have a versioned calibration
  artifact accepted by policy.

#### Fact-key safety

`fact_key` is a proposed grouping hint, not authority to replace a record.
AtMem must define and version its Unicode normalization, case folding,
namespace grammar, separator escaping, length limits, and structured components.
It must audit both the proposed key and canonical key plus the canonicalizer
version.

Supersession requires scope checks and an explicit validated relationship; a
key match alone is insufficient. A collision with an unrelated record is
quarantined. A supersession proposal from a different interpreter identity or
prompt version than the active record must route to review rather than perform
an automatic transition.

### 2. Explicit admission result

AtMem must return a typed decision rather than forcing clients to infer state
from created records:

```json
{
  "format": "atmem-memory-admission-v1",
  "proposal_id": "proposal_...",
  "decision": "quarantined",
  "reason_codes": ["conflicts_with_active_record"],
  "record_ids": [],
  "candidate_ids": ["candidate_..."],
  "related_record_ids": ["record_..."],
  "review_required": true,
  "audit_event_id": "audit_..."
}
```

Supported decisions:

- `active`;
- `quarantined`;
- `duplicate`;
- `conflict`;
- `rejected`;
- `invalid`.

Admission must be an atomic transaction including source linkage, candidate or
record mutation, graph-derived state, and audit evidence.

### 3. Source-message identity and retention

AtMem already links semantic records to episodes. AtBot readiness additionally
requires stable message-level references when the host can supply them.

Requirements:

- accept host message IDs without treating them as authenticated by default;
- record the assurance level of the host/source binding;
- preserve the exact source digest used for extraction;
- distinguish exact per-fact support from a set of candidate source messages;
- expose `get_source(record_id)` without weakening scope checks;
- prevent retention cleanup from silently removing required active-record
  evidence;
- allow policy-driven source-body retention while always retaining integrity
  metadata required by the audit contract.

### 4. Contradiction and supersession proposals

AtBot may suggest that a new fact contradicts or supersedes an existing fact,
but AtMem owns the transition.

Required relationship values:

- `duplicate`;
- `supports`;
- `extends`;
- `contradicts`;
- `supersedes`;
- `unrelated`;
- `uncertain`.

AtMem must:

- verify that referenced records exist in the same authorized scope;
- preserve old records and their history;
- never overwrite record content in place;
- apply deterministic policy to determine automatic versus reviewed changes;
- quarantine ambiguous or high-sensitivity corrections;
- issue an audit event binding the proposal, old record, new record, actor, and
  decision.

### 5. Governed hybrid agent recall

Semantic search currently acts as a derived investigator index. AtBot needs a
governed recall path that can use multiple candidate signals without allowing a
derived index to become canonical.

Proposed request:

```json
{
  "format": "atmem-recall-request-v1",
  "query": "Which seat should I book?",
  "subject_id": "user-1",
  "agent_id": "assistant-1",
  "workspace_id": "private",
  "limit": 8,
  "candidate_limit": 200,
  "signals": ["lexical", "semantic", "graph", "trust", "recency"],
  "semantic_index": "default",
  "min_score": 0.2,
  "context_budget_chars": 1800,
  "reranker": {
    "mode": "model",
    "provider": "openai",
    "model": "configured-model",
    "egress_class": "remote",
    "policy_id": "remote-rerank-v1"
  }
}
```

Requirements:

- scope and lifecycle filters execute before candidate exposure;
- the intended reranker, provider, and egress class are declared before AtMem
  selects or reveals candidates;
- sensitivity and egress policy filter the eligible set before candidate text
  can leave AtMem; undeclared or changed egress fails closed;
- lexical recall remains a safe fallback;
- semantic candidates are revalidated against canonical record digests and
  index generation;
- graph paths are bounded and returned as evidence;
- score components and fusion versions are recorded;
- AtBot may supply a reranking proposal but cannot introduce ineligible IDs;
- final selection is revalidated after external/model reranking;
- only final AtMem-selected records can receive an injection receipt;
- missing, dirty, stale, or dimension-incompatible indexes fail safely.

### 6. External reranker boundary

AtMem should not call a model. It should expose a staged contract:

1. AtBot declares the intended reranker, provider, and egress class.
2. AtMem returns an eligible, sensitivity-filtered, bounded candidate set with
   only the content permitted for that egress class.
3. AtBot returns an ordered list of candidate record IDs plus reranker metadata.
4. AtMem validates membership, scope, lifecycle, index generation, the egress
   declaration, and budget, then produces the final context package and receipt.

The reranker response must bind:

- input candidate-set digest;
- ordered record IDs;
- provider/model and prompt version;
- whether content left the local machine;
- output digest and completion status.

The response metadata confirms compliance; it is not the first egress check.
Changing provider or egress class after candidates are returned requires a new
request and newly filtered candidate set.

### 7. Stable context package and exposure receipt

Version the generic context boundary independently of the dashboard and any
specific host adapter.

The prepared context must contain:

- `inject` authorization;
- bounded context text;
- canonical record IDs;
- retrieval event and receipt IDs;
- subject, agent, workspace, session, run, and turn scope;
- context digest and byte/character counts;
- policy and ranking versions;
- explicit withheld/empty/degraded reasons.

Exposure confirmation must bind the exact prepared digest. Confirming a
different payload or scope must fail. Expired or already-consumed exposures
must follow an explicit replay policy.

#### Byte-stable context for KV and prompt caching

AtMem must make authorized memory context safe to reuse as part of an LLM's
cached prompt prefix. AtMem does not own the model KV cache, but it must return
a deterministic context block from which AtBot can construct a byte-for-byte
stable prefix.

The contract must define:

- canonical UTF-8 serialization, including Unicode normalization, escaping,
  field order, separators, and final-newline behavior;
- deterministic record ordering and identical rendering for identical inputs;
- `context_bytes_sha256`, serialization version, policy version, memory
  generation, and canonical record-version digests;
- a boundary between reusable context bytes and request-specific values such
  as timestamps, run IDs, receipt IDs, nonces, and the current query;
- fresh exposure authorization for every use, even when the authorized context
  bytes and underlying KV-cache entry are reused;
- invalidation when included memory changes, is superseded, quarantined,
  forgotten, or becomes ineligible, or when scope or policy changes;
- scope-bound cache identity so entries cannot be reused across unauthorized
  subjects, agents, workspaces, or tenants.

AtMem returns stable semantic content and digests, not provider-specific cache
handles. AtBot is responsible for placing the bytes at the same prompt position
and binding them to the provider, model, tokenizer, prompt, tool-schema, and
skill versions.

Cache reuse is an optimization, never authorization. A cache hit cannot bypass
retrieval eligibility, exposure confirmation, revocation, forgetting, or
egress policy. Provider-side prompt caching must remain disabled where
retention or data-location policy does not permit it.

### 8. Versioned generic runtime hooks

AtBot and future adapters need one host-neutral lifecycle:

```text
control_capture
control_prepare
control_exposure_shown
control_record_model_event
control_record_tool_event
control_turn_end
control_status
```

Required changes:

- publish JSON schemas and protocol versions;
- define idempotency and ordering for every event;
- distinguish caller assertion from adapter-verified observation;
- correlate run, turn, model, context, tool, and outcome identifiers;
- make incomplete and out-of-order events visible rather than inferred away;
- negotiate adapter capabilities at initialization;
- retain backward-compatible aliases for the current generic MCP surface during
  the documented migration window.

### 9. Complete forget cascade

Forgetting a record or source must remove or invalidate every recallable
derivative:

- canonical active record;
- lexical index entries;
- graph nodes/edges that have no remaining support;
- semantic vectors and cached candidate sets;
- media observation derivatives;
- prepared but unexposed context packages where policy requires revocation;
- AtBot-owned derivatives acknowledged through a deletion callback/receipt.

The response must distinguish logical exclusion, physical purge, derived-index
cleanup, externally acknowledged cleanup, and work that remains pending.

### 10. Concurrency, replay, and crash safety

AtBot will run concurrently with several agents. AtMem 2.2 must define:

- transaction and locking behavior for concurrent proposals;
- stable idempotency across process restarts;
- ordering rules for corrections arriving from different agents;
- atomic audit writes with canonical state changes;
- recovery of interrupted derived-index updates;
- bounded retry behavior;
- safe handling of a model result arriving after a turn was cancelled;
- no partially active memory after an exception.

### 11. Public interfaces and compatibility

The following must become documented public contracts:

- Python proposal/admission API;
- Python governed-recall API;
- host MCP schemas;
- operator review schemas;
- context package and exposure receipt;
- audit event families;
- capability negotiation and version reporting.

AtBot must be able to use only documented interfaces. Private SQLite tables,
dashboard endpoints, and OpenClaw-specific implementation details are not valid
integration contracts.

AtMem is the single source of truth for transport-neutral JSON Schemas. Typed
Python models, AtBot fixtures, the fake AtMem gateway, and the fake AtBot
adapter must be generated from or validated against the same versioned schema
artifacts. AtMem publishes immutable schema fixtures and compatibility rules;
AtBot CI pins and tests those fixtures. Hand-maintained duplicate contract
models are not permitted after Phase 0.

## Security invariants

AtMem 2.2 must preserve these invariants:

1. Model output is evidence-bearing input, never authority.
2. Scope filtering occurs before content is returned to AtBot or a reranker.
3. Untrusted tool/web/media content cannot silently become active memory.
4. Remote inference egress is declared and auditable.
5. Skills and prompts cannot grant permissions.
6. Derived indexes cannot resurrect quarantined, superseded, rejected, or
   forgotten memory.
7. Hash integrity proves retained-data consistency, not factual truth.
8. A host assertion that context was injected remains labeled with its
   assurance level.
9. A KV- or prompt-cache hit never substitutes for current scope, policy, and
   exposure authorization.
10. A caller-supplied fact key cannot authorize supersession or bypass
    relationship validation.
11. Candidate content cannot be exposed to a reranker whose egress class was
    not declared and permitted before candidate selection.

## Acceptance scenarios

AtMem is AtBot-ready only when automated tests demonstrate all of the following:

1. A source message becomes a proposal, an admitted record, a recalled context
   item, and an exact exposure receipt.
2. Replaying capture or proposal requests produces no duplicate mutation.
3. Reusing an idempotency key with different content fails closed.
4. A contradictory proposal cannot silently overwrite an active record.
5. Untrusted webpage or tool content is quarantined.
6. One workspace cannot retrieve or reference another workspace's records.
7. Semantic and graph candidates are revalidated against canonical state.
8. A stale or corrupt semantic index falls back or fails without unsafe recall.
9. An external reranker cannot add an ineligible record ID.
10. Forgetting removes the record from lexical, semantic, graph, context, and
    media-derived retrieval.
11. Failed admission or index maintenance leaves no partially active state.
12. A mismatched exposure digest cannot be confirmed.
13. Out-of-order or incomplete flight events remain visible in verification.
14. Remote inference metadata records provider, model, egress, and source/candidate
    digests without treating the remote model as an approver.
15. Every active model-interpreted fact can be traced to its retained source
    evidence and admission decision.
16. Preparing unchanged records under the same serialization and policy
    versions produces byte-for-byte identical context and the same digest.
17. Changing record content, eligibility, scope, policy, or serialization
    version changes the cache identity or makes the prior entry unusable.
18. Reusing stable context bytes still creates a fresh, scope-correct exposure
    receipt, and a forgotten record cannot be recovered through a cache hit.
19. Fact-key collisions and cross-interpreter supersession attempts route to
    quarantine or review without changing the active record.
20. Remote reranking receives no sensitivity-restricted candidate text unless
    the request declared an authorized remote egress policy in advance.
21. AtMem's real endpoints, AtBot's fake gateway, and the fake AtBot adapter
    pass the same pinned schema conformance suite.
22. Uncalibrated confidence cannot independently promote or reject a proposal.
23. Changing or omitting any member of the subject, agent, and workspace tuple
    cannot widen access, even when the remaining identifiers match.
24. The OpenClaw reference adapter passes the generic hook conformance suite
    without regressing copy, shadow, verify, activate, or restore behavior.

## Proposed delivery sequence

### Milestone A: contracts

- proposal/admission models and JSON schemas;
- one canonical schema bundle with generated-model and fake conformance tests;
- source-message references and idempotency;
- canonical fact-key, proposal-payload digest, and confidence semantics;
- public Python API and MCP transport;
- compatibility and migration tests.

### Milestone B: governed retrieval

- eligible candidate-set API;
- hybrid recall and external reranker boundary;
- pre-disclosure reranker egress filtering;
- stable context package and exposure receipt;
- canonical byte-stable context serialization and cache invalidation;
- derived-index validation tests.

### Milestone C: lifecycle completeness

- contradiction relationship and review contract;
- complete forget cascade and external cleanup acknowledgement;
- concurrency, crash recovery, and replay tests.

### Milestone D: adapter readiness

- versioned generic runtime hooks;
- capability negotiation;
- reference fake AtBot adapter generated from the canonical schema bundle;
- OpenClaw adapter conformance and Safe Switch regression suite;
- end-to-end acceptance suite.

## Non-goals for AtMem 2.2

- shipping an autonomous conversational agent;
- embedding Pydantic AI or another agent framework;
- choosing Qwen, OpenAI, DeepSeek, or another inference provider;
- storing AtBot's recent conversational buffer as canonical memory;
- allowing an LLM to approve memory or policy changes;
- replacing AtMem's canonical store with a vector database;
- matching Mem0's internal database layout;
- hosting a multi-tenant public control service.

## Definition of done

AtMem 2.2 is AtBot-ready when the separately packaged companion uses only
versioned public contracts, has no independent authority or product mode, can
submit model-derived proposals without direct storage access, can rank only
AtMem-authorized candidates, and can degrade without stopping baseline memory.
The unified AtMem dashboard must support natural-language governed-memory
query while authority, scope, lifecycle, deletion, cache invalidation, shadow
mode, multi-agent topology, adapter isolation, and audit invariants remain
enforced by AtMem.
