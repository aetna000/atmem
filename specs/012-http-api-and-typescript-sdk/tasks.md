# Tasks: HTTP API and TypeScript SDK

**Input**: Design documents from `specs/012-http-api-and-typescript-sdk/`

**Prerequisites**: The feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define versioned OpenAPI resources, pages, errors, request IDs, capabilities, and deprecation rules in `docs/contracts/atmem-api-v1.openapi.yaml` (FR-001–FR-003)
- [ ] [T002] Create `atmem/service/` as a regular package and implement the transport-neutral memory/query/review/audit/config/health service plus authorization matrix in `atmem/service/__init__.py` and `atmem/service/application.py` (FR-001, FR-006)

## Phase 2 — User Story 1 - Build against a stable API (Priority: P1)

- [ ] [T003] [US1] Implement `/v1` routes, loopback activation, redaction, timeouts, and cancellation in `atmem/control/server.py` and `tests/test_http_api.py` (FR-005, FR-009)
- [ ] [T004] [US1] Add transactional scoped idempotency/precondition receipts in `atmem/store/sqlite.py` using the Spec 010-owned global migration sequence from `specs/integration-ownership.md`; add race and real persisted published-version upgrade/rollback tests in `tests/test_api_idempotency.py`, `tests/test_api_upgrade.py`, and `tests/fixtures/upgrades/` (FR-004, FR-011)
- [ ] [T005] [US1] Build supported TypeScript SDK and Python contract client in `packages/typescript/` and `atmem/client.py` from pinned schemas (FR-007)

## Phase 3 — User Story 2 - Separate agent and admin authority (Priority: P2)

- [ ] [T006] [US2] Map MCP and migrate/contract-test CLI/dashboard in `atmem/mcp/server.py`, `atmem/cli.py`, and `atmem/control/assets/app.js` against public models; own CLI routing conventions while preserving the Spec 007 four-workspace dashboard shell per `specs/integration-ownership.md` (FR-008–FR-010)

## Phase 4 — Verification and Release Evidence

- [ ] [T007] Add pagination/privacy/error/version golden suites in `tests/test_api_contracts.py` and `packages/typescript/test/` (SC-001–SC-003)
- [ ] [T008] Publish SDK package/sample in `packages/typescript/` and compatibility policy/limitations in `docs/http-api.md` (SC-004)
- [ ] [T009] [P] Verify Python 3.10–3.13, npm/Python Apache-2.0-compatible dependency licensing, generated-client reproducibility, and clean base installation in `pyproject.toml`, `packages/typescript/package.json`, and `tests/test_sdk_packaging.py` (FR-012, SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: None.
**Task dependencies**: T001 → all; T002 → T003/T004/T006; T003/T004 → T005/T007; T005/T006/T007 → T008; T009 gates release.
