# Tasks: Governed Task State

## Phase 1 — Contracts and independent foundations

- [ ] [T001] Add dependency-free task profile, start request, five-value lifecycle, observed-step, state, proposal, decision, context, guard, governance-capability, and provenance contracts with closed parsing and canonical serialization in `atmem/contracts/task_state.py` and export them from `atmem/contracts/__init__.py` (FR-002–FR-006, FR-009, FR-016, FR-029–FR-035).
- [ ] [T002] [P] Add independently authored JSON schemas and valid/invalid vectors in `atmem/schemas/v1/task-profile.json`, `atmem/schemas/v1/task-start-request.json`, `atmem/schemas/v1/task-state.json`, `atmem/schemas/v1/task-state-proposal.json`, `atmem/schemas/v1/task-transition-decision.json`, and `atmem/schemas/v1/task-context-package.json` (FR-003–FR-006, FR-028).
- [ ] [T003] [P] Write failing contract tests for unknown fields, bounds, lifecycle values, observed-step classification, `no_change`, stable ordering, operation shapes, profile digests, reason codes, and canonical bytes in `tests/test_task_state_contracts.py` (FR-002–FR-006, FR-009, FR-016; SC-001, SC-003).
- [ ] [T004] Establish the separate public task-state package and domain models without importing optional intelligence/framework SDKs in `atmem/task_state/__init__.py` and `atmem/task_state/models.py` (FR-001, FR-027).
- [ ] [T005] Define and validate the built-in `general-v1` profile plus dry-run, immutable-version conflict, digest, authorization-request, and evidence contracts for custom profile registration in `atmem/task_state/profiles.py` (FR-003, FR-011, FR-029, FR-034).

## Phase 2 — Canonical persistence and transition authority

- [ ] [T006] Write failing persistence tests for additive schema creation, immutable revisions, field/status provenance, current-head lookup, exact scope, proposal idempotency, `no_change` steps, and all five lifecycle values in `tests/test_task_state_store.py` (FR-001, FR-002, FR-006, FR-010, FR-018, FR-022, FR-024, FR-026, FR-030).
- [ ] [T007] Add `governed_task_profiles`, `governed_tasks`, `governed_task_revisions`, `governed_task_provenance`, `governed_task_proposals`, and `governed_task_steps` with indexes and uniqueness constraints through the idempotent initializer in `atmem/store/sqlite.py` (FR-001, FR-002, FR-010, FR-026, FR-030).
- [ ] [T008] Implement exact-scope profile/task/proposal/revision/provenance/step repository operations, immutable custom-profile registration, and one-transaction head advancement in `atmem/store/sqlite.py` (FR-008–FR-010, FR-022, FR-024, FR-030, FR-034; SC-002).
- [ ] [T009] Write failing policy tests for the Governance Matrix, five lifecycle values, all phase/status edges, derived readiness, dependencies, schema locking, completion gates, corrections, evidence assurance, privileged skip/cancel/override operations, and stable reason codes in `tests/test_task_state_policy.py` (FR-003–FR-005, FR-011–FR-013, FR-021, FR-029, FR-035).
- [ ] [T010] Implement profile-driven delta validation and transition decisions in `atmem/task_state/policy.py`, rejecting full replacement, scope/profile mutation, unknown evidence, and unsupported regression (FR-007–FR-013).
- [ ] [T011] Write failing service tests for authorization-before-intelligence, head revalidation, accepted/rejected/conflict/`no_change` outcomes, concurrent successors, replay, open/pause/resume/complete/cancel/expire, terminal immutability, and crash recovery in `tests/test_task_state_service.py` (FR-006–FR-012, FR-018–FR-019, FR-022; SC-001, SC-002, SC-006).
- [ ] [T012] Implement task start, proposal admission, atomic revision commit, `no_change`, five-state lifecycle, terminal-task continuation linkage, and correction orchestration in `atmem/task_state/service.py` and expose it through `atmem/memory.py` (FR-002, FR-006–FR-013, FR-018–FR-022).

## Phase 3 — US1: Structured current task state (P1 MVP)

- [ ] [T013] [US1] Add deterministic synthetic three-item workflow fixtures covering progress, blocking, remaining work, restart, and `no_change` in `tests/fixtures/task_state/general-v1.json` (FR-002–FR-006; SC-001).
- [ ] [T014] [US1] Implement bounded canonical snapshots with stable item identity, constraints, source checklists, dependencies, schema lock, assurance, field/status provenance references, and last-progress metadata in `atmem/task_state/models.py` (FR-002–FR-005, FR-012, FR-030).
- [ ] [T015] [US1] Add start/read/advance/`no_change` restart integration coverage against a fresh SQLite store in `tests/test_task_state_service.py` (FR-002–FR-006, FR-010; SC-001).

## Phase 4 — US2: Governed evidence-linked transitions (P1)

- [ ] [T016] [US2] Extend evidence validation and audit payloads for task proposal, decision, revision, `no_change`, field/status provenance, correction, privileged governance action, and lifecycle events in `atmem/control/evidence.py` and `atmem/control/blackbox.py` (FR-009, FR-012, FR-017, FR-021, FR-029, FR-030, FR-035).
- [ ] [T017] [US2] Enforce actor/source/interpreter/evidence identity, assurance ceilings, and honest host-observed versus independently verified outcomes in `atmem/task_state/service.py` (FR-009, FR-012, FR-017, FR-024; SC-005).
- [ ] [T018] [US2] Add 1,000-attempt concurrency/replay tests proving one accepted successor per head and no duplicate revision for an idempotency key in `tests/test_task_state_store.py` and `tests/test_task_state_service.py` (FR-010; SC-002).
- [ ] [T019] [US2] Add tamper, stale, cross-scope, unknown-evidence, schema-widening, lifecycle, and model-overclaim tests in `tests/test_task_state_service.py` and `tests/test_control_evidence.py` (FR-007–FR-013, FR-017, FR-022, FR-024; SC-001, SC-005).

## Phase 5 — US3: Task context and execution guards (P1)

- [ ] [T020] [P] [US3] Write failing context tests for minimal content, stable UTF-8 bytes, byte budgets, stable ordering, cache keys/invalidation, shadow/completed/cancelled/expired/cross-scope withholding, and one exact exposure in `tests/test_task_state_context.py` (FR-015–FR-018, FR-022; SC-003).
- [ ] [T021] [P] [US3] Write failing guard tests for repeated equivalent actions, distinct task items, progress reset, dependency denial, out-of-scope signals, premature completion, and detection-versus-enforcement evidence in `tests/test_task_state_guards.py` (FR-013, FR-014, FR-017; SC-004).
- [ ] [T022] [US3] Implement the deterministic minimal task-state serializer, digest, bounded context package, generation-bound cache identity, and invalidation in `atmem/task_state/context.py` (FR-015, FR-016, FR-022).
- [ ] [T023] [US3] Implement action fingerprinting, no-progress evaluation, dependency/out-of-scope guards, and completion eligibility in `atmem/task_state/guards.py` (FR-013, FR-014).
- [ ] [T024] [US3] Route active task resolution and separately identified task-state data through `ControlPlaneManager.prepare()` and exact exposure confirmation in `atmem/control/manager.py` without weakening existing recalled-memory revalidation in `atmem/memory.py` (FR-008, FR-015–FR-019; SC-003, SC-006).
- [ ] [T025] [US3] Add deterministic benchmark cases for completed, remaining, blocked, skipped, failed, repeated-action, and premature-finish behavior in `atmem/benchmark/data/task-state-v1.json` and evaluate them in `atmem/benchmark/runner.py` (FR-013, FR-014; SC-004).

## Phase 6 — AtBot proposal intelligence and safe fallback

- [ ] [T026] [P] Add bounded task-state delta, attribution, affected-item, confidence, and reason types in `packages/atbot/src/atbot/domain.py` (FR-007, FR-009).
- [ ] [T027] [P] Write malicious/valid/unavailable proposal tests before implementation in `packages/atbot/tests/test_task_state.py` and `tests/test_task_state_atbot.py` (FR-007–FR-009, FR-019; SC-001, SC-006).
- [ ] [T028] Implement independently authored task-observation prompts and strict delta extraction in `packages/atbot/src/atbot/task_state.py` and `packages/atbot/src/atbot/prompts.py`, accepting only AtMem-authorized snapshot content (FR-007–FR-009, FR-019, FR-028).
- [ ] [T029] Add AtBot companion request/response routing and AtMem revalidation in `packages/atbot/src/atbot/companion.py`, `packages/atbot/src/atbot/service.py`, `atmem/control/atbot_companion.py`, and `atmem/task_state/service.py` (FR-007–FR-009, FR-019).
- [ ] [T030] Prove local typed host/operator transitions, `no_change`, completion validation, and current-state delivery with AtBot, semantic services, and network disabled in `tests/test_task_state_atbot.py` (FR-019, FR-027; SC-006).

## Phase 7 — US5: Host-neutral lifecycle integration (P2)

- [ ] [T031] [P] [US5] Write adapter conformance tests for task identity, observations, context, action/tool outcomes, completion, errors, terminal state, exact exposure, multi-agent isolation, and legacy capability reporting in `tests/test_task_state_adapters.py` (FR-015, FR-017–FR-019, FR-023, FR-024; SC-003, SC-006).
- [ ] [T032] [US5] Extend `AtMemAdapterIdentity` and `AtMemTurnLifecycle` with optional task identity and host-neutral observation/transition/guard methods in `atmem/adapters/base.py` (FR-006, FR-015, FR-017, FR-023, FR-024).
- [ ] [T033] [P] [US5] Map Pydantic AI model/tool hooks into the task lifecycle without replacing dependencies, history, tools, or model configuration in `atmem/adapters/pydantic_ai.py` (FR-023).
- [ ] [T034] [P] [US5] Map LangGraph middleware and raw lifecycle helpers into the task lifecycle without replacing graph state, checkpoints, tools, or model configuration in `atmem/adapters/langgraph.py` (FR-023).
- [ ] [T035] [US5] Extend the OpenClaw plugin contract and tests for exact task-context delivery, action/tool outcomes, completion enforcement capability, and backward-compatible legacy behavior in `integrations/openclaw/index.ts`, `integrations/openclaw/src/rpc-client.ts`, `integrations/openclaw/src/types.ts`, `integrations/openclaw/test/hooks.mjs`, and `integrations/openclaw/test/smoke.mjs` (FR-014, FR-015, FR-017, FR-023).
- [ ] [T036] [US5] Record per-adapter `delivery`, `guard_detection`, and `guard_enforcement` capabilities in `docs/capabilities.json` and assert that unsupported boundaries are never advertised in `tests/test_task_state_adapters.py` (FR-014, FR-023; SC-003).

## Phase 8 — US4: CLI and dashboard control (P2)

- [ ] [T037] [P] [US4] Write CLI tests for enable, start, list, show, timeline, provenance, health, verify, correct, pause, resume, complete, cancel, disable, custom-profile dry-run/register/list/show/verify, governance denial, JSON parity, confirmations, and inline guidance in `tests/test_task_state_cli.py` (FR-018, FR-020–FR-022, FR-029–FR-035; SC-009, SC-011–SC-013).
- [ ] [T038] [US4] Implement `atmem task` and `atmem task profile` commands through shared manager/service methods in `atmem/cli.py` with administrative capability, expected-revision, source, dry-run, and reason requirements where specified (FR-018, FR-020–FR-022, FR-029–FR-035).
- [ ] [T039] [P] [US4] Write dashboard API/UI tests for overview health, active-task summaries, detail, field/status provenance, timeline, correction, lifecycle/profile actions, CSRF, readable reasons, scope-filtered metrics, and collapsed technical evidence in `tests/test_task_state_dashboard.py` (FR-020, FR-021, FR-029–FR-034; SC-009, SC-011–SC-013).
- [ ] [T040] [US4] Add scope-authorized task, governance, provenance, profile-administration, and observability manager/web endpoints backed by the same authority methods in `atmem/control/manager.py`, `atmem/control/web.py`, and `atmem/control/server.py` (FR-020, FR-021, FR-029–FR-034).
- [ ] [T041] [US4] Add dashboard overview → task detail → evidence views with correction/lifecycle/profile actions in `atmem/control/assets/app.html`, `atmem/control/assets/app.js`, and `atmem/control/assets/app.css` (FR-020, FR-021, FR-029–FR-034; SC-009, SC-011–SC-013).

## Phase 9 — Deletion, migration, performance, and release evidence

- [ ] [T042] [P] Write task/subject deletion tests covering heads, revision content, proposals, steps, caches, registered derived artefacts, tombstones, and deletion receipts in `tests/test_task_state_deletion.py` (FR-025).
- [ ] [T043] Implement task-state forget/tombstone/verified-absence behavior in `atmem/task_state/service.py`, `atmem/store/sqlite.py`, and `atmem/maintenance.py` (FR-025).
- [ ] [T044] [P] Add persisted upgrade fixtures and release-workflow drills from every supported public version through create/advance/inspect/complete-or-cancel/delete in `tests/test_task_state_upgrade.py` and `.github/workflows/publish.yml` (FR-026; SC-008).
- [ ] [T045] Add query-plan and 1,000-operation p95 coverage for transition commits and context preparation in `tests/test_task_state_performance.py`, optimizing measured indexes only in `atmem/store/sqlite.py` (SC-007).
- [ ] [T046] Add dependency and artefact provenance checks proving no new mandatory model/framework SDK and no third-party research prompt, dataset, figure, model, or branded component is bundled in `tests/test_documentation.py`, `tests/test_provider_packaging.py`, and CI (FR-027, FR-028; SC-010).
- [ ] [T047] Document concepts, Governance Matrix, Provenance Model, Observability Requirements, setup, shadow evaluation, host capabilities, task operations, evidence meaning, fallback, deletion, rollback, and independently authored examples in `docs/governed-task-state.md`, `README.md`, `docs/current-status.md`, and `docs/capabilities.json` (FR-014, FR-018–FR-023, FR-028–FR-035; SC-009–SC-013).

## Phase 10 — Governance, provenance, and observability convergence

- [ ] [T048] [P] Add an exhaustive actor/capability/action/scope fixture and failing conformance tests in `tests/fixtures/task_state/governance-v1.json` and `tests/test_task_state_governance.py` (FR-029, FR-034, FR-035; SC-011).
- [ ] [T049] Implement closed capability derivation and Governance Matrix enforcement for reads, proposals, commits, corrections, profile registration, lifecycle, context, overrides, and deletion in `atmem/task_state/governance.py`, `atmem/task_state/service.py`, and `atmem/control/manager.py` (FR-029, FR-034, FR-035; SC-011).
- [ ] [T050] [P] Add complete task/field/status/transition/delivery/supersession/deletion lineage fixtures and failing provenance query tests in `tests/fixtures/task_state/provenance-v1.json` and `tests/test_task_state_provenance.py` (FR-030, FR-031, FR-033; SC-012).
- [ ] [T051] Implement the scope-authorized human-readable provenance resolver and deletion-minimized lineage projection in `atmem/task_state/provenance.py` and `atmem/task_state/service.py` (FR-030, FR-031, FR-033; SC-012).
- [ ] [T052] [P] Add deterministic lifecycle/transition/reason/guard/fallback/stale/prepared-exposed/latency/integrity fixtures plus scope and content-leak tests in `tests/fixtures/task_state/observability-v1.json` and `tests/test_task_state_observability.py` (FR-032, FR-033; SC-013).
- [ ] [T053] Implement the read-only scope-filtered observability projection and CLI/dashboard parity in `atmem/task_state/observability.py`, `atmem/control/manager.py`, `atmem/control/web.py`, and `atmem/cli.py` (FR-032, FR-033; SC-013).
- [ ] [T054] Run focused task-state suites, full Python 3.10–3.13 tests, AtBot tests, latest Pydantic AI/LangGraph tests, OpenClaw npm typecheck/test/smoke, clean-wheel checks, licence checks, deletion/restore regressions, persisted-data upgrade drills, and Governance/Provenance/Observability conformance; record exact evidence in this file (SC-001–SC-013).

## Dependencies and execution order

- T001–T005 establish contracts and profiles and block persistence/service work.
- T006–T012 establish canonical authority and block all user-story integration.
- T013–T019 complete structured state and transition authority before context,
  AtBot, adapters, or product controls can claim support.
- T020–T025 may split into context and guard work after T012, then converge at
  T024–T025.
- T026–T030 may proceed after T001–T012 and must complete before adapters use
  model-proposed transitions.
- T031–T036 require T020–T030; Pydantic AI and LangGraph mappings can proceed in
  parallel after host-neutral lifecycle methods exist.
- T037–T041 require T012 and may proceed in parallel with adapter-specific work.
- T042–T047 require the stable persistence/service/API surface; deletion,
  upgrade, performance, packaging, and documentation work can proceed in
  parallel where marked.
- T048–T053 converge the cross-cutting Governance Matrix, Provenance Model, and
  Observability Requirements after all product surfaces exist.
- T054 is the final release gate and runs last.

## MVP boundary

The smallest releasable internal MVP is T001–T025: governed local task state,
atomic transitions, evidence, deterministic context, guards, and benchmarks.
It must remain disabled for external hosts until the relevant T031–T036
adapter conformance work passes. CLI/dashboard exposure requires T037–T041.
