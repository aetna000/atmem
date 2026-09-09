# Tasks: Memory Lifecycle Controls

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/015/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Input**: Design documents from `specs/015-memory-lifecycle-controls/`

**Prerequisites**: Spec 010 for production backends plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Define lifecycle state/timestamp/policy/transition/receipt schemas and matrix in `atmem/lifecycle/models.py` and `atmem/schemas/v1/memory-lifecycle.json` (FR-001–FR-005)
- [x] [T002] Add backward-compatible canonical migration and rollback in `atmem/store/sqlite.py` using the Spec 010-owned global migration sequence from `specs/integration-ownership.md`; test real persisted fixtures from every supported published AtMem upgrade floor in `tests/fixtures/upgrades/` and `tests/test_lifecycle_migration.py` (FR-009–FR-010)

## Phase 2 — User Story 1 - Understand current validity (Priority: P1)

- [x] [T003] [US1] Centralize point-in-time eligibility and typed generation-checked transitions in `atmem/lifecycle/service.py` (FR-002, FR-004)

## Phase 3 — User Story 2 - Govern transitions and deletion (Priority: P2)

- [x] [T004] [US2] Implement ordered scope policy preview/scans and optional decay/promotion proposals in `atmem/lifecycle/policy.py` (FR-003, FR-005)
- [x] [T005] [US2] Implement transactional graph/vector/cache/context invalidation with retry/verification state in `atmem/lifecycle/invalidation.py` (FR-006)
- [x] [T006] [US2] Implement forget verification including declared backup retention/crypto-erasure evidence in `atmem/lifecycle/maintenance.py`, register it through Spec 007's shared maintenance interface, and test it in `tests/test_forget_verification.py` (FR-007)
- [x] [T007] [US2] Add common CLI/dashboard/API timeline, impact preview, actions, and verification UI in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-008)

## Phase 4 — Verification and Release Evidence

- [x] [T008] Add matrix, time-boundary, concurrency, exclusion, deletion, migration, and cross-surface gates in `tests/test_lifecycle.py` (SC-001–SC-004)

## Dependencies and Execution Order

**Cross-spec dependencies**: Spec 010 for non-SQLite backend conformance.
**Task dependencies**: T001 → all; T002 → T003; T003/T004 → T005/T007; T005 → T006/T008.


## Phase 5: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019, 023; see the roadmap for foundation versus integration ordering.

- [ ] [T009] Define failing boundary fixtures for FR-011, FR-012, SC-005 using `tests/test_lifecycle.py`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T010] Connect lifecycle events and cleanup receipts to context-grant invalidation in `atmem/lifecycle/` (FR-011, FR-012); depend on T009 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T011] Verify SC-005 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/015/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T010 and do not mark completion from declarations alone.

## Product-wide integration

- [ ] [T012] Define independent boundary fixtures for FR-013/SC-006 in `tests/test_memory_space_revocation.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T013] Implement FR-013 through `atmem/lifecycle/invalidation.py` and the owning service contracts; preserve legacy scope behavior and authorize all displayed facts/actions (depends on T012).
- [ ] [T014] Verify SC-006 through the applicable public/host/UI boundary in `tests/test_memory_space_revocation.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/015/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T013).
