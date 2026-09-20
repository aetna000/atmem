# Tasks: Temporal Memory Consolidation and Health Review

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/026/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews remain frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Status**: Planned, unchecked.

**Input**: [spec.md](spec.md), [plan.md](plan.md), [product requirements](../product-requirements.md).

**Prerequisites**: Existing Spec lifecycle/extraction foundations and the applicable Spec 022 shell for the native single-owner 2.4.0 profile. Stable Spec 012 memory-space membership is required for shared-space delivery, Spec 019 policy/package contracts for remote/provider egress, and Spec 023 for cross-provider propagation claims. Those later profiles do not block native single-owner health review. This work does not change the shipped 2.3.4b1 beta.

## Phase 1: Contract foundation and independent fixtures

- [ ] [T001] Freeze temporal kind, precision, assertion, derivation input/output and stable reason-code contracts in `atmem/temporal/models.py`, with schema tests in `tests/test_temporal_memory.py` covering missing time, timezone, partial dates and half-open intervals (FR-001–FR-004, FR-018; SC-001).
- [ ] [T002] Freeze health policy, cycle, finding, proposal, review and AtBot request/result contracts in `atmem/consolidation/models.py` and `packages/atbot/src/atbot/health.py`; prove AtBot outputs can only reference authorized input IDs (FR-005–FR-010, FR-014, FR-016; SC-002, SC-004; depends on T001).
- [ ] [T003] Define independent temporal-boundary, age, duplicate, overlap-conflict, staleness, poisoning, private/shared, crash/restart and unavailable-AtBot fixtures under `tests/fixtures/product/026/` before implementation, including expected reason codes and explicit non-claims (FR-001–FR-018; SC-001–SC-008; depends on T002).

## Phase 2: 2.4.0 temporal memory foundation

- [ ] [T004] Allocate canonical SQLite migrations through the Spec 010 registry for temporal assertions, generations and content-minimized health artifacts in `atmem/store/sqlite.py`; add real persisted upgrade, rollback/forward-recovery and legacy-unknown tests without enabling review or inferring dates on upgrade (FR-001, FR-006, FR-018; depends on T003).
- [ ] [T005] Implement interval, timezone, precision and trusted-time validation in `atmem/temporal/validation.py` and point-in-time/historical evaluation in `atmem/temporal/eligibility.py`; verify identical boundary reasons with virtual clocks (FR-001–FR-003; SC-001; depends on T004).
- [ ] [T006] Implement the local versioned derivation registry and `date-of-birth-to-age-v1` in `atmem/temporal/derivation.py`, including birthday, leap-day, timezone, insufficient-precision and non-persistence tests (FR-004; SC-001; depends on T005).
- [ ] [T007] Integrate negotiated temporal fields into Spec 006 extraction validation and review through `atmem/extract/models.py`, `atmem/extract/validation.py` and `atmem/extract/review.py`; ensure model-proposed timestamps cannot replace trusted source/receive time and ambiguous interpretations require review (FR-001–FR-006, FR-010, FR-018; SC-002; depends on T005).
- [ ] [T008] Extend Spec 015 lifecycle inspection and transitions through `atmem/lifecycle/service.py` without creating a second authority; join temporal projection, preserve immutable correction lineage and atomically invalidate registered derivatives after accepted changes (FR-003, FR-008, FR-010, FR-015; SC-002, SC-005; depends on T004–T007).
- [ ] [T009] Make conflict classification validity-overlap-aware in `atmem/extract/classify.py` and `atmem/extract/context.py`; retain non-overlapping history, create review findings for overlapping incompatibility and fail closed under stale generations (FR-005, FR-006, FR-010, FR-011; SC-002, SC-003; depends on T007–T008).
- [ ] [T010] Integrate explicit evaluation time, lifecycle/temporal generation revalidation, derived context values and unresolved-conflict withholding in `atmem/memory.py` and `atmem/retrieve/`; prove ineligible records cannot affect another candidate's rank or prepared context (FR-003, FR-004, FR-011, FR-012; SC-001, SC-003; depends on T006, T008–T009).
- [ ] [T011] Expose the same temporal inspection, historical-purpose and derivation results through `atmem/service/application.py`, CLI and `atmem/mcp/server.py`, with authenticated scope and negotiated compatibility tests (FR-003, FR-013, FR-016, FR-018; SC-001, SC-006; depends on T010; shared-space profile additionally requires stable Spec 012 contracts).

## Phase 3: 2.4.0 Memory Health review experience

- [ ] [T012] Implement bounded local exact-duplicate, deterministic-expiry and overlap-conflict analysis in `atmem/consolidation/deterministic.py`; age/recency alone must not establish invalidity (FR-005, FR-008, FR-011, FR-012; SC-003–SC-004; depends on T008–T010).
- [ ] [T013] Implement authenticated, generation-checked approve, edit-and-approve, reject and defer coordination in `atmem/consolidation/review.py`, delegating canonical effects to Specs 006/015 and preserving idempotent receipts and lineage (FR-006, FR-008, FR-010, FR-015; SC-002, SC-005; depends on T012).
- [ ] [T014] Implement the scope-safe Memory Health read model in `atmem/consolidation/projection.py` and common service operations in `atmem/service/application.py`; authorize item access, counts, filters, evidence joins and exports independently (FR-013, FR-016; SC-006; depends on T013; shared-space projection additionally requires stable Spec 012 feedback/membership contracts).
- [ ] [T015] Add Context → Memory Health summary, filters, explanations, timestamps and review actions to `atmem/control/assets/app.html`, `app.js` and `app.css`, reusing Spec 022 navigation and service authority; cover keyboard and 375px/1280px journeys in `tests/test_memory_consolidation.py` (FR-013; SC-007; depends on T014 and the applicable Spec 022 shell contract).

## Phase 4: 2.4.0 native single-owner opt-in background consolidation; later profile extensions

- [ ] [T018] Implement bounded, paginated and idempotent preview cycles with durable checkpoints in `atmem/consolidation/service.py`; bind scope, policy/capability versions, trusted evaluation time and source generations, and reconcile cancellation/crash/restart (FR-006–FR-007, FR-014; SC-005–SC-006; depends on T012–T014).
- [ ] [T019] Implement disabled, preview-only and separately activated deterministic modes in `atmem/consolidation/scheduler.py` and `atmem/maintenance.py`; require effect preview and current authorization, and never treat semantic proposals as automatically accepted (FR-007–FR-008, FR-014; SC-002, SC-005; depends on T018).
- [ ] [T020] Implement AtMem's minimized, scope-authorized AtBot health package and strict result validation in `atmem/control/atbot_companion.py`; enforce egress policy, ID subset, capability version, timeout/malformed fallback and final generation reload. The 2.4.0 profile may use no-egress/local execution only; remote/provider egress requires stable Spec 019 contracts (FR-005–FR-007, FR-009, FR-016; SC-004, SC-006; depends on T002, T018).
- [ ] [T021] Implement versioned semantic contradiction, possible-correction, possible-staleness and merge suggestions in `packages/atbot/src/atbot/health.py` with package-local tests; return typed proposals only and preserve deterministic fallback when no model/provider is configured (FR-005–FR-007, FR-009; SC-002, SC-004; depends on T020).
- [ ] [T022] Register consolidation queues, caches and prepared payloads with Spec 015 local invalidation and deletion for 2.4.0; extend to Spec 023 propagation and membership-removal races for later shared/provider profiles. Distinguish local invalidation, external acknowledgment and unknown propagation (FR-009, FR-015–FR-016; SC-003, SC-006; depends on T018–T021; expanded profile depends on Spec 012/023 contracts).
- [ ] [T023] Expose schedule/policy preview, activation, last cycle, coverage and safe recovery controls through the common service, CLI and dashboard; a refresh must not renew evaluation or verification time (FR-007, FR-013–FR-014; SC-005, SC-007; depends on T019–T022).

## Phase 5: 2.7 investigation integration for expanded profiles

- [ ] [T016] Publish typed finding/proposal/cycle evidence links for Spec 021 consumption through `atmem/consolidation/projection.py` and the shared evidence service; distinguish temporal contribution, observed exposure, possible effect and unknown causation (FR-006, FR-013–FR-014; depends on T014 and stable Spec 020/021 link contracts).
- [ ] [T017] Add investigation fixtures for expired delivery, unresolved conflict, unreviewed correction, unavailable semantic review and stale derived index in `tests/fixtures/product/026/`; prove exact evidence pivots and no causal or external-cleanup overclaim (FR-013–FR-017; SC-003–SC-004; depends on T016).

## Phase 6: acceptance, performance and release evidence

- [ ] [T024] Extend Spec 001 deterministic and optional hosted benchmark profiles with temporal boundaries, historical recall, derivation, contradiction, poisoning, cross-scope and unavailable-AtBot cases; retain per-case evidence and actual provider/model identity. The local 2.4.0 gate depends on T010 and T021–T023; investigation cases additionally depend on T017 (FR-017; SC-001–SC-006).
- [ ] [T025] Run scan-throughput and retrieval-overhead measurements on declared hardware/corpus sizes for the native single-owner 2.4.0 profile. When Spec 019 policy is enabled in a later provider profile, directly measure its combined overhead with Spec 026 temporal control against the 35 ms p95 composed budget; report provider, network, retrieval-model and AtBot latency separately under `docs/implementation-evidence/026/` (FR-014, FR-017; SC-008; depends on T024).
- [ ] [T026] Complete API/CLI/MCP/dashboard parity, upgrade/recovery, deletion, accessibility and applicable installed-host gates for the native single-owner 2.4.0 profile; run the two-cohort usability protocol and update `docs/current-status.md` with linked evidence and unsupported profiles. Repeat access/coverage gates when shared and provider profiles are added (FR-013–FR-018; SC-001–SC-008; depends on T015, T022–T025).
- [ ] [T027] Register and execute the Spec 026 assertions declared in `spec.md` through `atmem/invariants/` and the installed-package invariant gate; report each optional provider/host configuration as proven, partially proven or unproven without changing INV-001–INV-011 semantics (FR-009–FR-018; SC-002–SC-008; depends on T026).

## Dependencies and delivery checkpoints

`T001 → T002 → T003`; `T004 → T005 → T006`; `T005 → T007`; `T004–T007 → T008 → T009`; `T006,T008,T009 → T010 → T011`; `T008–T010 → T012 → T013 → T014 → T015`; `T012–T014 → T018 → T019`; `T002,T018 → T020 → T021`; `T018–T021 → T022 → T023`; `T010,T021–T023 → T024 → T025 → T026 → T027` for the native single-owner profile. Later investigation integration follows `T014 → T016 → T017 → T024` for its added fixtures; shared/provider/propagation profiles also require their named 012/019/023 contracts.

- **2.4.0 checkpoint**: T001–T015 and T018–T027 for the native single-owner profile, with no remote egress or external propagation claim. Optional AtBot runs only inside a permitted local/no-egress profile. Every local assertion must be backed by the corresponding installed-artifact evidence.
- [ ] [T028] **2.3.4 checkpoint**: the base AtMem wheel installs pinned AtFlows `0.1.1`, preserves the `atmem[atflows]` alias and verifies both through installed-artifact metadata and an opt-in read-only evidence-lead smoke gate. The versioned report has a stable correlated/unverified JSON shape and a human CLI view. `atmem status` and `atflows status` are read-only; standalone setup may print a separate one-time credential; delegated login uses AtMem-owned accounts and never recovers an existing password. Installation must not start an AtFlows server or change AtBot behavior (FR-016, FR-018; local stable-release gates are recorded under `docs/implementation-evidence/026/`; remote release gates remain pending). These release gates are tracked in the release roadmap; they do not deliver the Memory Health queue, and absence of a running AtFlows server never blocks the 2.4.0 health cycle.
- **2.5–2.6 checkpoints**: repeat the applicable T011/T014/T020/T022/T026/T027 gates for authenticated shared spaces and then governed provider connections.
- **2.7 checkpoint**: T016–T017, investigation consumption.
- **2.8.0 checkpoint**: repeat T022/T024–T027 with required Spec 023 cross-provider propagation evidence.

Completion of the 2.4.0 native single-owner checkpoint does not imply shared-space, remote-provider, investigation or cross-provider propagation coverage. No task authorizes release publication, external model egress or autonomous semantic mutation.
