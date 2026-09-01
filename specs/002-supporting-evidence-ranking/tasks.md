# Tasks: Governed Supporting-Evidence Ranking

## Phase 1: Foundational Ranker

- [x] T001 Implement the versioned, dependency-free score validation, scope-bound opaque grouping, strongest-two-peer support bonus, singleton preservation, and deterministic ordering in `atmem/retrieve/support.py` (FR-002–FR-006)
- [x] T002 Export the supporting-evidence ranker and algorithm identity from `atmem/retrieve/__init__.py` without adding a package dependency (FR-004, FR-013)
- [x] T003 Add unit tests for multi-chunk support, singleton groups, strongest-two-peer cap, clamping, non-finite rejection, deterministic ties, opaque identifiers, and cross-scope separation in `tests/test_supporting_evidence.py` (SC-001)

## Phase 2: Post-Authorization Candidate Aggregation

- [x] T004 Refactor `Memory.create_candidate_set_v1()` in `atmem/memory.py` to build an internal list only after canonical active/exclusion/scope/egress/content validation, then aggregate that eligible list (FR-001, FR-008)
- [x] T005 Persist additive record/support/aggregate signals, aggregate ordering, candidate digest coverage, and content-free audit metadata in `atmem/memory.py` without changing candidate format identifiers or SQLite schemas (FR-007, FR-012, FR-013)
- [x] T006 Add contract and security tests proving deleted, excluded, quarantined, cross-scope, remote-sensitive, duplicate-expansion, and missing-session records cannot create unauthorized support in `tests/test_contracts_v1.py` and `tests/test_supporting_evidence.py` (FR-001–FR-003, FR-017, SC-002)
- [x] T007 Add generation invalidation and final `prepare_context_v1()` revalidation tests showing stale support cannot authorize context in `tests/test_contracts_v1.py` (FR-010, FR-017)

## Phase 3: AtBot and Fallback Boundaries

- [x] T008 Allowlist bounded aggregation signals into AtBot's `eligible_memories` payload while excluding raw session provenance in `packages/atbot/src/atbot/companion.py` (FR-003, FR-009)
- [x] T009 Add AtBot package tests for signal forwarding, raw-session absence, valid subset/permutation ranking, unknown-ID filtering, and provider-exception fallback in `packages/atbot/tests/test_companion.py` (FR-009, FR-011, SC-004)
- [x] T010 Add AtMem companion fallback tests proving unavailable AtBot selects the first aggregate-ranked eligible record and never widens the set in `tests/test_atbot_companion.py` (FR-009–FR-011)

## Phase 4: Product Retrieval Integration

- [x] T011 Add dashboard `memory_query()` integration coverage showing durable authorization precedes aggregation and final context preparation revalidates the aggregate/AtBot order in `tests/test_atbot_companion.py` (FR-008–FR-010, SC-003)
- [x] T012 Add `control_prepare` integration coverage for the same candidate-set → aggregation → AtBot → revalidation sequence, including shadow and active modes, in `tests/test_atbot_companion.py` and `tests/test_generic_control.py` (FR-008–FR-011, FR-014, SC-003)
- [x] T013 Verify Pydantic AI, LangGraph, OpenClaw, multi-agent, deletion, dashboard, and safe-fallback regression boundaries with focused existing suites, changing production code only for feature-caused regressions (FR-014) — 129 passed, 2 skipped

## Phase 5: Benchmark Diagnostics and Evidence

- [x] T014 Add `--case-id` selection, exact selection validation, and per-case aggregation details to `tools/run_longmemeval_retrieval.py` (FR-015, SC-006)
- [x] T015 Route AtMem benchmark session ordering through the shared supporting-evidence aggregation helper without changing Mem0's path or the matched input/model/scoring contract in `tools/run_longmemeval_retrieval.py` (FR-015, FR-016)
- [x] T016 Add offline tests for focused selection, per-case evidence retention, aggregation details, and external-result compatibility in `tests/test_benchmark_external.py` and a new small licensed fixture if needed (FR-015, FR-016)
- [x] T017 Run the formerly rank-two focused case, the fixed 12-case campaign, and a separately identified held-out selection; retain new results under `docs/examples/` and document commands, configuration, direct outcomes, and limitations in `docs/benchmarks.md` (FR-016, SC-006, SC-007) — fixed 12: recall-any/all@5 1.000, MRR@5 0.9583; non-overlapping held-out 6: recall-any/all@5 and MRR@5 1.000; focused temporal case remained RR 0.5 and is documented as requiring AtBot temporal reasoning

## Phase 6: Verification and Delivery

- [x] T018 Run the deterministic benchmark release gate and confirm extraction, contradiction, injection, privacy, poisoning, fallback, token, and cost evidence remains valid (FR-014, SC-005) — 16/16 passed; extraction/contradiction/recall/fallback 1.000; incorrect injection/privacy leaks/poisoning successes 0; token and cost remain explicitly unavailable for the no-model deterministic path
- [x] T019 Run ranker, contract, control-plane, framework-adapter, OpenClaw, semantic, deletion, and AtBot package tests; record exact results in this task file (FR-014, SC-005) — focused regression selection: 129 passed, 2 skipped; AtBot package: 16 passed
- [x] T020 Run the full AtMem test suite with required loopback permission, confirm no dependency/schema/format-version drift, and reconcile implementation with `spec.md` and `plan.md` (FR-013, FR-014, SC-005) — full suite: 341 passed, 2 skipped, 1 upstream deprecation warning; `git diff --check` clean; no feature dependency, SQLite schema, or public format-identifier change
