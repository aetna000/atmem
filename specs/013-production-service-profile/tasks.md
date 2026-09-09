# Tasks: Production Service Profile

**Input**: Design documents from `specs/013-production-service-profile/`

**Prerequisites**: Specs 010, 012, and 015 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Produce threat model in `docs/security/production-threat-model.md` and principal/role/key/tenant/job/admin-audit contracts in `atmem/schemas/v1/` (FR-001–FR-008)

## Phase 2 — User Story 1 - Operate an isolated service (Priority: P1)

- [x] [T002] [US1] Implement scoped key issue/rotate/revoke/expiry and authorization matrix in `atmem/server/auth.py` and `tests/server/test_auth.py` (FR-002)
- [x] [T003] [US1] Enforce tenant/user/workspace/agent isolation in `atmem/server/repositories.py`, Spec 012's `atmem/service/application.py`, `atmem/server/cache_policy.py`, and `atmem/server/jobs.py`; configure Spec 010's `atmem/retrieve/cache.py` only through its public interface (FR-003)
- [x] [T004] [US1] Add production TLS/secret/encryption/retention/quota validation and safe startup in `atmem/server/config.py` and `tests/server/test_config.py` (FR-001, FR-004, FR-009)
- [x] [T005] [US1] Implement scoped idempotent workers, leases, retries, cancellation, and dead-letter inspection in `atmem/server/jobs.py` (FR-005)

## Phase 3 — User Story 2 - Recover and prove health (Priority: P2)

- [x] [T006] [US2] Add redacted health/metrics and separately authorized append-evidenced admin audit in `atmem/server/observability.py` and `atmem/server/admin_audit.py` (FR-006, FR-008)
- [x] [T007] [US2] Implement encrypted backup, verified restore, deletion checks, and DR drill receipts in `atmem/server/recovery.py` and `tests/server/test_recovery.py` (FR-007)
- [x] [T008] [US2] Run isolation, key, quota, load/failure, and RPO/RTO gates in `tests/server/`; publish operating/rollback guide in `docs/production-service.md` (SC-001–SC-004)

## Dependencies and Execution Order

**Cross-spec dependencies**: Specs 010, 012, and 015.
**Task dependencies**: T001 → all; T002/T003/T004 → T005/T006/T007; T005–T007 → T008.


## Phase 4: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 024; existing 010/012/015; see the roadmap for foundation versus integration ordering.

- [ ] [T009] Define failing boundary fixtures for FR-010, FR-011, SC-005 using `tests/server/`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T010] Close durable credential and end-to-end production-route enforcement gaps in `atmem/server/auth.py`, `atmem/server/config.py`, `atmem/server/jobs.py` (FR-010, FR-011); depend on T009 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T011] Verify SC-005 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `specs/implementation-review-2026-09-09.md`; depend on T010 and do not mark completion from declarations alone.
