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
- [ ] [T004] Implement and run the pre-change reader-free baseline for all three
  systems, retaining heavy raw outputs on `MEM` and the signed aggregate under
  `benchmarks/retrieval_quality/baselines/` (FR-025–FR-029).
- [x] [T005] Freeze disjoint development/confirmation IDs, reader/judge prompts,
  provider revisions, hardware, retry policy, seeds and cost ceilings in
  `benchmarks/retrieval_quality/protocols/2.3.8-context-engine.yaml`; include all
  inspected IDs in development and define per-arm formation/embedding/planner/
  navigator/reader/judge identities, top-k/context, maximum model calls/tokens/
  operations, equal-size development sweeps and symmetric repeats with no
  best-of selection (FR-027–FR-029, FR-035–FR-036).

**Checkpoint**: A real A/B/C baseline exists before candidate implementation.

## Phase 2 — Context Engine V3 contracts and governance shell

- [ ] [T006] [P] Add failing round-trip/malformed/compatibility tests for
  Formation V2, evidence obligations, navigation receipts, Sufficiency V2 and
  Context Package V3 in `tests/test_context_engine_contracts.py` (FR-001,
  FR-006, FR-009, FR-013–FR-016).
- [ ] [T007] [P] Add failing authority, egress, lifecycle, cross-scope
  noninterference and canonical-revalidation tests in
  `tests/test_context_engine_governance.py` (FR-002, FR-019, FR-022, SC-009).
- [ ] [T008] Implement additive host-neutral contracts in
  `atmem/context_engine/contracts.py`, export compatibility types through
  `atmem/contracts/`, and add fail-closed V3-to-V2 compatibility serialization
  plus golden tests for every status/reason mapping (FR-001, FR-020–FR-021,
  FR-034).
- [ ] [T009] Implement `ContextEngineService` authorization, generation binding,
  canonical reload/revalidation and audit boundary in
  `atmem/context_engine/service.py` without ranking logic (FR-002–FR-003).
- [ ] [T010] Add engine profile definitions and explicit
  `legacy-control`/`context-fast`/`context-navigate` shadow/active state in
  `atmem/context_engine/profiles.py` and the existing control store (FR-020).

**Checkpoint**: An engine can return only governed canonical identities; no new
formation or ranking exists yet.

## Phase 3 — Immutable source ranges and derived generations

- [ ] [T011] [P] Add failing source-range identity, ordered multimodal linkage,
  idempotency and source-once storage tests in
  `tests/test_context_engine_formation.py` (FR-004–FR-006, SC-002, SC-008).
- [ ] [T012] [P] Add failing interrupted migration, backfill, activation,
  published-store upgrade, and ingest/delete-under-V3 then rollback freshness
  tests in
  `tests/test_context_engine_migration.py` (FR-018–FR-020, FR-033, SC-009).
- [ ] [T013] Add encrypted schema/migration support for source ranges, view
  generations, compact units, links, coverage and loss receipts in
  `atmem/store/sqlite.py`; require SQLCipher provisioning/migration before typed
  activation, contentless/external-content FTS and household-encrypted vectors;
  do not duplicate source bodies (FR-004–FR-007, FR-018–FR-019, SC-008).
- [ ] [T014] Implement generation build/verify/activate/retire/rebuild and
  resumable backfill in `atmem/context_engine/formation.py` and
  `atmem/context_engine/coverage.py` (FR-005–FR-008, FR-020).
- [ ] [T015] Add category-level storage accounting and a source-duplication
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
- [ ] [T018] Implement deterministic raw-state/structural transition/source
  projection in `atmem/context_engine/formation.py` (FR-004–FR-006).
- [ ] [T019] Implement optional schema-constrained additive extraction and repair
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
- [ ] [T025] Implement independent raw-state, transition, fact/entity,
  procedure/rule, gotcha and premise pool interfaces/quotas in
  `atmem/context_engine/pools.py` (FR-010).
- [ ] [T026] Implement exact/FTS, semantic, temporal and link nomination with
  independent normalized signals and obligation-head reservation in
  `atmem/context_engine/retrieval.py` (FR-011–FR-012, FR-017).
- [ ] [T027] Implement generation-aware scoped caches whose keys include all
  authority, lifecycle, profile, model/index and query identities in
  `atmem/context_engine/retrieval.py` (FR-017, FR-019, FR-022).

**Checkpoint**: `context-fast` passes product-neutral retrieval and authority
tests without whole-store scans or a model dependency.

## Phase 6 — Bounded evidence navigation, sufficiency and packing

- [ ] [T028] [P] Add failing manifest/search/inspect/follow/submit budget and
  canonical-range validation tests in `tests/test_context_engine_navigation.py`
  (FR-013).
- [ ] [T029] [P] Add failing sufficiency/packing tests for complete, partial,
  conflicted, contradicted, stale, not-found-within-budget, policy-withheld,
  ordered, comparative, media and byte-exhausted contexts in
  `tests/test_context_engine_retrieval.py` (FR-014–FR-016, FR-034).
- [ ] [T030] Implement authorized compact manifests and bounded navigation
  operations in `atmem/context_engine/navigator.py`; never expose gold or whole
  source corpora to the navigator (FR-013, FR-017, FR-024).
- [ ] [T031] Implement obligation-grounded sufficiency in
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
  AgentRunbook-R/C adapters under `research/reference_parity/adapters/` without
  reference imports in `atmem/` (FR-024–FR-027).
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
  cassette per system on the development corpus and rerun the differential;
  stop if source coverage or reader-free quality regresses (FR-026–FR-029).

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
  reasoning-only or length-truncated output and terminate paid infrastructure
  promptly on failure (FR-026–FR-029, SC-015).
- [ ] [T045] Run AtMem, Mem0 OSS and AgentRunbook-R/C on the same frozen
  14-question LongMem development sample; produce a single matched table with
  accuracy, evidence metrics, latency, tokens, resource, storage and cost
  (`research/production_benchmarks/run_longmem_pilot.py`) (SC-003, SC-016).
- [ ] [T046] Run AtMem and matched Mem0 on the same frozen 18-task Dolphin
  development sample through Hermes; preserve all tasks and exact tool/grader
  evidence (`research/production_benchmarks/run_dolphin_development.py`) (SC-005).
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

- [ ] [T050] Validate SC-001–SC-018 from a signed/checksummed qualification index;
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

- T001–T005 precede implementation.
- T006–T010 block every new engine behavior.
- T011–T021 block retrieval work because unrepresented evidence cannot be fixed
  by ranking.
- T022–T033 block comparative and paid work.
- T034–T037 block paid development: comparators must exist first.
- T038–T043 block release qualification, not the no-model research loop.
- T044 blocks T045/T046; T045 and T046 must be matched tables, never AtMem-only.
- T048 is forbidden until T045 is complete, reproducible and frozen.
- Stop immediately on scope leakage, plaintext leakage, source loss, benchmark
  leakage, whole-store scans, invalid provider outputs, uncertain paid cleanup,
  or missing comparator identity.
- A failed benchmark target returns to the attributed formation, nomination,
  navigation, sufficiency, reader-use or agent-action stage. It does not trigger
  unbounded review cycles.
