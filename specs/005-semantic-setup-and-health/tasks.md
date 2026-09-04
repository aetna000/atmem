# Tasks: Semantic Setup and Health

**Input**: Design documents from `specs/005-semantic-setup-and-health/`

**Prerequisites**: Specs 001 and the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Define semantic manifest, health enum, reason codes, and JSON schema in `atmem/semantic/health.py` and `atmem/schemas/v1/`; validate every health state against the published schema and assert schema/implementation enum equality in `tests/test_semantic_schema.py` (FR-004–FR-006)
- [x] [T002] Add a multi-runtime model catalog, honest unknown-memory and accelerator detection, and deterministic hardware recommendation tests in `atmem/semantic/models.json`, `atmem/semantic/health.py`, and `tests/test_semantic_health.py` (FR-002–FR-003)
- [x] [T003] Detect legacy, missing, weak, stale, incompatible, partial, and healthy indexes in `atmem/semantic/health.py` (FR-005–FR-006)

## Phase 2 — User Story 1 - Enable local semantic recall (Priority: P1)

- [x] [T004] [US1] Implement consentful `semantic setup` covering download and Ollama/remote egress, measured operator-decision counting, and paraphrase verification in `atmem/cli.py` and `tests/test_semantic_setup.py` (FR-001–FR-003, FR-008; SC-005)

## Phase 3 — User Story 2 - Diagnose and repair an index (Priority: P2)

- [x] [T005] [US2] Implement checkpointed inactive-epoch rebuild and atomic activation in `atmem/semantic/index.py` (FR-007)
- [x] [T006] [US2] Add concurrent mutation, deletion, interruption, dimension, and disk-failure tests in `tests/test_semantic_rebuild.py` (FR-006–FR-008)
- [x] [T006a] [US2] Bind each epoch to a secret-free household-policy digest and invalidate epochs derived under a superseded policy in `atmem/semantic/index.py`, `atmem/semantic/health.py`, and `tests/test_semantic_policy_invalidation.py` (FR-009)
- [x] [T007] [US2] Add CLI status/rebuild/verify human and JSON contracts in `atmem/cli.py` and `tests/test_cli_guidance.py` (FR-005)
- [x] [T008] [US2] Add dashboard health card, evidence details, and state-valid corrective actions in `atmem/control/assets/app.js` and `tests/test_dashboard_daemon.py`; prove CLI JSON and dashboard-API payload equality for every health state in `tests/test_semantic_parity.py`; follow `docs/dashboard-design-language.md`, preserve four workspaces, and serialize shell integration through Spec 007 per `specs/integration-ownership.md` (FR-005; SC-002)

## Phase 4 — Verification and Release Evidence

- [x] [T009] Document setup, fallback, downloads, recovery, limitations, and controlled-usability protocol in `docs/semantic-search.md`; run automated bounded-step, base-install, and full regression suites (FR-001, FR-008–FR-010, SC-001–SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: None.
**Task dependencies**: T001 → T003–T009; T002 → T004; T003 → T005/T007/T008; T005 → T006/T006a/T009.
