# Click historical replay tasks

Implementation started under the owner's subsequent request; paid execution
remains separately gated. Dependencies flow by phase unless explicitly narrower below. Paths
are proposed implementation targets; task data is not claimed to exist yet.

## Phase 0 — Setup and protocol

- [x] [T001] Implement versioned protocol/task/run/result contracts in `benchmarks/code_replay/contracts.py`, rejecting missing chronology, versions, privacy profile, budgets and egress decisions. Verified by `tests/test_code_replay_contracts.py`; contract validation is not authorization or evidence that referenced artifacts are genuine. FR-002, FR-008, FR-009, FR-011, FR-012; SC-004.
- [x] [T002] Add frozen selection and exclusion-ledger support in `benchmarks/code_replay/select.py` with 100-entry first-parent horizon, five eligible tasks and no outcome-based filtering. Verified by `tests/test_code_replay_selection.py`; no actual Click tasks acquired/qualified yet (T004–T006 remain pending). FR-001; SC-001.
- [ ] [T003] Add dispatch-blocking authorization, budget and egress preflight to `benchmarks/code_replay/cli.py`; validate the Spec 042 T060 product capability receipt without changing owner configuration. B/D require Spec 042 T049–T051 and installed proof; C/D require the structural gates in the plan. FR-002, FR-012; SC-003.

  Partial: read-only `validate`, `select` and `preflight` commands exist and are
  tested in `tests/test_code_replay_preflight.py`. Preflight always reports blocked;
  no `run` command exists. Product capability and execution-authorization verifiers
  are not integrated. Referenced qualification hashes are declarations, not grants.
  T003 remains unchecked; no normal Codex trust or rich-knowledge gate is bypassed.

## Phase 1 — Foundational task/evaluator boundary

- [ ] [T004] Acquire/pin evaluator-only Click source and historic issue content, review redistribution/egress, and package permitted source/prompts in `benchmarks/code_replay/prepare.py`. FR-001, FR-002, FR-003; SC-001.
- [ ] [T005] Implement sealed grading and environment hashes in `benchmarks/code_replay/grade.py`, including parent-fail/reference-pass tests, regression/flake policy and anti-tamper rules. FR-007; SC-001.
- [ ] [T006] Record five authentic selected tasks and complete rejection ledger under `benchmarks/code_replay/tasks/`, and freeze protocol under `benchmarks/code_replay/protocols/` before target solving; blocked selection remains explicit. Depends T002, T004, T005. FR-001, FR-002, FR-007; SC-001.
- [ ] [T007] Implement source-only sandbox preparation, sanitized Git identity mapping, isolated homes/lanes/mounts and narrowly allowed inference transport in `benchmarks/code_replay/sandbox.py`. FR-003, FR-006, FR-010; SC-002.
- [ ] [T008] Integrate existing encrypted evidence retention, audited role checks, registered export/delete and readable dead-solver inspection in `benchmarks/code_replay/atmem_bridge.py`; no plaintext transcript side archive. FR-009, FR-010; SC-002, SC-006.
- [ ] [T009] Add negative future-object/remote/grader/host-file/cross-trial access and planted-secret/storage/disclosure tests in `tests/test_code_replay_isolation.py`. Depends T007, T008. FR-003, FR-009, FR-010; SC-002.

## Phase 2 — P1 matched real agent work

- [ ] [T010] Implement four-arm effective settings and ordinary host intake/recall/exposure probes in `benchmarks/code_replay/atmem_bridge.py`, enforcing product experience/applicability, rich-structure and normal-Codex blockers. Label assertion-only/syntax-index/harness diagnostics separately; no replacement product logic. FR-004, FR-009, FR-012; SC-003, SC-004.
- [ ] [T011] Implement bounded runner lifecycle, fresh sessions, agent/model pins, the plan's frozen three-row partial-position schedule, actual-order/deviation logging and terminal failure states in `benchmarks/code_replay/runner.py`; do not claim full position or carryover balancing. FR-004, FR-010, FR-011; SC-003, SC-004.
- [ ] [T012] Orchestrate arm-local trajectories using the qualified product formation/applicability services from Spec 042 T049–T051, not new harness classifiers; implement cold first task, capture-before-reset, authentic tree transitions and candidate/admitted/applicable/retrieved/delivered counts in `benchmarks/code_replay/history.py`. Depends T010. FR-005, FR-006; SC-003, SC-004.
- [ ] [T013] Implement stage durations, tokens/cache/price provenance, cold/warm overhead and measured-or-unknown fields in `benchmarks/code_replay/metrics.py`. FR-008, FR-011; SC-004, SC-005.
- [ ] [T014] Add matched-input/arm separation, hidden-grade withholding, reset/anchor races, timeout/product-failure and whole-repetition infrastructure rerun tests in `tests/test_code_replay_runner.py`; assert the frozen schedule, one run per arm/task/repetition, 60 planned sessions, three distinct positions per arm and unchanged row on infrastructure rerun. Depends T010–T013. FR-004, FR-005, FR-006, FR-007, FR-010, FR-011; SC-003, SC-004.

## Phase 3 — P2 transparent comparison

- [ ] [T015] Build authorized inspect/report operations in `benchmarks/code_replay/report.py` and `benchmarks/code_replay/cli.py`: per-task and trajectory table, harm/attrition/unknowns, cold task, total overhead, memory-source-applicability-context-use links and truthful partial capture. FR-008, FR-009, FR-011; SC-004, SC-005, SC-006.
- [ ] [T016] Test raw-to-summary denominators, no unsupported benefit claims, wrong-scope denials, protected export/delete and fresh-process evidence-only reconstruction in `tests/test_code_replay_reporting.py`. Depends T008, T013, T015. FR-009, FR-010, FR-011; SC-002, SC-005, SC-006.

## Phase 4 — Polish, qualification and gated pilot

- [ ] [T017] Document isolated setup/inspection and real-run gates in `benchmarks/code_replay/README.md`; add harness unit CI across Python 3.10–3.13 and platform-specific sandbox qualification in `.github/workflows/code-replay.yml`. FR-010, FR-012; SC-002, SC-003.
- [ ] [T018] Run disjoint fixture/integration dry runs and record exact configuration and unmet prerequisites in `benchmarks/code_replay/qualification.md`; fixtures are plumbing evidence only, not the five target tasks. Depends T009, T014, T016, T017. FR-002, FR-010, FR-012; SC-002, SC-003, SC-004.
- [ ] [T019] After separate execution/budget/egress authorization and all readiness gates, execute the frozen 60-session pilot or record a distinctly versioned reduced/blocked protocol using `benchmarks/code_replay/cli.py`; retain every failure and no adaptive target retry. Depends T006, T018. FR-002, FR-004, FR-005, FR-006, FR-007, FR-008, FR-010, FR-011, FR-012; SC-001–SC-005.
- [ ] [T020] Generate the owner-inspectable comparison through `benchmarks/code_replay/report.py`, including raw evidence references, per-task memories and caveats; do not publish externally without separate authorization. Depends T019. FR-009, FR-011, FR-012; SC-004, SC-005, SC-006.

## Coverage and scope

## Active reduced v2 implementation and execution

These narrower tasks do not mark the broader four-arm/normal-host tasks above
complete. The owner subsequently authorized completing implementation and the
five-task comparison; MEM is used only for benchmark inputs/archives.

- [x] [T021] Freeze the reduced C/D package from authentic Click history and recoverable pre-solution reports, retain all 26 examined entries, qualify each parent and two reference runs against the full frozen regression suite, record behavioral/environment adaptations before target solving. `frozen.py`, `freeze.py`; external protocol SHA-256 `c18f4802c426e316b0a5ca1f58a61188755f61fd92cdd179c106a1a988959d1d`.
- [x] [T022] Implement the explicitly selected installed-product benchmark bridge, isolated subscription CLI sessions, no-reference-feedback arm history and bounded termination; require frozen source/grader/artifact binding, per-run read-denial and rich-currentness checks. `history.py`, `pilot.py`, `runner.py`; disjoint bridge, anti-tamper and descendant-pipe tests. Normal Codex hooks remain unqualified, token limits remain post-turn audited, and v1 preflight remains blocked.
- [x] [T023] Add fresh-process protected-backup event recovery, scoped delete/adjacent preservation and recipient-encrypted exact-event export tests. `test_code_replay_evidence.py`; these prove declared-event preservation, not unobserved full model/system capture. Real pilot archive round trip remains part of T024.
- [x] [T024] Complete all 20 frozen attempts without adaptive retries, generate the authorized comparison and memory attrition trail, recipient-encrypt archives to MEM and verify exact retained-event round trips. Keep failures, missing/unknown measures and cold trajectories explicit. `report.py`, `test_code_replay_reporting.py`. Completed: C 7/10, D 6/10; eight observations admitted, zero prior-memory exposures and all ten paired context digests identical. Therefore no causal memory benefit/harm or speedup claim. See `RandD/2026-10-17-click-structure-experience-final.md`; 21 chunked recipient-encrypted run/protocol archives round-trip exact bytes. Git-config and scratch limitations are recorded; broad v1/normal-host/release tasks remain open.

## Original scope coverage

- [ ] [T027] Implement and run the owner-requested bounded structural-efficiency loop in `structure-improvement-loop.md`; preserve task/environment/solver fairness, explicit token and quality gates, all attempts, encrypted archives and separate tuning/confirmation reporting. Depends 042 T061/T062; prior results remain immutable.

  Forty sessions executed, all 45 encrypted bundles verified, and fresh-process
  recovery after RAM disposal recovered 142 events/40 trials. Neither token
  target is confirmed; task remains open for its acceptance outcome. See the
  RandD structural-efficiency report. Any next loop needs a new protocol and
  new transfer tasks, not relabelled first-loop failures.

## Fresh no-memory control (owner follow-up)

- [x] [T025] Freeze and test a distinct five-pair A/C follow-up with native tools unchanged, experience disabled, corrected Git runtime, empty additional context in A and installed structural delivery in C. See `structure-control-v3.md`; do not pool with v2 or call reused tasks confirmation. Qualified manifest SHA-256 `1143c194e0e02cacef5071828eaa7410a6e1dcae0d0e286d10cb46107dc14560`; 90 harness checks pass. Original preflight-only Git-path rejection retained separately; zero inference dispatches before correction.
- [x] [T026] Execute all ten attempts, retain failures and separate functional versus budget passes, compare quality/time/usage, archive exact declared events to MEM and verify fresh-process recovery before removing volatile scratch. Report in RandD without release/publication. Completed: A/C both 4/5 all-budget passes; A 5/5 versus C 4/5 functional default-suite passes. Median measured path 24.97s/32.75s; no net benefit demonstrated. Eleven encrypted archives round-trip exact events; after volatile scratch removal, a new process recovers 34 events and ten terminal trials without the vault. See `RandD/2026-10-17-click-native-structure-control.md`. Broader v1/product/release gates remain unchanged.

All FR-001–FR-012 and SC-001–SC-006 map to the tasks above. T019/T020 remain
future gated execution and are not authorized by the implementation request alone.
Spec 042 CK implementation and adapter qualification remain dependencies owned
by their own workstreams; do not quietly count an absent extractor as present.
Experience-only B has product dependencies too: Spec 042 T049–T051 and installed
proof, exposed through T060. Its availability is not implied by historical T012.
