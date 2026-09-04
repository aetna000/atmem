# Tasks: Governed Multimodal Memory

**Input**: Design documents from `specs/016-governed-multimodal-memory/`

**Prerequisites**: Specs 005, 008, and 015 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Move compatible media behavior into the `atmem/media/` package and define reference/custody/consent/locator/observation/processing/deletion schemas in `atmem/media/models.py` and `atmem/schemas/v1/media-observation.json` (FR-001–FR-003)

## Phase 2 — User Story 1 - Capture a media observation safely (Priority: P1)

- [ ] [T002] [US1] Implement safe host-controlled content access and explicit copied-byte receipts in `atmem/media/access.py` (FR-002, FR-006)
- [ ] [T003] [US1] Implement optional local/hosted processor boundary with authorization, redaction, egress, model/config evidence in `atmem/media/processors.py` (FR-003–FR-004)
- [ ] [T004] [US1] Add generation-bound optional multimodal derived index using Spec 005 compatibility/rebuild health in `atmem/media/index.py` (FR-005)

## Phase 3 — User Story 2 - Retrieve and delete derived knowledge (Priority: P2)

- [ ] [T005] [US2] Integrate Spec 008 retrieval revalidation/explanations and Spec 015 lifecycle/revocation/deletion verification in `atmem/media/service.py` and `atmem/lifecycle/invalidation.py` (FR-007–FR-009)
- [ ] [T006] [US2] Add consistent CLI/dashboard/API artifact/observation/consent/delete surfaces in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-009)

## Phase 4 — Verification and Release Evidence

- [ ] [T007] Add media-class, custody, sensitive, malicious, cross-scope, failure, rebuild, revocation, and deletion suites in `tests/test_media_governance.py` (SC-001–SC-004)
- [ ] [T008] Document host responsibilities, egress, retention, backup, supported locators, and proof limits in `docs/multimodal-observations.md`
- [ ] [T009] [P] Verify Python 3.10–3.13, Apache-2.0-compatible enterprise licensing for optional media/model dependencies, and base-install imports without extras in `pyproject.toml` and `tests/test_media_packaging.py` (FR-010, SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: Specs 005, 008, and 015.
**Task dependencies**: T001 → all; T002/T003 → T004/T005; T005 → T006/T007/T008; T009 gates release.
