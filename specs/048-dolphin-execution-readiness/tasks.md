# Tasks

## Setup

- [x] T001 Write spec/plan/tasks and `.specify/feature.json`; analyze coverage (FR-001–009).
- [x] T002 Persist startup/runbook pointers to this feature in `AGENTS.md` and `docs/benchmarks/dolphin-lessons-and-readiness.md` (FR-007).

## Foundational

- [x] T003 Implement profile and actual outgoing-tool validation in `benchmarks/dolphinbench/execution_profile.py`, `driver.py`, `gateway.py` (FR-001).
- [x] T004 Implement identity/receipt admission in `benchmarks/dolphinbench/readiness.py` and boundary tests in `tests/benchmarking/test_execution_readiness.py` (FR-005–006).
- [x] T005 Protect evidence and uncertain resume in `benchmarks/dolphinbench/safe_runner.py` and adapter; test crash-after-mutation/re-entry (FR-003).

## Qualification and pilot

- [x] T013 Freeze and enforce per-role routes/settings in `routes.json`, `readiness.py`, `gateway.py` and `runbook.md`; verify against completed 600-task provider records and reject drift (FR-009). Required before T008.

- [x] T006 Implement and run actual synthetic upstream MCP bridge/state/log qualification in `benchmarks/dolphinbench/qualify_execution.py` (FR-002–003).
- [x] T007 Implement fixed-pilot verification/reporting and run entry in `benchmarks/dolphinbench/pilot_readiness.py`; test 19/20, wrong IDs, costs/regressions/cohorts (FR-004).
- [x] T008 Original checkpoints/configuration recovered, fixed20 frozen, executed and independently validated. Result:20 graded,13 passed,7 failed;10 recoveries,0 regressions. See docs/benchmarks/dolphin-pilot20-20261026-report.md. Full600 remains unauthorized.
- [x] T009 Wire gate into existing campaign and adapter dispatch boundaries and prove failure before provider calls on missing/changed receipts (FR-006).

## Review and completion

- [x] T010 Run focused integration/negative tests and retain qualified receipts plus explicit not-ready status where live gates remain incomplete (FR-001–007).
- [x] T011 Request Claude Opus 5.5 medium read-only review, address findings and retain review metadata in `specs/048-dolphin-execution-readiness/review.md` (FR-008).
- [x] T012 Commit/push implementation and update durable runbook/checklist with exact verification and blockers (FR-007–008).

## Owner amendment — 20-task pilot

- [x] T014 Freeze exactly 20 stratified diagnostic IDs, update all guard/report/validator cardinalities, preserve original 60 evidence, and test19/20 plus stale-condition refusal.
- [x] T015 Prepare a separately versioned AtSys exact-command task with inspect-only retries; pin its command/validator, preserve the old blocked task, and verify its schema.
- [x] T016 Generate the new frozen condition and fresh native/app/crash qualification. Record readiness without claiming new pilot accuracy.


## Owner amendment — bounded repair, separate recovery epoch

Earlier no-repair/inspect-only retry restrictions are historical and superseded
within this scope. T008's old0/20 filesystem blocker is historical:023/085 and
their grades exist;129 executed but export failed. Parent is read-only evidence;
no workload is launched by this implementation worker.

- [x] T017 Implement exact finite recursive numeric export; preserve raw calls
  and default provenance, reject true differences, bool/string/nonfinite and
  unsafe ordering/targets (FR-010).
- [x] T018 Implement historical byte verifier, offline129 recovery receipt,
  immutable epoch lineage and exact completed execution/grade import (FR-011–012).
- [x] T019 Implement cumulative SQLite budget inheritance, exclusive intents,
  per-run lock, saved-grade skipping and actual resume/forward/report guards
  without weakening ordinary admission (FR-013).
- [x] T020 Add bounded supervisor repair template and executable handoff checks;
  parent execution remains separate from workspace coding repair (FR-014).
- [x] T021 Add focused numeric/offline recovery/import/crash/cost/entry/report
  acceptance tests and document exact commands and limitations.
- [x] T022 Root reviews implementation with Claude, resolves findings, performs
  fresh installed ARM zero-call qualification, freezes a new condition and
  prepares the real recovery epoch. No implementation-worker workload/commit.
- [x] T023 Root wires and launches supervised remaining17 only; grade recovered
  evidence once if needed, retain original grades, report all20 and regressions.
  Full600 remains blocked pending separately authorized readiness/promotion.

## Automatic parent verification — 2026-10-26

- [x] T024 Implement and pin trusted automatic parent, independent source/science/ledger/result guards and safe qualification/epoch retries; five parent guard tests pass.
- [x] T025 Enable bounded AtSys repair, verify an actual SQLite repair and automatic retry, and pass183 focused tests plus fresh zero-model qualification.
- [x] T026 Complete independent20-task report/validation; retain fixture failures and any control regressions. Full600 remains unauthorized.

## Owner amendment — routed fixed20 diagnostic, 2026-10-31

- [x] T027 Extend admission/dispatch/report validation for separately qualified
  `dolphin-routed-v1`; preserve MCP-only checks and frozen science; checkpoint=false.
- [x] T028 Test negative receipt/raw evidence cases; qualify actual native plugin,
  provider-bound inventory, refused detour, simulated write/state/log and crash
  recovery with zero model calls; issue fresh identity-bound receipts.
- [x] T029 Prepare separate exact-command AtSys task with USD10 cap,40-unit saved
  execution/grade progress, one-launch intent, inspect-only retries and terminal
  human-readable report. Submission/runtime status is persisted by AtSys.
