# Tasks: Production Service Profile

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/013/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

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

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: existing 010/012/015 contracts; 024 and 025 consume this subsystem and are not prerequisites for durable authentication.

- [ ] [T009] Define failing boundary fixtures for FR-010, FR-011, SC-005 using `tests/server/`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T010] [ROLLUP: decomposed into T012–T025] Complete durable credentials and actual production-boundary enforcement through the tasks below (FR-010, FR-011). This compatibility/completion marker adds no independent implementation estimate; close only after T012–T025 pass.
- [ ] [T011] Verify SC-005 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/013/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T010 and do not mark completion from declarations alone.

## FR-010: Durable identity and production enforcement subsystem

T009 supplies acceptance fixtures. The existing in-memory KeyAuthority is a baseline implementation, not completion of the tasks below. Contract dependencies are named individually to avoid cycles with 012 membership work.

- [ ] [T012] Freeze authenticated principal, credential ID/version, role/scope binding, revocation generation, rotation and trusted-proxy rules in `atmem/server/auth.py` and schemas under `atmem/schemas/`; document issuance/administration permissions and unknown-outcome behavior in `docs/security/production-threat-model.md` (FR-002, FR-010; depends on T009; consumes only existing Spec 012 principal/operation contracts).
- [ ] [T013] Allocate durable credential/role/revocation/audit storage through Spec 010 in `atmem/server/credential_store.py`; add migrations and repository tests for tenant filters, uniqueness, restart and transactional ownership in `tests/server/test_credential_store.py` (FR-010; depends on T012).
- [ ] [T014] Implement issuance and verification against the durable repository in `atmem/server/auth.py`; retain hashed-at-rest high-entropy key material, constant-time verification, expiry and scoped least privilege. Test that public responses and failures disclose no stored credential material in `tests/server/test_auth.py` (FR-002, FR-010; depends on T013).
- [ ] [T015] Implement transactional rotate/revoke/expire with expected generation and idempotency in `atmem/server/auth.py`; define replacement/overlap behavior explicitly and test simultaneous rotation/revocation and interrupted responses in `tests/server/test_credential_lifecycle.py` (FR-002, FR-010; depends on T014).
- [ ] [T016] Bind credential and role changes to durable separately authorized administrative audit in `atmem/server/admin_audit.py`; test transaction failure/retry without unaudited authority changes or leaked secrets in `tests/server/test_admin_audit.py` (FR-008, FR-010; depends on T015).
- [ ] [T017] Implement current revocation/role-generation checks across two replicas in `atmem/server/credential_store.py` and `atmem/server/cache_policy.py`; declare propagation bounds and partition behavior before testing, and deny operations when current required authority cannot be established in `tests/server/test_auth_replicas.py` (FR-010, SC-002; depends on T015).
- [ ] [T018] Bind actual production request authentication to durable identities in `atmem/control/web.py` and `atmem/server/auth.py`; reject caller-selected role/tenant headers as authority, validate configured proxy identity trust, and keep local bearer mode a separate explicit profile in `tests/server/test_production_auth_boundary.py` (FR-001–FR-003, FR-009–FR-011; depends on T014/T017).
- [ ] [T019] Enforce the complete registered production-route operation matrix through `atmem/service/application.py` and production routers, including admin/agent separation, exports, events and direct service calls; verify omissions fail closed in `tests/server/test_production_routes.py` (FR-003, FR-010; depends on T016/T018). Consumers 012/024/025 must register each new operation against this contract.
- [ ] [T020] Reauthorize queued work at claim and before privileged effects in `atmem/server/jobs.py`; preserve scoped actor/workload references without serializing reusable secrets, and exercise revoke-during-queue/retry/lease/cancel in `tests/server/test_job_authorization.py` (FR-005, FR-010; depends on T019).
- [ ] [T021] Bind cache keys, metrics, audit queries and exports to current scope/role generations in `atmem/server/cache_policy.py`, `atmem/server/observability.py` and `atmem/server/repositories.py`; test indirect identifier/count/content disclosure after revocation in `tests/server/test_production_isolation.py` (FR-003, FR-008, FR-010; depends on T019).
- [ ] [T022] Exercise backup/restore and forward recovery of credential/revocation state in `atmem/server/recovery.py` and `tests/server/test_credential_recovery.py`; define authority revalidation after rollback so a stale backup cannot resurrect revoked keys, and record the external authority assumptions (FR-007, FR-010; depends on T015–T017).
- [ ] [T023] Test actual profile startup and degraded credential-store behavior in `atmem/server/config.py` and `tests/server/test_production_faults.py`, including TLS rejection, storage outage, replica partition and audit failure; retain local/disconnected profile compatibility without bypassing production checks (FR-001, FR-010–FR-011; depends on T019–T022).
- [ ] [T024] Run the installed-service two-replica route/job/revocation matrix and supported published-state upgrade gates in `tests/server/test_production_installed.py`; measure the declared propagation bound with exact versions, failure schedules and unavailable cases (FR-010, SC-005; depends on T023).
- [ ] [T025] Append subsystem results under `docs/implementation-evidence/013/`, publish operational recovery/rotation guidance in `docs/production-service.md`, and link verified production capabilities from `docs/current-status.md`. Gate 024 fleet and 025 approval/activation claims on their actual registered routes passing this contract (FR-010–FR-011, SC-005; depends on T024).
