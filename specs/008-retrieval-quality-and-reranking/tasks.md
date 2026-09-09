# Tasks: Retrieval Quality, Embeddings, and Reranking

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/008/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

## Phase 1 — Lock the defects

- [x] [T001] Add failing burger-paraphrase, Australian-cars no-useful-memory, topical-non-answer, and AtBot-down fixtures in `tests/test_retrieval_quality.py` (FR-003–FR-005, FR-011–FR-014; SC-002–SC-005)
- [x] [T002] Add failing conformance coverage for dashboard, `control_prepare`, OpenClaw, Pydantic AI, LangGraph, and MCP in `tests/test_retrieval_adapter_conformance.py` and `integrations/openclaw/test/hooks.mjs` (FR-014; SC-004)

## Phase 2 — Contracts and calibration

- [x] [T003] Define typed signal/candidate/embedding/support/decision/reason contracts in `atmem/retrieve/models.py` and `atmem/schemas/v1/retrieval-decision.json` (FR-001, FR-003, FR-016)
- [x] [T004] Implement versioned normalization/threshold reconciliation in `atmem/retrieve/calibration.py` and `calibration-v1.json` (FR-003, FR-009–FR-010, FR-016)
- [x] [T005] Implement signal adapters/registry and exclude diagnostic hashing from injection eligibility in `atmem/retrieve/signals.py` (FR-001, FR-005, FR-009–FR-011)

## Phase 3 — Safe selection and fallback

- [x] [T006] Implement original-query direct/background/no-useful classification in `atmem/retrieve/rank.py` (FR-003–FR-004, FR-010–FR-013)
- [x] [T007] Replace first-candidate AtBot fallback with query-aware deterministic ranking/abstention in `atmem/control/atbot_companion.py` (FR-004, FR-015; SC-005)
- [x] [T008] Integrate shared decisions into `atmem/memory.py` and `atmem/control/manager.py` while preserving aggregation/revalidation/byte stability (FR-002, FR-014, FR-017; SC-007)
- [x] [T009] Add scope/generation/epoch/calibration/policy-safe cache keys and mandatory final reload in `atmem/retrieve/cache.py` (FR-020)

## Phase 4 — Production semantic profile

- [x] [T010] Extend embedding profiles with exact model/revision, prefixes, normalization, preprocessing, quality class, and license metadata in `atmem/semantic/` (FR-005–FR-008)
- [x] [T011] Apply query/document preprocessing, stale incompatible epochs, and test rebuild/restart in `tests/test_semantic_profiles.py` (FR-006, FR-008; SC-008)
- [x] [T012] Update CLI/dashboard health to identify diagnostic hashing and guide strong local setup in `atmem/cli.py` and `atmem/control/assets/` (FR-007)

## Phase 5 — Host-neutral delivery and UI

- [x] [T013] Route OpenClaw, Pydantic AI, LangGraph, and MCP through the shared decision, preserving no-useful-memory and eliminating host-local ranking (FR-014–FR-015)
- [x] [T014] Render support class, selected memories, safe explanation, withhold/degradation reason, and embedding health in the task-aware dashboard (FR-016; Spec 007 Amendment B)

## Phase 6 — Evaluation and gates

- [x] [T015] Add separate calibration/held-out fixtures, ablations, privacy/poisoning/conflict/failure cases, and optional pinned Mem0 comparison in `atmem/benchmark/data/` and tests (FR-018–FR-019; SC-001–SC-006)
- [x] [T016] Run adapter, Spec 002, semantic, benchmark, dashboard, OpenClaw, full pytest, and release-policy gates; document activation/rollback in `docs/retrieval-quality.md` (SC-001–SC-008)

## Dependencies

T001–T002 fail first. T003–T005 precede T006. T006 precedes T007–T009. T010 precedes T011–T012. T006–T012 precede T013–T014. T001–T014 precede T015–T016. Spec 007 Amendment B identity contracts precede task-aware T013–T014.


## Phase 7: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019; see the roadmap for foundation versus integration ordering.

- [ ] [T017] Define failing boundary fixtures for FR-021, FR-022, SC-009 using `tests/test_retrieval_adapter_conformance.py`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T018] Map native support decisions into provider-neutral context evidence in `atmem/retrieve/` (FR-021, FR-022); depend on T017 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T019] Verify SC-009 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/008/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T018 and do not mark completion from declarations alone.
