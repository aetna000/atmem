# Tasks: Agent Continuity Benchmark

## Active tasks — product-first correction, 2026-09-25

These tasks supersede the earlier execution order. Original T tasks below record
historical fixture work, not product acceptance. See `product-first-correction.md`.

- [x] [P000] Audit fixture recovery in `benchmarks/agent_continuity/runtime.py` and `adapters/atmem.py`; record product/rig split and corrected claims in `product-first-correction.md`.
- [x] [P001] Map PC-001–PC-003 to existing Spec 007/020 product services and a supported integration; define public contracts, storage/migration/security and exact user acceptance in `product-contracts.md`; read-only Claude review before code.
- [x] [P002] Implement PC-001 authoritative operation/receipt support in the owning AtMem package services identified by P001; product tests for intent/receipt crash windows, scope, conflicting payloads, concurrency and encrypted evidence.
- [x] [P003] Implement PC-002 shipped host/tool integration and PC-003 example/status/enablement outside `benchmarks/`; verify permissions, unknown outcomes, key expiry and safe retries. Record exact package paths and tests before marking complete.
- [x] [P004] Add installed-artifact acceptance for PC-005 with source/benchmark paths unavailable; user example must resume or block without harness state or decisions.
- [x] [P005] Coordinate AtFlows Spec 010 P101–P104: shipped identity/cost/recovery views; no test-generated replacement telemetry.
- [ ] [P006] Refactor `benchmarks/agent_continuity/runner.py`, `runtime.py` and adapters into fault/measurement-only product evaluation; preserve old fixtures as historical design tests. Test imports AND process data flow for compensation/oracle leakage (PC-005–PC-006).
- [ ] [P007] Qualify normal execution and four-arm crash/context/cost runs with frozen installed artifacts; preregister repeats/held-out analysis, preserve raw results and existing cumulative budget in `reports/`.
- [ ] [P008] Record read-only Claude review, findings/corrections and test evidence after each product milestone in `milestone-reviews.md`; run compatibility/docs/artifact gates before any feature claim.

## Historical tasks — superseded sequence, preserved evidence

P001–P004 evidence: `atmem/continuity/{service,client,integrations,tools,example,langgraph_example}.py`,
`docs/continuity.md`, product/HTTP/integration tests and
`results/product-acceptance-20260925-005` under the benchmark directory. Build005
direct and LangGraph examples each passed both actual process-kill receipt windows.
Published2.3.6 evidence-store upgrade preserves data and refuses old readers after
opt-in. Optional Spec007 task projection remains explicitly outside this delivered
operation profile. P005 also passes published AtFlows0.1.2 trace/login preservation,
installed SDK/HTTP, browser and existing observation/proxy compatibility gates;
see AtFlows Spec010 P104. P006–P008 remain open for their full study gates.

Status: offline foundation implemented, public evaluation pending. Checkboxes
represent whole-task completion, not partial scaffolding. Unit/smoke validation
may proceed while live-corpus G0/G1 items remain open; it does not advance G2.
Order is sequential unless a dependency says otherwise.

## G0 setup

- [ ] [T001] Pin public workload/runtime, simulator, licenses, eligibility, no-fault tolerance and current artifacts; split pilot/held-out clusters with recorded seed and ID digests in `benchmarks/agent_continuity/protocol-lock.json` (FR-001, FR-010, FR-011).
- [x] [T002] Audit current public APIs, legal state transitions and Spec 007/020 identities; record per-arm responsibility table and unsupported capabilities in `benchmarks/agent_continuity/capabilities.md` (FR-004, FR-006, FR-007, SC-002).
## G1 foundational harness

- [x] [T003] Build isolated destination classes and hidden ledger in `benchmarks/agent_continuity/destination.py` and `oracle.py`; test I/Q/N reconciliation and planted failures in `tests/benchmarking/test_agent_continuity.py` (FR-002, FR-005, SC-001).
- [ ] [T004] Implement verified process-kill barriers and fault dispositions in `benchmarks/agent_continuity/faults.py`; prove destination survival and ledger isolation in tests (FR-003, SC-001).
- [ ] [T005] Freeze durable baseline and negative control in `benchmarks/agent_continuity/runtime.py`; validate no-fault upstream suite equivalence (FR-001, FR-004, SC-001).
- [ ] [T011] Implement denominators, paired task-cluster uncertainty, safety/completion/coverage/resource/cost reporting in `benchmarks/agent_continuity/report.py`; test all metric edge cases (FR-008, FR-009, FR-011, SC-003).
## G2 current products

T011 is a prerequisite for T008: implement metric reporting and its edge-case
tests during G1 before producing any baseline report. Stable task IDs are retained.

- [ ] [T006] Add public AtMem adapter, explicit activation and revocation/supersession tests in `benchmarks/agent_continuity/adapters/atmem.py`; unsupported behavior remains a gap (FR-006, FR-007).
- [ ] [T007] Add optional current AtFlows adapter and lost/duplicate telemetry checks in `benchmarks/agent_continuity/adapters/atflows.py`, coordinated with AtFlows spec 010 T001–T002 (FR-009).
- [ ] [T008] Execute four-arm pilot without product fixes via `benchmarks/agent_continuity/runner.py`; freeze manifests/raw output hashes and write `benchmarks/agent_continuity/reports/current-baseline.md` (FR-004, FR-010, SC-002).
## G3 registration and G4 optional change gate

Any changed arm proposed by T010 needs a preregistration amendment before G5;
no change based on held-out outcomes belongs in the same confirmatory study.

- [ ] [T009] Freeze sample counts within the G0-locked split, primary comparisons/endpoints, multiplicity correction, margins, analysis and budget/stopping rules in `benchmarks/agent_continuity/preregistration.json` after pilot and before held-out runs (FR-011, SC-003).
- [ ] [T010] Review baseline gaps in `benchmarks/agent_continuity/reports/change-proposal.md`; seek separate approval for product fixes, map regression/artifact gates and preserve original baseline (FR-010, SC-004).
## G5 evaluation and publication

- [ ] [T012] Execute locked schedule for frozen current and preregistered changed arms using `benchmarks/agent_continuity/runner.py`; publish all dispositions, raw sanitized bundles, manifests, licenses and reproduction instructions in `benchmarks/agent_continuity/README.md` (FR-012, SC-003).
- [ ] [T013] Run compatibility gates for any approved product changes and document exact evidence/limitations in `benchmarks/agent_continuity/reports/final.md`; do not release automatically (FR-010, FR-012, SC-004).

## Partial work and next gates

### Offline milestone substeps (do not close parent gates)

- [x] [T001a] Verify imported upstream source/data bytes and policy/tool digests in `benchmarks/agent_continuity/retail.py`; reject non-pilot development replay (FR-001, FR-011).
- [x] [T005a] Add separate-process native retail tool boundary and exact native/wrapped pilot reference-action parity in `tests/benchmarking/test_continuity_retail.py`; label plumbing, not agent no-fault equivalence (FR-001, FR-002).
- [x] [T007a] After T005a and AtFlows T002a, exercise unmodified AtFlows server via isolated `tests/continuity/http-probe.ts` and `benchmarks/agent_continuity/observation.py`; report unsupported auth/accounting without compensation and detect/reject guarded-path egress attempts (FR-009, FR-010).
- [x] [T013a] Record read-only Claude review and corrected test evidence for M1/M2 in `specs/benchmarking/002-agent-continuity/milestone-reviews.md`, linked by AtFlows Spec 010; repeat this review gate for later milestones (FR-010, FR-012).

The gpt-4.1-2025-04-14 agent/simulator model and USD 20 total inference cap are
approved; exact prompts and operational limits remain to freeze. Offline substeps
proceed in order without marking T001/T005/T007 or G2 complete. Live current-product
evaluation remains ahead of product fixes.

- T001: pinned upstream bytes/license/runtime, customer-cluster split, source and
  built wheel hashes exist. Live prompt digests/operational budget remain to freeze.
- T004: eight process-kill barriers implemented/tested; the final-version 20-repeat
  qualification is still open. A development repeat run interrupted during review
  is not qualification evidence.
- T005: competent LangGraph baseline and naive negative control work offline;
  native retail tool-process parity now passes. Full retail agent/simulator
  orchestration and upstream no-fault equivalence still required.
- T011: independent effect/context scoring, cost accounting and descriptive
  timing/bootstrap utilities exist. Full inference, all resource/coverage metrics
  and preregistered analysis are not complete.
- T006: current host-boundary task adapter works; context revocation/supersession
  in agent execution and complete evidence capture remain unsupported here.
- T007: fixture encoder, inspector and unmodified-server HTTP probe exist;
  full workflow telemetry and four-arm execution remain open. Producer-scoped
  authentication is a recorded current-product gap, not supplied by the adapter.
- T008–T013: no live four-arm pilot, product fixes, held-out evaluation or release performed. The later T005b native-only task does not complete these gates.

### Paid pilot prerequisites (M3)

- [x] [T011a] Add persistent, concurrent-safe reservation/usage ledger and checksummed accounting export; test restart, ambiguous charges, duplicate dispatch, overrun and cap changes. Record Claude read-only review (FR-008, FR-009, FR-012). This does not finish T011 or integrate provider dispatch.
- [x] [T005b] Validate and run one native no-fault public pilot task with pinned upstream prompts/agent/simulator, budgeted direct transport, completed-step/raw-call logs and DB/NL grading; read-only Claude review before spend. Keep incomplete/failing runs and label native-only development evidence (FR-001, FR-008, FR-012). See `reports/native-pilot-20260925.md`: normal conversation termination, task reward zero, no product comparison.
