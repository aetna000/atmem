# Tasks: Temporal Memory Consolidation and Health Review

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/026/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews remain frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Status**: Planned, unchecked.

**Input**: [spec.md](spec.md), [plan.md](plan.md), [product requirements](../product-requirements.md).

**Prerequisites**: Existing Spec lifecycle/extraction foundations; stable Spec 012 memory-space membership for shared-space delivery; Spec 019 policy/package contracts for provider egress; Spec 022 for the common workspace. Spec 023 propagation is required only for the complete 2.8.0 claim. This work does not block 2.3.

## Phase 1: Contract foundation and independent fixtures

- [ ] [T001] Freeze temporal kind, precision, assertion, derivation input/output and stable reason-code contracts in `atmem/temporal/models.py`, with schema tests in `tests/test_temporal_memory.py` covering missing time, timezone, partial dates and half-open intervals (FR-001–FR-004, FR-018; SC-001).
- [ ] [T002] Freeze health policy, cycle, finding, proposal, review and AtBot request/result contracts in `atmem/consolidation/models.py` and `packages/atbot/src/atbot/health.py`; prove AtBot outputs can only reference authorized input IDs (FR-005–FR-010, FR-014, FR-016; SC-002, SC-004; depends on T001).
- [ ] [T003] Define independent temporal-boundary, age, duplicate, overlap-conflict, staleness, poisoning, private/shared, crash/restart and unavailable-AtBot fixtures under `tests/fixtures/product/026/` before implementation, including expected reason codes and explicit non-claims (FR-001–FR-018; SC-001–SC-008; depends on T002).

## Phase 2: 2.4 temporal memory foundation

- [ ] [T004] Allocate canonical SQLite migrations through the Spec 010 registry for temporal assertions, generations and content-minimized health artifacts in `atmem/store/sqlite.py`; add real persisted upgrade, rollback/forward-recovery and legacy-unknown tests without enabling review or inferring dates on upgrade (FR-001, FR-006, FR-018; depends on T003).
- [ ] [T005] Implement interval, timezone, precision and trusted-time validation in `atmem/temporal/validation.py` and point-in-time/historical evaluation in `atmem/temporal/eligibility.py`; verify identical boundary reasons with virtual clocks (FR-001–FR-003; SC-001; depends on T004).
- [ ] [T006] Implement the local versioned derivation registry and `date-of-birth-to-age-v1` in `atmem/temporal/derivation.py`, including birthday, leap-day, timezone, insufficient-precision and non-persistence tests (FR-004; SC-001; depends on T005).
- [ ] [T007] Integrate negotiated temporal fields into Spec 006 extraction validation and review through `atmem/extract/models.py`, `atmem/extract/validation.py` and `atmem/extract/review.py`; ensure model-proposed timestamps cannot replace trusted source/receive time and ambiguous interpretations require review (FR-001–FR-006, FR-010, FR-018; SC-002; depends on T005).
- [ ] [T008] Extend Spec 015 lifecycle inspection and transitions through `atmem/lifecycle/service.py` without creating a second authority; join temporal projection, preserve immutable correction lineage and atomically invalidate registered derivatives after accepted changes (FR-003, FR-008, FR-010, FR-015; SC-002, SC-005; depends on T004–T007).
- [ ] [T009] Make conflict classification validity-overlap-aware in `atmem/extract/classify.py` and `atmem/extract/context.py`; retain non-overlapping history, create review findings for overlapping incompatibility and fail closed under stale generations (FR-005, FR-006, FR-010, FR-011; SC-002, SC-003; depends on T007–T008).
- [ ] [T010] Integrate explicit evaluation time, lifecycle/temporal generation revalidation, derived context values and unresolved-conflict withholding in `atmem/memory.py` and `atmem/retrieve/`; prove ineligible records cannot affect another candidate's rank or prepared context (FR-003, FR-004, FR-011, FR-012; SC-001, SC-003; depends on T006, T008–T009).
- [ ] [T011] Expose the same temporal inspection, historical-purpose and derivation results through `atmem/service/application.py`, CLI and `atmem/mcp/server.py`, with authenticated scope and negotiated compatibility tests (FR-003, FR-013, FR-016, FR-018; SC-001, SC-006; depends on T010 and stable Spec 012 contracts for shared spaces).

## Phase 3: 2.5 Memory Health review experience

- [ ] [T012] Implement bounded local exact-duplicate, deterministic-expiry and overlap-conflict analysis in `atmem/consolidation/deterministic.py`; age/recency alone must not establish invalidity (FR-005, FR-008, FR-011, FR-012; SC-003–SC-004; depends on T008–T010).
- [ ] [T013] Implement authenticated, generation-checked approve, edit-and-approve, reject and defer coordination in `atmem/consolidation/review.py`, delegating canonical effects to Specs 006/015 and preserving idempotent receipts and lineage (FR-006, FR-008, FR-010, FR-015; SC-002, SC-005; depends on T012).
- [ ] [T014] Implement the scope-safe Memory Health read model in `atmem/consolidation/projection.py` and common service operations in `atmem/service/application.py`; authorize item access, counts, filters, evidence joins and exports independently (FR-013, FR-016; SC-006; depends on T013 and stable Spec 012 feedback/membership contracts).
- [ ] [T015] Add Context → Memory Health summary, filters, explanations, timestamps and review actions to `atmem/control/assets/app.html`, `app.js` and `app.css`, reusing Spec 022 navigation and service authority; cover keyboard and 375px/1280px journeys in `tests/test_memory_consolidation.py` (FR-013; SC-007; depends on T014 and the applicable Spec 022 shell contract).

## Phase 4: 2.6 investigation integration

- [ ] [T016] Publish typed finding/proposal/cycle evidence links for Spec 021 consumption through `atmem/consolidation/projection.py` and the shared evidence service; distinguish temporal contribution, observed exposure, possible effect and unknown causation (FR-006, FR-013–FR-014; depends on T014 and stable Spec 020/021 link contracts).
- [ ] [T017] Add investigation fixtures for expired delivery, unresolved conflict, unreviewed correction, unavailable semantic review and stale derived index in `tests/fixtures/product/026/`; prove exact evidence pivots and no causal or external-cleanup overclaim (FR-013–FR-017; SC-003–SC-004; depends on T016).

## Phase 5: 2.8.0 opt-in background consolidation

- [ ] [T018] Implement bounded, paginated and idempotent preview cycles with durable checkpoints in `atmem/consolidation/service.py`; bind scope, policy/capability versions, trusted evaluation time and source generations, and reconcile cancellation/crash/restart (FR-006–FR-007, FR-014; SC-005–SC-006; depends on T012–T014).
- [ ] [T019] Implement disabled, preview-only and separately activated deterministic modes in `atmem/consolidation/scheduler.py` and `atmem/maintenance.py`; require effect preview and current authorization, and never treat semantic proposals as automatically accepted (FR-007–FR-008, FR-014; SC-002, SC-005; depends on T018).
- [ ] [T020] Implement AtMem's minimized, scope-authorized AtBot health package and strict result validation in `atmem/control/atbot_companion.py`; enforce egress policy, ID subset, capability version, timeout/malformed fallback and final generation reload (FR-005–FR-007, FR-009, FR-016; SC-004, SC-006; depends on T002, T018 and stable Spec 019 egress contracts).
- [ ] [T021] Implement versioned semantic contradiction, possible-correction, possible-staleness and merge suggestions in `packages/atbot/src/atbot/health.py` with package-local tests; return typed proposals only and preserve deterministic fallback when no model/provider is configured (FR-005–FR-007, FR-009; SC-002, SC-004; depends on T020).
- [ ] [T022] Register consolidation queues, caches and prepared payloads with Spec 015/023 invalidation and deletion, distinguishing local invalidation, external acknowledgment and unknown propagation; verify membership-removal and forget races cannot dispatch stale review content (FR-009, FR-015–FR-016; SC-003, SC-006; depends on T018–T021 and Spec 023 propagation contracts).
- [ ] [T023] Expose schedule/policy preview, activation, last cycle, coverage and safe recovery controls through the common service, CLI and dashboard; a refresh must not renew evaluation or verification time (FR-007, FR-013–FR-014; SC-005, SC-007; depends on T019–T022).

## Phase 6: acceptance, performance and release evidence

- [ ] [T024] Extend Spec 001 deterministic and optional hosted benchmark profiles with temporal boundaries, historical recall, derivation, contradiction, poisoning, cross-scope and unavailable-AtBot cases; retain per-case evidence and actual provider/model identity (FR-017; SC-001–SC-006; depends on T010, T017, T021–T023).
- [ ] [T025] Run scan-throughput and retrieval-overhead measurements on declared hardware/corpus sizes, including direct measurement of Spec 019 policy plus Spec 026 temporal control overhead against the 35 ms p95 composed budget; report provider, network, retrieval-model and AtBot latency separately under `docs/implementation-evidence/026/` (FR-014, FR-017; SC-008; depends on T024).
- [ ] [T026] Complete API/CLI/MCP/dashboard parity, upgrade/recovery, deletion, accessibility, private/shared and applicable installed-host gates; run the two-cohort usability protocol and update `docs/current-status.md` with linked evidence and unsupported profiles (FR-013–FR-018; SC-001–SC-008; depends on T015, T022–T025).
- [ ] [T027] Register and execute the Spec 026 assertions declared in `spec.md` through `atmem/invariants/` and the installed-package invariant gate; report each optional provider/host configuration as proven, partially proven or unproven without changing INV-001–INV-011 semantics (FR-009–FR-018; SC-002–SC-008; depends on T026).

## Dependencies and delivery checkpoints

`T001 → T002 → T003`; `T004 → T005 → T006`; `T005 → T007`; `T004–T007 → T008 → T009`; `T006,T008,T009 → T010 → T011`; `T008–T010 → T012 → T013 → T014 → T015`; `T014 → T016 → T017`; `T012–T014 → T018 → T019`; `T002,T018 → T020 → T021`; `T018–T021 → T022 → T023`; `T010,T017,T021–T023 → T024 → T025 → T026 → T027`.

- **2.4 checkpoint**: T001–T011, limited to temporal foundation/manual behavior.
- **2.5 checkpoint**: T012–T015, Memory Health read/review experience.
- **2.6 checkpoint**: T016–T017, investigation consumption.
- **2.8.0 checkpoint**: T018–T027 plus required Spec 023 propagation evidence.

Completion of an earlier checkpoint does not imply the scheduled consolidation capability. No task authorizes release publication, external model egress or autonomous semantic mutation.
