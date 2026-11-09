# Implementation tasks — Spec 050

Status: implementation in progress. Foundation, generic MCP, outcome capture,
review and the pure rule compiler/evaluator are locally tested; a tested local host
candidate resolves the boundary prerequisite. See `implementation-evidence.md`;
unchecked tasks and full installed rule-service qualification are not complete.
Read `spec.md`, `plan.md`, `research.md` and the constitution before implementation.
Dependencies are sequential by phase; no delegated agent work is requested here.
Referenced new paths are implementation targets. No paid evaluation is authorized.

## Phase 1 — Baseline and contracts

- [x] [T001] Freeze native/current-AtMem baseline definitions, corpus and verification requirements, cost-zero default, three-attempt cap and all SC thresholds in `docs/benchmarks/verified-memory-feedback.md`; introduce bounded manifest fixtures under `tests/fixtures/feedback/`. Map FR-009, FR-022, FR-024; SC-003, SC-005.
- [x] [T002] Pin the initial installed Hermes version, dispatch/wrapper boundary, supported tool schemas and OS capability matrix in `docs/verified-memory-feedback.md`; record existing guard tests and limits before integration. Map FR-014, FR-021, FR-024; SC-004, SC-006.
- [x] [T003] Add versioned scope, outcome, verification, rule, qualification, activation, export and provider/MCP contracts in `atmem/contracts/feedback.py` and `atmem/schemas/v1/feedback-*.json`; validate bounded inputs and forbidden client-supplied roles in `tests/test_feedback_contracts.py`. Map FR-001, FR-002, FR-003, FR-005, FR-006, FR-011, FR-012, FR-019, FR-025, FR-026, FR-028, FR-029; SC-001, SC-008, SC-009.

## Phase 2 — Authoritative evidence and outcomes (after T001–T003)

- [x] [T004] Implement additive protected persistence in `atmem/feedback/store.py` and `atmem/evidence/store.py`; keep bounded evidence, mutation and idempotency receipt in one existing-vault transaction. Anchor scoped ciphertext using encrypted pending/committed Home checkpoints; effects require both commits. Opt-in container format 4 prevents unsafe old-reader rotation. Test encrypted metadata, rollback, concurrent retries, preserved existing evidence and multi-scope key rotation in `tests/test_feedback_store.py` and `tests/test_feedback_integrity.py`. Full dependent recovery remains T017. Map FR-002, FR-006, FR-018, FR-021; SC-002, SC-006.
- [x] [T005] Implement authenticated scoped operations in `atmem/feedback/service.py`, reusing authority and review identities; add cross-user/agent/workspace and non-disclosure tests in `tests/test_feedback_authority.py`. Map FR-001, FR-007, FR-018; SC-001.
## Phase 2a — Generic governed RAG/MCP (after T003–T005, before T006)

- [x] [T025] Implement owner-scoped provider registration and an encrypted-vault/RAM-FTS SQLite document provider in `atmem/knowledge/rag/{contracts,sqlite}.py` and shared persistence; define source revisions, explicit egress and bounded search/inspect. Test real temporary corpus, no plaintext disk index, migration and source isolation in `tests/test_rag_provider.py`. Map FR-001, FR-018, FR-025, FR-026, FR-027, FR-030; SC-001, SC-006, SC-008.
- [x] [T026] Implement scoped RAG service with provenance, jurisdiction/as-of filters, encrypted receipts, post-query revalidation and revision-bound inspection in `atmem/knowledge/rag/service.py`; test independent adapter, malformed/cross-scope results, revoked sources, injection, deadlines and offline failure in `tests/test_rag_service.py`. Map FR-025, FR-026, FR-027, FR-030; SC-001, SC-002, SC-008.
- [x] [T027] Implement the host-neutral local stdio server in `atmem/mcp/governed.py`, credential/agent/workspace binding, explicit protocol negotiation, closed tools and a CLI entry in `atmem/cli_feedback.py`; add actual subprocess MCP client tests in `tests/test_governed_mcp.py`. Expose only implemented capabilities, with no dependency on Hermes or privileged model tools. Map FR-001, FR-020, FR-028, FR-030; SC-001, SC-007, SC-008, SC-009.

## Phase 2b — Outcome verification (after T025–T027)

- [x] [T006] Link real context receipts, exact invocation/check evidence and late/duplicate observations in `atmem/feedback/service.py`; test a read success with a failed write and forbid combining partial calls in `tests/test_feedback_actions.py`. Map FR-002, FR-005, FR-006; SC-002.
- [ ] [T007] Implement scoped verifier registration, independent readback results, attestation tiers, disputes and evidence-backed failure attribution in `atmem/feedback/verification.py`; cover fabricated success, missing capture, poisoned feedback and delivered-but-not-applied in `tests/test_feedback_verification.py`. Map FR-003, FR-004, FR-005, FR-024; SC-001, SC-002.
- [x] [T008] Implement exact metric denominators, zero/unknown handling, episode uncertainty, cost and content-free telemetry in `atmem/feedback/metrics.py`; test abstain-all, unassessed answers, scope leakage and required-fact write failures in `tests/test_feedback_metrics.py`. Map FR-008, FR-023, FR-024; SC-003, SC-007.

## Phase 3 — Reviewed retrieval adaptation (after T004–T008)

- [x] [T009] Extend `atmem/extract/review.py` for revision-bound profile/rule proposals without changing ordinary fact admission; add stale/racing reviewer, injection and owner-versus-model capability tests in `tests/test_feedback_review.py`. Map FR-007, FR-010, FR-011, FR-012; SC-001.
- [ ] [T010] Implement frozen manifest validation, safe paired replay, bounded attempts, cost stops, independent verifier binding and expiring accept/reject/inconclusive receipts in `atmem/feedback/qualification.py`; test held-out contamination and unknown outcomes in `tests/test_feedback_qualification.py`. Map FR-003, FR-009, FR-010, FR-013, FR-022, FR-024; SC-003, SC-004, SC-005.
- [x] [T011] Integrate versioned ranking/threshold/packing profiles with `atmem/context_engine/profiles.py` and `atmem/context_engine/service.py`; prove scope invariance, disabled parity, shadow without mutation, qualified activation and local deterministic fallback in `tests/test_feedback_profiles.py`. Map FR-010, FR-017, FR-021; SC-001, SC-003, SC-005.

## Phase 4 — Rules and real enforcement (after T009–T011)

- [x] [T012] Implement the three-predicate rule representation and non-executable compiler in `atmem/rules/models.py` and `atmem/rules/compiler.py`; test unsupported language, arbitrary code, ambiguous aliases and source grounding in `tests/test_rule_compiler.py`. Map FR-011, FR-016; SC-001.
- [x] [T013] Implement deterministic evaluation, conflicting predicates, deny-wins and exact single-use approval binding in `atmem/rules/evaluator.py`; test changed arguments, replay, expiry and permission narrowing in `tests/test_rule_evaluator.py`. Map FR-001, FR-014, FR-015, FR-016; SC-001, SC-004.
- [x] [T014] Implement shadow/qualified/active/suspended/revoked/expired transitions and atomic revision-bound activation in `atmem/rules/lifecycle.py`; test failed qualification, stale source, duplicate transitions and crash recovery in `tests/test_rule_lifecycle.py`. Map FR-006, FR-007, FR-012, FR-013, FR-017; SC-001, SC-002.
- [x] [T028] Implement registered guarded execution in `atmem/mcp/guarded.py` using the shared evaluator/lifecycle and encrypted intent/result receipts; test two independent client identities, exact approval arguments, replay, concurrent duplicate keys, uncertain writes and advisory-only checks in `tests/test_guarded_mcp.py`. No arbitrary endpoints or host tools. Map FR-001, FR-014, FR-015, FR-017, FR-028, FR-029; SC-001, SC-004, SC-009.
- [x] [T015] Integrate `atmem/adapters/hermes/feedback_guard.py` with `atmem/adapters/hermes/action_guard_plugin.py` and existing `atmem/action_guard.py`; verify real before-dispatch interception, wrapper/batch coverage and deny-wins in `tests/test_feedback_hermes_boundary.py`. Map FR-014, FR-015, FR-016; SC-004.
- [ ] [T016] Derive scoped/versioned enforcement capability and audit receipts using `atmem/task_state/enforcement.py`; implement generic MCP proxy conformance plus installed Hermes adapter conformance in `tests/integration/test_feedback_hermes_installed.py` with a synthetic effect recorder and credential-free local tools. Prove actual blocked/allowed effects, TOCTOU denial, no shadow effects and honest advisory-only status elsewhere. Map FR-014, FR-015, FR-023, FR-024; SC-004, SC-006, SC-009.
- [ ] [T017] Implement dependent invalidation, revocation, rollback and restore reconciliation in `atmem/rules/lifecycle.py` and `atmem/feedback/store.py`; test source deletion during dispatch, stale caches, in-flight semantics and encrypted-store-only recovery in `tests/test_feedback_recovery.py`. Map FR-015, FR-017, FR-018, FR-021; SC-001, SC-002, SC-006.

## Phase 5 — Product surfaces and consented export (after T014–T017)

- [x] [T018] Add read/report/propose CLI and MCP contracts in `atmem/cli_feedback.py`, `atmem/cli.py` and the separate `atmem/mcp/governed.py` (existing default server unchanged), with separately authenticated owner operations; test scope, confirmation, sizes and parity in `tests/test_feedback_cli_mcp.py`. Map FR-001, FR-007, FR-020; SC-001, SC-007.
- [x] [T019] Add the shared `atmem/control/feedback.py` service routes and Feedback screen in `atmem/control/web.py` (the actual HTTP server) and `atmem/control/assets/{app.html,app.js,app.css}`; show exact receipts, quality counts and explicit activation/rollback controls. Add CSRF/auth, keyboard and browser journey tests in `tests/test_feedback_dashboard.py`. Map FR-008, FR-012, FR-017, FR-020, FR-023; SC-007.
- [x] [T020] Implement previewed purpose/recipient-bound verified-example export in `atmem/feedback/export.py`, with lineage and consent; exclude test splits, secrets, disputed/unverified/deleted sources and other users. Test withdrawal, tampered preview and encrypted destination handling in `tests/test_feedback_export.py`. Map FR-001, FR-018, FR-019, FR-020; SC-001, SC-007.

## Phase 6 — Evidence gates and documentation (after T018–T020)

- [ ] [T021] Execute real encrypted-store end-to-end and migration regression suites on Python 3.10–3.13 and Linux/macOS/Windows via a pinned job in `.github/workflows/verified-memory-feedback.yml`; record supported installed-host combinations. Include native/core/context/task-state/action-guard parity in `tests/integration/test_feedback_journey.py`. Map FR-002, FR-006, FR-014, FR-017, FR-018, FR-021; SC-001, SC-002, SC-004, SC-006.
- [ ] [T022] Implement reproducible latency/resource and quality report gates in `scripts/evaluate_verified_memory_feedback.py` and `tests/test_feedback_report_gates.py`; prove rejection of missing baselines/power/budgets and false success from synthetic-only data. Run synthetic contract measurements only until an approved efficacy manifest exists. Map FR-008, FR-009, FR-010, FR-013, FR-022, FR-023, FR-024; SC-003, SC-004, SC-005.
- [ ] [T023] With a separately approved bounded manifest, execute unchanged baselines then paired candidate evaluation, retaining every outcome and cost under `results/verified-memory-feedback/` with protected artifacts; stop at three attempts or any resource ceiling. Report accept/reject/inconclusive; do not run training or DolphinBench implicitly. Map FR-009, FR-010, FR-013, FR-022, FR-024; SC-003, SC-004, SC-005.
- [ ] [T024] Finish `docs/verified-memory-feedback.md`, `docs/benchmarks/verified-memory-feedback.md` and feature acceptance evidence: install/opt-in, privacy/deletion/export limits, capabilities, recovery and metric definitions. Review package/website release prerequisites only if publication is requested. Map FR-018, FR-019, FR-020, FR-021, FR-023, FR-024; SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007.

- [x] [T029] Reconcile public docs, feature statuses, CLI help and tool inventories against executable capabilities; add `scripts/check_feedback_docs.py` and `tests/test_feedback_docs.py` to reject Hermes-only descriptions, unimplemented tool claims and missing RAG/MCP boundaries. Finish `docs/governed-rag-and-mcp.md`. Map FR-024, FR-025, FR-026, FR-028, FR-029, FR-030; SC-007, SC-008, SC-009.

## Dependency and stop rules

T001–T003 establish contracts before storage. T004 precedes T005. T025–T027 follow T005 and precede T006–T008. Review and
qualification precede profiles and rules. T028 depends on T012–T014 and T027. T015 depends on T028; T016 depends
on T002/T015/T028. T017 precedes public activation controls. Export requires verified
outcomes and current consent. T023 is blocked until its distinct manifest/budget
is approved; lack of approval does not block offline work or documentation.
No task completion may be inferred from a planned filename, a unit-only mock,
a retrieved memory, a screenshot, or an agent's self-reported success.

Owner authorized routine implementation decisions without step-by-step supervision on 2026-11-09. Follow the revised dependency order autonomously; keep tests and checked tasks honest. External paid efficacy and publication retain their separate existing gates.


## 2026-11-10 implementation checkpoint

Checked tasks reflect implemented paths with real-store/client/browser/host
consumer tests, not a production efficacy result. In particular, active rule and
profile consumer tests use explicitly labelled trusted-store test receipts;
the production diagnostic qualifier cannot emit those accepted receipts.

- T007: independent readback, operation binding, disputes and proposed taxonomy
  exist; complete independently verified causal attribution remains unbuilt.
- T010/T022: frozen offline manifests, persistent attempt budgets, paired replay
  and insufficient-evidence/resource gates exist. Production accept/reject
  qualification and complete independently measured quality/power/resource gates
  remain unbuilt. Do not mark these complete because diagnostic reports pass.
- T016: eleven real-import Hermes candidate/service cases passed on macOS with
  Python 3.14.7. Full version/schema/OS conformance and derived task-state
  enforcement registration remain pending; the owner runtime is unchanged.
- T017: supported Home preflight/adoption automatically blocks feedback pending
  scoped owner reconciliation. Direct canonical database restore and arbitrary
  file-copy recovery still require operator reconciliation; full crash/deletion
  coverage outside the Home workflow remains pending.
- T021: source `61b64d5` passed 12 feature OS/Python jobs and all 48 main CI
  jobs. Final product source `a2fb7ce` also passed direct owner-Windows installed
  encryption (23 tests), checkpoint/action preflight and broad native/browser
  checks; the lone source-packaging harness path error passed on corrected-CWD
  rerun. See evidence for the POSIX-only skip and overlapping counts. Its feature
  matrix passed 11 jobs and hit the 15-minute deadline on Windows/Python 3.12;
  Windows CI now has a bounded 30-minute allowance with every check retained.
  Fresh final workflow results are tracked on PR #37. Broader T016/T017 acceptance
  remains open; these results do not complete the feature-wide acceptance task.
- T023 requires a separately approved bounded efficacy manifest. No such run,
  paid call, training or DolphinBench campaign was performed.
- T024: setup/privacy/limits/status documentation is updated; final feature-wide
  acceptance evidence remains incomplete until the remaining gates are met.
