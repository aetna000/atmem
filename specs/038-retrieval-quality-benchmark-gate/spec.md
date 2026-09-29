# Feature Specification: Retrieval Quality and Benchmark Release Gate

**Feature directory:** `specs/038-retrieval-quality-benchmark-gate`
**Created:** 2026-09-27
**Status:** Proposed
**Target:** AtMem 2.3.8 final retrieval-quality gate; prereleases may expose
explicitly labelled, opt-in research profiles but may not claim qualification.

## Overview

AtMem must retrieve memory that is sufficient to answer or act, not merely text
that is topically similar. The current governed hybrid path is strong on scope,
lifecycle, provenance and deterministic ranking, but the recorded
LongMemEval-V2 development slice exposed a deeper quality problem: AtMem often
found the correct application or trajectory while failing to preserve or select
the exact state, transition, ordered procedure, exception or outcome needed by
the reader. More ranking signals cannot recover information that was never
represented as the right memory object.

This feature makes retrieval quality a product capability and a release gate.
It separates four independently measurable stages:

1. **Formation** — turn full-fidelity source evidence into typed, loss-aware
   memory proposals without replacing the source.
2. **Retrieval** — nominate and expand evidence appropriate to the information
   need, while enforcing authority before intelligence.
3. **Sufficiency** — determine whether the bounded evidence actually supports
   the requested relation, sequence, state change, rule or exception.
4. **Delivery** — assemble concise, structured, provenance-bearing context that
   a fixed reader or agent can use correctly.

The benchmark harness remains inert. LongMemEval-V2 and DolphinBench supply
workloads, scoring and evidence collection; all memory formation, retrieval,
reconciliation and context construction must be implemented in AtMem and be
available to ordinary supported agents through host-neutral contracts.

## Problem model

AtMem currently over-relies on independently ranked bounded text records. That
fails in distinct ways:

- **Representation loss:** an exact UI value, negative observation, ordered
  step, precondition or post-action state is absent from the derived record.
- **Granularity mismatch:** a large chunk contains the answer but dilutes its
  relation; a small chunk contains a label but loses the surrounding state.
- **Relation blindness:** semantic similarity identifies the topic but not the
  requested attribute, subject, direction, order or polarity.
- **Temporal blindness:** an older valid state outranks the current state, or a
  transition is reduced to two unrelated observations.
- **Evidence isolation:** the useful fact needs its adjacent state, preceding
  action, next step or exception, but top-k returns unrelated high scorers.
- **Context usability:** retrieved evidence is technically relevant but
  repetitive, contradictory, poorly ordered or too opaque for the reader to
  apply.
- **Benchmark confounding:** end-task accuracy alone cannot show whether
  formation, retrieval, sufficiency or the reader caused the failure.

## User scenarios and independent acceptance

### US1 — Recall exact environment experience (P1)

An agent asks about an interface state, a before/after change, an ordered
workflow, a recurring failure mode or an invalid premise. AtMem returns the
smallest sufficient evidence set with state, order, polarity and provenance
preserved, or explicitly withholds when the store does not support the answer.

**Independent acceptance:** On frozen static, dynamic, procedure, gotcha and
premise fixtures, test formation and retrieval separately. Verify exact values,
negative facts, order, temporal validity, adjacent evidence and contradictions.
The reader is not required to validate the formation/retrieval fixtures.

### US2 — Apply a durable personal or organizational rule (P1)

An agent receives a normal task whose correct tool action depends on an old
preference, constraint or rule. AtMem retrieves the governing rule from the
correct persona and agent scope, includes the conditions under which it applies,
and does not expose another persona's memory.

**Independent acceptance:** Run the same agent/model with native memory and
AtMem against isolated persona histories. The AtMem arm must use read-only
checkpointed memory during evaluation, and app actions must be graded by the
benchmark rather than inferred from retrieved text.

### US3 — Understand why retrieval succeeded or failed (P1)

A maintainer can inspect formation coverage, candidate channels, expansions,
sufficiency decisions, selected evidence, withheld evidence, latency and cost
for one query without reading inaccessible scopes or treating a rank as proof.

**Independent acceptance:** Reconstruct a query from retained AtMem evidence
after the host process and derived index are removed. The report identifies the
first failed stage and does not require agent, provider or benchmark logs.

### US4 — Release only benchmark-qualified retrieval (P1)

A release owner can run frozen local conformance tests and pinned production
benchmarks, compare matched baselines, and determine automatically whether the
2.3.8 retrieval profile qualifies. A partial, mismatched, cherry-picked or
failed run cannot produce a passing release gate.

**Independent acceptance:** Exercise complete, partial, corrupt, mismatched and
held-out benchmark packages. Only the complete matched package can pass. Raw
per-case evidence remains available and benchmark code contains no memory
feature or answer-specific compensation.

### US5 — Choose a useful operating point (P2)

An operator can select a documented local-first retrieval profile that balances
quality, latency and context size. Profiles share the same authority and
sufficiency contracts; changing top-k or optional intelligence cannot widen
scope or bypass final validation.

**Independent acceptance:** Compare at least three predeclared operating points
with the same corpus, reader, judge and authority state. Report accuracy,
evidence sufficiency, p50/p95 latency, context tokens, storage and cost.

### US6 — Adopt and operate the capability without benchmark knowledge (P1)

A normal AtMem user can enable the candidate retrieval profile for an existing
agent through one guided CLI operation or the equivalent dashboard flow. The
same user can ask what AtMem remembered, why a memory was selected or withheld,
which source supports it, how much storage and time the path consumed, and how
to return to the prior profile. No benchmark package, benchmark vocabulary, or
manual database work is required.

**Independent acceptance:** From clean installed artifacts, configure a
supported native agent on Linux, macOS and Windows; validate Hermes natively on
Linux/macOS and through its documented WSL route on Windows. Form typed memory
from ordinary agent evidence, recall a fact, transition, procedure and
conditional rule through the public MCP and adapter contracts, inspect the same
decisions in CLI and dashboard, restart the processes, and roll back the
profile. The workflow must remain useful when optional model, semantic, graph
and AtFlows services are unavailable.

## Functional requirements

### Authority and source preservation

- **FR-001:** Every new formation, nomination, expansion, reranking and packing
  path MUST preserve authorization-before-intelligence, lifecycle filtering,
  scope isolation, final canonical revalidation, exact evidence linkage and
  encrypted-at-rest behavior required by the constitution.
- **FR-002:** Full-fidelity source episodes MUST remain immutable evidence.
  Derived memories, summaries, claims, procedures and indexes MUST reference
  source byte ranges or structured event identifiers and MUST NOT replace the
  retained source.
- **FR-003:** Formation output MUST be a versioned proposal. Deterministic code,
  AtBot or another registered model may propose typed memories, but only AtMem
  may admit, supersede, exclude, forget or expose them.
- **FR-004:** A failed or unavailable optional extractor, embedder, reranker or
  graph component MUST preserve a useful deterministic path or withhold; it
  MUST NOT silently admit raw telemetry, widen scope or label incomplete
  formation as complete.

### Typed memory formation

- **FR-005:** AtMem MUST support host-neutral typed derived memories for at
  least: atomic fact, durable rule/preference, static environment state,
  state-transition event, ordered procedure, failure/gotcha, and premise or
  applicability constraint. The ontology MUST be justified and tested with
  ordinary supported-agent sources from at least two non-benchmark domains per
  promoted kind; benchmark category names or examples MUST NOT be used as
  runtime routing keys.
- **FR-006:** Every typed memory MUST retain subject/entity, relation or action,
  value/outcome, polarity, observed-versus-inferred status, valid/event time,
  source scope, confidence, source references and formation version where the
  type makes those fields meaningful.
- **FR-007:** State-transition memories MUST preserve a bounded
  before-state/action/after-state tuple. They MUST distinguish an observed
  transition from a causal inference.
- **FR-008:** Procedure memories MUST preserve ordered steps, prerequisites,
  branch conditions, completion evidence and known failure conditions. A bag of
  semantically similar steps is not an ordered procedure.
- **FR-009:** Negative observations and invalid premises MUST preserve their
  polarity. Formation MUST NOT rewrite “no subscription,” “not available,” or
  “this workflow does not support X” into an affirmative topical memory.
- **FR-010:** Formation MUST retain both an atomic searchable representation and
  a bounded evidence neighborhood sufficient to recover labels, values,
  conditions and sequence. Chunk size alone MUST NOT define memory semantics.
- **FR-011:** Stable identity and reconciliation MUST detect exact duplicates,
  compatible restatements, corrections and conflicts. Corrections supersede
  prior current state without deleting historical evidence; unresolved
  conflicts remain explicit.
- **FR-012:** Formation MUST expose coverage and loss receipts: source events
  observed, proposals by type, admitted/withheld/rejected counts, unsupported
  media or fields, and source regions not represented by a derived memory.

### Information-need-aware retrieval

- **FR-013:** Retrieval MUST classify or explicitly accept one canonical
  product information need: `exact_fact`, `current_state`, `state_change`,
  `ordered_task`, `exception_risk`, `rule_application`, `assumption_check` or
  `relational_synthesis`. Personal preferences are scoped exact facts;
  historical-state questions are state changes with a temporal target. The
  type is a routing hint, never an authority decision. Runtime contracts and
  diagnostics MUST NOT use benchmark ability or application labels.
- **FR-014:** Retrieval MAY decompose a request into bounded subqueries for
  entity, relation, time, step, condition and expected answer form. The original
  request remains authoritative for final sufficiency.
- **FR-015:** Authorized lexical, exact-label/fact-key, semantic, graph,
  temporal and task-relation channels MUST nominate independently under declared
  quotas. Adding a channel MUST earn its place through ablation evidence.
- **FR-016:** Exact identifiers, interface labels, quoted strings, numeric
  values, symbols and negation MUST have a deterministic lexical path and MUST
  NOT depend exclusively on embeddings.
- **FR-017:** Graph nomination MUST operate on typed, source-linked relations
  and support bounded multi-hop retrieval without treating graph proximity as
  answer support.
- **FR-018:** Temporal nomination MUST distinguish event time, observation time
  and current validity. Recency MAY break ties among valid evidence but MUST NOT
  override explicit historical or superseded-state queries.
- **FR-019:** Retrieval MUST support bounded evidence-neighborhood expansion:
  adjacent source spans, preceding/following events, procedure neighbors and
  transition endpoints. Expansion MUST retain why each neighbor was included.
- **FR-020:** Retrieval MUST preserve independent source diversity and avoid
  filling the context budget with duplicate paraphrases from one event when a
  complementary condition, outcome or contradiction is available.

### Sufficiency and context construction

- **FR-021:** A versioned sufficiency decision MUST evaluate whether selected
  evidence supports the requested subject, relation, polarity, time, order and
  applicability. Topic similarity, frequency, importance, graph proximity and
  planner/critic scores are priors only.
- **FR-022:** Sufficiency MUST represent `sufficient`, `partial`,
  `contradictory`, `stale`, and `unsupported`. Only sufficient evidence may be
  labelled direct support; other states are withheld or explicitly marked as
  incomplete background according to policy.
- **FR-023:** Optional model-assisted sufficiency or reranking MUST see only
  authorized bounded candidates, have a pinned identity and egress decision,
  and return record identifiers plus reasons. AtMem MUST deterministically
  revalidate its output and remain functional without it.
- **FR-024:** Context packing MUST produce a host-neutral structured package
  containing the request, selected typed memories, ordered evidence, conflicts
  or uncertainty, source references, selection reasons, token/byte budget,
  generation and expiry. Adapters may serialize it but may not change its
  meaning.
- **FR-025:** The packing policy MUST optimize evidence sufficiency per bounded
  context budget rather than raw top-k score. It MUST record evidence excluded
  by budget and detect when required complementary evidence did not fit.
- **FR-026:** The delivered context MUST be concise enough for a fixed reader to
  use, while retaining exact labels, numbers, ordering, polarity and conditions.
  Summarization MUST NOT silently alter these fields.

### Measurement and benchmark integrity

- **FR-027:** AtMem MUST measure formation, nomination, expansion, sufficiency,
  packing and delivery separately, including item counts, p50/p95 latency,
  errors, context tokens/bytes and optional model cost. Unknown values MUST not
  be reported as zero.
- **FR-028:** Benchmark integrations MUST call the same public/product memory
  contracts used by supported agents. Benchmark code MUST NOT perform memory
  extraction, answer-aware filtering, query-specific repairs, retries that the
  product would not perform, or direct database/index searches unavailable to a
  normal client.
- **FR-029:** Development samples, plumbing tests, complete benchmark runs and
  official submissions MUST be visibly distinct. A development sample cannot
  satisfy a release or customer-quality claim.
- **FR-030:** Every production benchmark package MUST pin dataset and source
  revisions, split, leakage controls, AtMem and adapter commits, configuration,
  model/provider revisions, seeds or repeated-trial policy, hardware, resource
  limits, raw results, errors, cost, latency and checksums.
- **FR-031:** LongMemEval-V2 evaluation MUST use its official complete web and
  enterprise workloads, fixed `Qwen/Qwen3.5-9B` reader, required `gpt-5.2`
  judge and unchanged scoring. A precommitted stratified question-ID split
  within the 451 questions separates development from confirmation; Small and
  Medium MUST NOT be described as independent or held out because they reuse
  questions at different haystack scales. Provider routing MUST be pinned and
  recorded.
- **FR-032:** DolphinBench evaluation MUST ingest all three persona histories
  into separate AtMem scopes, checkpoint completed memory, keep it read-only
  across 600 fresh tasks, use matched agent/model/tool configurations, and
  retain all action-grading, cost and latency evidence.
- **FR-033:** Benchmark labels and expected answers MAY be used by scorers and
  post-run diagnosis only. They MUST NOT enter formation, retrieval, query
  expansion, sufficiency, packing or retry decisions.
- **FR-034:** Predeclared ablations MUST separately remove typed formation,
  neighborhood expansion, each nomination channel, temporal reasoning,
  sufficiency and structured packing. A component is promoted only when its
  quality contribution or required safety role is demonstrated.
- **FR-035:** Tuning MUST use a salted, precommitted, domain-by-ability
  stratified question-ID development partition that includes every previously
  inspected development case. Final quality confirmation MUST use the unseen
  confirmation question IDs with a frozen configuration; Medium reuses those
  IDs only to test scale. Any answer inspection or inspection-driven change
  resets the affected confirmation status.
- **FR-036:** Heavy benchmark data, model caches, raw runs and generated plots
  MUST be stored under the configured external benchmark root. Small manifests,
  schemas, analysis code and publication tables remain version controlled.

### Product, compatibility and release behavior

- **FR-037:** The base profile MUST remain local-first and useful without a
  hosted model. Hosted extraction, reranking or judging is opt-in, explicit,
  scoped and attributable.
- **FR-038:** Existing canonical records and evidence MUST remain readable.
  New typed derived state requires an additive versioned schema, deterministic
  rebuild from retained evidence where possible, crash-safe migration and
  verified deletion across every derivative.
- **FR-039:** Legacy retrieval remains available during qualification. Profile
  activation MUST begin in shadow mode, compare decisions without influencing
  the agent, require explicit promotion and provide a verified rollback.
- **FR-040:** CLI and dashboard MUST show active retrieval profile, formation
  coverage, sufficiency outcome, selected evidence types, latency, benchmark
  qualification and honest limitations from the same authority state.
- **FR-041:** Supported OpenClaw, Hermes, MCP, Pydantic AI and LangChain/
  LangGraph paths MUST consume the same host-neutral context package and scope
  rules. Host-specific prompt injection logic MUST remain in adapters.
- **FR-042:** The exact installed 2.3.8 candidate MUST pass Python 3.10–3.13,
  schema/migration, authority, deletion, adapter, dashboard, packaging,
  installed-artifact and benchmark claim gates before final release.
- **FR-043:** Release notes and public documentation MUST state which profiles
  passed which workload. “State of the art,” “beats,” “production quality,” or
  equivalent language requires the corresponding complete matched evidence.
- **FR-044:** Typed formation, information-need routing, neighborhood expansion,
  sufficiency and Context Package V2 MUST be accessible through versioned
  product APIs used by CLI, MCP and supported adapters. Benchmark modules MUST
  not be imported by, registered with, or required by the runtime feature.
- **FR-045:** The guided CLI and dashboard setup MUST discover the existing
  store and supported agents, preview additive storage/profile changes, enable
  shadow mode, verify one real formation-and-recall round trip, and provide a
  single rollback action. Machine-readable CLI output MUST expose the same
  authority state and reason codes as the dashboard.
- **FR-046:** MCP and adapter users MUST receive a stable, compact rendering of
  Context Package V2. A durable rule that governs an action MUST expose its
  applicability condition, required or prohibited action, source, and current
  validity as data rather than relying on an unqualified prose paragraph.
- **FR-047:** Formation and retrieval work MUST be incrementally bounded. Each
  stage MUST have configurable limits for source bytes, proposals, candidate
  counts, graph visits, neighbor depth, context bytes, concurrency and wall
  time; hitting a limit MUST produce a visible partial or withheld receipt
  rather than unbounded CPU, memory, storage or retry work.
- **FR-048:** Product diagnostics MUST use cursor/keyset pagination, bounded
  summaries and cached aggregate read models where appropriate. Opening the
  dashboard or asking for status MUST NOT scan or decrypt the complete evidence
  store, rebuild retrieval indexes, or load benchmark artifacts.
- **FR-049:** Paths, locking, subprocess invocation, atomic replacement,
  service discovery and optional accelerator behavior MUST use supported
  cross-platform abstractions. The base path MUST not require POSIX shell
  semantics, symlinks, fork, Unix signals, Docker or a GPU.
- **FR-050:** Product surfaces MUST explain sufficiency in ordinary language:
  what was requested, what AtMem found, what is missing or conflicting, what
  was shared with the agent, and which source supports it. Raw similarity
  scores and benchmark labels MAY appear in advanced details but MUST NOT be
  the only explanation.
- **FR-051:** AtMem MUST expose a host-neutral episode-ingest contract that
  losslessly accepts ordered text, state, action, tool and media references with
  truthful source kinds and stable source positions. Benchmark and host
  adapters may map native events to this contract but MUST NOT chunk, summarize,
  filter fields, form memories, search stores or label task abilities. This is
  an additive evolution of Source Capture V1 and media observation: it MUST
  write source evidence through the existing `EvidenceService.capture`
  authority rather than create another evidence or ingest system.
- **FR-052:** Context Package V2 MUST define a deterministic byte-stable
  projection to the existing Context Package V1. Sufficiency states map to the
  existing support classes as follows: `sufficient` to direct support;
  `partial`, `contradictory` and `stale` to qualified background or withholding
  by policy; and `unsupported` to no useful memory. No adapter may strengthen
  that mapping.
- **FR-053:** Shadow execution MUST be sampled and budgeted by default. It MUST
  expose added latency, CPU work, storage and optional model cost, and
  automatically stop candidate work at its budget without delaying the legacy
  response.
- **FR-054:** Retrieval qualification MUST include a pinned LoCoMo no-regression
  arm using the existing production benchmark contract to detect conversational
  and personal-memory regressions. BEAM applicability MUST be recorded; if the
  change does not exercise its scheduling/large-workload claim, the package
  states why it is not an accuracy gate rather than silently omitting it.
- **FR-055:** Structured observations MUST be validated at the assertion or
  field span that supports the proposed unit. Negation elsewhere in the same
  snapshot, accessibility tree, tool result or source part MUST NOT cause a
  faithful observation to be rejected or have its polarity changed. A proposal
  whose polarity cannot be grounded at its supporting span MUST be withheld
  with a specific reason.
- **FR-056:** Observation occurrence identity MUST be distinct from durable-fact
  identity. Every admitted observation MUST retain a collision-resistant
  episode, event and fragment identity without truncating away discriminators.
  Equal content observed in separate episodes MAY share deduplicated bytes but
  MUST retain every occurrence and its provenance. Supersession requires an
  explicit compatible fact identity plus correction or temporal-transition
  evidence; URL, source position or chunk coincidence alone is insufficient.
  Source and occurrence identifiers MUST use an unambiguous canonical encoding
  (length-prefixed or RFC 8785 JSON after Unicode NFC normalization) that
  includes authority scope and a version, without truncating or lossily
  normalizing discriminators; lifecycle, exclusion,
  quarantine, deletion and tombstone state MUST survive migration and rebuild,
  and ambiguous legacy supersessions MUST remain unavailable pending review
  rather than being blanket-reactivated. Ambiguous legacy rows MUST enter an
  authorized, audited review queue with `pending_review`, `reinstated`,
  `confirmed_superseded` and `rebuilt_from_evidence` outcomes; rebuilding from
  retained evidence is the default remedy. Byte deduplication MUST NOT cross an
  authority scope. Occurrence, identity-mapping and deduplicated-byte records
  are encrypted registered derivatives: forget MUST remove and verify their
  references, delete shared bytes after the last in-scope reference, and append
  an audit event.
- **FR-057:** Formation MUST be resumable across declared byte, proposal and
  wall-time boundaries. Receipts MUST distinguish processing completion,
  representation coverage and retrieval readiness; identify every processed,
  terminally unsupported/rejected and resumable source position; and expose the
  next resume position. Adapters or callers MUST retain and surface the receipt,
  MUST NOT checkpoint an unfinished formation as ready, and MUST NOT treat
  source capture as proof that derived evidence is retrievable. Resuming or
  changing independent episode ingestion order MUST not change the set of
  historically available observations or the current/superseded assignment,
  which is determined by event/assertion time rather than arrival order.
- **FR-058:** Candidate rank, channel score, episode occurrence and information-
  need obligations MUST survive canonical typed-unit reload and enter expansion
  and packing explicitly. Metadata or short unrelated units MUST NOT gain
  priority merely because rank information was discarded or because they cover
  generic non-empty fields. One shared authority/lifecycle/exclusion predicate
  MUST run before every reload, traversal or global escape-path lookup as well
  as during final revalidation; ineligible content MUST NOT influence paths,
  budgets, sufficiency, diagnostics or timing labels.
- **FR-059:** Sufficiency MUST bind each requested obligation to supporting
  evidence for the same entity, relation/action, polarity, temporal target and
  applicability. Evidence from unrelated episodes or entities MUST NOT be
  combined into a sufficient decision. Early packing termination is permitted
  only after all obligations are supported and a bounded contradiction/current-
  validity check completes.
  Obligations MUST use a versioned contract carrying entity/relation or action,
  polarity, temporal target, applicability, alternatives and unresolved
  interpretation, and MUST propagate unchanged from the product request through
  nomination, expansion, packing and the decision receipt.
- **FR-060:** Context budgets MUST cover the complete delivered reader input,
  including structured text, serialization overhead and original media or
  screenshots. Media MUST be deduplicated and selected because it discharges a
  named evidence obligation; it MUST NOT be appended outside the budget. The
  package MUST preserve every procedure prerequisite, step condition,
  completion criterion and failure condition. Original media bytes MUST first
  be retained as protected evidence and remain authoritatively resolvable after
  the source workspace or benchmark corpus is removed. Budget receipts MUST pin
  tokenizer/processor, chat template, image policy, host/request overhead and
  output allowance; exceeding the budget MUST yield a visible partial or
  unsupported package rather than silently dropping a required case.
- **FR-061:** Reader qualification MUST distinguish evidence availability from
  answer finalization. Before a scored paid sample, pinned short-control,
  oracle-evidence, product-context and worst-budget multimodal probes MUST
  record finish reason, final-answer presence, input/output tokens, latency,
  retries and cost. Reasoning-only, empty, unparsable or length-terminated
  output is an operational failure and MUST NOT be silently retried or scored
  as a memory-quality result. Each reader/agent/grader configuration requires
  its own frozen gate manifest bound to candidate, checkpoint, provider, model,
  processor, prompt, sampling, proxy, concurrency and budget identities. Every
  scored response MUST reapply finalization validation and immediately cancel
  siblings on failure with durable cleanup and cost evidence.

## Success criteria

### Mandatory 2.3.8 final release gates

- **SC-001:** Frozen local formation fixtures achieve at least 95% source-field
  preservation for exact labels, numeric values, polarity, ordered steps and
  before/action/after transitions, with zero invented source support.
- **SC-002:** Frozen retrieval fixtures achieve at least 90% evidence
  sufficiency recall within the declared context budget, at least 80% useful
  evidence precision, and at most 2% unsupported direct-support decisions.
  Every authorization, lifecycle, scope and deletion adversarial case passes.
- **SC-003:** On the precommitted unseen LongMemEval-V2 Small confirmation
  question IDs across both domains, the release candidate reaches at least 60%
  accuracy and exceeds a locally rerun, hardware- and provider-matched official
  `rag_query_to_slice_notes` comparator by at least 5 percentage points. The
  complete official Small score and every ability score are also reported but
  are not mislabeled held out. Retrieval records p50 at or below 2 seconds and
  p95 at or below 5 seconds on declared hardware.
- **SC-005:** At least two independent repetitions or a predeclared paired
  bootstrap analysis reports uncertainty for end-task quality; the lower bound
  of the declared primary improvement must remain above zero.
- **SC-006:** Benchmark packages have complete provenance, raw per-case results,
  p50/p95 latency, throughput, refusal/error rate, context usage, storage and
  model/tool cost. Claim validation rejects every deliberately incomplete or
  mismatched package.
- **SC-007:** Installed-candidate sampled shadow comparison, explicit activation and
  rollback succeed for OpenClaw and Hermes without changing model selection,
  tool state or memory outside the authorized scope, and remain within the
  declared shadow CPU, latency, storage and optional-cost budget.
- **SC-008:** All benchmark-heavy artifacts are written to the configured
  external root and verified by SHA-256 manifests; removal of the benchmark
  corpus and harness leaves the shipped retrieval feature fully functional.
- **SC-012:** A clean-install product journey on Linux, macOS and Windows can
  enable shadow mode, form and recall all seven typed unit kinds, inspect the
  result through CLI and dashboard, call the same path through MCP, restart,
  activate and roll back without benchmark files or manual database edits.
  Hermes is verified natively on Linux/macOS and by its documented WSL route on
  Windows; no native-Windows Hermes claim is made.
- **SC-013:** On the frozen CPU-only local workload with optional intelligence
  off, candidate retrieval has p50 at or below 500 ms and p95 at or below 2 s
  at 50,000 typed units, p95 at or below 5 s at 100,000 units, and peak retrieval
  RSS growth at or below 512 MiB. Sampled shadow adds no more than 20% p95
  latency to the legacy response. Status/dashboard requests remain bounded to
  one page plus cached aggregates, and idle background formation performs no
  polling work when the queue is empty. Exact hardware, corpus size, cold/warm
  state and page size are retained with the evidence.
- **SC-014:** Storage evidence reports source, canonical typed units, links,
  lexical, vector, graph, receipts and caches separately; full source text is
  stored once; and a repeated idempotent ingestion produces no net canonical or
  derived growth. Configured quotas fail visibly without corrupting admitted
  memory.
- **SC-015:** CLI, dashboard, MCP and at least two supported agent adapters
  expose identical profile identity, selected memory IDs, sufficiency state,
  source references and rollback state for the same request, while presenting a
  plain-language explanation suitable for a first-time user.
- **SC-016:** On the pinned Spec 035 LoCoMo confirmation workload, the selected
  typed profile does not regress the matched legacy profile by more than two
  absolute accuracy points, with quality, p50/p95 latency, error/refusal and
  resource evidence retained under the same claim rules.
- **SC-017:** Frozen formation fixtures and a rebuild of the retained
  development checkpoints produce zero unintended cross-episode, intra-episode
  or truncated-key supersessions; every repeated observation retains occurrence
  provenance; and structured snapshots containing unrelated negation preserve
  all grounded positive and negative fields. Mechanically, every supersession
  link MUST cite a compatible durable-fact identity plus explicit correction or
  transition evidence.
- **SC-018:** Every source part is either represented, terminally classified
  with a reason, or named by an unfinished receipt with an exact resume
  position. Processing completion, representation coverage and retrieval
  readiness are reported independently. Interrupted/resumed formation and at
  least two independent episode-ingestion orders produce the same authorized
  historical observation set and current/superseded assignment, and no receipt
  marked complete has unprocessed positions.
- **SC-019:** On the frozen fourteen-question LongMemEval-V2 development sample,
  at least 13 questions satisfy a frozen evaluator-owned evidence annotation:
  one complete minimal evidence set for answerable cases, the required explicit
  negative/contradiction for negative cases, or no supporting set plus the
  declared unsupported-premise evidence for abstention cases. Alternative
  sufficient sets and fixed source coordinates are permitted only when frozen
  before repair tuning. Useful-evidence precision uses the fixed source
  span/event denominator; both macro and micro precision MUST be at least 80%.
  Abstention cases score precision as one minus the fraction of packed spans
  that support the rejected premise, with an empty package scoring 1.0. SC-019
  is evaluated independently at 4K, 8K and 16K total-input profiles. The frozen
  regression case is question `1defc293` and its annotated minimal evidence set
  MUST remain fully packed;
  useful-evidence precision is at least 80% at span/event level, and the
  frozen regression case does not regress. Formation availability,
  nomination, expansion, packing and reader use are reported independently.
  This development diagnostic cannot support a customer-facing quality claim;
  a checked manifest MUST prove all fourteen IDs are disjoint from SC-003
  confirmation IDs.
- **SC-020:** Frozen 4K, 8K and 16K total-reader-token profiles count text and
  media. The selected profile is the smallest profile meeting SC-019, never
  exceeds its declared limit, and emits no context that omits a represented
  prerequisite, condition, ordered step or contradiction required for its
  sufficiency decision.
- **SC-021:** Each finalization-gate identity declares its probe set.
  LongMemEval completes twelve of twelve reader probes—three repetitions of
  each FR-061 reader condition—and at least three frozen judge probes with a
  usable final
  answer, no length termination, no hidden retry and complete latency/token/cost
  evidence. Failure blocks paid LongMemEval-V2 and DolphinBench development
  samples without weakening their frozen scoring or sample membership. Probe
  spend is separately preauthorized and accounted. LongMemEval reader/judge and
  DolphinBench Hermes/model/grader paths have separate gate identities and one
  cannot qualify the other. The Dolphin manifest declares three repetitions of
  each applicable Hermes/model and grader condition and records a reason for any
  inapplicable condition.

### Research and leaderboard targets

- **SC-004:** On complete DolphinBench with a matched Hermes/model baseline,
  AtMem improves absolute task accuracy by at least 5 percentage points
  (30/600 tasks), does not reduce any persona by more than 2 points, keeps total
  evaluated cost at or below 1.5 times baseline, and adds no more than 20%
  median task latency. This is research validation, not a stable-release
  blocker.
- **SC-009:** LongMemEval-V2 leadership target: at least 75% Small accuracy and
  70% Medium accuracy with positive LAFS gain over the published fixed
  reference frontier.
- **SC-010:** DolphinBench leadership target under the same Hermes/model family:
  exceed 424/600 while costing less than USD 96.21 and achieving median task
  latency below 37.7 seconds, or establish a new accuracy-cost/latency Pareto
  point under the benchmark's published method.
- **SC-011:** Ablation evidence attributes improvement to general product
  mechanisms rather than benchmark-specific tuning; every promoted component
  either improves a predeclared quality/system metric or enforces a required
  constitutional boundary.

Research targets guide the paper and leaderboard submission. Missing SC-004 or
SC-009 through SC-011 does not by itself fail 2.3.8 if SC-001 through SC-003,
SC-005 through SC-008 and SC-012 through SC-021 pass, but no corresponding
validation or leadership claim may be made.

## Edge cases

- The exact answer exists only in a screenshot or other non-text evidence.
- A procedure is distributed across several episodes and includes a conditional
  branch or failed attempt.
- The same label appears in different applications, entities or scopes.
- A current rule conflicts with an older rule, while the query asks about the
  historical state.
- A message describes another person's preference rather than the subject's.
- Negation, absence and invalid-premise evidence are semantically close to an
  affirmative statement.
- Retrieval finds the answer-bearing event but omits the field label, action or
  adjacent state needed to interpret it.
- A single source produces many duplicate derived memories and crowds out
  complementary evidence.
- Optional intelligence times out after producing a partial ranking.
- Memory changes or is revoked between nomination and delivery.
- The external benchmark volume is missing, renamed, full or disconnected
  during a run.
- Provider routing, model alias or price changes during repeated evaluation.
- A benchmark task completes correctly for the wrong reason or from model prior
  knowledge; evidence attribution must remain separate from outcome scoring.
- A source is larger than the configured formation budget or produces enough
  proposals to exceed a scope quota.
- The dashboard is opened against millions of evidence events while protected
  content remains encrypted.
- Windows rejects an atomic rename, another process holds the store lock, or a
  configured path contains spaces and non-ASCII characters.
- A rule is relevant by topic but its condition does not apply to the requested
  action.

## Non-goals

- Encoding benchmark answers, application-specific answer tables or task IDs in
  AtMem.
- Moving graders, repair logic or memory features into benchmark harnesses.
- Letting a model, graph, embedding index, planner or critic become canonical
  authority.
- Replacing full-fidelity evidence with summaries, typed memories or hashes.
- Claiming causal real-world success from retrieval or host-reported completion.
- Guaranteeing that every agent model will use sufficient context correctly.
- Shipping shared-memory membership behavior planned for later releases merely
  because benchmark personas use separate scopes.
- Making hosted extraction, Hugging Face or OpenAI a base-install dependency.

## Compatibility and release policy

This feature is additive where possible. Existing stores, legacy recall,
delegated context contracts and supported adapters remain readable and
reversible. Typed derivatives may be rebuilt from retained evidence; historical
content that was never captured cannot be invented during migration.

Published 2.3.8 prereleases remain historical artifacts. The final 2.3.8
release must not be described as retrieval-qualified until SC-001–SC-003,
SC-005–SC-008 and SC-012–SC-021 pass on the exact reviewed candidate. If they
do not pass, the final release is delayed or the retrieval profile remains
explicitly experimental in a differently scoped release; documentation may not
silently weaken the gate.
