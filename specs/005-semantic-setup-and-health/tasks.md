# Tasks: Semantic Setup and Health

**Input**: Design documents from `specs/005-semantic-setup-and-health/`

**Prerequisites**: Specs 001 and the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define semantic manifest, health enum, reason codes, and JSON schema in `atmem/semantic/health.py` and `atmem/schemas/v1/` (FR-004–FR-006)
- [ ] [T002] Add model catalog and deterministic hardware recommendation tests in `atmem/semantic/models.json` and `tests/test_semantic_health.py` (FR-002–FR-003)
- [ ] [T003] Detect legacy, missing, weak, stale, incompatible, partial, and healthy indexes in `atmem/semantic/health.py` (FR-005–FR-006)

## Phase 2 — User Story 1 - Enable local semantic recall (Priority: P1)

- [ ] [T004] [US1] Implement consentful `semantic setup` and paraphrase verification in `atmem/cli.py` and `tests/test_semantic_setup.py` (FR-001–FR-003, FR-008)

## Phase 3 — User Story 2 - Diagnose and repair an index (Priority: P2)

- [ ] [T005] [US2] Implement checkpointed inactive-epoch rebuild and atomic activation in `atmem/semantic/index.py` (FR-007)
- [ ] [T006] [US2] Add concurrent mutation, deletion, interruption, dimension, and disk-failure tests in `tests/test_semantic_rebuild.py` (FR-006–FR-009)
- [ ] [T007] [US2] Add CLI status/rebuild/verify human and JSON contracts in `atmem/cli.py` and `tests/test_cli_guidance.py` (FR-005)
- [ ] [T008] [US2] Add dashboard health card, evidence details, and state-valid corrective actions in `atmem/control/assets/app.js` and `tests/test_dashboard_daemon.py`; follow `docs/dashboard-design-language.md`, preserve four workspaces, and serialize shell integration through Spec 007 per `specs/integration-ownership.md` (FR-005)

## Phase 4 — Verification and Release Evidence

- [ ] [T009] Document setup, fallback, downloads, recovery, limitations, and controlled-usability protocol in `docs/semantic-search.md`; run automated bounded-step, base-install, and full regression suites (FR-001, FR-008–FR-010, SC-001–SC-005)

## Dependencies and Execution Order

**Dependencies**: T001 → T003–T009; T002 → T004; T003 → T005/T007/T008; T005 → T006/T009.
