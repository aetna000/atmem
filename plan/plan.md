# AtMem 2.2 implementation plan with AtBot intelligence

Status: proposed execution plan

Source contract: [AtMem 2.2 research](../research/research.md)

## Outcome

AtMem 2.2 is one agent-agnostic memory product with AtBot as its managed,
headless intelligence companion. AtBot never becomes an independent product
agent. AtMem remains the only authority, store, installer, and customer
interface.

AtMem exposes a stable, provider-neutral authority API that lets AtBot:

1. capture source messages;
2. submit model-derived memory proposals;
3. receive explicit admission decisions;
4. request governed recall candidates;
5. rerank only candidates authorized for the declared model and egress class;
6. receive byte-stable context packages;
7. confirm exact context exposure;
8. correct, supersede, and forget memory with complete evidence.

AtMem will not run an LLM, own an agent loop, or depend on Pydantic AI. AtBot
owns intelligence; AtMem owns canonical memory and memory authority.

The AtBot chat-style interface is merged into the AtMem dashboard as governed
memory query. The dashboard adopts the simpler dark visual language while
preserving shadow mode, multi-agent topology, review, provenance, storage,
deletion, audit, Safe Switch, restore, and OpenClaw controls.

## Delivery strategy

The work will be additive rather than a rewrite.

- Keep the existing `Memory.remember()` behavior and public CLI compatible
  during the 2.2 development cycle.
- Add a stricter proposal/admission path for model-generated input instead of
  routing AtBot through trusted interpreted-fact shortcuts.
- Preserve the current OpenClaw Safe Switch, shadow, activation, verification,
  and restore behavior.
- Publish contracts before building intelligence against them.
- Keep AtMem's canonical engine free of mandatory model, vector, agent-framework,
  and JSON-Schema runtime dependencies.
- Use feature flags or explicit version negotiation until the new contract
  passes the complete acceptance suite.

```text
contracts and scope
        ↓
proposal and admission
        ↓
governed recall and exposure
        ↓
lifecycle and forgetting
        ↓
generic adapters and OpenClaw conformance
        ↓
release hardening
```

## Current foundations to preserve

AtMem 2.1 already supplies useful implementation pieces:

- `atmem/core/canonical.py`: canonical JSON and SHA-256 helpers;
- `atmem/core/policy.py`: trust, duplicate, and lifecycle policy;
- `atmem/memory.py`: atomic memory operations and audit events;
- `atmem/store/sqlite.py`: canonical records, episodes, graph bindings,
  retrieval evidence, and transactions;
- `atmem/control/store.py`: candidates, previews, exposures, transitions, and
  control-plane schema migrations;
- `atmem/control/manager.py`: prepare and exposure orchestration;
- `atmem/control/server.py`: generic runtime hooks;
- `atmem/semantic/index.py`: generation-aware derived semantic index;
- existing generic-adapter, OpenClaw, recall, graph, audit, and failure tests.

The new design must reuse these guarantees without allowing their current
internal shapes to become the public AtBot protocol.

## Architectural decisions

### Contract ownership

AtMem is the only source of truth for transport-neutral JSON Schemas.

Proposed layout:

```text
atmem/contracts/
  __init__.py
  models.py
  validation.py
  canonical.py
  versions.py

atmem/schemas/v1/
  memory-proposal.json
  memory-admission.json
  source-capture.json
  recall-request.json
  candidate-set.json
  rerank-proposal.json
  context-package.json
  exposure-confirmation.json
  forget-request.json
  forget-receipt.json
  runtime-event.json
  capabilities.json
```

- Schemas are shipped as package data and copied into release artifacts.
- Python types are generated from or tested against those schemas.
- AtBot pins the immutable schema bundle in CI.
- The fake AtMem gateway, fake AtBot adapter, and real endpoints run the same
  conformance examples.
- Schema validation tooling may be a development dependency; the canonical
  engine remains dependency-free at runtime.

### Scope model

Every request carries the complete authority tuple:

- `subject_id`: who or what the memory is about;
- `agent_id`: the authenticated runtime identity making or receiving a request;
- `workspace_id`: the hard sharing and isolation boundary.

Session, run, turn, and task IDs are correlation fields only. They cannot grant
access. AtMem resolves adapter-reported identities through its canonical
topology and fails closed on missing, ambiguous, or inconsistent scope.

### Storage ownership

- The canonical SQLite database owns sources, proposals, admissions, records,
  relationships, lifecycle state, idempotency, and canonical audit events.
- The control evidence database continues to own runtime previews, exposures,
  transitions, and host-flight evidence.
- Derived vector and graph indexes remain rebuildable and non-authoritative.
- Cross-database work must use a durable operation/outbox record plus
  idempotent projection. It must not pretend that two SQLite files share one
  transaction.

### Compatibility

- Existing deterministic extraction remains supported.
- Existing trusted host-interpreted facts remain supported but are not the
  AtBot proposal interface.
- New schemas and APIs start at protocol `v1`, independently of package 2.2.
- Breaking protocol changes require a new protocol version, not silent field
  reinterpretation.

## Product-integration workstream: managed intelligence and unified UI

Goal: ship AtBot as an AtMem-managed intelligence component rather than a
second agent product.

### Deliverables

- [x] Add AtBot health, capability, extraction, expansion, ranking, and query
  companion contracts.
- [x] Ensure AtMem authorizes candidate content before companion delivery.
- [x] Revalidate every AtBot record ID before context construction.
- [x] Add deadline-bounded companion calls with deterministic AtMem fallback.
- [x] Remove independent AtBot task and customer-dashboard modes.
- [x] Add natural-language governed-memory query to the AtMem dashboard.
- [x] Apply the simple dark AtBot visual language without removing AtMem
  controls or evidence.
- [ ] Make AtMem verify/install, configure, start, and diagnose a pinned AtBot.
- [x] Preserve OpenClaw adapter behavior, shadow mode, multi-agent topology,
  activation, restore, bridge verification, and Black Box evidence.
- [ ] Publish the same host-neutral adapter boundary for Hermes and others.
- [x] Fuse original plus content-free AtBot query expansions across lexical,
  canonical fact-key, graph, and local-vector signals for dashboard and adapter
  retrieval.
- [x] Prove `fav food` retrieves `likes burgers` without allowing AtBot to
  introduce an unauthorized record.

### Exit gate

- The user operates one AtMem dashboard and one authority store.
- AtBot can disappear without stopping safe baseline extraction or recall.
- No AtBot ranking can add an unknown, stale, or unauthorized record.
- OpenClaw and generic adapter regression suites remain green.

## Workstream 0: baseline and contract harness

Goal: make the boundary executable before changing memory behavior.

### Deliverables

- [ ] Record the full current test baseline and runtime duration.
- [ ] Add `atmem/contracts` and the versioned schema bundle.
- [ ] Define common identifiers, timestamps, digests, reason codes, assurance
  levels, sensitivity levels, and egress classes.
- [ ] Define canonical UTF-8 and RFC 8785 serialization rules.
- [ ] Define forward-compatible unknown-field and unknown-enum behavior.
- [ ] Add positive and negative JSON fixtures for every contract.
- [ ] Add schema/model round-trip tests.
- [ ] Add a capability-negotiation response listing supported protocol
  versions and optional features.
- [ ] Export fixtures for AtBot without requiring access to AtMem internals.

### Exit gate

- AtMem types, JSON fixtures, and an AtBot-side generated client agree on every
  field and digest.
- No new public type is represented as an untyped `object` placeholder.
- Current AtMem and OpenClaw tests remain green.

## Workstream 1: identity, source capture, and idempotency

Goal: create a trustworthy source and retry boundary before accepting model
interpretation.

### Deliverables

- [ ] Add a versioned `SourceCaptureRequest` and `SourceCaptureResult`.
- [ ] Persist stable host message IDs with their assurance level.
- [ ] Store exact source-body digests and distinguish exact support from a set
  of candidate source messages.
- [ ] Validate subject, agent, and workspace topology before storing or
  returning content.
- [ ] Add canonical proposal-payload digest calculation.
- [ ] Define idempotency as retry identity, separate from semantic deduplication.
- [ ] Bind every idempotency key to the canonical payload digest.
- [ ] Return the original result for an exact replay.
- [ ] Fail closed when a key is reused with a different payload.
- [ ] Define source-body retention without allowing active records to lose
  required evidence silently.

### Likely code areas

- `atmem/contracts/*`
- `atmem/core/canonical.py`
- `atmem/control/topology.py`
- `atmem/store/sqlite.py`
- `atmem/memory.py`
- new `tests/test_contracts.py`
- new `tests/test_source_capture.py`

### Exit gate

- Capture is scope-safe, replay-safe, and traceable to an exact source digest.
- A retry after a process restart produces no duplicate source or audit event.

## Workstream 2: proposal and admission

Goal: let AtBot propose memory without giving its model mutation authority.

### Deliverables

- [ ] Add `MemoryProposal` and `MemoryAdmission` public types.
- [ ] Add canonical tables for proposals, admission decisions, proposal-source
  links, and decision reason codes.
- [ ] Implement `Memory.submit_proposal()` as an atomic operation.
- [ ] Support decisions: `active`, `quarantined`, `duplicate`, `conflict`,
  `rejected`, and `invalid`.
- [ ] Record interpreter provider, model, prompt version, assurance, egress,
  calibration ID, and source binding.
- [ ] Treat confidence as model self-report unless a pinned calibration artifact
  exists for the exact model, prompt, and fact category.
- [ ] Prevent uncalibrated confidence from independently promoting or rejecting
  a proposal.
- [ ] Return typed decisions instead of requiring clients to inspect tables.

### Fact-key hardening

- [ ] Add a versioned fact-key canonicalizer with Unicode normalization, case
  folding, namespace grammar, escaping, and length limits.
- [ ] Audit proposed key, canonical key, and canonicalizer version.
- [ ] Treat a fact-key match as a grouping hint, never sufficient authority to
  supersede a record.
- [ ] Quarantine collisions with unrelated active records.
- [ ] Route cross-interpreter or cross-prompt-version supersession to review.
- [ ] Preserve the current deterministic extractor through a compatibility
  policy while its keys migrate to the canonicalizer.

### Likely code areas

- `atmem/contracts/models.py`
- new `atmem/core/fact_keys.py`
- `atmem/core/policy.py`
- `atmem/memory.py`
- `atmem/store/sqlite.py`
- `atmem/graph.py`
- new `tests/test_proposals.py`
- new `tests/test_fact_key_security.py`

### Exit gate

- A model can propose a fact but cannot approve it.
- Admission, source linkage, canonical mutation, graph projection, and audit
  evidence are atomic or leave no active partial state.
- Poisoned keys cannot supersede unrelated records.

## Workstream 3: governed hybrid recall

Goal: expose useful candidates without allowing semantic search or an external
reranker to bypass authority.

### Deliverables

- [ ] Add `RecallRequest` and `EligibleCandidateSet` contracts.
- [ ] Filter subject, agent, workspace, lifecycle, trust, sensitivity, and
  egress before returning candidate content.
- [ ] Require the intended reranker provider, model, and egress class before
  candidate selection.
- [ ] Fuse lexical, semantic, graph, trust, and recency signals with versioned
  score metadata.
- [ ] Revalidate semantic candidates against record digests and index
  generation.
- [ ] Return bounded graph paths as evidence.
- [ ] Preserve lexical recall as the safe degraded path.
- [ ] Record candidate-set digest, canonical generations, and withheld reasons.

### External reranking

- [ ] Add `RerankProposal` and `FinalRanking` contracts.
- [ ] Reject record IDs outside the eligible candidate set.
- [ ] Require a new candidate request when provider or egress class changes.
- [ ] Revalidate scope, lifecycle, policy, generations, membership, and budget
  after reranking.
- [ ] Record provider, model, prompt version, input/output digests, and egress.

### Likely code areas

- `atmem/retrieve/rank.py`
- `atmem/semantic/index.py`
- `atmem/graph.py`
- `atmem/memory.py`
- `atmem/store/sqlite.py`
- new `tests/test_governed_recall.py`
- new `tests/test_reranker_boundary.py`

### Exit gate

- No candidate content leaves AtMem before scope, sensitivity, and declared
  egress checks.
- A stale index or hostile reranker cannot introduce an ineligible record.

## Workstream 4: stable context and exact exposure

Goal: produce authorized context that is auditable and safe for KV/prompt-cache
reuse.

### Deliverables

- [ ] Add `ContextPackage`, `ExposureConfirmation`, and `ExposureReceipt`
  contracts.
- [ ] Separate the stable context byte block from volatile envelope fields such
  as timestamps, nonces, run IDs, and receipt IDs.
- [ ] Define deterministic record ordering, separators, escaping, Unicode
  normalization, and final-newline behavior.
- [ ] Return context-byte digest, serializer version, policy version, record
  versions, scope, memory generation, and byte/token budgets.
- [ ] Issue fresh authorization and exposure receipts for every use, including
  cache hits.
- [ ] Reject mismatched, expired, replayed, or wrong-scope confirmations.
- [ ] Emit invalidation signals when memory, policy, permission, scope, or
  serialization changes.
- [ ] Keep provider-specific KV-cache handles outside AtMem.

### Storage decision

- [ ] Add a durable canonical preparation record or outbox entry before
  projecting preview/exposure evidence into `ControlStore`.
- [ ] Make projection idempotent and observable when incomplete.
- [ ] Correlate canonical retrieval, preparation, control preview, exposure,
  model call, and turn identifiers.

### Likely code areas

- `atmem/core/canonical.py`
- `atmem/control/manager.py`
- `atmem/control/store.py`
- `atmem/control/evidence.py`
- `atmem/store/sqlite.py`
- new `tests/test_context_contract.py`
- new `tests/test_context_cache_safety.py`

### Exit gate

- Identical authorized inputs produce byte-for-byte identical context and the
  same stable digest.
- Every actual use gets a fresh scope-correct exposure receipt.
- Forgotten or newly ineligible content cannot be authorized through a cache
  hit.

## Workstream 5: relationships, lifecycle, and forgetting

Goal: make changing and deleting memory complete, reversible where intended,
and externally verifiable.

### Deliverables

- [ ] Add typed `duplicate`, `supports`, `extends`, `contradicts`, `supersedes`,
  `unrelated`, and `uncertain` proposal relationships.
- [ ] Add a relationship/review table with proposal, actor, policy, old/new
  records, and decision evidence.
- [ ] Never update semantic record content in place.
- [ ] Add deterministic rules for automatic transitions and explicit review
  rules for ambiguous, sensitive, or cross-interpreter changes.
- [ ] Add `ForgetRequest` and composite `ForgetReceipt` contracts.
- [ ] Cascade forgetting through canonical records, episodes, lexical indexes,
  graph state, semantic vectors, candidate sets, context packages, and media
  derivatives.
- [ ] Send cleanup requests for AtBot-owned buffers, checkpoints, caches, and
  artifacts; record acknowledgement, failure, and pending work.
- [ ] Distinguish logical exclusion, physical purge, derived cleanup, and
  external cleanup in the receipt.

### Likely code areas

- `atmem/core/policy.py`
- `atmem/memory.py`
- `atmem/store/sqlite.py`
- `atmem/graph.py`
- `atmem/semantic/index.py`
- `atmem/media.py`
- `atmem/maintenance.py`
- new `tests/test_relationships.py`
- new `tests/test_forget_cascade.py`

### Exit gate

- A correction preserves history and cannot silently overwrite an old record.
- A completed forget receipt proves all local derivatives are gone and reports
  every external acknowledgement or outstanding cleanup item.

## Workstream 6: concurrency, recovery, and audit closure

Goal: behave safely with multiple AtBot and host processes.

### Deliverables

- [ ] Define locking and transaction behavior for concurrent proposal,
  promotion, supersession, recall, and forget operations.
- [ ] Add compare-and-set generation checks for decisions based on earlier
  candidate sets.
- [ ] Make idempotency durable across restarts and worker retries.
- [ ] Recover interrupted graph, semantic, and control-evidence projections.
- [ ] Reject late model results after cancellation or scope expiry.
- [ ] Make incomplete and out-of-order events visible in verification.
- [ ] Add bounded retry and dead-letter handling for durable cleanup/outbox work.
- [ ] Verify that canonical mutation and canonical audit evidence commit in one
  transaction.

### Exit gate

- Concurrent tests produce no duplicate admissions, lost updates, partially
  active records, or unreported projection failures.
- Crash recovery is deterministic and idempotent.

## Workstream 7: generic hooks and OpenClaw migration

Goal: make OpenClaw the first conforming adapter without tying AtBot to it.

### Deliverables

- [ ] Version schemas for capture, prepare, exposure, model, tool, turn-end, and
  status events.
- [ ] Add capability negotiation during adapter initialization.
- [ ] Define ordering, replay, cancellation, assurance, and correlation rules.
- [ ] Preserve compatibility aliases through a documented migration window.
- [ ] Generate the fake AtBot adapter from the canonical schema bundle.
- [ ] Move the OpenClaw bridge onto the same versioned hook contract.
- [ ] Keep host-specific copy/freeze/restore code behind the OpenClaw adapter.
- [ ] Run Safe Switch and Agent Black Box regression suites unchanged in intent.

### Likely code areas

- `atmem/control/server.py`
- `atmem/control/manager.py`
- `atmem/control/hosts.py`
- `atmem/control/openclaw_native.py`
- `atmem/openclaw_install.py`
- `atmem/mcp/server.py`
- `integrations/openclaw/`
- `tests/test_generic_control.py`
- `tests/test_openclaw_control.py`
- `tests/test_blackbox.py`

### Exit gate

- The fake adapter and OpenClaw pass the same generic contract suite.
- OpenClaw copy, shadow, verify, activate, and restore guarantees do not regress.

## Workstream 8: public surfaces and release hardening

Goal: ship a supportable AtMem 2.2 contract rather than an internal experiment.

### Deliverables

- [ ] Export documented Python APIs without exposing private database classes.
- [ ] Add versioned MCP/JSON surfaces for AtBot-safe operations.
- [ ] Add CLI diagnostics for protocol versions, capabilities, pending outbox
  work, index generations, and adapter health.
- [ ] Document storage migrations, downgrade limits, backup, restore, and
  recovery.
- [ ] Document source retention, remote egress, cache invalidation, and deletion
  semantics.
- [ ] Add protocol examples and an AtBot integration guide.
- [ ] Add release notes and update `docs/capabilities.json`.
- [ ] Run Python 3.10–3.13, encrypted/unencrypted, semantic/no-semantic, generic,
  and OpenClaw test matrices.
- [ ] Perform a clean 2.1-to-2.2 migration and restore drill on copied fixtures.

### Exit gate

- AtBot can integrate using public schemas and APIs only.
- No release-blocking safety metric regresses.
- Upgrade and restore evidence is retained and inspectable.

## Framework integration roadmap

Frameworks integrate with AtMem's host-neutral turn contract. They never call
AtBot directly and never receive authority to approve, store, correct, or delete
memory. AtBot remains AtMem's private intelligence companion.

1. [x] Unify `control_prepare` with the dashboard's AtBot-assisted hybrid
   retrieval: content-free expansion, scoped lexical/fact-key/graph/vector
   candidates, AtBot ranking, final AtMem ID validation, stable context, and
   exposure evidence.
2. [x] Route automatic authenticated capture through AtBot fact/entity/
   relationship proposals and AtMem admission. Preserve deterministic capture
   when AtBot is unavailable, and never let inference promote its own proposal.
3. [x] Publish Pydantic AI and LangGraph/LangChain adapters first. Both must pass
   the generic lifecycle conformance suite for capture, prepare, exact exposure,
   model/tool evidence, turn completion, failure, and multi-agent scope.
4. [ ] Add Microsoft Agent Framework and Google ADK adapters using context
   providers/middleware and model/tool callbacks respectively.
5. [ ] Add an OpenAI Agents SDK adapter using a runner/model-request boundary for
   injection and lifecycle hooks for evidence.
6. [ ] Add Hugging Face smolagents and CrewAI adapters. Their wrappers must make
   retrieval automatic rather than relying on the model to remember to call a
   memory tool.
7. [x] Keep MCP as the universal tool-only fallback. MCP exposes governed memory
   operations but does not claim automatic injection or exact model-boundary
   exposure unless a conforming host adapter reports those events.

Adapter release order is a packaging priority, not an authority hierarchy. All
adapters consume the same versioned AtMem contracts, preserve the framework's
native short-term/workflow state, and use AtMem for governed cross-session
memory. Each adapter must support shadow mode before active injection.

## Cross-cutting test gates

The following failures block release regardless of aggregate quality scores:

- cross-workspace or cross-subject memory exposure;
- model output authorizing its own memory mutation;
- fact-key collision silently superseding an unrelated record;
- remote candidate disclosure before egress authorization;
- an external reranker adding an ineligible record;
- forgotten content appearing through lexical, graph, semantic, context, media,
  retry, or cache state;
- a cache hit bypassing current retrieval or exposure authorization;
- idempotency replay producing a duplicate mutation;
- canonical mutation without its canonical audit evidence;
- OpenClaw restore or Safe Switch regression.

Required test layers:

1. unit tests for canonicalization, policy, identifiers, and reason codes;
2. schema fixtures and transport round trips;
3. storage migration and transaction tests;
4. property tests for idempotency, canonical bytes, and scope isolation;
5. adversarial fact-key, prompt-injection, reranker, and replay tests;
6. concurrent process and crash-recovery tests;
7. fake-gateway contract tests shared with AtBot;
8. end-to-end generic and OpenClaw adapter tests.

## Recommended pull-request sequence

Keep each change reviewable and independently green:

1. `contracts-v1`: schema bundle, common types, fixtures, negotiation.
2. `scope-source`: scope validation, source-message identity, retention.
3. `proposal-storage`: proposal/admission tables and idempotency.
4. `fact-key-policy`: canonicalization, collision, and review rules.
5. `proposal-api`: public Python API and admission decisions.
6. `eligible-recall`: filtered candidate contract and evidence.
7. `reranker-boundary`: declared egress and final-ranking validation.
8. `stable-context`: canonical bytes, generations, and invalidation.
9. `exposure-receipts`: exact confirmation and durable projection.
10. `relationships`: contradiction, support, and supersession review.
11. `forget-cascade`: local cleanup and external acknowledgement.
12. `concurrency-recovery`: generations, outbox, retry, and crash tests.
13. `generic-hooks-v1`: lifecycle schemas and fake adapter.
14. `openclaw-conformance`: bridge migration and Safe Switch regression.
15. `release-2.2`: docs, matrices, migration drill, and release gates.

## Parallel AtBot work allowed

AtBot does not need to wait for every workstream. It may proceed with:

- generated contract models and a fake `AtMemGateway` after workstream 0;
- extraction eval datasets and deterministic model fixtures;
- local/remote provider routing and egress policy;
- prompt assembly and KV-cache key design;
- skills, tools, tracing, and capability profiles;
- the memory-centre service shell.

AtBot must not ship a temporary canonical memory store or depend on AtMem's
private tables while waiting for later workstreams.

## First implementation target

The first build target is deliberately narrow:

```text
one authenticated source message
  -> one typed AtBot proposal
  -> one AtMem admission decision
  -> one governed recall
  -> one byte-stable context package
  -> one exact exposure receipt
```

It must also prove that:

- replay creates no duplicate;
- a poisoned fact key cannot replace unrelated memory;
- an untrusted source is quarantined;
- a remote reranker cannot see disallowed candidates;
- another workspace cannot retrieve the memory;
- forgetting removes the memory and invalidates prepared context.

## Definition of AtBot-ready

AtMem 2.2 is ready for AtBot when:

- all public interaction uses versioned schemas and typed Python APIs;
- AtBot can capture, propose, recall, rerank, expose, correct, and forget without
  database access;
- AtMem can reject every unsafe proposal and ineligible retrieval;
- every active model-derived memory links to retained source evidence and an
  admission decision;
- context is deterministic enough for safe prompt-prefix caching while every
  use still receives fresh authorization;
- deletion reaches all local derivatives and reports external cleanup;
- the fake AtBot adapter and real OpenClaw adapter pass one conformance suite;
- the complete existing test suite and new release-blocking gates pass;
- AtBot can replace its model or agent framework without changing AtMem's
  canonical memory or protocol semantics.
