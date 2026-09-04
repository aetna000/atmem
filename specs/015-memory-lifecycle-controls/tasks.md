# Tasks: Memory Lifecycle Controls

**Input**: Design documents from `specs/015-memory-lifecycle-controls/`

**Prerequisites**: Spec 010 for production backends plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define lifecycle state/timestamp/policy/transition/receipt schemas and matrix in `atmem/lifecycle/models.py` and `atmem/schemas/v1/memory-lifecycle.json` (FR-001–FR-005)
- [ ] [T002] Add backward-compatible canonical migration and rollback in `atmem/store/sqlite.py`; test real persisted fixtures from every supported published AtMem upgrade floor in `tests/fixtures/upgrades/` and `tests/test_lifecycle_migration.py` (FR-009–FR-010)

## Phase 2 — User Story 1 - Understand current validity (Priority: P1)

- [ ] [T003] [US1] Centralize point-in-time eligibility and typed generation-checked transitions in `atmem/lifecycle/service.py` (FR-002, FR-004)

## Phase 3 — User Story 2 - Govern transitions and deletion (Priority: P2)

- [ ] [T004] [US2] Implement ordered scope policy preview/scans and optional decay/promotion proposals in `atmem/lifecycle/policy.py` (FR-003, FR-005)
- [ ] [T005] [US2] Implement transactional graph/vector/cache/context invalidation with retry/verification state in `atmem/lifecycle/invalidation.py` (FR-006)
- [ ] [T006] [US2] Implement forget verification including declared backup retention/crypto-erasure evidence in `atmem/maintenance.py` and `tests/test_forget_verification.py` (FR-007)
- [ ] [T007] [US2] Add common CLI/dashboard/API timeline, impact preview, actions, and verification UI in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-008)

## Phase 4 — Verification and Release Evidence

- [ ] [T008] Add matrix, time-boundary, concurrency, exclusion, deletion, migration, and cross-surface gates in `tests/test_lifecycle.py` (SC-001–SC-004)

## Dependencies and Execution Order

**Cross-spec dependency**: Spec 010 for non-SQLite backend conformance.
**Task dependencies**: T001 → all; T002 → T003; T003/T004 → T005/T007; T005 → T006/T008.
