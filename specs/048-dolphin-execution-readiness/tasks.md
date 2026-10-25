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
- [x] T007 Implement fixed-pilot verification/reporting and run entry in `benchmarks/dolphinbench/pilot_readiness.py`; test 59/60, wrong IDs, costs/regressions/cohorts (FR-004).
- [ ] T008 Obtain original frozen checkpoints/private runtime configuration; freeze candidate JSON and run the actual 60-task pilot; retain output under a new run identity (FR-004–005). Original volume now mounted read-only; isolated checkpoint copies verified. Pilot attempted with frozen configuration; 0/60. BLOCKED on owner Hermes subscription OAuth sign-in; see verification.md.
- [x] T009 Wire gate into existing campaign and adapter dispatch boundaries and prove failure before provider calls on missing/changed receipts (FR-006).

## Review and completion

- [x] T010 Run focused integration/negative tests and retain qualified receipts plus explicit not-ready status where live gates remain incomplete (FR-001–007).
- [x] T011 Request Claude Opus 5.5 medium read-only review, address findings and retain review metadata in `specs/048-dolphin-execution-readiness/review.md` (FR-008).
- [x] T012 Commit/push implementation and update durable runbook/checklist with exact verification and blockers (FR-007–008).
