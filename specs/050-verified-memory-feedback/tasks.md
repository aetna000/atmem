# Implementation tasks — Spec 050

Status: planned, not implemented. Every item below is unchecked deliberately.
Read `spec.md`, `plan.md`, `research.md` and the constitution before implementation.
Dependencies are sequential by phase; no delegated agent work is requested here.
Referenced new paths are implementation targets. No paid evaluation is authorized.

## Phase 1 — Baseline and contracts

- [ ] [T001] Freeze native/current-AtMem baseline definitions, corpus and verification requirements, cost-zero default, three-attempt cap and all SC thresholds in `docs/benchmarks/verified-memory-feedback.md`; introduce bounded manifest fixtures under `tests/fixtures/feedback/`. Map FR-009, FR-022, FR-024; SC-003, SC-005.
- [ ] [T002] Pin the initial installed Hermes version, dispatch/wrapper boundary, supported tool schemas and OS capability matrix in `docs/verified-memory-feedback.md`; record existing guard tests and limits before integration. Map FR-014, FR-021, FR-024; SC-004, SC-006.
- [ ] [T003] Add versioned scope, outcome, verification, rule, qualification, activation and export contracts in `atmem/contracts/feedback.py` and `atmem/schemas/v1/feedback-*.json`; validate bounded inputs and forbidden client-supplied roles in `tests/test_feedback_contracts.py`. Map FR-001, FR-002, FR-003, FR-005, FR-006, FR-011, FR-012, FR-019; SC-001.

## Phase 2 — Authoritative evidence and outcomes (after T001–T003)

- [ ] [T004] Implement additive protected persistence and migration in `atmem/feedback/store.py`, `atmem/store/sqlite.py` and `atmem/evidence/store.py`; test encrypted metadata, staged evidence/outbox recovery and old-store upgrade in `tests/test_feedback_store.py`. Map FR-002, FR-006, FR-018, FR-021; SC-002, SC-006.
- [ ] [T005] Implement authenticated scoped operations in `atmem/feedback/service.py`, reusing authority and review identities; add cross-user/agent/workspace and non-disclosure tests in `tests/test_feedback_authority.py`. Map FR-001, FR-007, FR-018; SC-001.
- [ ] [T006] Link real context receipts, exact invocation/check evidence and late/duplicate observations in `atmem/feedback/service.py`; test a read success with a failed write and forbid combining partial calls in `tests/test_feedback_actions.py`. Map FR-002, FR-005, FR-006; SC-002.
- [ ] [T007] Implement scoped verifier registration, independent readback results, attestation tiers, disputes and evidence-backed failure attribution in `atmem/feedback/verification.py`; cover fabricated success, missing capture, poisoned feedback and delivered-but-not-applied in `tests/test_feedback_verification.py`. Map FR-003, FR-004, FR-005, FR-024; SC-001, SC-002.
- [ ] [T008] Implement exact metric denominators, zero/unknown handling, episode uncertainty, cost and content-free telemetry in `atmem/feedback/metrics.py`; test abstain-all, unassessed answers, scope leakage and required-fact write failures in `tests/test_feedback_metrics.py`. Map FR-008, FR-023, FR-024; SC-003, SC-007.

## Phase 3 — Reviewed retrieval adaptation (after T004–T008)

- [ ] [T009] Extend `atmem/extract/review.py` for revision-bound profile/rule proposals without changing ordinary fact admission; add stale/racing reviewer, injection and owner-versus-model capability tests in `tests/test_feedback_review.py`. Map FR-007, FR-010, FR-011, FR-012; SC-001.
- [ ] [T010] Implement frozen manifest validation, safe paired replay, bounded attempts, cost stops, independent verifier binding and expiring accept/reject/inconclusive receipts in `atmem/feedback/qualification.py`; test held-out contamination and unknown outcomes in `tests/test_feedback_qualification.py`. Map FR-003, FR-009, FR-010, FR-013, FR-022, FR-024; SC-003, SC-004, SC-005.
- [ ] [T011] Integrate versioned ranking/threshold/packing profiles with `atmem/context_engine/profiles.py` and `atmem/context_engine/service.py`; prove scope invariance, disabled parity, shadow without mutation, qualified activation and local deterministic fallback in `tests/test_feedback_profiles.py`. Map FR-010, FR-017, FR-021; SC-001, SC-003, SC-005.

## Phase 4 — Rules and real enforcement (after T009–T011)

- [ ] [T012] Implement the three-predicate rule representation and non-executable compiler in `atmem/rules/models.py` and `atmem/rules/compiler.py`; test unsupported language, arbitrary code, ambiguous aliases and source grounding in `tests/test_rule_compiler.py`. Map FR-011, FR-016; SC-001.
- [ ] [T013] Implement deterministic evaluation, conflicting predicates, deny-wins and exact single-use approval binding in `atmem/rules/evaluator.py`; test changed arguments, replay, expiry and permission narrowing in `tests/test_rule_evaluator.py`. Map FR-001, FR-014, FR-015, FR-016; SC-001, SC-004.
- [ ] [T014] Implement shadow/qualified/active/suspended/revoked/expired transitions and atomic revision-bound activation in `atmem/rules/lifecycle.py`; test failed qualification, stale source, duplicate transitions and crash recovery in `tests/test_rule_lifecycle.py`. Map FR-006, FR-007, FR-012, FR-013, FR-017; SC-001, SC-002.
- [ ] [T015] Integrate `atmem/adapters/hermes/feedback_guard.py` with `atmem/adapters/hermes/action_guard_plugin.py` and existing `atmem/action_guard.py`; verify real before-dispatch interception, wrapper/batch coverage and deny-wins in `tests/test_feedback_hermes_boundary.py`. Map FR-014, FR-015, FR-016; SC-004.
- [ ] [T016] Derive scoped/versioned enforcement capability and audit receipts using `atmem/task_state/enforcement.py`; implement installed Hermes conformance in `tests/integration/test_feedback_hermes_installed.py` with a synthetic effect recorder and credential-free local tools. Prove actual blocked/allowed effects, TOCTOU denial, no shadow effects and honest advisory-only status elsewhere. Map FR-014, FR-015, FR-023, FR-024; SC-004, SC-006.
- [ ] [T017] Implement dependent invalidation, revocation, rollback and restore reconciliation in `atmem/rules/lifecycle.py` and `atmem/feedback/store.py`; test source deletion during dispatch, stale caches, in-flight semantics and encrypted-store-only recovery in `tests/test_feedback_recovery.py`. Map FR-015, FR-017, FR-018, FR-021; SC-001, SC-002, SC-006.

## Phase 5 — Product surfaces and consented export (after T014–T017)

- [ ] [T018] Add read/report/propose CLI and MCP contracts in `atmem/cli_feedback.py`, `atmem/cli.py` and `atmem/mcp/server.py`, with separately authenticated owner operations; test scope, confirmation, sizes and parity in `tests/test_feedback_cli_mcp.py`. Map FR-001, FR-007, FR-020; SC-001, SC-007.
- [ ] [T019] Add the shared `atmem/control/feedback.py` service routes and Feedback screen in `atmem/control/server.py` and `atmem/control/assets/{app.html,app.js,app.css}`; show exact receipts, quality counts and explicit activation/rollback controls. Add CSRF/auth, keyboard and browser journey tests in `tests/test_feedback_dashboard.py`. Map FR-008, FR-012, FR-017, FR-020, FR-023; SC-007.
- [ ] [T020] Implement previewed purpose/recipient-bound verified-example export in `atmem/feedback/export.py`, with lineage and consent; exclude test splits, secrets, disputed/unverified/deleted sources and other users. Test withdrawal, tampered preview and encrypted destination handling in `tests/test_feedback_export.py`. Map FR-001, FR-018, FR-019, FR-020; SC-001, SC-007.

## Phase 6 — Evidence gates and documentation (after T018–T020)

- [ ] [T021] Execute real encrypted-store end-to-end and migration regression suites on Python 3.10–3.13 and Linux/macOS/Windows via a pinned job in `.github/workflows/verified-memory-feedback.yml`; record supported installed-host combinations. Include native/core/context/task-state/action-guard parity in `tests/integration/test_feedback_journey.py`. Map FR-002, FR-006, FR-014, FR-017, FR-018, FR-021; SC-001, SC-002, SC-004, SC-006.
- [ ] [T022] Implement reproducible latency/resource and quality report gates in `scripts/evaluate_verified_memory_feedback.py` and `tests/test_feedback_report_gates.py`; prove rejection of missing baselines/power/budgets and false success from synthetic-only data. Run synthetic contract measurements only until an approved efficacy manifest exists. Map FR-008, FR-009, FR-010, FR-013, FR-022, FR-023, FR-024; SC-003, SC-004, SC-005.
- [ ] [T023] With a separately approved bounded manifest, execute unchanged baselines then paired candidate evaluation, retaining every outcome and cost under `results/verified-memory-feedback/` with protected artifacts; stop at three attempts or any resource ceiling. Report accept/reject/inconclusive; do not run training or DolphinBench implicitly. Map FR-009, FR-010, FR-013, FR-022, FR-024; SC-003, SC-004, SC-005.
- [ ] [T024] Finish `docs/verified-memory-feedback.md`, `docs/benchmarks/verified-memory-feedback.md` and feature acceptance evidence: install/opt-in, privacy/deletion/export limits, capabilities, recovery and metric definitions. Review package/website release prerequisites only if publication is requested. Map FR-018, FR-019, FR-020, FR-021, FR-023, FR-024; SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007.

## Dependency and stop rules

T001–T003 establish contracts before storage. T004 precedes T005–T008. Review and
qualification precede profiles and rules. T015 depends on T012–T014; T016 depends
on T002/T015. T017 precedes public activation controls. Export requires verified
outcomes and current consent. T023 is blocked until its distinct manifest/budget
is approved; lack of approval does not block offline work or documentation.
No task completion may be inferred from a planned filename, a unit-only mock,
a retrieved memory, a screenshot, or an agent's self-reported success.
