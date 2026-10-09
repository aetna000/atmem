# Tasks: AtMem Context Engine

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/context-engine-v3.md`, and `alignment.md`

**Rule**: Tests are written first for every behavioral slice. No paid benchmark
run starts until its cheaper prerequisite gates pass. No AtMem-only paid
development run is permitted after the matched adapters are ready.

## Phase 1 — Freeze direction and baselines

- [x] [T001] Record the controlling/superseded specification matrix and 2.3.8
  release disposition in `docs/release-roadmap.md` and
  `specs/040-atmem-context-engine/alignment.md` (FR-031–FR-032).
- [x] [T002] Freeze disjoint development/sealed-holdout halves of one
  benchmark-neutral minimal-evidence corpus with source ranges for exact fact,
  correction, comparison, negative premise, transition, procedure, gotcha,
  conflict, temporal and private/shared-agent cases; pin a system-neutral
  output-to-source-span normalizer before any system run in
  `research/reference_parity/fixtures/` (FR-024–FR-028, SC-001).
- [x] [T003] Pin neutral result/cassette schemas plus AtMem, Mem0 OSS and
  AgentRunbook-R/C revisions/configuration hashes, dataset commit/license/SHA,
  model and embedding revisions, prompts, normalizer hash and encrypted-cassette
  policy in
  `research/reference_parity/contracts.py` and
  `research/reference_parity/sources.json` (FR-025–FR-029).
- [x] [T004] Implement and run the pre-change reader-free baseline for AtMem,
  Mem0 OSS and AgentRunbook-R, retaining raw outputs on `MEM` and the
  checksum-bound aggregate under `benchmarks/retrieval_quality/baselines/`;
  AgentRunbook-C/V2 remains in the model-directed cassette/live gates T034/T037
  (FR-025–FR-029).
- [x] [T005] Freeze disjoint development/confirmation IDs, reader/judge prompts,
  provider revisions, hardware, retry policy, seeds and cost ceilings in
  `benchmarks/retrieval_quality/protocols/2.3.8-context-engine.yaml`; include all
  inspected IDs in development and define per-arm formation/embedding/planner/
  navigator/reader/judge identities, top-k/context, maximum model calls/tokens/
  operations, equal-size development sweeps and symmetric repeats with no
  best-of selection (FR-027–FR-029, FR-035–FR-036).
- [x] [T005A] Generate and validate nested, answer-blind five-percent manifests
  at `benchmarks/retrieval_quality/protocols/longmemeval-v2-development-5pct-v1.json`
  and `benchmarks/retrieval_quality/protocols/dolphinbench-development-5pct-v1.json`;
  retain the historical 14/18 manifests unchanged and add contract tests in
  `tests/test_retrieval_quality_protocol.py` (FR-028, FR-037).
- [x] [T005B] Freeze full-run-equivalent effective configurations and add a
  validator that proves the 23/30 selectors change only case IDs—not source,
  modalities, methods, models, prompts, tools, budgets, retries, judge/grader,
  instrumentation, failures or report schema—in
  `atmem/benchmark/contracts.py` and `tests/test_retrieval_quality_protocol.py`
  (FR-038, SC-019).
- [x] [T005C] Freeze evaluator-only requirement manifests for all 23 LongMemEval
  questions and 30 Dolphin tasks, including requirement classes and action
  prerequisites, with hashes and product-inaccessibility tests under
  `benchmarks/retrieval_quality/protocols/` (FR-028, FR-039–FR-040, SC-019).
- [x] [T005D] Add versioned requirement-ledger, terminal-outcome and pre-action
  gate contracts plus validators that reject absent stages, unknown-as-success,
  timeout/parse/provider/silent-no-call blocks and always-blocking positive
  controls in `atmem/benchmark/attribution.py` and contract/integration tests
  (FR-041–FR-043, SC-020).
- [x] [T005E] Reanalyse the retained pre-change twelve-case raw results by
  requirement class and earliest evidenced failure, writing a checksum-bound
  small-diagnostic-only table under `benchmarks/retrieval_quality/reports/`
  without changing its frozen inputs (FR-044).
- [x] [T005F] Freeze the evaluator review procedure, add unsigned fail-closed
  23/30 review packets, checksum-bound observation validation, complete ledger
  builders and report/Project-Atlas renderers; no missing or unreviewed stage
  can be finalized or aggregated (FR-039–FR-043, SC-019–SC-020).
- [x] [T005G] Fail closed when any checkpoint, removal-control, ingestion, or
  paid runner imports AtMem from the source checkout instead of the pinned
  installed wheel.
- [x] [T005H] Bind Dolphin removal targets to frozen evaluator-only source
  provenance; canonical registry wording must not be mistaken for verbatim
  product memory, and absent represented source units remain formation failures.
- [x] [T005I] Retain the first full-history 30-task removal diagnostic as
  non-benchmark evidence: 14 valid named blocks, 10 unrepresented source
  targets (five pending review and five typed validation rejection), and six
  non-atomic/gate-mismatch outcomes. Do not tune the evaluator to hide them.
- [x] [T005J] Add exact source-linked sentence/bounded-clause observations with
  stable offsets, reserved structural schema validation and regression tests;
  require the smallest exclusive one-requirement removal unit set and emit
  `non_atomic_removal_target` instead of deleting a multi-requirement episode
  (FR-046–FR-047, SC-021).
- [x] [T005K] Add an opt-in scope-bound authorized history-import review flow
  using public review APIs, single-use authorization and audit receipts. Prove
  default imports remain fail-closed and evaluator manifests cannot enter the
  product path (FR-045, SC-009, SC-021).
- [x] [T005L] Build and install a clean candidate wheel, rebuild all three
  encrypted Dolphin persona checkpoints from full history, rerun all 30 removal
  controls, and retain formation/review/atomization counts. Paid evaluation is
  blocked until every applicable control is valid and zero unknown/system
  outcomes are credited (FR-039–FR-047, SC-019–SC-021). The `449b559` rebuild
  completed 13,539/13,539 sessions with zero model calls, but remains a failed
  gate: 18/30 controls were valid, 12/30 failed, and encrypted checkpoint
  storage was 1,027,932,160 bytes for 7,727,403 source-message bytes. The
  `8652889` compact V3 attempt rebuilt all 13,539 sessions at 245,264,384 bytes
  with zero model calls and no duplicated source bodies, but remains a failed
  gate: 25 controls exposed duplicate evidence identifiers across typed views
  and five removal targets remained non-atomic. No failed control was credited.
  Clean commit `3831928` rebuilt all 13,539 sessions into three encrypted V3
  checkpoints (311,545,856 bytes; 1.21x--1.28x logical derived/source ratio;
  zero source duplication). All 30 restored-evidence gates opened and all 30
  deterministic request-aligned removals produced a named pre-action block,
  with zero model/tool calls or system-failure credit. See
  `benchmarks/retrieval_quality/reports/dolphin-action-gate-3831928.md`.
- [x] [T005M] Fail closed when the frozen AgentRunbook-R comparator uses the
  local deterministic hash embedding route, and install an exact verifier-bound
  compatibility patch that truncates on that embedder's regex-token boundary
  without attempting an unrelated Hugging Face tokenizer download. Reject any
  other comparator source change and rerun only incomplete checkpoint arms
  (FR-039, FR-041, SC-019).
- [x] [T005N] Make resumable matched-checkpoint construction replace stale
  local embedding readiness receipts before accepting a loopback endpoint.
  Prove a prior dead port cannot be reused and preserve completed arms while
  rerunning only an incomplete comparator workspace (FR-039, SC-019).
- [x] [T005O] Stream checkpoint hashing in bounded one-megabyte blocks so
  multi-gigabyte encrypted memories can be validated and resumed without
  loading an entire database file into RAM (FR-039, SC-013, SC-019).
- [x] [T005P] Copy every completed LongMem and Dolphin five-percent checkpoint
  to `MEM`, revalidate content and logical persona receipts after transfer, and
  publish a checksum-bound readiness report that explicitly excludes scores and
  incomplete AgentRunbook work (FR-039, SC-019).
- [x] [T005Q] Make the documented no-egress LongMem preflight validate the
  durable RunPod account credential without requiring the ephemeral reader key
  that exists only after pod provisioning; retain the live-key requirement for
  every paid case (FR-035, SC-019).
- [x] [T005R] Add an equivalent no-egress Dolphin preflight that validates the
  official 30-task split, matched adapter/driver, installed artifact,
  checkpoint digest, attribution artifacts, and durable provider credentials
  without requiring finalization evidence or starting paid calls (FR-035,
  FR-038, SC-019).
- [ ] [T005S] Pin the official AGMI repository commit, package version, AtMem
  adapter, T1–T9 attack implementations and the two published AtMem 2.3.7 rows;
  add an installed-artifact runner and retain the exact published 0/9
  chain-only and 1/9 externally checkpointed reproduction before changing
  product behavior (`research/production_benchmarks/run_agmi_integrity.py`,
  `benchmarks/retrieval_quality/protocols/agmi-atmem-v1.json`) (FR-048, SC-022).

**Checkpoint**: A real A/B/C baseline exists before candidate implementation.

## Phase 2 — Context Engine V3 contracts and governance shell

- [x] [T006] [P] Add failing round-trip/malformed/compatibility tests for
  Formation V2, evidence obligations, navigation receipts, Sufficiency V2 and
  Context Package V3 in `tests/test_context_engine_contracts.py` (FR-001,
  FR-006, FR-009, FR-013–FR-016).
- [x] [T007] [P] Add failing authority, egress, lifecycle, cross-scope
  noninterference and canonical-revalidation tests in
  `tests/test_context_engine_governance.py` (FR-002, FR-019, FR-022, SC-009).
- [x] [T008] Implement additive host-neutral contracts in
  `atmem/context_engine/contracts.py`, export compatibility types through
  `atmem/contracts/`, and add fail-closed V3-to-V2 compatibility serialization
  plus golden tests for every status/reason mapping (FR-001, FR-020–FR-021,
  FR-034).
- [x] [T009] Implement `ContextEngineService` authorization, generation binding,
  canonical reload/revalidation and audit boundary in
  `atmem/context_engine/service.py` without ranking logic (FR-002–FR-003).
- [x] [T010] Add engine profile definitions and explicit
  `legacy-control`/`context-fast`/`context-navigate` shadow/active state in
  `atmem/context_engine/profiles.py` and the existing control store (FR-020).

**Checkpoint**: An engine can return only governed canonical identities; no new
formation or ranking exists yet.

## Phase 3 — Immutable source ranges and derived generations

- [x] [T011] [P] Add failing source-range identity, ordered multimodal linkage,
  idempotency and source-once storage tests in
  `tests/test_context_engine_formation.py` (FR-004–FR-006, SC-002, SC-008).
- [ ] [T012] [P] Add failing interrupted migration, backfill, activation,
  published-store upgrade, and ingest/delete-under-V3 then rollback freshness
  tests in
  `tests/test_context_engine_migration.py` (FR-018–FR-020, FR-033, SC-009).
- [x] [T013] Add encrypted schema/migration support for source ranges, view
  generations, compact units, links, coverage and loss receipts in
  `atmem/store/sqlite.py`; require SQLCipher provisioning/migration before typed
  activation, contentless/external-content FTS and household-encrypted vectors;
  do not duplicate source bodies (FR-004–FR-007, FR-018–FR-019, SC-008).
- [x] [T014] Implement generation build/verify/activate/retire/rebuild and
  resumable backfill in `atmem/context_engine/formation.py` and
  `atmem/context_engine/coverage.py` (FR-005–FR-008, FR-020).
- [x] [T015] Add category-level storage accounting and a source-duplication
  detector in `atmem/context_engine/coverage.py` plus CLI JSON output (FR-018,
  SC-008).
- [ ] [T016] Prove verified deletion and lifecycle invalidation across source
  links, every view/index, cache, preparation, backup and export using
  `tests/test_context_engine_governance.py` (FR-019, SC-009).

**Checkpoint**: Canonical source is retained once and a derived generation can
be rebuilt/rolled back safely.

## Phase 4 — High-recall multi-view formation

- [ ] [T017] [P] Add failing deterministic fixtures for all eight evidence-view
  kinds, correction/occurrence linkage, negative observations and uncovered
  source regions in `tests/test_context_engine_formation.py` (FR-005–FR-007).
- [x] [T018] Implement deterministic raw-state/structural transition/source
  projection in `atmem/context_engine/formation.py` (FR-004–FR-006).
- [x] [T019] Implement optional schema-constrained additive extraction and repair
  with pinned model identity, bounded concurrency/deadline and exact source-range
  validation in `atmem/context_engine/formation.py` (FR-006–FR-008).
- [ ] [T020] Implement fact/entity occurrence linking and source-grounded
  correction/supersession/conflict reconciliation without granting model write
  authority in `atmem/context_engine/formation.py` (FR-007–FR-008).
- [ ] [T021] Run formation on the frozen parity corpus and iterate until SC-002
  passes with explicit loss receipts and no source duplication; retain cassettes
  externally and aggregate evidence in
  `benchmarks/retrieval_quality/reports/context-engine-formation.md` (SC-014).

**Checkpoint**: Formation—not retrieval—can account for every answer-bearing
source range.

## Phase 5 — Obligation-first deterministic retrieval

- [ ] [T022] [P] Add failing planner fixtures for entities, relations, time,
  polarity, applicability, ordered steps, comparisons, conflicts and premise
  validation in `tests/test_context_engine_retrieval.py` (FR-009, FR-012).
- [ ] [T023] [P] Add failing pool-isolation, no-recency-filler, bounded-index,
  comparison-head and multi-obligation tests in
  `tests/test_context_engine_retrieval.py` (FR-010–FR-012, FR-017).
- [ ] [T024] Implement deterministic and optional schema-constrained query plans
  in `atmem/context_engine/planner.py`, preserving the original query and an
  auditable fallback (FR-009).
- [x] [T025] Implement independent raw-state, transition, fact/entity,
  procedure/rule, gotcha and premise pool interfaces/quotas in
  `atmem/context_engine/pools.py` (FR-010).
- [ ] [T026] Implement exact/FTS, semantic, temporal and link nomination with
  independent normalized signals and obligation-head reservation in
  `atmem/context_engine/retrieval.py` (FR-011–FR-012, FR-017).
- [x] [T027] Implement generation-aware scoped caches whose keys include all
  authority, lifecycle, profile, model/index and query identities in
  `atmem/context_engine/retrieval.py` (FR-017, FR-019, FR-022).

**Checkpoint**: `context-fast` passes product-neutral retrieval and authority
tests without whole-store scans or a model dependency.

## Phase 6 — Bounded evidence navigation, sufficiency and packing

- [x] [T028] [P] Add failing manifest/search/inspect/follow/submit budget and
  canonical-range validation tests in `tests/test_context_engine_navigation.py`
  (FR-013).
- [ ] [T029] [P] Add failing sufficiency/packing tests for complete, partial,
  conflicted, contradicted, stale, not-found-within-budget, policy-withheld,
  ordered, comparative, media and byte-exhausted contexts in
  `tests/test_context_engine_retrieval.py` (FR-014–FR-016, FR-034).
- [x] [T030] Implement authorized compact manifests and bounded navigation
  operations in `atmem/context_engine/navigator.py`; never expose gold or whole
  source corpora to the navigator (FR-013, FR-017, FR-024).
- [x] [T031] Implement obligation-grounded sufficiency in
  `atmem/context_engine/sufficiency.py`; model confidence cannot satisfy an
  obligation (FR-014).
- [ ] [T032] Implement coverage-maximizing total-input packing, ordered evidence,
  protected media and grounded action constraints in
  `atmem/context_engine/packing.py` (FR-015–FR-016).
- [ ] [T033] Integrate fast and navigate paths through
  `atmem/context_engine/service.py` with one canonical final revalidation and
  audit receipt (FR-001–FR-003, FR-013–FR-016).

**Checkpoint**: SC-001 passes reader-free on the frozen corpus.

## Phase 7 — Reference parity and measured iteration

- [ ] [T034] Implement neutral out-of-process AtMem, Mem0 OSS and
  AgentRunbook-R/C adapters under `research/reference_parity/adapters/` and
  production LongMem/Dolphin shims under `research/production_benchmarks/`
  without reference imports in `atmem/`; record resolved module, source commit,
  model route and artifact digest for every arm (FR-024–FR-027, FR-035).
- [ ] [T035] Implement deterministic cassette and reader-free runner/reporting in
  `research/reference_parity/runner.py`, including exact evidence-set metrics,
  latency, bytes and storage (FR-025–FR-029).
- [ ] [T036] Run the frozen reader-free differential and iterate only on
  development fixtures until AtMem is reproducibly at least 10% relatively
  better than both reference systems, then evaluate the sealed holdout once;
  log every A-to-B result, including
  regressions, in `benchmarks/retrieval_quality/reports/context-engine-trajectory.md`
  (FR-026–FR-029, SC-001, SC-017).
- [ ] [T037] Capture one bounded pinned live extraction/planning/navigation
  cassette per system on the development corpus, validate encrypted external
  retention and replay it through the neutral runner; stop if source coverage
  or reader-free quality regresses (FR-026–FR-029, FR-036).

**Checkpoint**: The new design has cheaper comparative evidence before paid
answer/action scoring.

## Phase 8 — Product surfaces, performance and installed qualification

- [ ] [T038] [P] Expose engine profile/status, coverage, sufficiency, sources,
  shadow comparison and repair actions through shared control service plus CLI
  in `atmem/control/manager.py` and `atmem/cli.py` (FR-020–FR-023).
- [ ] [T039] [P] Expose the same contract through MCP in `atmem/mcp/server.py`
  and dashboard routes/components under `atmem/control/` (FR-021–FR-023).
- [ ] [T040] Update OpenClaw, Hermes, Pydantic AI and LangChain/LangGraph adapter
  translations without host-specific ranking rules; preserve setup/restore and
  shadow defaults (FR-020–FR-022, SC-010).
- [ ] [T041] Emit content-free stage events and verify optional AtFlows grouping
  by agent/profile/stage without runtime dependency or protected content
  (`atmem/context_engine/telemetry.py`) (FR-023).
- [ ] [T042] Add the 100k-unit cold/warm, concurrent ten-agent, storage-growth,
  50k/100k absolute latency/RSS, sampled-shadow ≤20% overhead, navigation
  p95/cost, concurrent ten-agent, storage-growth including FTS/vectors,
  stolen-store, idle CPU, cache invalidation and no-full-scan gates in
  `tests/test_context_engine_performance.py` (FR-017–FR-018, SC-007–SC-008).
- [ ] [T043] Build the candidate wheel and run fresh/upgrade/shadow/activate/
  restart/query/inspect/rollback on macOS, Linux and Windows-compatible paths;
  retain installed evidence outside the repo (FR-030, SC-009–SC-012, SC-011).

### Phase 8A — Memory integrity and AGMI qualification

- [ ] [T043A] Add failing product tests for AGMI T1–T8 mutations that prove the
  edit landed and require content, deletion, insertion, ordering,
  cross-context, rollback-replay and metadata mismatches to fail before context
  delivery; include matching controls and explicit error-state assertions
  (`tests/test_integrity.py`, `tests/test_context_engine_governance.py`)
  (FR-049, FR-051, SC-022).
- [ ] [T043B] Implement indexed record-to-chain commitments and pre-delivery
  verification covering content, identity, subject/scope, order and
  security-relevant metadata without whole-store reads
  (`atmem/store/sqlite.py`, `atmem/context_engine/service.py`) (FR-049,
  FR-051, SC-007, SC-022).
- [ ] [T043C] Add failing crash, stale/missing/forged checkpoint, backup,
  restore, migration and key-rotation tests, then implement the recoverable
  external monotonic checkpoint protocol outside the store directory
  (`atmem/integrity.py`, `tests/test_integrity.py`) (FR-050–FR-051, SC-022).
- [ ] [T043D] Expose identical integrity status and repair guidance through
  CLI, MCP, dashboard, Hermes and OpenClaw; prove altered content is withheld
  and legacy/unanchored state is not displayed as verified (FR-021, FR-051,
  SC-009–SC-010, SC-022).
- [ ] [T043E] Build and install a clean candidate and run all pinned AGMI T1–T9
  cases in chain-only and external-checkpoint profiles on macOS, Linux and
  Windows-compatible paths. Require zero silent T1–T8 accepts, anchored T9
  detection, matching-control false-positive rate zero, and an explicit
  chain-only T9 `unanchored` result; retain raw evidence and prepare an upstream
  re-measurement request (FR-048–FR-051, SC-012, SC-022).

## Phase 9 — Matched paid development and confirmation

- [ ] [T044] Run a no-judge preflight plus configuration-specific finalization
  probes for every 4K/8K/16K reader, judge and agent route; reject malformed,
  reasoning-only or length-truncated output, verify the candidate checkout is
  imported ahead of site packages, validate the sample-size-only equivalence
  receipt, and terminate paid infrastructure promptly on failure
  (FR-026–FR-029, FR-035, FR-038, SC-015, SC-019).
- [x] [T044A] Freeze and validate the six-question LongMem progress checkpoint,
  bind its selected identifiers and diagnostic claim into finalization/run
  identity, and execute every matched arm with the production pipeline.
  Preserve failures in the denominator and retain the stage evidence without
  stopping, restarting or changing the complete run because of its score
  (FR-035, FR-037A, FR-038–FR-042, SC-015–SC-016, SC-019).
  The first paid stage (`6814770-r1`) retained all 30 matched outcomes and
  measured AtMem 4/6, current AgentRunbook-R 2/6, verified evidence 4/6,
  Mem0 OSS 0/6 and no-memory 0/6. Expansion remains locked because AtMem only
  tied the stronger retained AgentRunbook-R same-six reference (4/6), rather
  than beating it. Attribution returned to two bounded defects: excess UI
  context caused one reader/provider failure, and OR-fallback field matches
  allowed unrelated Incident/Change surfaces to outrank the requested Problem
  workflow. The same six IDs MUST be rerun after those generic defects pass
  reader-free and installed-artifact gates; the other 17 remain inaccessible.
  The second paid attempt (`3ea37cd-r2-attempt2`) was stopped at the earliest
  mathematically terminal checkpoint: AtMem was 2/4, so 5/6 was no longer
  reachable. No provider errors were counted as retrieval failures and the
  single L40S pod was confirmed terminated. The attempt established two
  distinct defects: a common misspelling (`intergrates`) suppressed the exact
  Outlook relation facet, and canonical JSON accessibility trees produced a
  12.7 KiB range that buried option-field evidence. The generic correction
  accepts the misspelling as the same explicit relation, bounds structured
  source ranges at exact escaped line boundaries, nominates every explicit
  option field from the requested workflow sources, and applies source-diverse
  FTS shortlisting. On the real frozen enterprise checkpoint, reader-free
  evidence now contains Outlook within 15.3 KiB and contains Subcategory,
  Assignment Group and State while excluding Routing Cluster within 15.5 KiB.
  A clean checkpoint and installed artifact MUST be produced before paid
  attempt 3; T045 remains locked until a paid stage reaches at least 5/6.
  Attempt 3 reached no benchmark case: the clean enterprise database had been
  formed but was not installed under the frozen runner's `memory_state/atmem.db`
  layout. The runner terminated its sole pod before any reader case and the
  reservation was reconciled as a conservative local-termination upper bound.
  The checkpoint is now installed, all seven required prebuilt configurations
  are present, and the runner validates them before creating paid output or
  reserving provider cost. This infrastructure-only attempt is not a retrieval
  result and does not alter the retained stage scores.
  Attempt 4 (`27f8033-r4-attempt4`) was stopped as soon as a strict win became
  impossible. AtMem scored 4/6, tying rather than exceeding the retained
  AgentRunbook-R 4/6 reference, so T045 stayed locked and the remaining 17
  questions were not exposed. Attribution separated two faults: the paid run
  restored a stale 1.72 GB checkpoint instead of the verified 1.95 GB
  checkpoint, and transition retrieval delivered the pre-change Dell option
  state rather than the requested post-change relative price. On the verified
  checkpoint, reader-free validation now preserves the three real Problem
  fields while excluding the invented distractor fields, and ranks the
  post-change `Ubuntu [subtract $100.00]` source range first. The same six IDs
  MUST pass the installed-artifact and paid stage again before T045 unlocks.
  Attempt 5 (`2767f37-r5-attempt5`) passed that gate with the exact installed
  wheel and verified 1.95 GB checkpoint: AtMem 5/6, AgentRunbook-R 3/6, Mem0
  OSS 1/6, verified evidence 5/6 and no memory 0/6. AtMem therefore exceeded
  both the live AgentRunbook-R result and the retained 4/6 same-six reference.
  The sole AtMem miss was the ordered-workflow count (`one` rather than
  `three`); it remains an attributed development defect, but does not block the
  precommitted >=5/6 stage threshold. All 30 matched outcomes were retained,
  the A100 reader pod terminated automatically after 2,156.470 seconds, and
  its conservative runtime estimate was $1.072245. T045 is now unlocked; this
  six-question development result is a stop/go diagnostic, not a benchmark
  claim.
- [ ] [T045] Run AtMem, Mem0 OSS and AgentRunbook-R/C on the same frozen
  nested 23-question LongMem five-percent development sample; produce a single matched table with
  accuracy, per-requirement pipeline coverage, product-context versus verified-
  evidence reader attribution, latency, tokens, resource, storage and cost
  inputs for product context, evaluator-verified minimal evidence and no memory
  under the same pinned reader; retain complete eight-stage ledgers and the
  deterministic terminal classification table
  (`research/production_benchmarks/run_longmem_pilot.py`)
  (FR-039–FR-042, SC-003, SC-016, SC-019–SC-020).
  Full attempt 6 reached the first ten frozen questions with AtMem 7/10,
  AgentRunbook-R 2/10 and Mem0 OSS 1/10, but the run was deliberately
  interrupted before the inherited 3,600-second pod-runtime envelope could
  convert the remaining thirteen questions into artificial system failures.
  This partial result is operational evidence only and MUST NOT be reported as
  the five-percent score. The production-equivalent envelope is corrected to
  10,800 seconds at the same pinned $1.79/hour route, with a $5.37 GPU cap and
  immediate termination after reader completion. Runtime reservation covers
  the entire envelope, including readiness and validation time already billed;
  sample, model, prompts, retrieval, scoring and denominator are unchanged.
  Attempt 7 then completed the same six-question checkpoint at AtMem 2/6,
  AgentRunbook-R 2/6, Mem0 OSS 0/6 and verified evidence 4/6. AtMem and
  AgentRunbook-R each incurred one `reader did not produce a complete final
  answer` system failure after consuming the 20,000-token completion budget;
  neither failure is attributed to memory. The run stopped before question 7
  was credited. The common reader route now sends the protocol seed `23801`
  per request and retains the closing brace before stopping at the answer
  contract's required `\\boxed{...}` boundary. This is applied identically to
  every arm and is bound into finalization identity; memory formation,
  retrieval, packed context, prompt and grader remain unchanged.
- [ ] [T044B] Keep the complete paid LongMem and Dolphin product path on the
  Mac/MEM topology with exactly one local case at a time, thread caps and low
  process priority; use the pinned RunPod Linux GPU only for Qwen inference.
  Bind controller/concurrency and RunPod image/GPU/resource/cleanup identity
  into finalization, retain checkpoints and durable evidence on `MEM`, and
  test that the operator workstation never performs model inference
  (FR-029, FR-035, FR-038, FR-053, SC-012, SC-019).
- [ ] [T046] Run AtMem and matched Mem0 on the same frozen 30-task Dolphin
  development sample through Hermes; preserve all tasks and exact tool/grader
  evidence, and run removal/positive-control tests whose block receipt names the
  missing requirement and distinguishes timeout/provider/parse/silent-no-call
  outcomes; for every applicable task pair each removal with a restored-evidence
  positive control and reject always-blocking gates
  (`research/production_benchmarks/run_dolphin_development.py`)
  (FR-039–FR-043, SC-005, SC-019–SC-020).
  The first complete matched run retained all 30 tasks with zero system
  failures: AtMem 2/30 and 15/97 checks; Mem0 OSS 3/30 and 16/97 checks.
  Removal controls were 30/30; paired removal/restored positive controls were
  28/30 because restored evidence remained over-blocked for `morgan:063` and
  `morgan:138`. This is valid development evidence, not a passing target and
  not an official score. T046 remains open until reviewed requirement-stage
  ledgers are complete and the post-remediation run is retained.
- [ ] [T046A] Freeze the six-case Dolphin remediation subset
  (`morgan:063`, `morgan:138`, `alex:082`, `morgan:103`, `alex:026`,
  `riley:126`) and add evaluator-blind root-cause reporting plus synthetic
  no-model contracts for represented action facts, obligation coverage,
  restored-gate opening and passing-action non-regression
  (`benchmarks/retrieval_quality/protocols/`,
  `research/production_benchmarks/`, `tests/`) (FR-054, SC-024).
- [ ] [T046B] Correct the earliest generic formation, retrieval or packing
  defects evidenced by T046A without benchmark-specific query rules; require
  6/6 restored gates open, 6/6 removal blocks remain named/fail-closed, both
  prior fully passing tasks remain passing, and no-model/product contract tests
  pass before paid scoring (`atmem/context_engine/`,
  `research/production_benchmarks/`) (FR-014–FR-016, FR-043, FR-054, SC-024).
- [ ] [T046C] Rebuild fresh isolated AtMem and Mem0 persona checkpoints and run
  the unchanged matched 30-task Dolphin protocol once; retain all 30 tasks and
  97 checks, zero system failures, costs, tool traces, removal/positive
  controls and the pre-change table. Make no superiority claim unless AtMem
  exceeds Mem0 on both task and check totals
  (`research/production_benchmarks/run_dolphin_matched.py`,
  `benchmarks/retrieval_quality/reports/`) (FR-038–FR-043, FR-054, SC-024).
- [ ] [T047] Freeze the selected candidate only if T045/T046 targets pass; repeat
  the chosen development arm once to reject a non-reproducible peak. Otherwise
  return to the earliest attributed failing stage, not prompt/weight thrashing.
- [ ] [T048] Run precommitted disjoint untouched LongMemEval confirmation IDs
  exactly once for the frozen candidate, aside from documented infrastructure
  retries; run complete Small separately as non-held-out and produce symmetric
  per-run/mean/cost-normalized/paired-bootstrap analysis (SC-004, SC-013).
- [ ] [T049] If separately budget-approved, run all 600 Dolphin tasks for AtMem
  and the matched baseline from a pre-scoring hashed persona checkpoint, report
  600/600 and 582 non-development tasks separately as tuned-on-corpus/held-out-
  tasks, package upstream results and request explicit approval before submission
  (SC-006).

## Phase 10 — Release decision and documentation

- [ ] [T050] Validate SC-001–SC-024 from a signed/checksummed qualification index;
  missing evidence is fail/invalid, never skipped (FR-029–FR-032).
- [ ] [T051] Update product, CLI/MCP, dashboard, storage, migration, benchmark and
  limitation documentation plus `docs/release-roadmap.md`; keep 2.3.8 Hermes,
  MCP registry, AtFlows redaction and continuity commitments visible (FR-021,
  FR-030–FR-032).
- [ ] [T052] Run one bounded Claude Opus 5.5 medium read-only final review of the
  implemented diff and evidence, resolve only concrete blocker findings, then
  rerun affected gates without opening a new architecture cycle.
- [ ] [T052A] After T050–T052 pass, set the next beta version on the exact
  reviewed commit, build and install its wheel in a clean environment, and
  rerun the release-associated LongMemEval-V2, DolphinBench and AGMI gates.
  Reject any result whose installed version, commit or artifact SHA-256 differs
  from the beta qualification index (FR-030, FR-032, FR-052, SC-023).
- [ ] [T053] Commit and push the reviewed candidate. Prepare or publish 2.3.8 only
  upon a separate explicit request and follow `AGENTS.md` release completion
  rules; do not tag from this implementation task.

## Dependencies and stop conditions

- T001–T005A precede benchmark-readiness implementation.
- T006–T010 block every new engine behavior.
- T011–T021 block retrieval work because unrepresented evidence cannot be fixed
  by ranking.
- T022–T033 block comparative and paid work.
- T034–T037 block paid development: comparators must exist first.
- T038–T043 block release qualification, not the no-model research loop.
- T005S and T043A–T043E block integrity claims and stable promotion; they do not
  justify interrupting an already-authorized paid reader run.
- T005A–T005E and T034–T044B block T045/T046; T045 and T046 must be matched tables,
  never AtMem-only.
- T048 is forbidden until T045 is complete, reproducible and frozen.
- Stop immediately on scope leakage, plaintext leakage, source loss, benchmark
  leakage, whole-store scans, invalid provider outputs, uncertain paid cleanup,
  missing comparator identity or another defect that invalidates completeness
  or comparability. Do not stop or restart because a valid score is low.
- A failed benchmark target is retained and reported honestly. It may inform a
  later separately authorized iteration, but cannot interrupt these final runs
  or trigger an unbounded review cycle.
