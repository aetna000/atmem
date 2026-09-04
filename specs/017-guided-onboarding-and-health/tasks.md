# Tasks: Guided Onboarding and Health

**Input**: Design documents from `specs/017-guided-onboarding-and-health/`

**Prerequisites**: Specs 005, 006, 008, 012, and 015 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define setup step/check/action/receipt and unified health schemas in `atmem/onboarding.py` and `atmem/schemas/v1/onboarding-state.json` (FR-001, FR-005)

## Phase 2 — User Story 1 - Complete guided setup (Priority: P1)

- [ ] [T002] [US1] Implement non-mutating discovery and change/consent plan for existing and fresh installs in `atmem/onboarding.py` (FR-002, FR-004)
- [ ] [T003] [US1] Implement idempotent checkpointed apply, activation guard, resume, and compensating rollback in `atmem/onboarding.py` and `tests/test_onboarding_recovery.py` (FR-001–FR-003, FR-008)
- [ ] [T004] [US1] Implement synthetic capture/paraphrase/context/evidence and restore-readiness verification in `atmem/onboarding_verify.py` (FR-001, FR-008)

## Phase 3 — User Story 2 - Diagnose from dashboard or CLI (Priority: P2)

- [ ] [T005] [US2] Aggregate host/store/AtBot/semantic/evidence/deletion/backup health and safe actions in `atmem/control/topology.py` (FR-005)
- [ ] [T006] [US2] Implement evidence-based why-remembered/retrieved/injected/withheld explanations in `atmem/control/explain.py` (FR-006)
- [ ] [T007] [US2] Build CLI human/JSON wizard and dashboard wizard from the same contracts in `atmem/cli.py` and `atmem/control/assets/app.js`, with redaction tests in `tests/test_onboarding.py`; preserve `docs/dashboard-design-language.md` and shared ownership in `specs/integration-ownership.md` (FR-005, FR-009)

## Phase 4 — Verification and Release Evidence

- [ ] [T008] Add OpenClaw, Pydantic AI, LangGraph, and HTTP installed-package examples in `docs/examples/onboarding/` and `tests/test_documentation.py` (FR-007)
- [ ] [T009] Run interruption/parity/security/controlled-usability/automated-step/example gates in `tests/test_onboarding.py` and publish migration/rollback guidance in `docs/onboarding.md` (SC-001–SC-005)

## Dependencies and Execution Order

**Dependencies**: Specs 005, 006, 008, 012, and 015; T001 → all; T002 → T003; T003/T004/T005/T006 → T007; T007/T008 → T009.
