# Feature Specification: Production Service Profile

**Feature directory**: `specs/013-production-service-profile`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P2.13

## Overview

Define an explicitly activated production service profile with authentication, tenant isolation, scoped keys, secure transport/secrets, quotas, workers, metrics, backup, and disaster recovery. It must not imply that the loopback dashboard is already a multi-user service.

## User Scenarios & Testing

### User Story 1 - Operate an isolated service (Priority: P1)

An administrator provisions tenants and scoped, expiring API keys; users can access only their tenant/user/workspace/agent resources. Agent principals cannot read administrative audit or control global policy.

**Why this priority**: Tenant isolation and least privilege are prerequisites for any honest multi-user claim.

**Independent Test**: Run the full cross-tenant authorization matrix through API, cache, job, export, metric, and audit paths.

**Acceptance Scenario**: **Given** two tenants and scoped principals, **when** either probes the other's resources, **then** every path denies access without existence leakage.

### User Story 2 - Recover and prove health (Priority: P2)

Operators observe redacted service/store/index/worker health, enforce quotas/retention, rotate secrets/keys, create verified backups, and rehearse restoration against declared RPO/RTO targets.

**Why this priority**: A secure service is not production-ready without observable recovery.

**Independent Test**: Revoke a key, exhaust a quota, fail a worker, and restore a verified backup in an isolated deployment.

**Acceptance Scenario**: **Given** a valid backup and declared recovery targets, **when** a restore drill runs, **then** integrity/isolation checks pass and an RPO/RTO receipt is emitted.

### Edge Cases

- Key revocation during a request, tenant deletion during a job, worker lease expiry, quota races, partial backup, and dependency outage fail without crossing authority scope.
- Non-loopback startup without valid TLS/authentication is rejected.
- Metrics, logs, dead-letter views, and backup manifests cannot become side channels for scoped content.

## Requirements

### Functional Requirements

- **FR-001**: Non-loopback service mode MUST require authenticated TLS and explicit production configuration validation.
- **FR-002**: Principals, roles, and scoped API keys MUST support issuance, expiry, rotation, revocation, least privilege, and hashed-at-rest key material.
- **FR-003**: Tenant, user, workspace, agent, and administrative boundaries MUST be enforced in application and storage queries, caches, jobs, metrics, and logs.
- **FR-004**: Secret sources, encryption at rest/in transit, retention, and quota policies MUST be configured without exposing secret values.
- **FR-005**: Background workers MUST use authenticated scoped job envelopes, idempotency, leases, retries, dead-letter state, and cancellation.
- **FR-006**: Health/metrics MUST expose availability, saturation, lag, failures, and degraded dependencies without scoped content.
- **FR-007**: Backup and disaster recovery MUST bind configuration/schema/data digests, support encrypted storage, and verify restore plus deletion/retention policy.
- **FR-008**: Administrative audit MUST be append-evidenced, separately authorized, and inaccessible to agent principals.
- **FR-009**: The local single-user profile MUST remain available and MUST not be silently upgraded into production mode.

### Key Entities

- **Service Principal**: Tenant-bound user, agent, worker, or administrator identity.
- **Scoped API Key**: Hashed credential with role, scope, expiry, rotation, and revocation state.
- **Job Envelope**: Idempotent scoped work reference, lease, attempts, and terminal outcome.
- **Recovery Receipt**: Backup/restore identities, digests, schema/config versions, and verification.

## Success Criteria

### Measurable Outcomes

- **SC-001**: An isolation suite records zero cross-tenant access through API, jobs, cache, metrics, logs, exports, and backups.
- **SC-002**: Revoked/expired keys stop new operations within the declared propagation bound.
- **SC-003**: Load/failure tests meet published quotas and availability targets without bypassing authorization.
- **SC-004**: A clean restore drill meets declared RPO/RTO and produces a verified receipt.

## Out of Scope

Managed SaaS operation, unsupported multi-region consensus, or storing plaintext API keys.

## Assumptions

- Specs 010, 012, and 015 are completed before production readiness is claimed.
- Operators provide supported TLS certificates, secret storage, and backup destinations.
- The local single-user profile remains a distinct supported deployment mode.
