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

- [x] [T019] [US2] Extend evidence validation and audit payloads for task proposal, decision, revision, `no_change`, expiry, field/status provenance, correction, privileged governance action, and lifecycle events in `atmem/control/evidence.py` and `atmem/control/blackbox.py` (FR-009, FR-012, FR-017, FR-021, FR-029, FR-030, FR-035, FR-036).
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
- [x] [T032] [US3] Add deterministic benchmark cases for completed, remaining, blocked, skipped, failed, repeated-action, premature-finish, expired, overflow, and instruction-shaped behavior in `atmem/benchmark/data/task-state-v1.json` and `atmem/benchmark/runner.py` (FR-013, FR-014, FR-036–FR-038; SC-004, SC-014, SC-015).

## Phase 7 — AtBot proposal intelligence and safe fallback

- [x] [T033] [P] Add bounded task-state delta, attribution, affected-item, confidence, and reason types in `packages/atbot/src/atbot/domain.py` (FR-007, FR-009).
- [x] [T034] [P] Write malicious/valid/unavailable proposal tests before implementation in `packages/atbot/tests/test_task_state.py` and `tests/test_task_state_atbot.py` (FR-007–FR-009, FR-019, FR-038; SC-001, SC-006, SC-015).
- [x] [T035] Implement independently authored task-observation prompts and strict delta extraction in `packages/atbot/src/atbot/task_state.py` and `packages/atbot/src/atbot/prompts.py`, accepting only AtMem-authorized snapshot content and treating all observation text as data (FR-007–FR-009, FR-019, FR-028, FR-038).
- [x] [T036] Add AtBot companion request/response routing and AtMem revalidation in `packages/atbot/src/atbot/companion.py`, `packages/atbot/src/atbot/service.py`, `atmem/control/atbot_companion.py`, and `atmem/task_state/service.py` (FR-007–FR-009, FR-019).
- [x] [T037] Prove local typed host/operator transitions, `no_change`, completion validation, and current-state delivery with AtBot, semantic services, and network disabled in `tests/test_task_state_atbot.py` (FR-019, FR-027; SC-006).

## Phase 8 — US5: Host-neutral lifecycle integration (P2)

- [x] [T038] [P] [US5] Write adapter conformance tests for exact task identity, absent/unknown/terminal/cross-scope identity, multiple-open-task non-selection, observations, context, action/tool outcomes, completion, errors, terminal state, exact exposure, multi-agent isolation, and current/legacy capability negotiation in `tests/test_task_state_adapters.py` (FR-015, FR-017–FR-019, FR-023, FR-024, FR-039; SC-003, SC-006, SC-016).
- [x] [T039] [US5] Extend `AtMemAdapterIdentity` and `AtMemTurnLifecycle` with task identity that is optional only for legacy task-unaware operation and required for task-aware observation/transition/guard methods in `atmem/adapters/base.py`; absent identity disables task-state delivery and never triggers discovery. Add authoritative governed-task-state delivery/detection/enforcement flags in `atmem/contracts/versions.py` and align `atmem/schemas/v1/capabilities.json` (FR-006, FR-015, FR-017, FR-023, FR-024, FR-039; SC-016).
- [x] [T040] [P] [US5] Map Pydantic AI model/tool hooks into the task lifecycle without replacing dependencies, history, tools, or model configuration in `atmem/adapters/pydantic_ai.py` (FR-023, FR-039).
- [x] [T041] [P] [US5] Map LangGraph middleware and raw lifecycle helpers into the task lifecycle without replacing graph state, checkpoints, tools, or model configuration in `atmem/adapters/langgraph.py` (FR-023, FR-039).
- [x] [T042] [US5] Extend the OpenClaw plugin contract and tests for exact task-context delivery, action/tool outcomes, completion enforcement capability, runtime negotiation, and backward-compatible legacy behavior in `integrations/openclaw/index.ts`, `integrations/openclaw/src/rpc-client.ts`, `integrations/openclaw/src/types.ts`, `integrations/openclaw/test/hooks.mjs`, and `integrations/openclaw/test/smoke.mjs` (FR-014, FR-015, FR-017, FR-023, FR-039; SC-016).
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

## Phase 12 — Amendment A: host-driven task binding and proposal

Revision 5 (2026-09-05) resolves fourth-review findings I1, U1, and C1, adding
host-proposal to the adapter-keyed capability data in T080, complete session
identity with negative vectors to T059, and the wrong-session guarantee to T083.

Revision 4 (2026-09-05) resolves third-review findings A1–A5, adding FR-054
session binding of host submissions to T071, T072, T074, and T079, adapter-keyed
capability data to T080, and a genuinely executed three-version CI matrix to
T058. Task numbering is unchanged.

Revision 3 (2026-09-05) resolves second-review findings C1 (critical), I1, C2,
I2, C3, U1, R1, I3, and T1. Phase 12 is renumbered into execution order so the
task list reads in the sequence it must be worked: contracts and session
generation before binding resolution, observation infrastructure before bridge
integration. Task IDs T058–T083 replace the Revision 2 numbering; none had been
started.

### 12a — Premise, contracts, and profile

- [x] [T058] Establish the amendment's premises as maintained fixtures against a finite, testable matrix. The bridge's `peerDependencies` range is open-ended (`openclaw >=2026.7.1-2`), so record the plugin hook-context shape for exactly three versions — the declared minimum, the lockfile version, and the latest compatible version CI resolves — in `integrations/openclaw/test/fixtures/hook-context/`, and assert against the resolved dependency that (a) no context an amendment hook receives declares a governed task identity, (b) every such hook **declares** `sessionId`, the value FR-052 binds as `session_epoch`, and `sessionKey`, the FR-042 conversation address, and (c) the contexts FR-050's in-host surface runs under declare the owner signal. Record per-field optionality and do not assert presence at runtime: these fields are declared optional, so a declaration proves only that binding is possible for this host. Report the optional set on every run as the standing fail-closed obligation (FR-050, FR-052); runtime population is proven by T078, not here. CI MUST install each of the three versions in isolation and execute the premise check against it — a fixture never run against its version is documentation, not a check — and MUST record the resolved version of the moving "latest" entry in the run summary. An unrecorded resolved version fails with instructions rather than being absorbed silently. A version that adds task identity produces a fixture diff that re-scopes the amendment toward FR-043's first resolution step rather than failing permanently. In `tests/test_task_state_binding.py` assert only what Python can prove: the complete registered MCP tool inventory matches the pre-amendment surface exactly, no registered tool declares task-mutating or unexpected task-identity inputs under any name, and `0078`–`0079` remain the sole unused identifiers in Spec 007's reserved block. No check may read a globally installed OpenClaw (FR-042, FR-047, FR-050, FR-052).

- [x] [T059] [P] Add dependency-free session-binding and host-boundary contracts with closed parsing, canonical serialization, and stable reason codes including `task_binding_conflict` and `task_binding_stale_session` in `atmem/contracts/task_state.py`, plus independently authored versioned schemas `atmem/schemas/v1/task-session-binding.json`, `host-task-proposal-request.json`, `host-task-observation-request.json`, and `host-task-lifecycle-request.json` with valid/invalid vectors. Host-boundary requests are public contracts distinct from the internal proposal type and carry explicit adapter and host identity. Each of the three MUST require the complete FR-054 session identity — `host_type`, `session_key`, and `session_epoch` — as schema-required fields, or MUST document the authenticated transport envelope that supplies all three; session identity is an addressing claim AtMem resolves and checks, which is why it is permitted where an authority claim is not. Requests MUST have no actor-role, capability, or authority field. Vectors must include a submission carrying one such field, and submissions missing, emptying, or malforming each of the three session identity fields, asserting every one parses as malformed rather than resolving with a partial identity (FR-042, FR-044, FR-051, FR-052, FR-054; SC-027).
- [x] [T060] Extend the profile contract for FR-052 in `atmem/contracts/task_state.py`, `atmem/schemas/v1/task-profile.json`, and `atmem/task_state/profiles.py`: add the supplemental binding lifetime and the reset-signal requirement, give `general-v1` its default, and prove in `tests/test_task_state_contracts.py` and `tests/test_task_state_upgrade.py` that existing persisted profiles without the field load unchanged and the published schema accepts both shapes. The lifetime is supplemental expiry only and MUST NOT be expressible as a substitute for a reset signal (FR-052; SC-008, SC-029).

### 12b — Session generation, storage, and resolution

- [x] [T061] [P] Write failing binding tests for the exact `(subject, agent, workspace, host_type, session_key, session_epoch)` uniqueness key, at-most-one-active-per-key, many-to-one targeting, registration/revocation evidence and history, eligibility at registration, unresolvable-after-terminal, refusal of retargeting as an update, and cross-scope non-disclosure in `tests/test_task_state_binding.py`. Assert explicitly that exact scope alone does NOT prevent a recycled key in the same scope from inheriting a binding, and that a reset occurring inside a declared lifetime still withholds, so the FR-052 generation is proven load-bearing rather than assumed (FR-042, FR-052, FR-024, FR-029; SC-019, SC-025, SC-029).
- [x] [T062] Add `governed_task_session_bindings` through the idempotent initializer in `atmem/store/sqlite.py` using reserved bootstrap identifier `0078`, with `session_epoch` in the active-row uniqueness constraint, revocation retention, and resolution index; record in `specs/integration-ownership.md` that `0079` is the last identifier remaining in Spec 007's reserved block (FR-042, FR-052, FR-026).
- [x] [T063] Implement FR-052 session generation in `atmem/task_state/binding.py`: bind `session_epoch` at registration, include it in the uniqueness key, and withhold with `task_binding_stale_session` on epoch mismatch or a host-reported session start later than registration, requiring explicit operator re-confirmation with no automatic recovery. Report session binding unavailable in the capability response for a host that can supply neither a generation nor a reliable session start, and refuse to bind such a host under a lifetime alone (FR-052, FR-048; SC-025, SC-029).
- [x] [T064] Implement registration, revocation, listing, and single-answer resolution in `atmem/task_state/binding.py`, returning exactly one task ID or one withholding reason and exposing no candidate collection at any layer (FR-042, FR-043).
- [x] [T065] [P] Write the failing exhaustive resolution-matrix test over {explicit identity, active binding, both agreeing, both disagreeing, neither} × {open, paused, terminal, cross-scope, unknown, stale-generation} asserting disposition, reason code, and zero task-state bytes for every non-delivering cell, plus zero exposure evidence on withholding, in `tests/test_task_state_context.py` (FR-015, FR-043, FR-052; SC-019).
- [x] [T066] Route FR-043 resolution into the existing `ControlPlaneManager.prepare_task_context` path in `atmem/control/manager.py` so eligibility, expiry, budget, escaping, exposure, and non-disclosure rules apply unchanged; withhold on disagreement with `task_binding_conflict` without preferring either source (FR-015, FR-043; SC-019).
- [x] [T067] Implement FR-053 truthful exposure in `atmem/control/manager.py` and `atmem/task_state/service.py`: preparation authorizes exactly one model call; confirm exposure truthfully where the adapter proves the bytes reached the boundary even if the task became terminal or unbound in between, recording the terminal outcome as a separate later event linked to that delivery; record preparation without exposure where delivery is disproven or unprovable; never suppress or rewrite evidence of a delivery that occurred. Add both-direction delivery-race tests in `tests/test_task_state_context.py` (FR-017, FR-053; SC-028).

### 12c — Observation and delta production

- [x] [T068] [P] Write failing observation tests in `tests/test_task_state_observation.py` for the FR-049 entry points: bounded authenticated observation → authorization → AtBot companion candidate → head revalidation → commit or refusal; the identical fixture set with AtBot and the network disabled producing deterministic `no_change`; derived idempotency keys collapsing retried hooks, duplicated tool results, and replayed turns to one decision; content-derived and random keys rejected; and payload minimization proving no raw prompt, full tool result, secret, or chain-of-thought is carried (FR-049, FR-019, FR-038; SC-024).
- [x] [T069] Implement the observation entry point as `control_observe_task_step` in `atmem/control/manager.py` and `atmem/control/server.py`, routing through the existing `packages/atbot/src/atbot/task_state.py` companion path unchanged and revalidating every returned delta against the current head before commit; assert no adapter code path can synthesize a delta (FR-007, FR-049, FR-019).
- [x] [T070] Make FR-049 path (b) real at the model boundary: register the agent-facing typed-delta tool with the host through `api.registerTool` in `integrations/openclaw/src/task-tools.ts` and `integrations/openclaw/index.ts`, alongside the existing `memory_search` and `memory_get` registrations. Name the tool, define the result the model reads back for each of `accepted`, `rejected`, `conflict`, and `no_change` so a rejection is interpretable rather than blindly retried, and add tool-boundary tests for each outcome in `integrations/openclaw/test/hooks.mjs`. If the tool is not registered, path (b) MUST NOT be advertised in the capability response (FR-049; SC-030).

### 12d — Host-boundary proposal path

- [x] [T071] [P] Write failing host-boundary tests for valid deltas, stale revisions, replayed idempotency keys, cross-scope tasks, unknown evidence, and every operator-only action refused on capability grounds before content evaluation, in `tests/test_task_state_host_proposal.py`; extend `tests/fixtures/task_state/governance-v1.json` with the host-agent row. Cover disabled and shadow as distinct paths: a disabled scope refuses immediately before identity resolution or content evaluation with minimal evidence and no disclosure, while a shadow scope evaluates fully and records the decision it would have made without committing. Cover FR-054 wrong-session submission for observation, proposal, and lifecycle request alike: two open tasks in one authorized scope bound to two sessions, each naming the other's task, refused before content evaluation with a non-disclosing reason and both heads unchanged; plus a submission whose session resolves to nothing, refused rather than trusted (FR-044–FR-046, FR-029, FR-051, FR-054; SC-021, SC-027, SC-031).
- [x] [T072] Derive the host-agent capability ceiling in `atmem/task_state/governance.py` and implement `propose_task_delta` and `request_task_lifecycle` manager methods in `atmem/control/manager.py`, routing through the existing `TaskStateService` with `ActorRole.AGENT` alongside the operator paths and refusing operator-only actions before delta content is evaluated. Implement FR-054 session binding of submissions: resolve `(host_type, session_key, session_epoch)` through the FR-043 resolver on every observation, proposal, and lifecycle request and require the submitted `task_id` to equal the resolved task, refusing mismatches before content evaluation with a non-disclosing reason and refusing outright where resolution yields nothing — the submitted identifier is a redundant assertion to check, never the authority. Actor role derives from authenticated transport and registered adapter identity only (FR-044, FR-045, FR-051, FR-054; SC-021, SC-031).
- [x] [T073] Add `control_propose_task_delta` and `control_request_task_lifecycle` to `atmem/control/server.py` with closed argument schemas, and binding endpoints to `atmem/control/web.py`; mutations never auto-retry after conflict and unauthorized lookup stays non-disclosing (FR-044, FR-045, FR-047, FR-051).
- [x] [T074] [P] Reuse the SC-002 concurrency harness against the host-boundary path for 1,000 concurrent and replayed proposals in `tests/test_task_state_host_proposal.py`, proving one accepted successor per head and no duplicate revision per idempotency key. Include concurrent submissions from two sessions bound to two tasks in one scope, proving each advances only its own task and every cross-session attempt is refused (FR-044, FR-054; SC-020, SC-031).

### 12e — Operator surfaces and bridge integration

- [x] [T075] Implement `atmem task bind`, `atmem task unbind`, and `atmem task bindings` in `atmem/cli.py` under the shared privileged preview/confirmation contract, requiring authenticated capability, exact scope, reason, source, session generation, and `--yes` for non-interactive use, with human/JSON parity and exit codes 0/1/2 per FR-040 (FR-042, FR-052, FR-040).
- [x] [T076] Add the owner-gated in-host binding surface in `integrations/openclaw/src/commands.ts` and `integrations/openclaw/index.ts` for bind, unbind, and status scoped to the caller's own conversation, gated on the existing `ctx.senderIsOwner` signal, resolving the session key internally and never returning or displaying it. The command MUST pass OpenClaw's `ctx.sessionId` as `session_epoch` on registration. Refuse non-owner calls without disclosing whether a binding exists; carry the same authority, reason, source, evidence, and confirmation requirements as the CLI path. Add owner and non-owner tests to `integrations/openclaw/test/hooks.mjs` (FR-050, FR-052; SC-026).
- [x] [T077] Resolve task identity through the manager rather than `ctx.taskId` alone, presenting OpenClaw's `ctx.sessionId` as `session_epoch` on every context lookup so binding and resolution cannot disagree about which conversation they mean, and submit bounded FR-049 observations — never adapter-synthesized deltas — from the existing `after_tool_call` and `agent_end` hooks in `integrations/openclaw/index.ts`, `integrations/openclaw/src/rpc-client.ts`, and `integrations/openclaw/src/types.ts`, minimizing payloads to profile-declared fields and deriving idempotency keys from stable host identifiers only. Keep memory-only behavior byte-identical when no identity resolves and continue to claim no execution-blocking capability (FR-046, FR-047, FR-049, FR-052).
- [x] [T078] Prove epoch rotation and fail-closed handling in `integrations/openclaw/test/hooks.mjs`: assert `session_epoch` rotates across `before_reset`, `session_start`, and the subsequent `before_prompt_build`, that a recycled session key in the same scope withholds under `task_binding_stale_session`, and that a reset occurring inside a declared binding lifetime still withholds. Because every identity field is optional (T058), also assert the absent cases: a turn presenting no `sessionId`, no `sessionKey`, or neither withholds and never resolves on the remaining fields, and a bind attempt lacking either is refused. Scope this honestly — the existing harness drives handlers through `fakeApi` with fabricated contexts, so it proves the bridge's own rotation and fail-closed logic, **not** that a real OpenClaw populates these optional fields. No task may describe it as runtime proof. Runtime population stays unproven by design, which is precisely why FR-050 and FR-052 require failing closed rather than assuming presence; an upstream OpenClaw hook harness, if one ever ships, would be a separate task (FR-050, FR-052; SC-025, SC-029).
- [x] [T079] Add the end-to-end OpenClaw test in `integrations/openclaw/test/hooks.mjs` that binds a session through the in-host command, delivers exact task context on a turn carrying no host task identity, confirms exposure exactly once, advances the task by host observation and by the registered agent tool, is denied premature completion, is refused when it names a second task bound to a different session in the same scope, and withholds after revocation, asserting the prepared/exposed/withheld counter sequence (FR-047, FR-054; SC-022, SC-031).

### 12f — Mirroring, documentation, and release

- [x] [T080] Add authoritative capability data to `atmem/contracts/versions.py` and mirror it in `atmem/schemas/v1/capabilities.json` and `docs/capabilities.json`. Availability that varies by host MUST be adapter-keyed, following the existing `governed_task_enforcing_adapters` pattern rather than inventing one: add `governed_task_session_binding_adapters`, `governed_task_host_proposal_adapters`, and `governed_task_agent_delta_tool_adapters`, since one adapter may supply a reset signal, accept authenticated session-bound requests, or register the tool while another does not, and a single boolean cannot truthfully describe both. Any retained global flag means only that the runtime implements the capability, and each adapter response MUST derive its own availability from the keyed data. Assert runtime/schema/documentation equality and add mixed fixtures covering all three keyed capabilities — one adapter with a reset signal and one without, one able to host-propose and one not, one registering the agent tool and one not — in `tests/test_task_state_adapters.py` and `tests/test_documentation.py`, with guard enforcement still reported unavailable (FR-048, FR-049, FR-052; SC-023, SC-029, SC-030).
- [x] [T081] Add binding and host-proposal counters to the scope-filtered projection in `atmem/task_state/observability.py`, and render bindings, their resolution state, and stale-generation withholding in the dashboard's governed-task surfaces per the FR-041 state and accessibility contract in `atmem/control/assets/app.{html,js,css}` (FR-032, FR-041, FR-042, FR-052).
- [x] [T082] Extend deletion and forget behavior to bindings in `atmem/task_state/service.py`, `atmem/store/sqlite.py`, and `tests/test_task_state_deletion.py`, and add binding rows and lifetime-bearing profiles to the persisted-upgrade drill in `tests/test_task_state_upgrade.py` (FR-025, FR-026, FR-052; SC-008).
- [x] [T083] Document binding, the required reset signal, resolution order, truthful exposure under FR-053, host observation and the registered agent tool, the capability ceiling, per-adapter capability derivation, disabled-versus-shadow behavior, revocation as rollback, and the unchanged guard-enforcement boundary in `docs/governed-task-state.md`, `README.md`, and `docs/current-status.md`. State plainly that a host can only update the task bound to its current session: naming a sibling task in the same authorized scope is refused, so scope alone never grants write access to another conversation's work. Prove the no-bindings regression path leaves every existing memory-only and task-unaware test green (FR-046–FR-054; SC-019–SC-031).
- [x] [T084] Prepare release artefacts per `AGENTS.md`: add `docs/releases/v<VERSION>.md` — the artefact required before tagging; the repository has no `CHANGELOG.md` and one must not be invented — carrying the user-visible change, exact install and upgrade commands, migration and opt-in behavior, compatibility, and honest limitations. Align versions across the `atmem` distribution, the `atbot` distribution, and the OpenClaw bridge `package.json`, and add a matching `docs/current-status.md` section. The note MUST state that guard enforcement remains unavailable and that this amendment makes Governed Task State reachable rather than blocking. No release proceeds without this task (FR-047, FR-048).
- [x] [T085] Run the full amendment gate — resolution matrix including stale generation, delivery-race exposure truthfulness both ways, observation with and without AtBot, agent-tool boundary outcomes, epoch rotation across reset hooks, in-host owner gating, host-contract validation, disabled-versus-shadow separation, wrong-session refusal across all three host operations, mixed-adapter capability derivation, host-proposal concurrency, capability conformance, no-bindings regression, persisted upgrade, profile compatibility, dashboard state and accessibility, and the complete existing suite — and record exact evidence in this file (SC-019–SC-031, and SC-001–SC-018 unregressed).

### T058 evidence (2026-09-05)

Premises verified against all three matrix entries, each executed rather than
recorded:

| Version | Label | Task identity | `sessionId` / `sessionKey` declared | Owner signal declared |
| --- | --- | --- | --- | --- |
| 2026.7.1-2 | min (peer floor) | none | yes, optional | yes, optional |
| 2026.8.1 | lockfile | none | yes, optional | yes, optional |
| 2026.9.1 | latest | none | yes, optional | yes, optional |

Hook-to-context mapping is identical across all three: `before_prompt_build`,
`llm_input`, `agent_end`, and `before_reset` receive `PluginHookAgentContext`;
`after_tool_call` receives `PluginHookToolContext`; `session_start` and
`session_end` receive `PluginHookSessionContext`. Fields were only added between
versions, never removed.

Three findings that constrain later tasks:

- **Every identity field is optional.** `sessionId`, `sessionKey`, and
  `senderIsOwner` are declared `?:` on every context that carries them, the sole
  exception being `sessionId` on `PluginHookSessionContext`. A declaration
  therefore proves only that binding is *possible* for this host, never that
  identity arrives on a given turn. The premise gate asserts the weaker true
  claim and prints the optional set every run as a standing obligation; spec
  Revision 6 adds the matching fail-closed rules to FR-050 and FR-052. Runtime
  population is **not** proven anywhere: the npm harness drives handlers through
  `fakeApi` with fabricated contexts, so T078 proves the bridge's own rotation
  and fail-closed logic and nothing about what a real OpenClaw passes. That is
  the reason absence must fail closed rather than be assumed away.
- `sessionId` is **not** declared on `PluginHookMessageContext`, only on the
  agent, tool, and session contexts. The epoch design holds because every hook
  Amendment A resolves identity in receives one of the latter. A future hook
  choice must be checked against this, not assumed.
- `senderIsOwner` is declared on `OpenClawPluginToolContext` and
  `PluginCommandContext` but **not** on `PluginHookAgentContext`. FR-050's owner
  gate therefore works only because T076's bind/unbind/status is a command or
  tool; the same gate in a hook would read an undeclared field. Note that
  `integrations/openclaw/index.ts:481` already reads `ctx.senderIsOwner` from a
  hook context in the delegated-context path — outside T058's scope, but it is
  reading a field OpenClaw does not declare there.

Delivered: `integrations/openclaw/test/lib/hook-context-shape.mjs`,
`test/lib/record-hook-context.mjs`, `test/hook-context-compat.mjs`, three
fixtures under `test/fixtures/hook-context/` recording per-field optionality,
the `openclaw-hook-context-matrix` CI job gating `distribution`, and
`tests/test_task_state_binding.py`.

The Python gate separates the historical premise from the live surface, so the
amendment can land without weakening its own evidence. The pre-amendment MCP
surface is frozen in `tests/fixtures/task_state/pre-amendment-mcp-surface.json`
and the "no task write path" claim is asserted against that recording, where it
stays permanently true. Live-surface assertions then allow exactly the three
tools Amendment A authorizes — `control_observe_task_step` (T069),
`control_propose_task_delta` and `control_request_task_lifecycle` (T073) — named
in an allowlist written before they exist, and confine task identity and
mutating inputs to that reviewed set. Scanning is schema-based, not name-based:
a write path called `control_update_state` contains no "task" and would slip
past a name filter.

Verified by simulation: injecting all three amendment tools leaves every T058
test passing **unedited**, and injecting an unreviewed fourth
(`control_force_task_complete`) is caught. Injecting `control_update_state` is
caught by the schema scan. One recorded nuance —
`control_task_exposure_shown` is keyed by `delivery_id`, not `task_id`, so
preparation is what names a task while confirmation only acknowledges the
delivery preparation authorized.

Checks: `npm test` passes with the premise check first in the chain; typecheck
clean; the premise check passes independently against each matrix version via
`OPENCLAW_PROBE_DIR`; full Python suite 1096 passed, 3 skipped (was 1091/3).

Deviation from the Revision 5 task text: that text said CI must "install and run
the suite" against all three versions. CI runs the **premise check** against all
three, not the full `npm test`. The full suite needs a built `dist/` and a local
Python install per version and would fail on unrelated API drift, which would
obscure the premise signal rather than sharpen it. The task text above is
updated to say so.

### Amendment A evidence (T085, 2026-09-05)

Run against the working tree at AtMem `2.2.6b6`, AtBot `0.1.0a6`, OpenClaw
bridge `2.2.6-beta.4`.

| Check | Result |
| --- | --- |
| Full Python suite | 1247 passed, 3 skipped |
| Session bindings (key, generation, resolution matrix) | 23 passed |
| Host-boundary contracts + published schemas | 61 passed |
| Host-boundary gates, ceiling, concurrency | 49 passed |
| Premise gate (T058) | 5 passed |
| Context and delivery, incl. binding resolution + truthful exposure | 40 passed |
| Deletion, incl. bindings as derivatives | 16 passed |
| Persisted upgrade, all five published floors | 45 passed |
| Adapters + adapter-keyed capability mirroring | 35 passed |
| Dashboard states, incl. unbound-scope explanation | 26 passed |
| CLI journey, incl. bind/unbind/bindings | 32 passed |
| OpenClaw npm suite | hook-context, setup, hooks, task tools, delegated contract |
| OpenClaw smoke + journey | real `atmem control mcp`, full sequence |
| Typecheck / build | clean |
| Python 3.10 grammar | every module parses |
| Clean import | no optional SDK loaded |

The end-to-end journey runs against a spawned `atmem control mcp`, not a stub:
unbound withholds -> operator binds from the CLI -> a turn carrying no host task
identity is delivered its bound task -> exposure confirmed exactly once ->
progress reported by host proposal -> replay collapses to one decision ->
premature completion denied -> a sibling task in the same scope refused ->
terminal task withheld -> reset withholds -> revoke withholds -> counters agree.

Findings recorded during implementation:

- **Withholdings for unresolved identity cannot be recorded as deliveries.**
  `governed_task_deliveries.task_id` is a foreign key, and a turn where nothing
  resolved has no task to key to. A placeholder row would put a task id in the
  evidence that never existed. Resolved withholdings are recorded; unresolved
  ones show as the absence of a delivery plus a zero active-binding count in
  health. Spending `0079` on a nullable column was considered and rejected.
- **`TaskOperation` and `EvidenceRef` had no `from_dict`**, so operation parsing
  was duplicated ad hoc in `service.py` and `cli.py`. Canonical parsers were
  added rather than a third copy; `TaskOperation.from_dict` takes an assurance
  override so a channel imposes its own ceiling instead of trusting the payload.
- **A host completing an item must cite evidence.** The policy already required
  it, so the registered `task_report_progress` tool attaches its own tool call,
  recorded at `asserted` assurance and never upgraded.
- **`0079` is now the only identifier left** in Spec 007's reserved block.

Deviations from the task text, and why:

- **T079** was written for `hooks.mjs`. The journey lives in
  `test/task-journey.mjs` and drives a real spawned control-plane server
  instead, which proves more than the fabricated-context harness could. The
  fabricated-context checks that belong in the bridge live in
  `test/task-tools.mjs` and are labelled as bridge logic only.
- **T081's** dashboard work reports binding counts and explains an unbound
  scope; it does not add a binding *mutation* surface to the dashboard.
  Registering a binding stays an authenticated CLI or in-host owner action, so
  the dashboard gains no capability the CLI does not already gate.

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
- Phase 12 is written in execution order; its sub-phases 12a–12f may be worked
  top to bottom without consulting this section. The ordering constraints below
  are stated for verification, not because the list contradicts them.
- T058 is the premise gate and runs before any amendment design work. A premise
  that no longer holds re-scopes the amendment rather than being worked around.
- 12a (T058–T060) establishes contracts and the profile field. T060 precedes all
  binding work because the uniqueness key and the supplemental lifetime are
  profile-bound.
- 12b (T061–T067) builds session generation before resolution: T063 precedes
  T064 and T066, since resolution cannot be implemented against a key that omits
  `session_epoch`. T061 and T065 must fail before T063, T064, and T066 pass.
  T067 delivers FR-053 truthful exposure and must land with the delivery route,
  not after it.
- 12c (T068–T070) defines where a delta comes from and precedes every bridge
  task, since the bridge cannot submit to an entry point that does not exist.
  T068's AtBot-disabled fixtures must fail before T069 makes them pass. T070
  registers the model-facing tool; without it FR-049 path (b) is unavailable and
  must not be advertised.
- 12d (T071–T074) adds the host write path only after the capability ceiling is
  derived, never asserted at the tool boundary. It also depends on 12b: FR-054
  resolves every submission through the FR-043 resolver, so the write path
  cannot be built before resolution exists.
- 12e (T075–T079) exposes operator and host surfaces after their authority
  exists. T076 depends on T075 and adds no capability above it. T077 must not
  change memory-only behavior when no identity resolves. T078 and T079 are the
  host-side proofs and run after both bridge tasks.
- 12f (T080–T085) mirrors capabilities, observability, deletion, upgrade, and
  documentation. T084 prepares release artefacts and T085 is the amendment
  release gate; both run last, T084 before T085.

## Delivery boundaries

- **Earliest risk-reduction slice**: T000–T012 proves one local profile, three
  transition operations, restart persistence, atomic revision, and provenance
  without AtBot, guards, dashboard, or adapters.
- **Releasable internal MVP**: T000–T032 adds complete structured state, expiry,
  evidence, deterministic context, guards, and benchmarks.
- External host enablement remains disabled until T038–T043 adapter and
  capability conformance passes. CLI/dashboard exposure requires T023–T050.
- **Amendment A reachability slice**: 12a and 12b (T058–T067) make task context
  deliverable from a host that supplies no task identity, with no host write
  path yet. Session generation and truthful exposure are inside this slice, not
  after it — a binding without reset detection is not safely deliverable, and a
  delivery route that misrecords exposure is not honestly deliverable.
- **Amendment A complete**: 12c–12f (T068–T085) add the observation and
  registered-tool entry points, the host write path, operator binding controls
  including the in-host surface, capability negotiation, release artefacts, and
  the end-to-end OpenClaw proof. T085 gates the release.
- Guard enforcement remains out of scope. Amendment A makes Governed Task State
  reachable from OpenClaw; it does not make it blocking, and no task may
  advertise otherwise.

## Delivered Evidence (T057)

Run on 2026-09-05 against the working tree.

| Check | Result |
| --- | --- |
| Full Python suite | 1091 passed, 3 skipped |
| Prerequisite gate (`test_task_state_prerequisites.py`) | 11 passed |
| Walking skeleton | 2 passed |
| Contracts + published schemas | 77 passed |
| Store, policy, service | 149 passed |
| Expiry (injectable clock, incl. maintenance scan) | 24 passed |
| Governance conformance | 33 passed |
| Context, guards, observability | 70 passed |
| Adapters + capability mirroring + derived enforcement | 30 passed |
| CLI journey | 32 passed |
| Dashboard states | 23 passed |
| Deletion | 14 passed |
| Persisted upgrade, all five published floors | 45 passed |
| AtBot proposals + fallback | 20 passed |
| Tamper / adversarial | 26 passed |
| Deterministic benchmark | passed, 24/24 cases |
| Governed Task State benchmark | passed, 10/10 cases |
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

## Completion Pass (2.2.6b5)

- **T019** — the content-minimizing Black Box vocabulary now correlates exact
  task identity, context preparation/exposure, revisions, outcomes, reason
  codes, evidence IDs, affected items, and digests. Raw task content remains an
  unsupported payload.
- **T032** — `task-state-v1.json` and `run_task_state_benchmark()` execute the
  ten named deterministic risk cases and bind the report to a stable digest.
- **T036** — the authenticated loopback companion route carries only an
  AtMem-authorized exact snapshot and observation. Both the client and the
  authority service revalidate identity, revision, referenced entities, closed
  operations, assurance, and policy before AtMem commits.
- **T040–T042** — Pydantic AI, LangGraph, and OpenClaw deliver separately
  labelled task context only when the host binds an exact task ID, acknowledge
  exact exposure, retain legacy task-unaware behavior, and preserve host-owned
  models, tools, history, dependencies, graph state, and checkpoints. Runtime
  capability negotiation still truthfully reports guard enforcement as false.
- Release artifacts built as AtMem `2.2.6b5`, AtBot `0.1.0a6`, and OpenClaw
  bridge `2.2.6-beta.3`; both Python distributions pass `twine check`, and the
  OpenClaw build, contract tests, and real-server smoke test pass.
