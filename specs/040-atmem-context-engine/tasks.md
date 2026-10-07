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
  `benchmarks/retrieval_quality/protocols/` (FR-028, FR-039, SC-019).
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
  require one-requirement removal units and emit `non_atomic_removal_target`
  instead of deleting a multi-requirement episode (FR-046–FR-047, SC-021).
- [x] [T005K] Add an opt-in scope-bound authorized history-import review flow
  using public review APIs, single-use authorization and audit receipts. Prove
  default imports remain fail-closed and evaluator manifests cannot enter the
  product path (FR-045, SC-009, SC-021).
- [ ] [T005L] Build and install a clean candidate wheel, rebuild all three
  encrypted Dolphin persona checkpoints from full history, rerun all 30 removal
  controls, and retain formation/review/atomization counts. Paid evaluation is
  blocked until every applicable control is valid and zero unknown/system
  outcomes are credited (FR-039–FR-047, SC-019–SC-021).

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

## Phase 9 — Matched paid development and confirmation

- [ ] [T044] Run a no-judge preflight plus configuration-specific finalization
  probes for every 4K/8K/16K reader, judge and agent route; reject malformed,
  reasoning-only or length-truncated output, verify the candidate checkout is
  imported ahead of site packages, validate the sample-size-only equivalence
  receipt, and terminate paid infrastructure promptly on failure
  (FR-026–FR-029, FR-035, FR-038, SC-015, SC-019).
- [ ] [T045] Run AtMem, Mem0 OSS and AgentRunbook-R/C on the same frozen
  nested 23-question LongMem five-percent development sample; produce a single matched table with
  accuracy, per-requirement pipeline coverage, product-context versus verified-
  evidence reader attribution, latency, tokens, resource, storage and cost
  inputs for product context, evaluator-verified minimal evidence and no memory
  under the same pinned reader; retain complete eight-stage ledgers and the
  deterministic terminal classification table
  (`research/production_benchmarks/run_longmem_pilot.py`)
  (FR-039–FR-042, SC-003, SC-016, SC-019–SC-020).
- [ ] [T046] Run AtMem and matched Mem0 on the same frozen 30-task Dolphin
  development sample through Hermes; preserve all tasks and exact tool/grader
  evidence, and run removal/positive-control tests whose block receipt names the
  missing requirement and distinguishes timeout/provider/parse/silent-no-call
  outcomes; for every applicable task pair each removal with a restored-evidence
  positive control and reject always-blocking gates
  (`research/production_benchmarks/run_dolphin_development.py`)
  (FR-039–FR-043, SC-005, SC-019–SC-020).
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

- [ ] [T050] Validate SC-001–SC-021 from a signed/checksummed qualification index;
  missing evidence is fail/invalid, never skipped (FR-029–FR-032).
- [ ] [T051] Update product, CLI/MCP, dashboard, storage, migration, benchmark and
  limitation documentation plus `docs/release-roadmap.md`; keep 2.3.8 Hermes,
  MCP registry, AtFlows redaction and continuity commitments visible (FR-021,
  FR-030–FR-032).
- [ ] [T052] Run one bounded Claude Opus 5.5 medium read-only final review of the
  implemented diff and evidence, resolve only concrete blocker findings, then
  rerun affected gates without opening a new architecture cycle.
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
- T005A–T005E and T034–T044 block T045/T046; T045 and T046 must be matched tables,
  never AtMem-only.
- T048 is forbidden until T045 is complete, reproducible and frozen.
- Stop immediately on scope leakage, plaintext leakage, source loss, benchmark
  leakage, whole-store scans, invalid provider outputs, uncertain paid cleanup,
  or missing comparator identity.
- A failed benchmark target returns to the attributed formation, nomination,
  navigation, sufficiency, reader-use or agent-action stage. It does not trigger
  unbounded review cycles.
