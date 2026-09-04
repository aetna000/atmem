# Tasks: Memory Extraction and Updating

**Input**: Design documents from `specs/006-memory-extraction-and-updating/`

**Prerequisites**: Spec 001 and the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define proposal/class/evidence/precondition schemas and compatibility tests in `atmem/schemas/v1/memory-proposal.json`, `atmem/extract/models.py`, and `tests/test_extract_contracts.py` (FR-001–FR-002)

## Phase 2 — User Story 1 - Produce a governed proposal (Priority: P1)

- [ ] [T002] [US1] Implement bounded authorized entity/pronoun context and influence receipts in `atmem/extract/context.py` (FR-003, FR-010)
- [ ] [T003] [US1] Implement duplicate/refinement/contradiction/correction/supersession classification in `atmem/extract/classify.py` (FR-004)
- [ ] [T004] [US1] Normalize rule and AtBot outputs through one poison-aware validator in `atmem/extract/validation.py` and `packages/atbot/src/atbot/extraction.py` (FR-005, FR-007, FR-009)

## Phase 3 — User Story 2 - Correct without duplicate pollution (Priority: P2)

- [ ] [T005] [US2] Add transactional generation-checked commit and immutable lineage migration in `atmem/memory.py` and `atmem/store/sqlite.py`; test upgrades from real persisted fixtures for every supported published AtMem upgrade floor in `tests/fixtures/upgrades/` and `tests/test_extract_upgrade.py` (FR-005, FR-011)
- [ ] [T006] [US2] Implement policy-driven quarantine and review service/actions in `atmem/extract/review.py` (FR-006, FR-008)
- [ ] [T007] [US2] Add consistent CLI/dashboard queues, detail views, reason codes, and JSON contracts in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-008)

## Phase 4 — User Story 3 - Resist instruction-shaped memory (Priority: P3)

- [ ] [T008] [US3] Add class/action/correction/poison/privacy/failure fixtures to `atmem/benchmark/data/deterministic-v1.json` and `tests/test_extract.py` (SC-001–SC-003)

## Phase 5 — Verification and Release Evidence

- [ ] [T009] Document governance, fallback, review, rollback, and limitations in `docs/memory-extraction.md`; run migration and full regression tests (FR-009–FR-010, SC-004)

## Dependencies and Execution Order

**Dependencies**: T001 → all; T002/T003 → T004; T004 → T005/T006; T005/T006 → T007/T008/T009.
