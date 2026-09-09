# Tasks: HTTP API and TypeScript SDK

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/012/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Input**: Design documents from `specs/012-http-api-and-typescript-sdk/`

**Prerequisites**: The feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Define versioned OpenAPI resources, pages, errors, request IDs, capabilities, and deprecation rules in `docs/contracts/atmem-api-v1.openapi.yaml` (FR-001–FR-003)
- [x] [T002] Create `atmem/service/` as a regular package and implement the transport-neutral memory/query/review/audit/config/health service plus authorization matrix in `atmem/service/__init__.py` and `atmem/service/application.py` (FR-001, FR-006)

## Phase 2 — User Story 1 - Build against a stable API (Priority: P1)

- [x] [T003] [US1] Implement `/v1` routes, loopback activation, redaction, timeouts, and cancellation in `atmem/control/server.py` and `tests/test_http_api.py` (FR-005, FR-009)
- [x] [T004] [US1] Add transactional scoped idempotency/precondition receipts in `atmem/store/sqlite.py` using the Spec 010-owned global migration sequence from `specs/integration-ownership.md`; add race and real persisted published-version upgrade/rollback tests in `tests/test_api_idempotency.py`, `tests/test_api_upgrade.py`, and `tests/fixtures/upgrades/` (FR-004, FR-011)
- [x] [T005] [US1] Build supported TypeScript SDK and Python contract client in `packages/typescript/` and `atmem/client.py` from pinned schemas (FR-007)

## Phase 3 — User Story 2 - Separate agent and admin authority (Priority: P2)

- [x] [T006] [US2] Map MCP and migrate/contract-test CLI/dashboard in `atmem/mcp/server.py`, `atmem/cli.py`, and `atmem/control/assets/app.js` against public models; own CLI routing conventions while preserving the Spec 007 four-workspace dashboard shell per `specs/integration-ownership.md` (FR-008–FR-010)

## Phase 4 — Verification and Release Evidence

- [x] [T007] Add pagination/privacy/error/version golden suites in `tests/test_api_contracts.py` and `packages/typescript/test/` (SC-001–SC-003)
- [x] [T008] Publish SDK package/sample in `packages/typescript/` and compatibility policy/limitations in `docs/http-api.md` (SC-004)
- [x] [T009] [P] Verify Python 3.10–3.13, npm/Python Apache-2.0-compatible dependency licensing, generated-client reproducibility, and clean base installation in `pyproject.toml`, `packages/typescript/package.json`, and `tests/test_sdk_packaging.py` (FR-012, SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: None.
**Task dependencies**: T001 → all; T002 → T003/T004/T006; T003/T004 → T005/T007; T005/T006/T007 → T008; T009 gates release.


## Phase 5: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019–021; see the roadmap for foundation versus integration ordering.

- [ ] [T010] Define failing boundary fixtures for FR-013, FR-014, SC-006 using `tests/`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T011] Extend public service models and transport projections for the unified workflow in `atmem/service/application.py`, `atmem/client.py`, `packages/typescript/`, `docs/contracts/atmem-api-v1.openapi.yaml` (FR-013, FR-014); depend on T010 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T012] Verify SC-006 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/012/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T011 and do not mark completion from declarations alone.

## Product-wide integration

- [ ] [T013] Define independent boundary fixtures for FR-015/SC-007 in `tests/test_memory_space_contracts.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T014] [ROLLUP: decomposed into T016–T032] Complete the FR-015 space/membership and feedback subsystem through the separately testable tasks below. This row is a compatibility/completion marker, not an additional implementation estimate; close only after T016–T032 pass.
- [ ] [T015] Verify SC-007 through the applicable public/host/UI boundary in `tests/test_memory_space_contracts.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/012/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T014).

## FR-015: Memory-space authority and feedback subsystem

These tasks replace T014's implementation estimate. T013 supplies independent acceptance fixtures. Contract work can proceed against the existing authenticated principal interface; production deployment additionally requires 013 T012/T018/T019. No task depends on completion of fleet or connection UI.

- [ ] [T016] Freeze MemorySpace, SpaceMembership, permission decision, expected-revision and feedback/time contracts in `atmem/service/space_contracts.py` and versioned schemas under `atmem/schemas/`; define immutable tenant/workspace identity, owner transfer, member removal, read/write-propose/admin distinctions and legacy scope mapping, with independent vectors in `tests/test_memory_space_contracts.py` (FR-015; depends on T013 and the 013 T012 principal contract for enterprise profiles).
- [ ] [T017] Allocate transactional space/membership/generation/audit migrations through Spec 010 in `atmem/store/sqlite.py`; encode uniqueness, foreign keys, owner constraints and scoped lookup indexes, preserving legacy records without automatic sharing (FR-015; depends on T016).
- [ ] [T018] Implement scoped space repositories in `atmem/service/spaces.py` with authenticated identity binding, private-default creation, bounded list/get/count/cursor operations and non-disclosing absent/denied results; test same-name spaces across tenants in `tests/test_memory_space_repository.py` (FR-015; depends on T017).
- [ ] [T019] Implement the read/write-propose/admin decision matrix in `atmem/service/space_permissions.py`; intersect membership with tenant/workspace/subject/source/purpose restrictions, deny implicit child-agent inheritance and privilege escalation, and test every grant combination in `tests/test_memory_space_permissions.py` (FR-015; depends on T018).
- [ ] [T020] Implement add/change/remove member and ownership-transfer transactions in `atmem/service/spaces.py` with expected generation, idempotency, actor/time/reason audit and lost-update handling; test concurrent owner/member edits and owner-removal behavior in `tests/test_memory_space_membership.py` (FR-015; depends on T019).
- [ ] [T021] Integrate explicit destination-space admission and contributor lineage with Spec 006 in `atmem/memory.py`; prove a read-only member cannot write, approve or share, and an agent cannot choose another authenticated actor in `tests/test_memory_space_admission.py` (FR-015, PR-003; depends on T019–T020).
- [ ] [T022] Integrate authorized multi-space retrieval with Spec 019 in `atmem/context/policy.py` and `atmem/service/application.py`; carry source-space and membership generations into packages without weakening signed delegation or source restrictions; test private-record exclusion and broad external credentials in `tests/test_context_governance.py` (FR-015, PR-004; depends on T019–T021 and the 019 package contract).
- [ ] [T023] Connect membership commits to Spec 015 invalidation and supported dispatch revalidation in `atmem/lifecycle/invalidation.py` and `atmem/context/grants.py`; independently schedule removal/read/cache/dispatch races, crash recovery and disconnected consumers in `tests/test_memory_space_revocation.py` (FR-015, PR-003–PR-004; depends on T020/T022 and the existing invalidation interface).
- [ ] [T024] Implement explicitly authorized cross-space copy/share transitions with effect preview and lineage in `atmem/service/spaces.py`, preserving original contributor/source restrictions and distinguishable conflicting assertions; test that sharing never silently overwrites another space in `tests/test_memory_space_lineage.py` (FR-015, PR-003; depends on T021/T023).
- [ ] [T025] Enforce independent memory, execution-history, incident and credential-access grants in `atmem/service/application.py` and related service projections; test joins, counts, exports and indirect references in `tests/test_memory_space_isolation.py` (FR-015; depends on T019/T024, plus 013 T019 for the production route matrix).
- [ ] [T026] Implement the shared reason/effect/uncertainty/action and timestamp-provenance envelope in `atmem/service/feedback.py`; consume actual domain checks without treating page refresh as verification, and validate unknown/skewed/expired times in `tests/test_feedback_contract.py` (FR-015, PR-005–PR-006; depends on T016).
- [ ] [T027] Expose scoped space/membership/feedback operations in `atmem/control/server.py`, `atmem/mcp/server.py` and `atmem/cli.py` through the same service; bind administrative operations to authenticated capabilities and run transport-denial parity in `tests/test_memory_space_contracts.py` (FR-015; depends on T020/T025/T026).
- [ ] [T028] Add Python/TypeScript space and feedback clients through `atmem/client.py`, `packages/typescript/` and negotiated OpenAPI schemas; test old clients, closed-schema versioning and independently authored golden vectors in `packages/typescript/test/` (FR-015; depends on T027).
- [ ] [T029] Exercise published-database upgrade, interrupted migration, restart, rollback/forward recovery and legacy scope equivalence in `tests/test_memory_space_upgrade.py` using fixtures under `tests/fixtures/upgrades/`; prove no newly shared or privatized legacy records (FR-015; depends on T017/T023/T028).
- [ ] [T030] Run adversarial concurrent multi-agent membership, revocation, source-conflict and cross-tenant matrices in `tests/test_memory_space_isolation.py` and `tests/test_memory_space_revocation.py`; retain schedules and exact denied boundaries, not just aggregate pass counts (FR-015, SC-007; depends on T023/T025/T029).
- [ ] [T031] Measure scoped pagination/query plans and membership-write/dispatch-check overhead under declared load in `tests/test_memory_space_performance.py`; freeze test scale and thresholds before measurement, report every miss and optional backend separately (FR-015, SC-007; depends on T028/T030).
- [ ] [T032] Run installed Python/TypeScript/MCP/UI contract acceptance and affected invariant/privacy gates; append exact results under `docs/implementation-evidence/012/`, publish compatibility guidance in `docs/http-api.md`, and link supported profiles from `docs/current-status.md` (FR-015, SC-007; depends on T026–T031).
