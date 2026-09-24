# Tasks: Agent Continuity Benchmark

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

- T001: pinned upstream bytes/license/runtime, customer-cluster split, source and
  built wheel hashes exist. Live prompt digests/operational budget remain to freeze.
- T004: eight process-kill barriers implemented/tested; the final-version 20-repeat
  qualification is still open. A development repeat run interrupted during review
  is not qualification evidence.
- T005: competent LangGraph baseline and naive negative control work offline;
  native retail adapter and upstream no-fault equivalence still required.
- T011: independent effect/context scoring, cost accounting and descriptive
  timing/bootstrap utilities exist. Full inference, all resource/coverage metrics
  and preregistered analysis are not complete.
- T006: current host-boundary task adapter works; context revocation/supersession
  in agent execution and complete evidence capture remain unsupported here.
- T007: explicit OTLP fixture encoder and AtFlows current-product inspector exist;
  authenticated live producer integration and four-arm execution remain open.
- T008–T013: no live pilot, product fixes, held-out evaluation or release performed.
