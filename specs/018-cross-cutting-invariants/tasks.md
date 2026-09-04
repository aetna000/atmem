# Tasks: Cross-Cutting Invariant Conformance

**Input**: Design documents from `specs/018-cross-cutting-invariants/`

**Prerequisites**: Shipped behavior of Specs 001–004 plus the feature plan

**Organization**: Foundational registry work precedes independently testable user-story phases; the blocking gate and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define the versioned invariant registry schema with stable IDs, guarantee statement, governing principle, owning assertions, declared configurations, verdict, and amendment history in `atmem/invariants/models.py` and `atmem/schemas/v1/invariant-registry.json` (FR-001, FR-005, FR-008)
- [ ] [T002] Encode `INV-001`–`INV-011` from the `todo.md` guarantee list with their constitution principle references in `atmem/invariants/registry.py`, and reject any invariant lacking an owning assertion (FR-002–FR-003)
- [ ] [T003] Implement the verdict evaluator distinguishing `proven`, `partially_proven` with named uncovered configuration, and `unproven` with named missing or unrunnable assertion in `atmem/invariants/verdict.py` (FR-005)

## Phase 2 — User Story 1 - Prove the guarantees still hold (Priority: P1)

- [ ] [T004] [P] [US1] Add baseline assertions for `INV-001` canonical authority, `INV-002` authorization before intelligence, and `INV-003` ranking revalidation in `tests/invariants/test_authority.py`, reusing existing candidate-set and `prepare_context_v1()` fixtures (FR-002–FR-003, FR-010)
- [ ] [T005] [P] [US1] Add baseline assertions for `INV-004` explicit shadow mode and activation, `INV-005` byte-stable receipt-bound context, and `INV-006` human-readable provenance and history in `tests/invariants/test_delivery.py` (FR-002–FR-003, FR-010)
- [ ] [T006] [P] [US1] Add baseline assertions for `INV-007` deletion across canonical/graph/vector/derived copies, `INV-008` honest Agent Black Box proof boundaries, and `INV-009` reversible OpenClaw migration in `tests/invariants/test_deletion_and_proof.py` (FR-002–FR-003, FR-010)
- [ ] [T007] [P] [US1] Add baseline assertions for `INV-010` local operation and deterministic fallback and `INV-011` backward-compatible persisted-data upgrades in `tests/invariants/test_local_and_upgrade.py`, reusing `tests/fixtures/upgrades/` without adding a competing migration sequence (FR-002–FR-004, FR-010)
- [ ] [T008] [US1] Implement the content-minimized report writer and offline/no-extras execution against the installed package in `atmem/invariants/report.py` and `tests/invariants/test_packaging.py` (FR-004, FR-009; SC-002, SC-005)

## Phase 3 — User Story 2 - Catch a regression at the boundary (Priority: P1)

- [ ] [T009] [US2] Implement the seeded-violation harness and prove each invariant fails with its own ID and causes no other invariant failure in `tests/invariants/test_mutations.py` (FR-007; SC-003)
- [ ] [T010] [US2] Wire the release gate to fail on any `unproven` verdict, failing assertion, or skipped suite run, reporting invariant ID, guarantee, owning spec, assertion, and evidence in `.github/workflows/invariants.yml` and `tools/check_invariants.py` (FR-007; SC-001)

## Phase 4 — User Story 3 - Attest what a feature touched (Priority: P2)

- [ ] [T011] [US3] Implement the attestation loader that reads each spec's declared invariant IDs, rejects conflicting attestations, and fails an unattested change to an invariant-bearing surface in `atmem/invariants/attestation.py` and `tests/invariants/test_attestation.py` (FR-006, FR-011; SC-004)
- [ ] [T012] [US3] Add an `## Invariant Attestation` section naming affected invariant IDs to Specs 005–017 and record invariant-registry ownership in `specs/integration-ownership.md` (FR-006; SC-004)

## Phase 5 — Verification and Release Evidence

- [ ] [T013] Capture the Specs 001–004 baseline, publish the resulting gap list, and flip the gate from advisory to blocking in `docs/invariants.md` (FR-010; SC-001)
- [ ] [T014] [P] Verify Python 3.10–3.13, clean base installation without extras, offline execution without a configured provider, and absence of secrets or scoped content in every report fixture in `tests/invariants/test_packaging.py` (FR-004, FR-009; SC-002, SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: None. Specs 005–017 attest into this registry; this spec does not consume their output.
**Task dependencies**: T001 → all; T002/T003 → T004–T008; T004–T008 → T009/T010; T003 → T011; T011 → T012; T009/T010/T012 → T013; T008 → T014.
