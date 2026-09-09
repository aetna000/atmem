# Tasks: Memory Migration and Interoperability

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/014/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Input**: Design documents from `specs/014-memory-migration-interoperability/`

**Prerequisites**: Spec 006 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Define neutral archive, provenance/history, mapping, checkpoint, and receipt schemas in `atmem/interchange/models.py` and `atmem/schemas/v1/memory-archive.json` (FR-001, FR-006)

## Phase 2 — User Story 1 - Preview and import Mem0 data (Priority: P1)

- [x] [T003] [US1] Implement Mem0 reader and explicit scope/source/metadata mapping report in `atmem/interchange/mem0.py` (FR-002, FR-009)
- [x] [T004] [US1] Implement deterministic dry-run planner and conflict/review routing in `atmem/interchange/plan.py` (FR-003–FR-004)
- [x] [T005] [US1] Implement transactional idempotent batch commit, resume, verification, and rollback receipts in `atmem/interchange/importer.py` (FR-005–FR-006)
- [x] [T006] [US1] Add CLI/API admin surfaces with progress, counts, JSON, cancellation, and redaction in `atmem/cli.py` and `atmem/control/server.py`

## Phase 3 — User Story 2 - Export neutral evidence (Priority: P2)

- [x] [T002] [US2] Implement streaming validated neutral export with scope/lifecycle/redaction policy in `atmem/interchange/export.py` (FR-007)

## Phase 4 — Verification and Release Evidence

- [x] [T007] Add format upgrade, interruption, replay, tamper, scope, rollback, and round-trip suites in `tests/test_interchange.py` (FR-008, SC-001–SC-004)
- [x] [T008] Publish neutral format, Mem0 mapping/loss table, migration and rollback guide in `docs/memory-interchange.md`

## Dependencies and Execution Order

**Cross-spec dependencies**: Spec 006.
**Task dependencies**: T001 → all; T002/T003 → T004; T004 → T005/T006; T005 → T007/T008.


## Phase 5: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019, 022; see the roadmap for foundation versus integration ordering.

- [ ] [T009] Define failing boundary fixtures for FR-010, FR-011, SC-005 using `tests/test_interchange.py`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T010] Add no-migration provider-switch journeys alongside explicit archive migration in `atmem/interchange/`, `docs/memory-interchange.md` (FR-010, FR-011); depend on T009 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T011] Verify SC-005 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/014/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T010 and do not mark completion from declarations alone.
