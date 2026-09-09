# Tasks: Guided Onboarding and Health

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/017/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Input**: Design documents from `specs/017-guided-onboarding-and-health/`

**Prerequisites**: Specs 005, 006, 008, 012, and 015 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Define setup step/check/action/receipt and unified health schemas in `atmem/onboarding.py` and `atmem/schemas/v1/onboarding-state.json` (FR-001, FR-005)

## Phase 2 — User Story 1 - Complete guided setup (Priority: P1)

- [x] [T002] [US1] Implement non-mutating discovery and change/consent plan for existing and fresh installs in `atmem/onboarding.py` (FR-002, FR-004)
- [x] [T003] [US1] Implement idempotent checkpointed apply, activation guard, resume, and compensating rollback in `atmem/onboarding.py` and `tests/test_onboarding_recovery.py` (FR-001–FR-003, FR-008)
- [x] [T004] [US1] Implement synthetic capture/paraphrase/context/evidence and restore-readiness verification in `atmem/onboarding_verify.py` (FR-001, FR-008)

## Phase 3 — User Story 2 - Diagnose from dashboard or CLI (Priority: P2)

- [x] [T005] [US2] Aggregate host/store/AtBot/semantic/evidence/deletion/backup health and safe actions in `atmem/control/topology.py` (FR-005)
- [x] [T006] [US2] Implement evidence-based why-remembered/retrieved/injected/withheld explanations in `atmem/control/explain.py` (FR-006)
- [x] [T007] [US2] Build CLI human/JSON wizard and dashboard wizard from the same contracts in `atmem/cli.py` and `atmem/control/assets/app.js`, with redaction tests in `tests/test_onboarding.py`; preserve `docs/dashboard-design-language.md` and shared ownership in `specs/integration-ownership.md` (FR-005, FR-009)

## Phase 4 — Verification and Release Evidence

- [x] [T008] Add OpenClaw, Pydantic AI, LangGraph, and HTTP installed-package examples in `docs/examples/onboarding/` and `tests/test_documentation.py` (FR-007)
- [x] [T009] Run interruption/parity/security/controlled-usability/automated-step/example gates in `tests/test_onboarding.py` and publish migration/rollback guidance in `docs/onboarding.md` (SC-001–SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: Specs 005, 006, 008, 012, and 015.
**Task dependencies**: T001 → all; T002 → T003; T003/T004/T005/T006 → T007; T007/T008 → T009.


## Phase 5: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019–022; see the roadmap for foundation versus integration ordering.

- [ ] [T010] Define failing boundary fixtures for FR-010, FR-011, SC-006 using `tests/test_onboarding.py`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T011] Replace unconditional memory readiness with adoption-specific checks in `atmem/onboarding.py`, `atmem/onboarding_verify.py` (FR-010, FR-011); depend on T010 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T012] Verify SC-006 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/017/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T011 and do not mark completion from declarations alone.

## Product-wide integration

- [ ] [T013] Define independent boundary fixtures for FR-012/SC-007 in `tests/test_onboarding.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T014] Implement FR-012 through `atmem/onboarding.py` and the owning service contracts; preserve legacy scope behavior and authorize all displayed facts/actions (depends on T013).
- [ ] [T015] Verify SC-007 through the applicable public/host/UI boundary in `tests/test_onboarding.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/017/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T014).
