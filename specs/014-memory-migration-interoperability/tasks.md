# Tasks: Memory Migration and Interoperability

**Input**: Design documents from `specs/014-memory-migration-interoperability/`

**Prerequisites**: Spec 006 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define neutral archive, provenance/history, mapping, checkpoint, and receipt schemas in `atmem/interchange/models.py` and `atmem/schemas/v1/memory-archive.json` (FR-001, FR-006)

## Phase 2 — User Story 1 - Preview and import Mem0 data (Priority: P1)

- [ ] [T003] [US1] Implement Mem0 reader and explicit scope/source/metadata mapping report in `atmem/interchange/mem0.py` (FR-002, FR-009)
- [ ] [T004] [US1] Implement deterministic dry-run planner and conflict/review routing in `atmem/interchange/plan.py` (FR-003–FR-004)
- [ ] [T005] [US1] Implement transactional idempotent batch commit, resume, verification, and rollback receipts in `atmem/interchange/importer.py` (FR-005–FR-006)
- [ ] [T006] [US1] Add CLI/API admin surfaces with progress, counts, JSON, cancellation, and redaction in `atmem/cli.py` and `atmem/control/server.py`

## Phase 3 — User Story 2 - Export neutral evidence (Priority: P2)

- [ ] [T002] [US2] Implement streaming validated neutral export with scope/lifecycle/redaction policy in `atmem/interchange/export.py` (FR-007)

## Phase 4 — Verification and Release Evidence

- [ ] [T007] Add format upgrade, interruption, replay, tamper, scope, rollback, and round-trip suites in `tests/test_interchange.py` (FR-008, SC-001–SC-004)
- [ ] [T008] Publish neutral format, Mem0 mapping/loss table, migration and rollback guide in `docs/memory-interchange.md`

## Dependencies and Execution Order

**Cross-spec dependencies**: Spec 006.
**Task dependencies**: T001 → all; T002/T003 → T004; T004 → T005/T006; T005 → T007/T008.
