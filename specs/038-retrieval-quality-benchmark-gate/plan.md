# Retrieval Quality and Benchmark Release Gate Plan

## Technical context

- **Runtime:** Python 3.10–3.13.
- **Authority:** existing `Memory`, lifecycle, policy, scope and final context
  validation contracts.
- **Persistence:** existing SQLite and PostgreSQL store abstractions plus the
  protected evidence store; additive migrations only.
- **Retrieval:** current lexical/fact/semantic/graph RRF nomination and calibrated
  support decisions remain the compatibility baseline.
- **Optional intelligence:** registered local embedder/AtBot by default;
  explicitly configured hosted providers only when egress is allowed.
- **Tests:** pytest across supported Python versions, schema and installed-wheel
  gates, adapter conformance and real persisted-state upgrades.
- **Benchmarks:** official LongMemEval-V2 and DolphinBench repositories pinned by
  commit; heavy artifacts rooted at the configured external benchmark volume.
- **Observability:** AtMem retains authority and decision evidence; AtFlows may
  consume versioned stage events but is not required for retrieval correctness.
- **Product surfaces:** existing Python API, CLI, MCP, dashboard, OpenClaw and
  Hermes integrations; Pydantic AI and LangChain/LangGraph contract adapters.
- **Portability:** pathlib/platform abstractions and Python subprocess/file-lock
  behavior supported on Linux, macOS and Windows without a shell, symlink,
  Docker or GPU requirement on the base path. Hermes is native-tested on
  Linux/macOS and exercised through its documented WSL path on Windows; AtMem,
  MCP and supported native adapters retain direct Windows coverage.

## Constitutional checks

- **Authority before intelligence:** eligibility and scope are evaluated before
  every optional extractor, ranker, graph traversal and sufficiency assistant;
  canonical authority is revalidated before delivery.
- **Evidence and lifecycle:** immutable source capture remains authoritative;
  typed units and indexes are rebuildable derivatives with exact source links,
  deletion and supersession behavior.
- **Determinism and degradation:** the local deterministic path is complete;
  optional model, semantic, graph and AtFlows services may improve a result but
  their absence cannot change authority or prevent recall.
- **Benchmark rigor:** frozen development/confirmation identifiers, matched
  baselines, uncertainty, costs, stage attribution and invalid-package rejection
  protect claims from answer leakage and selective reporting.
- **Regression coverage:** LongMemEval tests long-horizon retrieval, LoCoMo
  protects established conversational/personal memory, and BEAM applicability
  is stated explicitly rather than assumed.
- **Portability and usability:** installed artifacts, public API, CLI, MCP,
  dashboard, migration, rollback and bounded resource behavior are release
  evidence, not post-benchmark follow-up work.

## Architecture decisions

### Review correction — repair representation before ranking

The 2026-09-29 independent Claude and Codex Astra reviews make formation and
identity correctness the first implementation boundary. Retained encrypted
development checkpoints showed two different failure modes: enterprise state
was mostly rejected or skipped during formation, while web state was heavily
suppressed by cross-episode supersession. Retrieval tuning begins only after a
reader-free rebuild proves that answer-bearing evidence survives formation and
remains historically addressable.

The correction is implemented as one product path, not benchmark compensation:

1. validate structured assertions against their exact supporting field/span;
2. preserve collision-resistant occurrence identity separately from durable
   fact identity and reconciliation;
3. make formation receipts resumable and impossible to discard silently;
4. preserve retrieval rank and query obligations through canonical reload;
5. bind sufficiency to query/evidence pairs;
6. budget the entire reader input, including media;
7. qualify reader finalization independently from retrieval accuracy.

### A. Extend the existing extraction pipeline with typed memory units

Retain source episodes once in the protected evidence store. Admit compact typed
memory units as an additive evolution of the existing
`atmem.extract.ExtractionProposal` and exact `ProposalEvidence` contracts. Do
not create a second admission pipeline. Structured payloads reference source
positions and do not copy full source text into every derivative.

Initial unit kinds:

- `atomic_fact`
- `durable_rule`
- `environment_state`
- `state_transition`
- `procedure`
- `failure_gotcha`
- `premise_constraint`

Every unit has a common envelope for scope, entity, time, polarity, provenance,
confidence, lifecycle and formation identity. Kind-specific payloads preserve
state fields, transition endpoints, ordered steps or rule conditions.

The first activated deterministic producer prioritizes `environment_state`,
`state_transition` and `procedure`; atomic facts and durable rules reuse and
extend current extraction behavior. Failure/gotcha and premise/applicability
are initially represented through explicit trigger, outcome, polarity and
condition fields and graduate to distinct promoted profiles only after
non-benchmark fixtures show a measurable benefit. The schema supports all
seven kinds from the start so this rollout does not require another contract.

### B. Treat formation as proposals plus deterministic admission

The existing extraction/application service accepts a source episode and
invokes one or more registered
proposal producers:

1. deterministic event/structure extractor;
2. optional registered model extractor over authorized bounded content;
3. host-provided structured observations through the same proposal contract.

It validates schemas, links exact source evidence, reconciles stable identities,
records loss/coverage, then uses existing AtMem authority to admit or withhold.
Model output never writes directly to storage.

Structured snapshots are observations, not one affirmative proposition. The
producer emits field- or bounded-span-grounded units and validation evaluates
the polarity of that unit's support, not arbitrary words elsewhere in the
snapshot. Formation checkpoints store the last processed source position and
resume deterministically. A `complete` receipt is valid only when every source
position is represented, explicitly unsupported, or rejected with a reason.

Occurrence identifiers are collision-resistant structured digests over scope,
episode, event, part and fragment. They are never shortened by prefix
truncation. A separate durable-fact key supports correction/conflict logic.
Repeated equal observations retain separate occurrence links even when their
payload bytes are deduplicated. Reconciliation cannot infer correction from a
shared URL, state index, chunk ordinal or ingestion order.

The persisted schema separates `source_identity_v2`, `occurrence_identity_v1`
and `durable_fact_identity_v2`. Their canonical preimages are versioned JSON
arrays serialized with RFC 8785 JCS after Unicode NFC normalization rather than
delimiter-concatenated strings and include authority scope;
digests remain independent of execution budgets. An additive old-to-new mapping
retains legacy identifiers, evidence links and every lifecycle/exclusion state.
Migration never reactivates a superseded, deleted, rejected, excluded,
quarantined or ambiguous legacy row. Historical queries may nominate a
superseded observation only through an explicit historical obligation and the
same authority predicate used for active retrieval.

The occurrence, mapping and deduplicated-byte tables are encrypted registered
derivatives. Deduplication is scope-local. Forget removes one occurrence without
affecting other authorized references, deletes shared bytes at the final
in-scope reference, verifies every derivative and records the mutation. An
ambiguous legacy row is placed in the product review queue; authorized CLI and
dashboard actions resolve it to reinstated, confirmed superseded or rebuilt
from retained evidence with append-only audit evidence.

Migration uses an additive encrypted generation with explicit checkpoints. It
is tested from published 2.3.x and beta stores, crashes safely at every
checkpoint, and rolls back by reselecting the untouched legacy profile without
deleting the new generation or emitting plaintext. Reader-free qualification
both migrates copies of retained checkpoints in place and rebuilds them from
retained evidence, then compares authorized historical/current state except for
explicitly queued ambiguity.

Original media bytes are captured into the protected evidence store before a
media occurrence is retrieval-ready. Locators remain provenance only. Backup,
restore and deletion cover the protected artifact and its derivatives, and an
installed-artifact disaster test removes the original host/dataset directory
before reconstructing the selected evidence.

Host and benchmark adapters submit ordered native evidence through
`episode-ingest-v1`, an additive envelope over existing `source-capture-v1` and
media-observation contracts. The product service writes it through
`EvidenceService.capture`, preserving text/state snapshots, annotated actions,
tool boundaries and media references with truthful source kinds and stable
positions. This is not a second ingest or evidence pipeline. Adapters do not
crop accessibility trees, turn trajectories into fixed character chunks or
form memory. Loss-aware formation is entirely product code.

### C. Route by information need

Extend recall requests additively with an optional versioned information-need
profile. The one canonical product enum is `exact_fact`, `current_state`,
`state_change`, `ordered_task`, `exception_risk`, `rule_application`,
`assumption_check` and `relational_synthesis`. Personal preferences are scoped
exact facts; historical-state questions are state changes with a temporal
target. A caller may provide a declared type. Unknown requests use the general
profile. Benchmark ability and application names are forbidden from runtime
contracts, code branches and diagnostics.

The profile controls channel quotas and required sufficiency slots, not scope,
policy or lifecycle. The eight request needs map to four operational profiles:

- **exact/state:** `exact_fact` and `current_state`, including scoped personal
  facts/preferences and exact values/labels;
- **temporal/change:** `state_change`, including historical state and
  before/action/after transitions;
- **procedure/action:** `ordered_task`, `exception_risk` and
  `rule_application`, including action constraints;
- **premise/relational:** `assumption_check` and `relational_synthesis`.

Unknown or compound requests use a bounded general composition of these quotas.

### D. Retrieve multiple views, not duplicated memories

Create derived searchable views over one canonical unit:

- exact/lexical view of labels, values and identifiers;
- semantic view of a concise relation statement;
- temporal keys;
- graph edges among typed entities and events;
- source adjacency and procedure/transition links.

Indexes contain record IDs and derived search material, remain rebuildable and
never become authority. Content-addressed source references avoid the prior
storage pattern of repeating whole chunks across tables.

### E. Expand a bounded evidence neighborhood

After initial nomination, `EvidenceExpander` follows only registered edges:

- source episode previous/next events;
- transition before/action/after;
- procedure predecessor/successor/branch;
- rule condition and exception;
- conflict/supersession lineage;
- bounded typed graph paths.

Expansion records the seed, path, budget and reason. It revalidates every added
record and cannot traverse inaccessible nodes.

### F. Make sufficiency a separate contract

`SufficiencyDecision` evaluates requested slots against selected typed units:

- subject/entity match;
- requested relation/action;
- polarity;
- time/current-state requirement;
- step order or transition completeness;
- applicability conditions;
- conflicts and freshness.

The deterministic engine handles explicit structured slots. Optional AtBot or a
registered reranker may propose sufficiency over authorized candidates, but must
return evidence IDs and slot reasons for deterministic revalidation.

The five sufficiency states project onto the existing three support classes:
`sufficient` becomes `direct_support`; `partial`, `contradictory` and `stale`
become explicitly qualified `background_context` only when policy permits and
are otherwise withheld; `unsupported` becomes `no_useful_memory`. Context
Package V2 has a canonical byte-stable V1 projection for old clients. Projection
can remove new fields but cannot strengthen support or change selected IDs.

### G. Pack for complementarity

`ContextAssemblerV2` greedily maximizes required-slot coverage, source diversity
and exact-field preservation per token/byte cost. It penalizes duplicate
paraphrases and includes conflict/uncertainty labels. It emits a versioned
host-neutral package; adapters only serialize it.

### H. Activate through shadow comparison

The typed profile begins disabled. Shadow mode runs legacy and candidate paths
against the same request, retaining decisions, selected IDs, context hashes and
stage timings without influencing the agent. Promotion is explicit and scoped;
rollback returns to legacy without deleting typed units or evidence.

### I. Keep one product path and several views

The application service owns `form`, `recall`, `explain`, `profile` and
`rollback`. CLI, MCP, dashboard and host adapters call this service rather than
reimplementing formation or selection. The benchmark adapter is another client
of this public boundary and is never imported by product code.

The default user journey is deliberately short:

1. `atmem retrieval setup` discovers the store and supported agents, then shows
   the proposed profile, scope, storage and optional egress.
2. The command enables candidate shadow mode and runs one ordinary typed
   formation-and-recall verification through the product API.
3. `atmem retrieval status` and the dashboard show a plain-language result plus
   advanced evidence details.
4. `atmem retrieval activate` changes the scoped profile explicitly;
   `atmem retrieval rollback` restores the previous profile without deleting
   evidence or typed units.

MCP exposes the same stable request/response contracts. Host adapters render
the returned package for their host but do not choose different evidence.

### J. Treat action constraints as typed delivery, not prompting folklore

When the need is rule application, Context Package V2 contains a machine-
readable action constraint with subject, applicability conditions, required or
prohibited action, target/parameters when present, validity, contradictions and
source references. A concise text rendering is provided for models that accept
only text. Both representations share one digest and selected evidence IDs.

### K. Bound every stage and make limits observable

The service accepts a versioned budget envelope. Formation bounds source bytes,
proposal count, optional extractor concurrency and wall time. Retrieval bounds
subqueries, per-channel nominations, graph visits, adjacency depth, candidate
count, context bytes/tokens and optional intelligence time. Limit exhaustion
returns a partial/withheld receipt with missing slots; it never triggers an
unbounded retry loop.

Dashboard reads use keyset pagination and cached aggregates. Status and health
paths never rebuild an index or decrypt/scan full evidence. Cache identity
includes scope, policy generation, lifecycle generation and profile version.

## Contracts and data model

### New additive contracts

- `memory-unit-v2`: common typed unit envelope plus kind payload.
- `formation-request-v1`: source, scope, producer policy and idempotency.
- `formation-receipt-v1`: coverage, proposal/admission/loss counts and source
  references.
- `information-need-v1`: type, entities, relation, temporal target, polarity,
  expected form and required evidence slots.
- `evidence-neighborhood-v1`: seeds, linked records, paths and budgets.
- `sufficiency-decision-v1`: status, required/covered/missing slots,
  contradictions, evidence IDs and reasons.
- `context-package-v2`: structured typed memories, ordered source evidence,
  selection decisions, budget and lifecycle identities.
- `retrieval-stage-event-v1`: content-free stage counts, latency, errors and
  optional model usage for AtFlows consumption.

### Persistent changes

Prefer canonical typed payloads inside the existing protected record envelope.
Add only the indexes/link tables required for stable source adjacency, typed
relations and formation receipts. Semantic metadata remains encrypted; plaintext
database inspection must not reveal unit content, entities, relations or source
text.

All migrations must:

1. inventory prior records and index generations;
2. preserve legacy reads;
3. build typed state in a new generation;
4. verify source links and counts;
5. activate atomically;
6. survive interruption at every checkpoint;
7. support verified deletion and deterministic rebuild;
8. never invent structure for evidence that was not retained.

## Proposed source layout

```text
atmem/
  extract/
    models.py                 # extend existing proposal v2
    deterministic.py
    reconcile.py
    validation.py             # extend existing proposal validation
  retrieve/
    intent.py
    expand.py
    sufficiency.py
    assemble.py
    profiles.py
    hybrid.py                 # extend existing nomination path
    models.py                 # additive decision types
  contracts/
    models.py                 # host-neutral contract classes
  schemas/v1/
    episode-ingest.json
    formation-request.json
    formation-receipt.json
    information-need.json
    evidence-neighborhood.json
    sufficiency-decision.json
    retrieval-stage-event.json
  schemas/v2/
    memory-unit.json
    context-package.json
  store/
    sqlite.py
    postgres.py
  control/
    manager.py                # profile, shadow and dashboard read model
  evidence/
    service.py                # existing EvidenceService.capture authority
  memory.py                   # existing proposal admission/application path
  benchmark/
    contracts.py              # strengthen claim gates

research/production_benchmarks/
  longmemeval_v2.py           # orchestration only; official harness does scoring
  dolphinbench.py             # orchestration only; official harness does grading
  quality_analysis.py         # paired/uncertainty and stage attribution

benchmarks/retrieval_quality/
  README.md
  protocols/
  manifests/
  reports/                    # small versioned summaries, not heavy raw data

tests/
  test_memory_formation.py
  test_memory_reconciliation.py
  test_retrieval_intent.py
  test_evidence_expansion.py
  test_retrieval_sufficiency.py
  test_context_assembler_v2.py
  test_retrieval_shadow_profile.py
  test_retrieval_quality_gate.py
  test_retrieval_storage_bounds.py
  test_retrieval_migration.py
```

Dashboard work extends the existing AtMem control UI rather than creating a
second application or source of truth. AtFlows receives only the new versioned
stage events and renders grouped agent/profile/stage metrics in its own repo
when a compatible companion version is available.

AtFlows changes are companion observability work, not a runtime dependency. Its
dashboard groups stage duration, counts, limit exhaustion and optional cost by
agent, profile and information-need type. It must not receive protected memory
content or decide retrieval outcomes. A missing or stopped AtFlows process has
no effect on formation, recall or rollback.

## Storage and performance constraints

- Store source bytes once and reference them by protected artifact/segment ID.
- Do not persist the same full text independently in canonical, graph, lexical,
  vector and benchmark tables.
- Record derived storage by category: canonical units, links, lexical index,
  vector index, graph index and evidence.
- Enforce per-source and per-scope proposal quotas with visible withholding;
  never silently truncate.
- Bound query decomposition, channel candidates, graph visits, neighborhood
  expansion, sufficiency candidates and context bytes independently.
- Reuse indexes and embeddings only under complete content/scope/policy/model
  identities; invalidate on lifecycle or generation change.
- Replace per-query temporary full-text construction and whole-corpus loading
  before typed profile activation. Exact/fact/FTS nomination uses persistent
  store indexes with authority predicates and keyset-bounded record reloads.
  The current 10,000-record/8 MiB hybrid collector limit is a known correctness
  blocker, not deferred optimization.
- Use packed float32 embeddings in derived stores where applicable and retire
  old inactive generations after verified activation and rollback windows.

Initial default limits are configuration, not benchmark-tuned constants. They
are frozen with fixture evidence before a production benchmark run:

| Boundary | Required behavior |
| --- | --- |
| Source input | Byte/item ceiling with a loss receipt for unrepresented regions |
| Formation | Proposal/type/scope quotas, bounded optional workers and deadline |
| Nomination | Independent per-channel quotas and a total authorized-candidate cap |
| Expansion | Maximum depth, edges, records and elapsed time |
| Sufficiency | Bounded evidence set; unknown/partial is explicit |
| Packing | Exact byte/token ceiling with excluded-evidence reasons |
| Diagnostics | Keyset page limit and cached aggregate generation |

Performance gates compare candidate and legacy paths on the same frozen local
workload and report cold/warm state, hardware, corpus size and page size. The
first implementation is rejected if it improves benchmark accuracy by scanning
the whole store or shifting large work into dashboard/status requests.

SC-003 remains the end-to-end target, but known full-scan and temporary-index
work is removed before benchmark tuning. Stage metrics then guide further
optimization; accuracy improvements that rely on whole-store scans fail the
product gate.

## Benchmark design

### Stage 0 — Frozen product fixtures

Build benchmark-neutral fixtures from supported agent evidence covering exact
labels/numbers, negation, temporal correction, transitions, ordered procedures,
conditional rules, conflicts, multi-hop relations and scope attacks. Freeze
them before tuning thresholds.

### Stage 1 — LongMemEval-V2 development

- Before typed runs, commit a salted-hash, domain-by-ability stratified
  question-ID split. Previously inspected dev10 IDs belong to development.
  Gold answers remain scorer-only and are inaccessible to product and adapter
  processes.
- Use official Small web and enterprise workloads, tuning only on development
  question IDs.
- Fixed reader: `Qwen/Qwen3.5-9B` through a pinned Hugging Face provider.
- Fixed judge: `gpt-5.2`, medium reasoning.
- Compare matched no-retrieval, official RAG slice+notes, legacy AtMem, typed
  AtMem operating points and declared ablations.
- Keep raw datasets, caches and runs on the external benchmark root.
- Use official scoring unchanged; separately report formation coverage,
  retrieved-answer support, sufficiency and reader-use stages.

### Stage 2 — LongMemEval-V2 confirmation and scale

Freeze the selected profile before evaluating unseen confirmation question IDs
on Small. Report the complete official Small result separately. Then run the
same frozen confirmation IDs on Medium as a larger-haystack scale test; Medium
is not an independent question split. Package official results and compute
paired bootstrap intervals plus LAFS without using confirmation answers for
tuning.

### Stage 3 — DolphinBench action validation

- Pin the official benchmark release.
- Use one matched Hermes/model configuration for built-in and AtMem arms.
- Map each persona to an independent AtMem authority scope.
- Ingest every message in order, wait for formation completion, checkpoint and
  make memory read-only during all 600 fresh tasks.
- Preserve complete agent/tool/grader evidence, token usage, cost and latency.
- Diagnose whether failures occurred at memory formation, retrieval, delivery,
  agent reasoning, tool selection or grading.

### Evaluation budget

Use no more than 20 complete paid evaluation configurations without a new
budget decision, and target no more than eight in this plan. Run formation,
retrieval and answer-in-context ablations first with local fixtures and no paid
judge. Paid configurations are limited to selected comparator/legacy/typed
arms, frozen confirmation/scale runs and an explicitly approved matched
Dolphin pair. Calibration, failed provider calls and retries are counted and
retained. Predeclare which runs are development, confirmation, scale and
submission; do not select the best random outcome.

## Release gates

`atmem retrieval qualify --release 2.3.8 --package <path>` will validate a
signed/checksummed qualification index referencing:

- local formation/retrieval fixtures;
- full LongMemEval-V2 Small paired results;
- matched pinned LoCoMo legacy/candidate no-regression results;
- the recorded BEAM applicability decision;
- installed product-journey, bounded-resource and CLI/MCP/dashboard/adapter
  parity evidence;
- DolphinBench paired results only when a separately approved research package
  is supplied; absence does not fail the stable product gate;
- uncertainty analysis;
- authority/deletion/migration/adapter gates;
- installed candidate identity;
- external artifact checksums and availability.

The command emits pass/fail/invalid with individual criterion evidence. It does
not run paid benchmarks implicitly and does not treat a missing file as a skip.

## Implementation phases

1. **Protocol and contract freeze:** benchmark-neutral fixtures, a precommitted
   question split, typed schemas, budget envelopes, metrics and claim
   vocabulary. Exit: malformed, leaking and incomplete packages are rejected by
   tests.
2. **Indexed compatibility foundation:** add persistent exact/FTS lookup and
   bounded canonical reloads before typed units become queryable, preserving
   legacy behavior while removing per-query whole-corpus work.
3. **Formation vertical slice:** deterministic formation of all seven unit
   kinds, governed admission, reconciliation, source links and loss receipts.
   Exit: frozen preservation, idempotency, deletion and storage tests pass.
4. **Answerable retrieval vertical slice:** add deterministic intent routing,
   independent exact/lexical/semantic/temporal/graph nomination over the
   persistent bounded lookup foundation, bounded
   neighborhoods, sufficiency and complementary packing. Exit: frozen
   sufficiency/authority/performance gates pass without an optional model.
5. **Real product journey:** application service, CLI, MCP, dashboard and two
   agent adapters share one package; shadow setup, activation, restart and
   rollback work. Exit: installed Linux/macOS/Windows evidence and browser/CLI
   parity, with the benchmark tree removed.
6. **Measured optimization:** optional intelligence and channel/profile changes
   enter only through predeclared ablations. Exit: each promoted component earns
   quality, latency or a required safety role.
7. **Production benchmarks:** LongMemEval Small development, frozen Small
   confirmation, Medium same-question scale evaluation and LoCoMo no-regression.
   Matched DolphinBench action evaluation remains separately approved research.
   Exit: complete raw packages, uncertainty, stage attribution and no harness
   compensation.
8. **Candidate qualification:** exact installed artifacts, migration, deletion,
   adapters, documentation and final 2.3.8 release decision.

## Verification strategy

Before any new paid benchmark call, run a reader-free checkpoint replay that
measures, for each frozen question: source representation, active historical
availability, nomination, neighborhood completion, packed minimal-evidence-set
coverage, useful-evidence precision and total reader tokens including images.
The replay compares the original checkpoint, admission/budget repair, identity
repair, combined repair and retrieval/packing additions so each improvement has
causal evidence.

Development evidence annotations live only in evaluator-owned external-root
artifacts bound to development IDs and immutable source hashes. Runtime product
code, adapters and confirmation execution cannot import or read them. Changing
an annotation must not change formation, retrieval, packing or reader input.
The annotation contract distinguishes answerable, explicit-negative and
unsupported/abstention cases, alternative minimal sets, ordering, polarity and
fixed source coordinates.

Then run a separately budgeted twelve-call finalization probe: short control, oracle evidence,
product context and worst-budget multimodal context, each repeated three times.
All twelve must contain a parseable final answer and must not terminate for
length. This probe tests serving/finalization only and is not reported as memory
accuracy.

The enforced sequence is: freeze contracts/annotations; repair authority,
media retention, formation and identity; pass the reader-free formation rebuild;
repair retrieval/sufficiency/packing; pass reader-free evidence, security,
migration and installed-artifact gates; obtain independent review; commit and
push the reviewed candidate; pass the configuration-specific paid finalization
probe; then run the corresponding scored development sample. Existing paid
tasks T059, T061 and T064 are subject to the same prerequisite chain.

- Contract/schema round trips and rejected malformed proposals.
- Property tests for stable identities, ordering, polarity and deterministic
  packing.
- Authority tests proving denied content cannot affect candidate counts, graph
  paths, sufficiency, packing or telemetry.
- Migration tests from published stores with interruption at each checkpoint.
- Stolen-store scans for planted semantic text and protected metadata.
- Deletion tests across canonical units, links, graph, lexical/vector indexes,
  caches, backups and exports.
- Cross-version Python and installed-wheel tests.
- Adapter conformance for OpenClaw, Hermes, MCP, Pydantic AI and
  LangChain/LangGraph.
- Full benchmark package validators and deliberately invalid packages.
- Browser verification that CLI and dashboard show the same authority state.
- Product-code import test proving benchmark packages are absent and cannot be
  loaded by formation/retrieval runtime modules.
- Cross-platform installed journey on Linux, macOS and Windows with paths that
  contain spaces and non-ASCII characters, restart and lock contention. Hermes
  is native-tested on Linux/macOS and WSL-tested on Windows without claiming a
  native Windows Hermes runtime.
- Matched pinned LoCoMo legacy/candidate no-regression evidence, plus an explicit
  BEAM applicability decision for the selected change set.
- Performance/storage regression evidence for idle CPU, cold/warm p50/p95,
  keyset pages, cache invalidation, idempotent ingestion and category growth.
- MCP/CLI/dashboard/adapter golden-contract test for profile, selected IDs,
  sufficiency, provenance, action constraints and rollback.

## Documentation and release changes

- Update the 2.3.8 roadmap so retrieval qualification is a final release gate,
  while preserving Hermes, MCP registry and AtFlows secret-redaction scope.
- Document profiles, local/hosted dependencies, storage growth, shadow
  activation, rollback and benchmark limitations.
- Add a 2.3.8 release note only during release preparation and follow the
  repository release completion rule; planning creates no tag or package.
