# Tasks — Hermes integration

Core implementation is underway under the user-approved `authorized-at-recall-v1`
profile in `contracts.md`; per-model-call revalidation is deferred, not blocking.
Follow phase order. Do not start paid work
without a run-specific budget. Paths for new files are proposed.

## A. Source and contract qualification

- [x] T001 Inspect pinned Hermes discovery, MemoryProvider/Manager, final model context, spill, native memory and lifecycle source; record tested hook/capability/version/license matrix in `specs/037-hermes-integration/research.md` and `validation.md` (FR-001, FR-005, FR-007, FR-009). Source probes pass; per-request enforcement is deferred, not certified.
- [x] T002 Audit `atmem/server/auth.py`, `atmem/client.py`, `atmem/service/` and existing control APIs; document server-bound profile credentials, least privilege and proposed additive operations in `specs/037-hermes-integration/contracts.md` (FR-003, FR-006). Wire schema waits for T003's profile decision.
- [x] T003 Specify checkpoint generation/content identity, read-only memory versus append-only evidence, encrypted queue/acknowledgment semantics and interrupted restore in `specs/037-hermes-integration/contracts.md`; resolve Phase A delivery/identity gates before B (FR-002, FR-004, FR-005, FR-011). User approved fresh-recall authorization; product bindings use operator-selected scope. HTTP provisioning and enforcement remain T004, not a claimed existing feature.

## B. Product integration

- [ ] T004 Implement scoped Hermes binding in `atmem/adapters/hermes/` and necessary versioned product RPCs in `atmem/control/web.py` using existing `atmem/service/` authority; test denial of forged subject/role/session and cross-profile/child authority in `tests/test_hermes_authority.py` (FR-003, FR-006; SC-002). Scoped RPC and trusted provisioning methods pass the reviewed milestone; public admin provisioning/setup remains linked to T006.
- [ ] T005 Ship the provider directory from `atmem/adapters/hermes/package.py` and `assets/plugin_entry.py`, included in built distribution metadata; test Hermes discovery without modifying its managed Python dependencies or AtMem base imports in `tests/test_hermes_packaging.py` (FR-001; SC-001). Wheel payload/native ABC registration passes; full native plugin-discovery acceptance remains.
- [ ] T006 Implement preview, idempotent setup, explicit activation, backup, conflict-safe restore and crash receipts in `atmem/hermes_install.py` and `atmem/cli.py`; test interrupted transitions and untouched native stores in `tests/test_hermes_install.py` (FR-002, FR-006; SC-001).
- [ ] T007 Implement ordinary governed capture/recall/tools, durable retry identities and bounded context-aware worker/drain behavior in `atmem/adapters/hermes/`; test queue exhaustion, duplicate delivery, crash and background failures in `tests/test_hermes_lifecycle.py` (FR-004, FR-006; SC-002).
- [ ] T008 Implement fresh authorization for returned nominations and safe context bounds in `atmem/adapters/hermes/`; test first-turn/repeated-call behavior, spills, revocation races, supersession, quarantine, expiry, deleted records and stale cache in `tests/test_hermes_delivery.py` (FR-005; SC-002).
- [ ] T009 Bind captured boundaries to encrypted AtMem evidence through `atmem/evidence/`; test privilege matrix, secret handling, loss of keys/storage, captured-byte reconstruction without host logs and honest missing-hook labels in `tests/test_hermes_evidence.py` (FR-007; SC-003).
- [ ] T010 Add shared CLI/dashboard Hermes status, scope, setup/activation/restore, local display time and actionable errors under `atmem/cli.py` and existing dashboard assets located during implementation; record exact asset paths in this task before edits and test in `tests/test_hermes_dashboard.py` (FR-008; SC-003).

## C. Installed product acceptance — required before benchmark code

- [ ] T011 Build and test fresh install, upgrade, disable/restore, provider conflicts and concurrent sessions without benchmark imports in `tests/installed_hermes_acceptance.py`; record exact macOS/Linux and Windows/WSL coverage in `specs/037-hermes-integration/validation.md`; run existing OpenClaw/framework regressions (FR-009; SC-001, SC-002, SC-003).
- [ ] T012 Implement or extend product snapshot/read-only capabilities in `atmem/control/memory_checkpoints.py` and existing authorization services; test durable cross-process checkpoints, incomplete queues, content tampering, every mutation path and separate evidence sink in `tests/test_hermes_checkpoints.py` (FR-004, FR-011; SC-002).

## D. Inert DolphinBench driver and no-cost checks

- [ ] T013 Add upstream/data/license/artifact/model/tool/settings manifest and split policy in `benchmarks/dolphinbench/manifest.json`; use no secret values and pin artifacts before execution (FR-010, FR-013).
- [ ] T014 Implement only upstream identity/invocation/freeze/verification/accounting delegation in `benchmarks/dolphinbench/driver.py`; invoke installed Hermes and AtMem; forbid product recovery/extraction/ranking implementation in the rig (FR-010, FR-011).
- [ ] T015 Implement exact interaction/usage recording, persisted cost ledger, in-flight budget reservations and safe resume in `benchmarks/dolphinbench/recording.py`; record pricing provenance and separate grader/infra totals (FR-012, FR-013; SC-004).
- [ ] T016 Test MCP wiring, fresh conversations/personas, mutation denial, sandbox answer/real-tool exclusion, actual-request/export equivalence, unknown usage, retries, budget stop and resume in `tests/benchmarking/test_dolphinbench_contracts.py`; run upstream no-cost prepare and verify archive schema/size in `tests/benchmarking/test_dolphinbench_submission.py` (FR-010, FR-011, FR-012, FR-014; SC-004, SC-005).

## E. Budgeted public-data evaluation

- [ ] T017 Record new pilot budget/model/grader approval and credential-presence checks in `benchmarks/dolphinbench/runs/README.md`; execute deterministic public-data pilot only after T011–T016 pass, retain complete evidence and measured full-run cost estimate; label partial, not leaderboard-qualified (FR-012, FR-013; SC-004).
- [ ] T018 After separate full-run approval, freeze configurations and run matched native/AtMem arms with full histories and all 600 tasks; add Mem0 only if approved and available. Store immutable manifests/raw evidence per run under the operator-selected protected output root, indexed by `benchmarks/dolphinbench/runs/README.md` (FR-010–FR-013; SC-005).
- [ ] T019 Produce per-task/per-persona paired results, bootstrap uncertainty, repeated-run policy, untouched-task disclosure, resource/latency/cost accounting and failure analysis in `benchmarks/dolphinbench/report.md`; keep historical baselines distinct and claim no unrun replication (FR-012, FR-013; SC-004, SC-005).
- [ ] T020 Validate the complete upstream submission ZIP and website size limit; document self-submitted/unverified status in `benchmarks/dolphinbench/submission.md`; submit only upon explicit approval and record the actual resulting URL/status (FR-014; SC-005).

## F. Documentation and handoff

- [ ] T021 Write setup/configuration/restore/egress/coverage/troubleshooting guide in `docs/website/integrations/hermes.md`, update navigation/manifest and relevant API references, and test all documented installed commands (FR-001, FR-002, FR-006, FR-008, FR-014; SC-001).
- [ ] T022 Reconcile `specs/011-framework-adapter-conformance/`, `specs/integration-ownership.md`, `docs/release-roadmap.md` and `specs/product-roadmap.md` with verified capabilities; record all gates in `specs/037-hermes-integration/validation.md`; select a release only with explicit authorization and follow `docs/release-coordination.md` including the separate owner-reviewed AtMem.ai PR (FR-009, FR-014).

## G. First-class Hermes experience (required for integration beta)

- [ ] T023 Extend T006/T010 in `atmem/hermes_install.py`, `atmem/cli.py` and existing dashboard integration surfaces with the FR-015 command family, `init` discovery, consolidated `status`, shared preview/apply and exact repair actions. Record actual asset paths before editing; test CLI/dashboard agreement in `tests/test_hermes_dashboard.py`.
- [ ] T024 Extend `tests/test_hermes_install.py` and `tests/installed_hermes_acceptance.py` with provider-switch, custom Home, two profiles, occupied ports, interrupted upgrade, conflict-safe restore and fresh/upgrade journeys. Record receipts and capability comparison in `specs/037-hermes-integration/parity.md`; show that no history import occurred (FR-016, SC-006).
- [ ] T025 Implement versioned, secret-safe observation/correlation under `atmem/adapters/hermes/` only after AtFlows Spec 006 T055 identifies real host hooks. Test actual-session cross-dashboard evidence, unavailable AtFlows, reconnect and profile isolation in `tests/test_hermes_observability.py` (FR-017, SC-007).
- [ ] T026 Complete AtFlows Spec 006 T055–T067 and update `docs/website/integrations/hermes.md` with the coordinated installed versions, supported capture matrix and tested commands. Attach raw sanitized acceptance records to `validation.md` before any parity claim (SC-006/007). Depends on T011, T023–T025; these product gates precede T017 paid evaluation.

## H. Native provider-list slice (prioritized within T005/T006)

- [x] T027 Update Spec 037 spec/plan/tasks for FR-018/019/SC-008; obtain read-only Claude design review and resolve blocking findings before this slice's code edits. Claude final read-only design gate: no blockers for inactive discovery; activation remains separate.
- [x] T028 Make `atmem/adapters/hermes/assets/plugin_entry.py` register an unavailable native provider without connection files, with safe setup diagnostics. Extend `tests/test_hermes_packaging.py` for invalid/missing config, secrets and native discovery/status behavior (FR-018).
- [x] T029 Add preview/idempotent atomic inactive installation and ownership hashes in `atmem/hermes_install.py`, `atmem/cli.py` and `tests/test_hermes_install.py`. Reject unsafe targets/unmanaged or edited payloads; preserve native config and stores; do not mint credentials (FR-019). Tested on macOS; Linux primitive implemented but not executed here.
- [x] T030 Extend `tests/installed_hermes_payload.py` and native integration tests to verify actual discovery/dashboard metadata, unavailable selection denial and configured temporary capture/new-session recall through normal AtMem APIs. Run focused regressions/build and read-only Claude code review before local apply (SC-008).
- [x] T031 Apply reviewed artifact's inactive plugin to the existing local Hermes Home and verify its actual dashboard provider list. Record package hash, host version, default provider preservation and exact live readiness in `validation.md`. Do not claim full activation, AtFlows observation or benchmark completion (FR-018/019, SC-008). Native dashboard metadata helper verified; root HTTP 200; authenticated browser rendering was not inspected.

T028 also covers the no-write setup hook, optional status argument, manifest
guidance and bounded configured probe. T029 covers write-free preview, exclusive
publication and crash/unsafe-target tests. T030 distinguishes dashboard refusal
from the generic picker/forced-selection host fallback and verifies proposal
review/admission before recall. These are review gates, not deferred polish.

## Requirements coverage

- [x] T032 Review and deploy the tested development wheel to the explicitly requested local AtMem installation; preserve rollback material and Home backup, leave dependencies and provider selection unchanged, restart the existing dashboard daemon, verify RPC denial/dashboard health, and record exact artifact/provenance in `validation.md` (FR-002/006/009).

Implementation progress, 2026-09-26: scoped transport, encrypted credential
lifecycle, core binding/provider and packaged payload are implemented. The focused
suite passes 91 tests with one skip, and a clean installed-wheel payload check
passes. Claude completed read-only review and follow-up; exact scope, findings,
artifact hash and limitations are in `validation.md`. Keep tasks unchecked until
public setup, full native discovery, durability and broader acceptance pass.
Standalone Hermes is now installed (see validation addendum). No AtMem provider
activation, AtFlows runtime connection or benchmark result exists.

| Requirement | Tasks |
| --- | --- |
| FR-001 | T001, T005, T021 |
| FR-002 | T003, T006, T021 |
| FR-003 | T002, T004 |
| FR-004 | T003, T007, T012 |
| FR-005 | T001, T003, T008 |
| FR-006 | T002, T004, T006, T007, T021 |
| FR-007 | T001, T009 |
| FR-008 | T010, T021 |
| FR-009 | T001, T011, T022 |
| FR-010 | T013, T014, T016, T018 |
| FR-011 | T003, T012, T014, T016, T018 |
| FR-012 | T015–T019 |
| FR-013 | T013, T015, T017–T019 |
| FR-014 | T016, T020–T022 |
| FR-015 | T006, T010, T023, T026 |
| FR-016 | T006, T024, T026 |
| FR-017 | T025, T026 |
| FR-018 | T027, T028, T030, T031 |
| FR-019 | T027, T029, T030, T031 |
| SC-008 | T028–T031 |
| SC-006 | T011, T023, T024, T026 |
| SC-007 | T025, T026 |
| SC-001 | T005, T006, T011, T021 |
| SC-002 | T004, T007, T008, T011, T012 |
| SC-003 | T009–T011 |
| SC-004 | T015–T017, T019 |
| SC-005 | T016, T018–T020 |
