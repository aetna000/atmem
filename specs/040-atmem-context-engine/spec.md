# Feature Specification: AtMem Context Engine

**Feature Branch**: `bench/longmemeval-v2`

**Created**: 2026-10-01

**Status**: Approved for implementation; protocol corrections incorporated

**Target release**: AtMem `2.3.8` final

**Input**: Replace AtMem's formation and retrieval core without treating the
current architecture as a constraint. Preserve AtMem as a context provider and
preserve governance. Use the strongest reproducible ideas from AgentRunbook-C,
AgentRunbook-R and Mem0, then prove the result on matched LongMemEval-V2 and
DolphinBench evaluations.

## Overview

AtMem will expose one governed context-engine contract while replacing its
current formation, indexing, retrieval-navigation and packing implementation.
The engine must retain immutable source episodes, derive high-recall
source-linked evidence views, plan explicit evidence obligations for each
query, retrieve independently from complementary views, inspect bounded source
neighbourhoods when indexes are insufficient, and emit the smallest package
that satisfies or truthfully fails those obligations.

Only two architectural commitments constrain the replacement:

1. AtMem is a host-neutral context provider. It supplies governed evidence and
   action constraints; the consuming agent/model remains responsible for the
   answer or action.
2. AtMem remains the canonical authority. Scope, provenance, admission,
   lifecycle, retention, deletion, encryption, disclosure and audit cannot be
   delegated to a model, benchmark harness, host adapter or derived index.

The current retrieval implementation remains available only as a frozen A/B
control and rollback profile until the new engine passes release gates. It does
not constrain the new internal design.

## User Scenarios & Testing

### User Story 1 — Receive answer-bearing governed context (Priority: P1)

An agent asks AtMem for context and receives exact, source-linked evidence that
covers every material part of the information need, or a typed partial,
conflicted, contradicted or budget-bounded not-found result. Comparisons contain
evidence for every side;
procedures preserve order; state questions preserve time and polarity; invalid
premises produce contradicting evidence instead of plausible invention.

**Why this priority**: AtMem has no product value as a context provider if the
right source evidence is retained but not delivered in usable form.

**Independent Test**: Run the frozen benchmark-neutral evidence corpus through
the new public context contract without a reader model. Compare selected source
ranges with evaluator-owned minimal evidence sets.

**Acceptance Scenarios**:

1. **Given** a question comparing two forms, **when** context is prepared,
   **then** at least one exact supporting source range for each form is packed
   before optional background evidence.
2. **Given** a question whose premise is false, **when** the complete relevant
   source surface contradicts the premise, **then** the package is marked
   `contradicted` and contains the positive contradicting evidence.
3. **Given** a procedure or state transition, **when** context is prepared,
   **then** ordered before/action/after or ordered step evidence is preserved.
4. **Given** no adequate evidence, **when** sufficiency is evaluated, **then**
   AtMem withholds a confident package and reports the missing obligations and
   exact search budget. `not_found_within_budget` is never represented as proof
   that the fact does not exist.

---

### User Story 2 — Learn from complete source episodes without losing facts (Priority: P1)

An agent or host submits an ordered episode once. AtMem preserves the immutable
source and derives raw-state slices, transitions, facts/entities, procedures,
rules, failures/gotchas and premise constraints without silently discarding
unrepresented regions. Model-assisted extraction may improve recall but cannot
admit memory or replace the source.

**Why this priority**: Retrieval cannot recover evidence that formation never
represented or retained.

**Independent Test**: Form the frozen reference-parity corpus and verify exact
source coverage, typed-view coverage, loss receipts, idempotency, storage
amplification and reconstruction with optional intelligence available and
unavailable.

**Acceptance Scenarios**:

1. **Given** a source episode containing an exact fact, transition, procedure,
   gotcha and negative observation, **when** formation completes, **then** every
   evaluator-owned evidence range is retained and reachable through at least one
   appropriate view.
2. **Given** malformed or incomplete model extraction, **when** AtMem validates
   it, **then** unsupported proposals are rejected and a loss receipt identifies
   the uncovered source rather than claiming complete formation.
3. **Given** the same source is replayed, **when** formation runs again, **then**
   canonical identities and views are idempotent.

---

### User Story 3 — Navigate evidence when fixed top-k retrieval is insufficient (Priority: P1)

For difficult questions, the engine can triage trajectory summaries, search
independent evidence views, inspect exact bounded source spans, follow verified
links and stop once the declared obligations are satisfied. Navigation is
budgeted, scope-authorized, auditable and cannot submit unsupported prose as
evidence.

**Why this priority**: AgentRunbook-C demonstrates that query-time source
navigation can recover exact evidence that static similarity ranking misses.

**Independent Test**: Use frozen trajectories where the answer-bearing state is
not in the first lexical/semantic results; verify bounded navigation reaches the
minimal evidence set without reading the whole corpus.

**Acceptance Scenarios**:

1. **Given** an indexed shortlist with incomplete evidence, **when** navigation
   is enabled, **then** only authorized summaries/spans are inspected and every
   submitted claim is revalidated against canonical source bytes.
2. **Given** operation, byte or time limits are exhausted, **when** obligations
   remain open, **then** the engine returns `partial` or
   `not_found_within_budget` with a complete budget receipt.
3. **Given** optional navigation intelligence is unavailable, **when** recall
   runs, **then** deterministic multi-view retrieval remains usable and safe.

---

### User Story 4 — Operate and compare retrieval profiles (Priority: P2)

An operator can run legacy and candidate engines in shadow, compare evidence
coverage, answer/action quality, latency, storage and cost, activate the new
engine explicitly, and roll back without losing canonical source or governance
state. CLI, MCP, dashboard and supported adapters expose the same profile and
decision contract.

**Independent Test**: Install a built artifact on macOS, Linux and Windows,
exercise context through CLI, MCP, Hermes and OpenClaw, compare shadow results,
activate, restart and restore the previous profile.

**Acceptance Scenarios**:

1. **Given** a legacy installation, **when** the candidate engine is enabled in
   shadow, **then** it cannot influence the agent and its comparative metrics are
   clearly labelled.
2. **Given** successful qualification, **when** the operator activates the new
   profile, **then** all product surfaces report the same engine identity,
   sufficiency and source IDs.
3. **Given** rollback, **when** the previous profile is restored, **then** source,
   lifecycle and audit state remain intact and candidate derived views may be
   rebuilt or deleted independently.

---

### User Story 5 — Prove benchmark leadership honestly (Priority: P1)

Maintainers run AtMem, Mem0 and AgentRunbook on frozen matched development sets,
freeze the selected AtMem configuration, and then evaluate untouched
confirmation/full sets. Results include failures, uncertainty, latency, tokens,
cost, resource use and stage attribution. A release or public claim is blocked
when evidence is partial or unmatched.

**Independent Test**: Validate a complete qualification package whose raw
results reproduce every aggregate and whose comparator identities, prompts,
models, budgets and dataset hashes match the frozen protocol.

**Acceptance Scenarios**:

1. **Given** the nested 23-question LongMemEval five-percent development slice,
   **when** a candidate
   is tuned, **then** AtMem, Mem0 OSS and AgentRunbook-R/C use identical eligible
   questions, source data, reader/judge configuration and budgets, with
   unavoidable differences disclosed.
2. **Given** the nested 30-task Dolphin five-percent development slice, **when** AtMem is compared
   with Mem0, **then** the Hermes/model/tools/grader configuration is matched and
   all failed tasks stay in the denominator.
3. **Given** a selected profile, **when** confirmation begins, **then** no
   confirmation answer, grader output or task state is available to formation,
   retrieval, prompts or tuning.
4. **Given** either five-percent development profile, **when** its runner is
   compared with the corresponding full benchmark runner, **then** the only
   permitted reduction is the number of selected question/task IDs. Formation,
   retrieval, modalities, reader/agent, tools, prompts, token and operation
   budgets, retries, judge/grader, requirement attribution, telemetry, failure
   retention and report schema MUST remain production-equivalent.

---

### User Story 6 — Refuse tampered or replayed memory before use (Priority: P1)

An operator can verify that storage-level edits cannot silently become agent
context. AtMem binds every served record, its ordering, owner/scope metadata and
lifecycle state to an authenticated integrity commitment. An optional monotonic
checkpoint held outside the attacker-controlled store additionally detects
whole-store rollback. Integrity failure is a typed, auditable, fail-closed read
outcome and never a successful empty recall.

**Independent Test**: Run the pinned AGMI AtMem adapters and all nine at-rest
attacks against an installed candidate in both `audit-chain` and
`audit-chain+external-checkpoint` modes, retaining the landed-edit control,
read-path result, explicit verification result and exact detection point.

**Acceptance Scenarios**:

1. **Given** content, deletion, insertion, reordering, cross-context,
   rollback-replay or metadata tampering within the live store, **when** the
   affected memory would be read, **then** AtMem detects the mismatch before
   emitting context and records a stable integrity reason.
2. **Given** a whole-store snapshot rollback and an intact external checkpoint
   outside the attacker's writable directory, **when** the store opens or is
   read, **then** AtMem detects the stale generation before serving memory.
3. **Given** chain-only mode and an attacker who can atomically roll back every
   byte of the store, **when** no trusted state exists outside that store,
   **then** AtMem labels snapshot freshness `unanchored` rather than claiming
   rollback detection. This cryptographic limit is reported separately from
   the externally anchored result.
4. **Given** an integrity mismatch, **when** an agent, CLI, MCP or dashboard
   requests the memory, **then** every surface exposes the same fail-closed
   status and repair guidance without returning the altered content.

### Edge Cases

- A source may be fully retained but incompletely represented; formation and
  retrieval coverage must be reported separately.
- A question may need multiple entities, times, states, procedure steps, media
  and negative evidence; no single high-score candidate may erase an obligation.
- Later corrections may supersede current facts while historical questions
  still require earlier evidence.
- Empty search, malformed model output, model timeout, unavailable embeddings,
  stale indexes and navigation exhaustion must remain safe typed outcomes.
- Optional intelligence may nominate queries or candidates but cannot see
  unauthorized content, admit memory, or make sufficiency true without source.
- Deleted, revoked, expired, quarantined, excluded or cross-scope evidence must
  not affect counts, ranking, navigation, packing or telemetry.
- Context and media together must respect one total-input budget.
- Repeated benchmark runs must not select the best random outcome or silently
  drop failed provider calls.
- A small development sample must not use shortened context, text-only
  substitutes, weaker instrumentation, omitted comparators, relaxed validation,
  or cheaper execution semantics unless that difference is also part of the
  frozen full-run protocol and is disclosed as a separate operating point.
- A store-local hash chain cannot prove freshness after a complete atomic
  rollback of itself; only a protected monotonic value outside the attacker's
  rollback domain can close that case.
- Integrity validation must not turn deletion, empty recall, database errors or
  unsupported historical rows into apparent successful tamper detection.

## Requirements

### Functional Requirements

- **FR-001 — Public boundary**: The replacement MUST remain a host-neutral
  context provider and MUST return a versioned evidence package containing
  status, bounded context, selected canonical IDs, exact provenance, excluded
  evidence reasons, budgets and optional action constraints.
- **FR-002 — Governance shell**: AtMem MUST authorize before any intelligence
  component receives candidate content and MUST canonically revalidate every
  selected source/record immediately before persistence and delivery.
- **FR-003 — Replaceable core**: Formation, query planning, indexing, ranking,
  navigation, sufficiency and packing MUST be replaceable behind FR-001. The new
  engine MUST NOT import or call the legacy ranker except through a benchmark or
  shadow comparison adapter.
- **FR-004 — Immutable source**: Each ordered source episode and supported media
  MUST be retained once with stable source/range identities. Derived views MUST
  reference source rather than duplicate full source bodies.
- **FR-005 — Multi-view formation**: Formation MUST create independently
  queryable raw-state, transition, fact/entity, procedure, rule, failure/gotcha
  and premise/negative-evidence views where grounded by source.
- **FR-006 — Coverage and loss**: Formation MUST emit source-region coverage,
  proposal/admission/rejection counts and explicit loss/unsupported receipts.
  Representation completeness MUST NOT be inferred from processing completion.
  An authorized retained source range that is withheld from retrieval MAY be
  used only to decide that a query-derived obligation has lost coverage. Its
  value MUST NOT become a candidate, context byte, or missing-obligation label;
  the externally visible label MUST be derived from the request itself.
- **FR-007 — Reconciliation**: Add, update, correction, supersession, conflict,
  duplicate occurrence and negative observations MUST preserve source lineage,
  current/historical state and idempotent replay.
- **FR-008 — Optional formation intelligence**: Model-assisted extraction MAY
  improve recall using a pinned, explicit local or approved-egress profile, but
  deterministic fallback MUST remain usable and the model MUST have no mutation
  or authority role.
- **FR-009 — Information-need plan**: Each query MUST produce explicit evidence
  obligations covering requested entities, relations/actions, values, polarity,
  time, applicability, procedure order, comparison sides, conflicts and premise
  validity as applicable.
- **FR-010 — Independent pools**: Raw states, transitions, procedures,
  failures/gotchas, facts/entities, rules and negative/premise evidence MUST have
  independent nomination budgets so one pool cannot consume all capacity.
- **FR-011 — Hybrid nomination**: Exact, lexical, semantic, temporal, entity/link
  and optional learned signals MUST remain independently attributable. Raw scores
  from unlike scales MUST NOT be directly added or maximized.
- **FR-012 — Obligation-first selection**: Selection MUST reserve evidence for
  every required obligation before adding redundant support. Comparison and
  multi-part questions MUST retain distinct evidence heads where required.
- **FR-013 — Evidence navigation**: A bounded navigator MUST support manifest
  triage, search, exact source inspection, adjacency following and submission.
  Submitted ranges MUST be canonically revalidated and fit one operation/byte/
  time budget.
- **FR-014 — Sufficiency**: The engine MUST distinguish `sufficient`, `partial`,
  `conflicted`, `contradicted`, `stale`, `not_found_within_budget` and
  `withheld_by_policy` using source-backed obligation coverage. `contradicted`
  requires positive contradicting evidence; `not_found_within_budget` records
  searched views and limits and MUST NOT claim absence.
  Similarity, model confidence and common product practice cannot establish
  sufficiency.
- **FR-015 — Context packing**: Packing MUST maximize obligation coverage under
  one total-input budget, preserve ordering and polarity, include compact source
  references, and explain material evidence excluded by budget or policy.
- **FR-016 — Action constraints**: For agent-action questions, context MAY expose
  source-backed governing condition, required/prohibited action, target and
  validity. It MUST remain evidence for the agent, not an AtMem-executed action.
- **FR-017 — Performance**: Product retrieval MUST use persistent scoped indexes,
  bounded/keyset reads and generation-aware caches. It MUST NOT scan the full
  canonical store, build a corpus-wide temporary index per query, or load an
  entire trajectory corpus into memory.
- **FR-018 — Storage**: The implementation MUST measure canonical, evidence,
  link, lexical, vector, cache and benchmark storage separately; derived storage
  MUST be rebuildable and MUST NOT duplicate immutable source bodies.
- **FR-019 — Lifecycle**: Deletion, exclusion, expiry, correction, revocation and
  scope changes MUST invalidate every derived view/cache and pass verified
  deletion without requiring the original agent or model.
- **FR-020 — Profiles and rollback**: `legacy-control`, `context-fast`, and
  `context-navigate` profiles MUST have explicit identities, limits, dependencies
  and fallback behavior. Candidate profiles begin in shadow and activate only
  after qualification; rollback preserves canonical state.
- **FR-021 — Product parity**: CLI, MCP, dashboard, OpenClaw, Hermes, Pydantic AI
  and LangChain/LangGraph MUST consume the same FR-001 contract and show the same
  active/shadow profile, status, sufficiency, sources and actionable failures.
- **FR-022 — Agent and memory tenancy**: Every operation MUST bind subject,
  workspace, agent, session, run and turn where available. Private agent memory
  is default; explicitly shared memory uses existing authority, membership and
  provenance rules without merging agent histories.
- **FR-023 — Observability**: AtMem MUST record content-free stage duration,
  counts, limits, cache state, model identity/usage and failures. AtFlows MAY
  render these by agent/profile/stage but cannot receive protected memory content
  or become a runtime dependency.
- **FR-024 — Benchmark isolation**: Official benchmark adapters MUST be inert
  consumers of public product APIs. Product modules MUST NOT import benchmark
  questions, answers, annotations, graders or reference implementations.
- **FR-025 — Reference laboratory**: Pinned Apache-2.0 AgentRunbook-C/C V2,
  AgentRunbook-R and Mem0 OSS adapters MUST run outside product runtime through a
  neutral evidence/result contract. Hosted Mem0 results MUST be labelled
  separately from OSS matched runs.
- **FR-026 — Evaluation ladder**: Every iteration MUST pass structural tests,
  reference cassette replay, reader-free minimal-evidence evaluation and a
  bounded live micro differential before a paid end-to-end run.
- **FR-027 — Matched comparisons**: AtMem and locally runnable comparators MUST
  use the same frozen inputs, model family/revision, prompts where contracts
  permit, context/output budgets, hardware class, retries, judge and failure
  denominator. Unmatched official numbers are context only.
- **FR-028 — Leakage control**: Development and confirmation IDs MUST be frozen
  before tuning. Gold answers and minimal evidence annotations are evaluator-only
  and inaccessible to product/adapters; confirmation is run once per frozen
  candidate except documented infrastructure retries.
- **FR-029 — Complete evidence**: Reports MUST retain per-case outputs, errors,
  stage attribution, p50/p95 latency, throughput, tokens, resource use, storage,
  cost, configuration hashes and uncertainty. Partial runs cannot support release
  or leadership claims.
- **FR-030 — Installed qualification**: Release evidence MUST use the exact built
  candidate on macOS, Linux and Windows-compatible paths, cover fresh install and
  upgrade, and verify CLI/MCP/dashboard/adapters without benchmark packages.
- **FR-031 — Release alignment**: Spec 040 supersedes retrieval-engine design in
  Specs 008, 031, 035 and 038 for AtMem 2.3.8. Their governance, benchmark
  provenance and completed historical evidence remain valid. Specs 003, 004,
  006, 015, 018, 019, 020, 028, 030 and 037 retain their authority, evidence,
  encryption, portability and adapter ownership.
- **FR-032 — Claim gate**: No release note, dashboard or website may claim that
  AtMem beats a comparator until the complete matched qualification satisfies
  the relevant success criterion. Extrapolated, development, peak or unmatched
  results MUST be labelled accordingly.
- **FR-033 — Default and rollback**: Fresh installations MAY activate
  `context-fast` only after its local qualification passes. Upgrades MUST retain
  `legacy-control` as active and run V3 in sampled shadow until explicit
  activation. Rollback MUST rebuild the legacy derived state from canonical
  source and verify lifecycle freshness before serving it; dual-maintaining
  legacy indexes is forbidden by default.
- **FR-034 — Compatibility fail-closed**: Context Package V3 statuses other
  than `sufficient` MUST serialize to Context Package V2 as withheld/abstain
  with a stable reason code. Compatibility MUST never turn partial, conflicted,
  contradicted, stale, budget-exhausted or policy-withheld evidence into an
  answerable V2 package.
- **FR-035 — Benchmark symmetry**: Every compared arm MUST declare formation,
  embedding, planner/navigator, reader and judge identities; prompts; top-k and
  context limits; maximum model calls/tokens/operations per query; retries;
  temperature/seeds; hardware; and cost. Each arm receives the same-size frozen
  development sweep, the same repetitions, and no best-of selection. Reports
  include accuracy at matched cost as well as each system's recommended profile.
- **FR-036 — Benchmark privacy**: Approved benchmark egress MUST disclose the
  exact fields/providers, emit a content-free audit record, honor dataset
  licenses, and keep any protected model cassette encrypted with the AtMem
  household key. A product or comparator adapter cannot silently export user or
  benchmark source.
- **FR-037 — Five-percent development profiles**: The paid development runners
  MUST use immutable, checksum-bound, answer-blind samples containing exactly
  23 of 451 LongMemEval-V2 questions and exactly 30 of 600 DolphinBench tasks.
  Each profile MUST be nested over the historical 14/18 calibration slice,
  preserve the existing development/confirmation boundary, and rederive its
  membership from the pinned salt and public identifiers before execution.
- **FR-037A — Staged LongMem stop/go gate**: Before spending the complete
  23-question LongMemEval-V2 development budget, the runner MUST execute the
  immutable six-question stage declared by
  `longmemeval-v2-stage-gate-v1.json`. The stage MUST preserve every production
  setting and matched arm required by FR-035 and FR-038; only the public case
  count may differ. It is a diagnostic, not a five-percent result. AtMem MUST
  score strictly above AgentRunbook-R on that stage before the remaining 17
  questions may run. A tie or loss MUST stop paid execution, retain all
  outcomes, attribute the earliest failing pipeline stage, and return to an
  implementation fix followed by an identical-stage rerun. Cases, order,
  reader, judge or budgets MUST NOT be changed in response to an outcome.
- **FR-038 — Sample-size-only reduction**: The 23-question and 30-task
  development runs MUST execute the same production benchmark pipeline and
  quality gates intended for the corresponding full run. The sample selector
  MAY reduce only the set of public case identifiers. It MUST NOT reduce source
  history, screenshots or other modalities for a selected case; formation or
  retrieval work; matched comparator arms; model, prompt, tool, judge or grader
  quality; context/output/operation budgets; retry and timeout policy;
  requirement-level attribution; telemetry; raw evidence; error classification;
  reproducibility metadata; or reporting fields. Any unavoidable difference
  MUST fail the equivalence gate or be declared as a separately named,
  non-comparable operating point.
- **FR-039 — Complete failure attribution**: Every one of the 23 LongMemEval
  questions and 30 DolphinBench tasks MUST receive evaluator-only requirement
  annotations and a terminal stage classification. LongMemEval MUST distinguish
  incomplete source/formation/retrieval/packing from reader non-use by comparing
  product context with verified complete evidence under the same reader
  configuration. Dolphin removal tests count a safety block only when a
  pre-action receipt names the removed requirement and proves the model was not
  invoked and no tool call occurred; timeout, provider error, parse error,
  generic abstention and silent no-call are failures, never valid blocks.
- **FR-040 — Evaluator-only requirement manifests**: Before any scored run, an
  immutable evaluator-owned manifest MUST enumerate every material requirement
  for all 23 LongMemEval questions and 30 DolphinBench tasks. Requirements MUST
  use one or more of these classes: exact fact/value, entity/relation,
  time/current state, state transition, procedure step/order, applicability
  condition, comparison side, polarity/negative premise, conflict/correction,
  action target, required action, and prohibited action. Each requirement MUST
  have a stable identifier and source reference. Gold answers, source labels,
  load-bearing-fact identifiers and requirement annotations MUST remain outside
  AtMem runtime inputs and product-visible retrieval state.
- **FR-041 — Requirement-stage ledger**: Evaluation MUST record each requirement
  through `source_exists`, `represented`, `nominated`, `expanded`, `packed`,
  `delivered`, `used_by_reader`, and `reflected_in_answer_or_action`. Every stage
  MUST be `passed`, `failed`, `not_reached`, or `not_applicable` with evidence or
  a reason; absent observations MUST NOT become zero, false success, or inferred
  passage. Each case MUST end in exactly one of source/dataset, formation,
  retrieval, packing, reading, parsing, provider/system, action-attempt,
  action-success, or action-failure outcomes, using the earliest evidenced
  failure without hiding later system errors. A frozen evaluator-only review
  protocol MUST define permitted evidence and the decision rule for every
  stage. `used_by_reader` MUST be labelled as an observable response/controlled-
  input proxy and MUST NOT claim access to hidden model cognition.
- **FR-042 — Controlled reader attribution**: Every LongMemEval development
  question MUST run the same pinned reader and prompt against three inputs:
  exactly the product context, evaluator-provided verified complete minimal
  evidence, and no memory. Classification MUST follow the predeclared decision
  table: absent source is a source/dataset failure; unrepresented source is a
  formation failure; represented but undelivered evidence is retrieval/packing;
  incomplete product context with successful verified evidence is a memory
  pipeline failure; complete product context with successful verified evidence
  but a wrong product answer is reader-use/noise; a wrong verified-evidence
  answer is reader capability/prompt; and timeout, truncation, malformed output,
  parse error or provider error is a system failure.
- **FR-043 — Pre-action Dolphin gating and controls**: For tasks with remembered
  prerequisites, the host adapter MUST evaluate AtMem's named obligation
  sufficiency before invoking Hermes or any model. A missing obligation MUST
  produce `blocked_missing_requirement`, name the exact missing requirement,
  record `model_invoked=false` and zero tool calls, and prevent action. A removal
  test succeeds only on that receipt; timeout, provider error, parse error,
  generic abstention and silent no-call fail. Restoring the evidence MUST open
  the same gate, invoke Hermes and permit the expected tool call, so an
  always-blocking implementation cannot pass.
- **FR-044 — Historical diagnostic reanalysis**: The frozen pre-change 12-case
  reader-free diagnostic MUST be reanalysed by requirement class, reporting
  totals and the earliest failed stage from its retained per-case evidence. It
  MUST remain labelled a small diagnostic and MUST NOT be combined with, or
  presented as evidence for, the 23/30 development benchmark result.
- **FR-045 — Authorized history-import review**: A bulk history import MAY
  settle source-grounded pending proposals only when an operator explicitly
  enables a scope-bound import authority. Each decision MUST use the public
  review service for pending semantic/action proposals, name the principal and
  source, and leave one content-free import-authorization receipt per source
  episode. Exact source-range observations MAY be admitted directly under that
  frozen authority to avoid per-span review duplication. The authority MUST
  NOT be enabled by default, MUST NOT admit a
  rejected or unsupported proposal, and MUST NOT read evaluator manifests,
  questions, expected answers, task labels or graders. Benchmark setup MUST
  freeze this choice before scoring and report all approved, rejected and still
  pending counts.
- **FR-046 — Minimal source-linked observations**: Lossless formation MUST keep
  independently addressable exact source spans at sentence or bounded-clause
  granularity in addition to semantic typed views. A fallback observation MUST
  use a structural schema identity rather than pretending that schema labels
  occur in the source, while its value and polarity remain exactly grounded.
  Typed validation MUST NOT reject reserved structural labels solely because
  those labels are absent from prose. Each unit MUST retain exact offsets and a
  stable source identity; a unit spanning multiple evaluator requirements
  cannot support a one-requirement removal claim.
- **FR-047 — Removal-unit integrity**: Every Dolphin removal control MUST map the
  removed evaluator requirement to the smallest represented source-linked unit
  set that contains no other material requirement for that task. A requirement
  spanning adjacent clauses MAY use multiple exact units only when every unit
  is exclusive to that requirement and the receipt names the complete set. If
  atomization cannot isolate it, the control MUST fail as
  `non_atomic_removal_target`; deleting a whole episode and treating unrelated
  missing obligations as the intended block is forbidden. Positive control
  MUST restore the same unit identities. Where a task has several removable
  requirements, the control target MUST be frozen before product execution by
  the deterministic `query_aligned_requirement_v1` rule: greatest normalized
  lexical coverage by the official task request, then greatest overlap count,
  then stable requirement ID. Product output and gate outcome MUST NOT
  participate in target selection.
- **FR-048 — Pinned AGMI qualification**: The benchmark program MUST pin the
  official `tech4biz-yasha/agmi` commit, package version, AtMem adapter source,
  attack versions and tests for both `atmem-chain` and
  `atmem-chain+checkpoint`. It MUST run an installed AtMem artifact on macOS,
  Linux and Windows-compatible paths, preserve all T1–T9 landed-edit controls,
  and report accepted, reported and rejected-on-read separately. A locally
  adapted version-pin test is development evidence only until upstream
  re-measures the released version.
- **FR-049 — Record-to-chain verification**: Integrity verification MUST compare
  canonical records against their authenticated creation/update/lifecycle
  commitments, including content, stable record identity, subject/scope,
  ordering and security-relevant metadata. Verification of the audit chain's
  internal links alone is insufficient. A mismatch MUST be detected before the
  affected record can enter a context package, and the receipt MUST name the
  failed invariant without disclosing protected content.
- **FR-050 — External rollback checkpoint**: The anchored profile MUST maintain
  a crash-safe monotonic sequence and authenticated root outside the
  attacker-controlled store directory. Store commit and checkpoint advancement
  MUST have a recoverable two-phase protocol; missing, stale, forged,
  inaccessible or partially advanced checkpoints MUST fail closed. The
  checkpoint file and key MUST have explicit placement, permission, backup,
  migration, rotation and restore contracts. Chain-only mode MUST expose its
  inability to detect atomic whole-store rollback as `unanchored`, not silently
  inherit the anchored claim.
- **FR-051 — Integrity product contract**: CLI, MCP, dashboard and supported
  adapters MUST expose the same `verified`, `tampered`, `unanchored`,
  `checkpoint_unavailable` and `legacy_uncommitted` states. Upgrade MUST
  inventory historical records, build and verify commitments before activation,
  preserve a reversible backup, and never silently serve an uncommitted legacy
  row under a verified label. Integrity checks MUST be indexed/incremental and
  meet SC-007 without whole-store verification on every query.
- **FR-052 — Beta-bound benchmark identity**: Development-checkout scores MUST
  remain diagnostic. Any benchmark result presented as a reproducible release
  result MUST be rerun from the exact installed beta artifact after the
  candidate passes its no-cost, matched-quality, integrity and installed-path
  gates. The result MUST bind the beta version, commit, artifact SHA-256,
  dataset manifests and evaluator configuration; a later source-tree result
  MUST NOT be attributed to that beta.

### Key Entities

- **Source Episode**: Immutable ordered text/tool/media evidence with authority,
  actor, time, lifecycle and stable source ranges.
- **Evidence View**: Rebuildable source-linked raw state, transition, fact/entity,
  procedure, rule, gotcha or premise projection.
- **Evidence Obligation**: A query-time requirement for entity, relation, value,
  polarity, time, condition, step, comparison side or contradiction.
- **Retrieval Manifest**: Authorized summaries and view counts used for bounded
  query triage without exposing the entire source corpus.
- **Navigation Receipt**: Operations, bytes, elapsed time, inspected/submitted
  ranges and exhaustion reasons.
- **Sufficiency Decision**: Required/covered/missing obligations, evidence,
  contradictions, lifecycle state and status.
- **Context Package**: The governed reader/agent-facing evidence product.
- **Engine Profile**: Versioned formation/retrieval/navigation/packing identity
  with dependencies, budgets and activation mode.
- **Qualification Package**: Immutable matched benchmark evidence and claims.

## Success Criteria

### Measurable Outcomes

- **SC-001 — Reader-free evidence**: On the sealed holdout half of a frozen,
  benchmark-neutral reference corpus, `context-fast` answer-bearing minimal-
  evidence recall is at least 0.90 and typed-status accuracy is at least 0.95;
  the claimed `context-navigate` profile reaches at least 0.95 recall,
  comparison-side coverage 1.00 and contradiction detection at least 0.95.
  Unauthorized exposure is zero for both. The corpus has a separately frozen
  development half and a pinned, system-neutral output-to-source-span normalizer.
  This is a paid-run go/no-go gate, never leaderboard evidence.
- **SC-002 — Formation coverage**: Every evaluator-owned answer-bearing source
  range is retained; at least 0.98 is reachable through an appropriate derived
  view; all remaining gaps have explicit loss receipts.
- **SC-003 — LongMemEval development**: On the frozen 23-question five-percent slice, the
  selected AtMem profile exceeds the strongest locally matched Mem0 OSS or
  AgentRunbook-R/C arm by at least 10% relative accuracy, with all 23 questions
  completed and no lower evidence-set recall.
- **SC-004 — LongMemEval claim gate**: On precommitted confirmation IDs that are
  disjoint from every development or answer-inspected ID, AtMem exceeds the
  strongest locally matched comparator by at least 10% relative accuracy and
  the paired 95% bootstrap interval for the absolute difference excludes zero.
  The complete official Small set is additionally reported as non-held-out.
  Inspecting any confirmation answer resets its confirmation status. Failure
  blocks a leadership claim, not an otherwise qualified 2.3.8 release.
- **SC-005 — Dolphin development**: On the frozen 30-task five-percent slice
  with matched Hermes/model/tools/grader, AtMem passes at least 27/30 tasks and
  exceeds the matched Mem0 arm by at least three tasks.
- **SC-006 — Dolphin claim gate**: A persona-formation checkpoint is frozen and
  hashed before task scoring. On all 600 official tasks, AtMem exceeds the frozen
  leaderboard leader and the locally matched Mem0 arm by at least one task, with
  paired uncertainty, all failures retained, and cost no more than 1.5 times the
  matched baseline. The research run is not required to preserve a usable local
  package, but is required for a public Dolphin leadership claim. Reports show
  both 600/600 and the 582 non-development tasks and label the result
  `tuned-on-corpus, held-out tasks` rather than corpus-held-out.
- **SC-007 — Performance**: On the frozen CPU-only 50k-unit workload,
  `context-fast` warm p50 is at most 500ms, p95 at most 2s and RSS at most
  512MiB. On 100k units its p95 is at most 3s. `context-navigate` has an absolute
  p95 ceiling of 30s and model cost ceiling of USD 0.05/query. No query performs
  a whole-corpus scan. Sampled shadow adds at most 20% p95 latency, CPU time and
  storage and at most doubles formation-model cost. Matched benchmark reports
  retain cost-normalized accuracy; accuracy never waives an absolute ceiling.
- **SC-008 — Storage**: All derived data including FTS and vector indexes is no
  more than 1.5 times immutable retained source bytes. FTS uses contentless or
  external-content tables; vectors use the same household encryption boundary.
  Category growth is reported, a rebuild reproduces identities without source
  duplication, and stolen-store tests disclose no plaintext semantic content.
- **SC-009 — Governance**: Authority, cross-scope noninterference, deletion,
  revocation, encrypted-at-rest, dead-agent reconstruction and audit suites have
  zero critical failures across all profiles.
- **SC-010 — Product journey**: The exact installed candidate passes fresh,
  upgrade, shadow, activate, restart, query, inspect and rollback journeys through
  CLI/MCP/dashboard plus OpenClaw and Hermes on supported OS profiles.
- **SC-011 — Resilience**: With optional models, embeddings and AtFlows disabled,
  deterministic context remains correct on the frozen safety corpus and every
  degradation is visible without widening access.
- **SC-012 — Reproducibility**: A clean machine can reproduce every aggregate
  from retained manifests/raw results and verify source, code, package, model,
  prompt, judge and comparator hashes.
- **SC-013 — Release quality floor**: On the precommitted LongMemEval
  confirmation IDs the selected shipped profile reaches at least 60% accuracy,
  improves by at least five percentage points over official
  `rag_query_to_slice_notes`, and is non-inferior to `legacy-control`; the pinned
  LoCoMo confirmation score regresses by no more than two points. SC-001–SC-002
  and SC-007–SC-012 plus SC-014–SC-019 MUST also pass. A failure blocks stable
  2.3.8 promotion but does not block unrelated Hermes/MCP/AtFlows work.
- **SC-014 — Formation invariants**: Rebuilding retained source reproduces
  stable occurrence/durable-fact identities, corrections and supersession; every
  source part is represented or terminally classified with no silent omission.
- **SC-015 — Reader/context profiles**: Frozen 4K, 8K and 16K total-reader-token
  profiles count text, media and protocol overhead and pass truncation/finalizer
  probes for every reader, judge and agent route.
- **SC-016 — Reader-free regression**: At least 21/23 LongMem development cases
  have answer-bearing evidence reachable before reader invocation, including the
  pinned `1defc293` regression case; result status distinguishes evidence
  availability from reader use.
- **SC-017 — Ablation evidence**: Predeclared ablations separately remove typed
  formation, routing, independent pools, neighbourhood expansion, navigation,
  sufficiency and complementary packing, and preserve negative results.
- **SC-018 — Release versus claim decision**: Stable 2.3.8 is publishable when
  SC-013 and its referenced safety/product gates pass. SC-003–SC-004 are the
  LongMem leadership target; SC-005–SC-006 are the Dolphin readiness/leadership
  targets. A qualified release that misses a claim gate ships V3 only as
  experimental/shadow and makes no benchmark-leading claim.
- **SC-019 — Five-percent fidelity and attribution**: A machine-readable
  equivalence receipt proves that selected-case count is the only execution
  difference between each five-percent profile and its frozen full-run
  protocol. All 23 LongMemEval and all 30 DolphinBench cases have complete
  per-requirement stage records and exactly one terminal outcome; aggregates
  reconcile to 23 and 30 with no unknown encoded as success. Every Dolphin
  removal-test success names the removed requirement and records
  `model_invoked=false` and zero tool calls. This gate permits a development
  claim only and cannot substitute for the full 451/600 claim runs.
- **SC-020 — Attribution and action-gate integrity**: All evaluator manifest
  hashes validate; all 53 cases reconcile to complete requirement-stage ledgers
  and one terminal outcome; all 23 LongMemEval cases contain product,
  verified-evidence and no-memory reader results from the same pinned reader;
  and every applicable Dolphin removal/restore pair proves both fail-closed
  blocking and a working positive path. Reports separately count retrieval,
  packing, reading, parsing, provider and action failures, and never credit an
  unknown, timeout, error or silent no-call as safety success.
- **SC-021 — Import and atomization qualification**: On the frozen 30-task
  Dolphin development sample, every removal target is either a single
  source-linked unit or an explicit failed `non_atomic_removal_target`; no
  pending proposal is silently promoted. An authorized history import records
  its principal and one authorization receipt per imported source episode plus
  ordinary review receipts for pending semantic/action proposals, consumes no
  evaluator-only data, and leaves zero unreported pending/rejected units.
- **SC-022 — AGMI integrity qualification**: On the pinned official AGMI T1–T9
  at-rest suite, the installed candidate detects T1–T8 before altered memory is
  returned in both profiles, with zero silent accepts and zero false detections
  on matching controls. With the external checkpoint intact and outside the
  attacker-controlled directory, T9 is also detected before read. Chain-only
  T9 is reported as the explicit `unanchored` technical limit and is never
  counted as protected. Results reproduce on macOS, Linux and
  Windows-compatible paths and are submitted for upstream re-measurement before
  any public claim replaces the published AtMem 2.3.7 rows.
- **SC-023 — Beta reproducibility**: The benchmark qualification index names
  one installed beta version and artifact SHA-256, and every release-associated
  LongMemEval-V2, DolphinBench and AGMI row verifies that exact identity before
  execution. Development-checkout rows are labelled diagnostic and excluded
  from beta aggregates.

## Assumptions

- AgentRunbook and Mem0 code remains available under Apache-2.0 at the pinned
  revisions already recorded in `research/reference_parity/sources.json`.
- Benchmark datasets and heavy raw artifacts remain on the `MEM` external
  volume; source code, schemas, adapters and small reports remain in the repo.
- RunPod may host the pinned Qwen reader/formation model and OpenAI may provide
  the pinned judge when the frozen protocol permits egress and cost.
- AGMI's at-rest attacker can write the database/store directory but does not
  possess AtMem integrity keys; the anchored T9 claim additionally requires the
  external checkpoint to remain outside that writable/rollback boundary.
- Benchmark success may require replacing most existing formation/retrieval
  internals; public context/governance contracts and persisted-source migration
  remain mandatory.
- Planning authorizes no release or leaderboard submission.

## Explicit Non-Goals

- Copying third-party source directly into AtMem runtime instead of reimplementing
  the underlying technique against AtMem contracts.
- Making AtMem an answering model, agent loop, tool executor or benchmark-specific
  oracle.
- Keeping legacy ranking behavior, schemas or internal modules merely for code
  compatibility when migration and rollback can preserve user data safely.
- Treating a 3% sample, peak run, extrapolation, hosted Mem0 number or published
  AgentRunbook score as a matched final comparison.
