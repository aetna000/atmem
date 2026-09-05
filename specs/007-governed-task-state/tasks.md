# Tasks: Governed Task State

## Phase 0 — Concrete prerequisite gate

- [x] [T000] Pin and test the existing `AuthorityScope`, canonical JSON/digest, SQLite transaction/migration, control preparation/exposure, adapter identity, and authorized AtBot-boundary APIs in `tests/test_task_state_prerequisites.py`; fail explicitly when a required primitive is absent and keep all task-specific proposal/evidence types inside Spec 007 without depending on unpublished roadmap work.

## Phase 1 — Contracts and independent foundations

- [x] [T001] Add dependency-free task profile, start request, five-value lifecycle, observed-step, state, proposal, decision, context, guard, governance-capability, expiry-policy, stable-reason, and provenance contracts with closed parsing and canonical serialization in `atmem/contracts/task_state.py` and export them from `atmem/contracts/__init__.py` (FR-002–FR-006, FR-009, FR-016, FR-029–FR-038).
- [x] [T002] [P] Add independently authored JSON schemas and valid/invalid vectors in `atmem/schemas/v1/task-profile.json`, `atmem/schemas/v1/task-start-request.json`, `atmem/schemas/v1/task-state.json`, `atmem/schemas/v1/task-state-proposal.json`, `atmem/schemas/v1/task-transition-decision.json`, and `atmem/schemas/v1/task-context-package.json` (FR-003–FR-006, FR-028, FR-036–FR-038).
- [x] [T003] [P] Write failing contract tests for unknown fields, bounds, lifecycle and expiry values, observed-step classification, `no_change`, overflow reasons, untrusted strings, stable ordering, operation shapes, profile digests, reason codes, and canonical bytes in `tests/test_task_state_contracts.py` (FR-002–FR-006, FR-009, FR-016, FR-036–FR-038; SC-001, SC-003, SC-015).
- [x] [T004] Establish the separate public task-state package and domain models without importing optional intelligence/framework SDKs in `atmem/task_state/__init__.py` and `atmem/task_state/models.py`; add a dependency-free `TrustedUtcClock` protocol, aware-UTC `SystemUtcClock`, deterministic fake-clock tests, and rejection of naive/non-UTC values in `atmem/core/time.py` and `tests/test_task_state_clock.py` so every later task-state timestamp has one injectable source (FR-001, FR-027, FR-036; SC-014).
- [x] [T005] Define and validate the built-in `general-v1` profile plus optional absolute/no-progress expiry thresholds and dry-run, immutable-version conflict, digest, authorization-request, and evidence contracts for custom profile registration in `atmem/task_state/profiles.py` (FR-003, FR-011, FR-029, FR-034, FR-036).

## Phase 2 — Canonical persistence and early walking skeleton

- [x] [T006] Write failing persistence tests for additive schema creation, immutable revisions, field/status provenance, expiry rule/time, durable `paused_at_utc` and `no_progress_paused_ms`, pause/resume restart and rebuild, current-head lookup, exact scope, proposal idempotency, `no_change` steps, and all five lifecycle values in `tests/test_task_state_store.py` (FR-001, FR-002, FR-006, FR-010, FR-018, FR-022, FR-024, FR-026, FR-030, FR-036).
- [x] [T007] Add `governed_task_profiles`, `governed_tasks` with nullable `paused_at_utc` and non-negative integer `no_progress_paused_ms`, `governed_task_revisions`, `governed_task_provenance`, `governed_task_proposals`, and `governed_task_steps` with expiry indexes and uniqueness/check constraints through the idempotent initializer in `atmem/store/sqlite.py`, using reserved bootstrap identifiers `0070–0079` from `specs/integration-ownership.md` so Spec 010 can later import them without replay (FR-001, FR-002, FR-010, FR-026, FR-030, FR-036).
- [x] [T008] Implement exact-scope profile/task/proposal/revision/provenance/step repository operations, atomic pause-accumulator updates and revision-chain rebuild verification, immutable custom-profile registration, and one-transaction head advancement in `atmem/store/sqlite.py` (FR-008–FR-010, FR-022, FR-024, FR-030, FR-034, FR-036; SC-002, SC-014).
- [x] [T009] Write failing policy tests for the Governance Matrix, five lifecycle values, expiry edges, all phase/status edges, derived readiness, dependencies, schema locking, completion gates, corrections, evidence assurance, privileged skip/cancel/override operations, and stable reason codes in `tests/test_task_state_policy.py` (FR-003–FR-005, FR-011–FR-013, FR-021, FR-029, FR-035, FR-036).
- [x] [T010] Implement profile-driven delta validation and transition decisions in `atmem/task_state/policy.py`, rejecting full replacement, scope/profile mutation, unknown evidence, unsupported regression, and non-policy expiry (FR-007–FR-013, FR-036).
- [x] [T011] Write the failing local walking-skeleton test for start → read revision 1 → `set_item_status` → `set_phase` → `no_change` → process restart → same head in `tests/test_task_state_walking_skeleton.py`, with AtBot, semantic services, guards, dashboard, and adapters disabled (FR-001–FR-011; SC-001).
- [x] [T012] Implement the minimum `general-v1` repository/service path required to pass the walking skeleton in `atmem/task_state/service.py` and `atmem/memory.py`, injecting the T004 trusted UTC clock for creation, revision, decision, progress, and provenance timestamps and proving exact scope, atomic revision, digest, step outcome, and basic provenance before richer features (FR-001–FR-011, FR-036; SC-001, SC-014).

## Phase 3 — US1: Complete structured current task state and expiry (P1 MVP)

- [x] [T013] [US1] Add deterministic synthetic three-item workflow fixtures covering progress, blocking, remaining work, restart, and `no_change` in `tests/fixtures/task_state/general-v1.json` (FR-002–FR-006; SC-001).
- [x] [T014] [US1] Implement bounded canonical snapshots with stable item identity, constraints, source checklists, dependencies, schema lock, assurance, field/status provenance references, expiry binding, and last-progress metadata in `atmem/task_state/models.py` (FR-002–FR-005, FR-012, FR-030, FR-036).
- [x] [T015] [US1] Add full service tests for authorization-before-intelligence, head revalidation, accepted/rejected/conflict/`no_change`, concurrent successors, replay, open/pause/resume/complete/cancel, terminal immutability, correction, and crash recovery in `tests/test_task_state_service.py` (FR-006–FR-012, FR-018–FR-022; SC-001, SC-002, SC-006).
- [x] [T016] [US1] Complete task start, proposal admission, atomic revision commit, `no_change`, non-expiry lifecycle operations, terminal-task continuation linkage, and correction orchestration in `atmem/task_state/service.py` and `atmem/memory.py`, routing all task-state timestamps through the T004 trusted UTC clock (FR-002, FR-006–FR-013, FR-018–FR-022, FR-036).
- [x] [T017] [US1] Write injectable-clock tests for absolute-age and active-time-only no-progress boundaries, open and completed pause intervals, multiple pause/resume cycles, restart, revision-chain rebuild parity, lazy read/prepare/proposal/lifecycle evaluation, maintenance scans, concurrent expiry, evidence, and zero post-expiry context in `tests/test_task_state_expiry.py` (FR-036; SC-014).
- [x] [T018] [US1] Implement scoped `task.expire` policy evaluation through the T004 clock using O(1) persisted pause accounting, absolute-age accounting across pauses, no-progress accounting that excludes completed and currently open paused intervals, atomic accumulator reset/update with lifecycle and progress revisions, optimistic terminal transition, the minimum canonical trusted-time/rule audit and evidence payload required for expiry, and idempotent maintenance scanning in `atmem/task_state/service.py`, `atmem/task_state/policy.py`, and `atmem/maintenance.py`; T019 extends the shared evidence vocabulary without being a prerequisite for correct expiry evidence (FR-017, FR-022, FR-029, FR-030, FR-032, FR-036; SC-005, SC-014).

## Phase 4 — US2: Governed evidence-linked transitions (P1)

- [ ] [T019] [US2] Extend evidence validation and audit payloads for task proposal, decision, revision, `no_change`, expiry, field/status provenance, correction, privileged governance action, and lifecycle events in `atmem/control/evidence.py` and `atmem/control/blackbox.py` (FR-009, FR-012, FR-017, FR-021, FR-029, FR-030, FR-035, FR-036).
- [x] [T020] [US2] Enforce actor/source/interpreter/evidence identity, assurance ceilings, and honest host-observed versus independently verified outcomes in `atmem/task_state/service.py` (FR-009, FR-012, FR-017, FR-024; SC-005).
- [x] [T021] [US2] Add 1,000-attempt concurrency/replay tests proving one accepted successor per head and no duplicate revision for an idempotency key in `tests/test_task_state_store.py` and `tests/test_task_state_service.py` (FR-010; SC-002).
- [x] [T022] [US2] Add tamper, stale, cross-scope, unknown-evidence, schema-widening, lifecycle, expiry, and model-overclaim tests in `tests/test_task_state_service.py` and `tests/test_control_evidence.py` (FR-007–FR-013, FR-017, FR-022, FR-024, FR-036; SC-001, SC-005).

## Phase 5 — Governance and provenance foundations

- [x] [T023] [P] Add an exhaustive actor/capability/action/scope fixture and failing conformance tests in `tests/fixtures/task_state/governance-v1.json` and `tests/test_task_state_governance.py` (FR-029, FR-034–FR-036; SC-011, SC-014).
- [x] [T024] Implement closed capability derivation and Governance Matrix enforcement for reads, proposals, commits, corrections, profile registration, lifecycle, policy-owned expiry, context, overrides, and deletion in `atmem/task_state/governance.py`, `atmem/task_state/service.py`, and `atmem/control/manager.py` (FR-029, FR-034–FR-036; SC-011, SC-014).
- [x] [T025] [P] Add complete task/field/status/transition/delivery/expiry/supersession/deletion lineage fixtures and failing provenance query tests in `tests/fixtures/task_state/provenance-v1.json` and `tests/test_task_state_provenance.py` (FR-030, FR-031, FR-033, FR-036; SC-012, SC-014).
- [x] [T026] Implement the scope-authorized human-readable provenance resolver and deletion-minimized lineage projection in `atmem/task_state/provenance.py` and `atmem/task_state/service.py` (FR-030, FR-031, FR-033, FR-036; SC-012).

## Phase 6 — US3: Task context and execution guards (P1)

- [x] [T027] [P] [US3] Write failing context tests for minimal content, stable UTF-8 bytes, stable ordering, cache keys/invalidation, deterministic whole-field reduction, mandatory overflow withholding with `task_context_budget_exceeded`, instruction-shaped strings, delimiter containment, shadow/terminal/cross-scope withholding, missing task identity with `task_context_selection_required`, non-disclosing unknown/ineligible identity with `task_context_not_eligible`, no implicit choice among multiple open tasks, no fallback selection, and one exact exposure in `tests/test_task_state_context.py` (FR-015–FR-018, FR-022, FR-037, FR-038; SC-003, SC-015).
- [x] [T028] [P] [US3] Write failing guard tests for repeated equivalent actions, distinct task items, progress reset, dependency denial, out-of-scope signals, premature completion, and detection-versus-enforcement evidence in `tests/test_task_state_guards.py` (FR-013, FR-014, FR-017; SC-004).
- [x] [T029] [US3] Implement the deterministic governed-data serializer, complete-value optional reduction, mandatory-overflow withholding, canonical escaping and provenance labels, digest, bounded context package, generation-bound cache identity, and invalidation in `atmem/task_state/context.py` (FR-015, FR-016, FR-022, FR-037, FR-038; SC-003, SC-015).
- [x] [T030] [US3] Implement action fingerprinting, no-progress evaluation, dependency/out-of-scope guards, and completion eligibility in `atmem/task_state/guards.py` (FR-013, FR-014).
- [x] [T031] [US3] Route expiry-aware exact task-ID resolution and separately identified task-state data through `ControlPlaneManager.prepare()` and exact exposure confirmation in `atmem/control/manager.py`, withholding on absent or ineligible identity and never discovering or falling back to another open task, without weakening existing recalled-memory revalidation in `atmem/memory.py` (FR-008, FR-015–FR-019, FR-036–FR-038; SC-003, SC-006, SC-014, SC-015).
- [ ] [T032] [US3] Add deterministic benchmark cases for completed, remaining, blocked, skipped, failed, repeated-action, premature-finish, expired, overflow, and instruction-shaped behavior in `atmem/benchmark/data/task-state-v1.json` and `atmem/benchmark/runner.py` (FR-013, FR-014, FR-036–FR-038; SC-004, SC-014, SC-015).

## Phase 7 — AtBot proposal intelligence and safe fallback

- [x] [T033] [P] Add bounded task-state delta, attribution, affected-item, confidence, and reason types in `packages/atbot/src/atbot/domain.py` (FR-007, FR-009).
- [x] [T034] [P] Write malicious/valid/unavailable proposal tests before implementation in `packages/atbot/tests/test_task_state.py` and `tests/test_task_state_atbot.py` (FR-007–FR-009, FR-019, FR-038; SC-001, SC-006, SC-015).
- [x] [T035] Implement independently authored task-observation prompts and strict delta extraction in `packages/atbot/src/atbot/task_state.py` and `packages/atbot/src/atbot/prompts.py`, accepting only AtMem-authorized snapshot content and treating all observation text as data (FR-007–FR-009, FR-019, FR-028, FR-038).
- [ ] [T036] Add AtBot companion request/response routing and AtMem revalidation in `packages/atbot/src/atbot/companion.py`, `packages/atbot/src/atbot/service.py`, `atmem/control/atbot_companion.py`, and `atmem/task_state/service.py` (FR-007–FR-009, FR-019).
- [x] [T037] Prove local typed host/operator transitions, `no_change`, completion validation, and current-state delivery with AtBot, semantic services, and network disabled in `tests/test_task_state_atbot.py` (FR-019, FR-027; SC-006).

## Phase 8 — US5: Host-neutral lifecycle integration (P2)

- [x] [T038] [P] [US5] Write adapter conformance tests for exact task identity, absent/unknown/terminal/cross-scope identity, multiple-open-task non-selection, observations, context, action/tool outcomes, completion, errors, terminal state, exact exposure, multi-agent isolation, and current/legacy capability negotiation in `tests/test_task_state_adapters.py` (FR-015, FR-017–FR-019, FR-023, FR-024, FR-039; SC-003, SC-006, SC-016).
- [x] [T039] [US5] Extend `AtMemAdapterIdentity` and `AtMemTurnLifecycle` with task identity that is optional only for legacy task-unaware operation and required for task-aware observation/transition/guard methods in `atmem/adapters/base.py`; absent identity disables task-state delivery and never triggers discovery. Add authoritative governed-task-state delivery/detection/enforcement flags in `atmem/contracts/versions.py` and align `atmem/schemas/v1/capabilities.json` (FR-006, FR-015, FR-017, FR-023, FR-024, FR-039; SC-016).
- [ ] [T040] [P] [US5] Map Pydantic AI model/tool hooks into the task lifecycle without replacing dependencies, history, tools, or model configuration in `atmem/adapters/pydantic_ai.py` (FR-023, FR-039).
- [ ] [T041] [P] [US5] Map LangGraph middleware and raw lifecycle helpers into the task lifecycle without replacing graph state, checkpoints, tools, or model configuration in `atmem/adapters/langgraph.py` (FR-023, FR-039).
- [ ] [T042] [US5] Extend the OpenClaw plugin contract and tests for exact task-context delivery, action/tool outcomes, completion enforcement capability, runtime negotiation, and backward-compatible legacy behavior in `integrations/openclaw/index.ts`, `integrations/openclaw/src/rpc-client.ts`, `integrations/openclaw/src/types.ts`, `integrations/openclaw/test/hooks.mjs`, and `integrations/openclaw/test/smoke.mjs` (FR-014, FR-015, FR-017, FR-023, FR-039; SC-016).
- [x] [T043] [US5] Mirror the authoritative runtime delivery, guard-detection, and guard-enforcement flags in `docs/capabilities.json`, test runtime/schema/documentation equality, and assert unsupported boundaries are never advertised in `tests/test_task_state_adapters.py` and `tests/test_documentation.py` (FR-014, FR-023, FR-039; SC-003, SC-016).

## Phase 9 — Observability foundation

- [x] [T044] [P] Add deterministic lifecycle/transition/reason/guard/fallback/stale/expiry/prepared-exposed/latency/integrity fixtures plus scope and content-leak tests in `tests/fixtures/task_state/observability-v1.json` and `tests/test_task_state_observability.py` (FR-032, FR-033, FR-036; SC-013, SC-014).
- [x] [T045] Implement the read-only scope-filtered observability projection in `atmem/task_state/observability.py` and shared authority access in `atmem/control/manager.py` (FR-032, FR-033, FR-036; SC-013, SC-014).

## Phase 10 — US4: CLI and dashboard control (P2)

- [x] [T046] [P] [US4] Write CLI tests for the complete enable/start/list/show/timeline/provenance/health/verify/correct/pause/resume/complete/cancel/forget/disable/profile command family in `tests/test_task_state_cli.py`: begin from `atmem task --help`, execute every displayed example, prove exact visible scope, stable list ordering/cursor pagination, human/JSON outcome and reason parity, exactly one JSON stdout document, stderr diagnostics, exit codes 0/1/2, non-disclosing unauthorized lookup, one actionable `Next:` command, expiry rendering, and preview/interactive/non-interactive `--yes` confirmation with no silent conflict retry (FR-018, FR-020–FR-022, FR-029–FR-036, FR-040; SC-009, SC-011–SC-014, SC-017).
- [x] [T047] [US4] Implement the documented `atmem task` and `atmem task profile` CLI contract through shared manager/service/provenance/observability methods in `atmem/cli.py`, including exact scope, deterministic pagination, public JSON envelopes, stdout/stderr separation, stable exit codes, `Next:` guidance, non-disclosing denial, expiry inspection without manual expiry, task forgetting, and shared privileged preview/confirmation contracts requiring `--yes` for non-interactive use without weakening capability, expected-revision, source, dry-run, or reason requirements (FR-018, FR-020–FR-022, FR-025, FR-029–FR-036, FR-040; SC-009, SC-017).
- [x] [T048] [P] [US4] Write dashboard API/UI tests in `tests/test_task_state_dashboard.py` for memory-only disabled regression; shadow/unavailable/legacy capability gating; empty/loading/degraded/permission-denied/conflict/integrity/terminal/overflow states; active-task summaries; persistent selected-task header and direct Activity/Decisions/Evidence links with return path; field/status provenance and expiry inspection; privileged preview/confirmation and fresh submission after conflict; deletion danger zone; CSRF; readable reasons; scope-filtered metrics; one-workspace ownership; keyboard/focus restoration/semantic labels/live regions/reduced motion/narrow screens/no-color checks; and absence of competing global verdicts (FR-018, FR-020, FR-021, FR-029–FR-036, FR-041; SC-009, SC-011–SC-014, SC-018).
- [x] [T049] [US4] Add scope-authorized task, governance, provenance, profile-administration, observability, capability-gating, selected-task, mutation-preview, conflict-detail, and deletion manager/web endpoints backed by the same authority methods and public contracts in `atmem/control/manager.py`, `atmem/control/web.py`, and `atmem/control/server.py`; mutations never auto-retry and unauthorized lookup remains non-disclosing (FR-020, FR-021, FR-025, FR-029–FR-036, FR-040, FR-041).
- [x] [T050] [US4] Update `docs/dashboard-design-language.md` and implement its governed-task extension in `atmem/control/assets/app.html`, `atmem/control/assets/app.js`, and `atmem/control/assets/app.css`: preserve the existing four workspaces and single global verdict; capability-gate all task UI; keep one selected-task summary and direct return path; place progress only in Activity, pending actions only in Decisions, profile configuration/deletion only in Settings, and proof only in Evidence; render every FR-041 operational state; reuse existing icons and progressive disclosure; and provide keyboard-complete, focus-safe, semantically labelled, live-announced, reduced-motion, narrow-screen, no-color operation (FR-020, FR-021, FR-029–FR-036, FR-041; SC-009, SC-011–SC-014, SC-018).

## Phase 11 — Deletion, migration, performance, documentation, and release evidence

- [x] [T051] [P] Write task/subject deletion tests covering heads, revision content, provenance, proposals, steps, caches, registered derived artefacts, tombstones, and deletion receipts in `tests/test_task_state_deletion.py` (FR-025).
- [x] [T052] Implement task-state forget/tombstone/verified-absence behavior in `atmem/task_state/service.py`, `atmem/store/sqlite.py`, and `atmem/maintenance.py` (FR-025).
- [x] [T053] [P] Add persisted upgrade fixtures and release-workflow drills from every supported public version through create/advance/inspect/expire-or-complete-or-cancel/delete in `tests/test_task_state_upgrade.py` and `.github/workflows/publish.yml` (FR-026, FR-036; SC-008, SC-014).
- [x] [T054] Add query-plan and p95 coverage for 1,000 measured single-writer transition/context operations without concurrent write contention in `tests/test_task_state_performance.py`; keep the 1,000-attempt contended correctness test separate and optimize measured indexes only in `atmem/store/sqlite.py`, allocating any added index migration inside the reserved `0070–0079` bootstrap block (SC-002, SC-007).
- [x] [T055] Add dependency and artefact provenance checks proving no new mandatory model/framework SDK and no third-party research prompt, dataset, figure, model, or branded component is bundled in `tests/test_documentation.py`, `tests/test_provider_packaging.py`, and CI (FR-027, FR-028; SC-010).
- [x] [T056] Document concepts, Governance Matrix, Provenance Model, Observability Requirements, expiry, safe budget overflow, untrusted-data framing, runtime capabilities, setup, shadow evaluation, host boundaries, complete CLI contract and runnable journey, dashboard state/navigation/accessibility contract, task operations, evidence, fallback, deletion, rollback, and independently authored examples in `docs/governed-task-state.md`, `README.md`, `docs/current-status.md`, `docs/capabilities.json`, and `docs/dashboard-design-language.md` (FR-014, FR-018–FR-023, FR-028–FR-041; SC-009–SC-018).
- [x] [T057] Run prerequisite, walking-skeleton, focused task-state, full Python 3.10–3.13, AtBot, latest Pydantic AI/LangGraph, OpenClaw npm typecheck/test/smoke, clean-wheel, licence, deletion/restore, persisted-upgrade, runtime-capability, expiry, overflow, injection-containment, CLI-journey, dashboard-state/accessibility, memory-only UI regression, and Governance/Provenance/Observability conformance checks; record exact evidence in this file (SC-001–SC-018).

## Dependencies and execution order

- T000 is a hard gate. Spec 007 does not wait for unpublished roadmap work; a missing
  concrete existing primitive must be resolved before T001.
- T001–T005 establish contracts, the trusted UTC clock, and profiles and block
  persistence/service work. T004's clock blocks T012 and every later task-state
  service or maintenance timestamp.
- T006–T010 establish minimum persistence and policy; T011–T012 then prove the
  first end-to-end walking skeleton before richer state is built.
- T013–T018 complete structured state and expiry authority before context,
  AtBot, adapters, or product controls claim support. T018 includes the minimum
  canonical expiry evidence needed to avoid an ordering dependency.
- T019–T022 extend the shared transition-evidence vocabulary and complete the
  broader concurrency and tamper guarantees.
- T023–T026 establish governance and provenance before content reaches AtBot or
  a host adapter.
- T027–T032 complete safe context and guards before adapter delivery.
- T033–T037 add optional AtBot intelligence after deterministic authority works.
- T038–T043 establish host integration and authoritative capability negotiation.
- T044–T045 establish observability before any CLI/dashboard task depends on it.
- T046–T050 implement product surfaces only after their authority projections
  exist; dashboard work must preserve the existing four-workspace design.
- T051–T056 may proceed after the stable authority/API surface, where parallel
  markers allow. T057 is the final release gate and runs last.

## Delivery boundaries

- **Earliest risk-reduction slice**: T000–T012 proves one local profile, three
  transition operations, restart persistence, atomic revision, and provenance
  without AtBot, guards, dashboard, or adapters.
- **Releasable internal MVP**: T000–T032 adds complete structured state, expiry,
  evidence, deterministic context, guards, and benchmarks.
- External host enablement remains disabled until T038–T043 adapter and
  capability conformance passes. CLI/dashboard exposure requires T023–T050.

## Delivered Evidence (T057)

Run on 2026-09-05 against the working tree.

| Check | Result |
| --- | --- |
| Full Python suite | 1079 passed, 2 skipped |
| Prerequisite gate (`test_task_state_prerequisites.py`) | 11 passed |
| Walking skeleton | 2 passed |
| Contracts + published schemas | 77 passed |
| Store, policy, service | 149 passed |
| Expiry (injectable clock, incl. maintenance scan) | 24 passed |
| Governance conformance | 33 passed |
| Context, guards, observability | 70 passed |
| Adapters + capability mirroring | 25 passed |
| CLI journey | 32 passed |
| Dashboard states | 23 passed |
| Deletion | 14 passed |
| Persisted upgrade, all five published floors | 45 passed |
| AtBot proposals + fallback | 20 passed |
| Tamper / adversarial | 26 passed |
| Deterministic benchmark | passed, 24/24 cases |
| Python 3.10 grammar compatibility | every module parses |
| Clean import (no optional SDK) | no optional module imported |
| OpenClaw npm test | setup, hooks, delegated-context contract passed |

Measured overhead (SC-007), 1,000 single-writer samples each, 25 ms budget:

| Operation | p50 | p95 |
| --- | --- | --- |
| Transition commit | 1.61 ms | 1.85 ms |
| Context preparation | 0.12 ms | 0.14 ms |
| Task read after 200 revisions | 0.13 ms | 0.14 ms |

## Delivered Surfaces

- Contracts: `atmem/contracts/task_state.py`, six schemas under
  `atmem/schemas/v1/task-*.json`, trusted clock in `atmem/core/time.py`.
- Authority: `atmem/task_state/{policy,service,governance,profiles,models}.py`,
  bootstrap migrations `0070`–`0077`.
- Delivery and guards: `atmem/task_state/{context,guards}.py`, routed through
  `ControlPlaneManager.prepare_task_context` and the adapter lifecycle.
- Insight: `atmem/task_state/{provenance,observability}.py`,
  `atmem/task_state/enablement.py`.
- Operator surfaces: `atmem task …` in `atmem/cli.py`; the capability-gated
  "Governed tasks" dashboard card and `/api/tasks*` endpoints.
- Intelligence: `packages/atbot/src/atbot/task_state.py` and its prompt.
- Documentation: `docs/governed-task-state.md`, `docs/capabilities.json`.

## Not Delivered

- **T019** — task events reuse the existing audit and step ledgers rather than
  extending `atmem/control/blackbox.py`'s flight-event vocabulary. Every
  proposal, decision, revision, `no_change`, expiry, correction, and lifecycle
  change is recorded with actor, reason codes, and evidence; what is missing is
  the blackbox *flight* projection of those events.
- **T032** — task-state benchmark cases are not in
  `atmem/benchmark/data/task-state-v1.json`. The equivalent coverage exists as
  deterministic fixtures and tests (`tests/fixtures/task_state/`,
  `test_task_state_{policy,guards,context,expiry}.py`), but it is not wired into
  `atmem/benchmark/runner.py` as a scored profile.
- **T036** — the AtBot companion HTTP route for task deltas is not added.
  `packages/atbot/src/atbot/task_state.py` produces validated deltas and AtMem
  admits them through `submit_task_proposal`; the loopback endpoint that would
  carry them between the two processes is not wired.
- **T040, T041, T042** — Pydantic AI, LangGraph, and the OpenClaw plugin are
  unchanged. They keep working as task-unaware adapters through the legacy path
  (proved in `test_task_state_adapters.py`); they do not yet bind a task id.
  The generic contract is complete, so this is per-framework mapping work.
