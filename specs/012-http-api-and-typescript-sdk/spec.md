# Feature Specification: HTTP API and TypeScript SDK

**Feature directory**: `specs/012-http-api-and-typescript-sdk`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P1.11

## Overview

Expose stable local application contracts for memory, query, review, audit, configuration, and health so clients do not import Python internals or depend on OpenClaw. Support Python, TypeScript, and MCP from the same semantics.

## User Scenarios & Testing

### User Story 1 - Build against a stable API (Priority: P1)

An application uses a versioned loopback HTTP API and generated/supported TypeScript client for memory and query operations with typed requests, responses, errors, timeouts, filtering, pagination, and idempotent mutation.

**Why this priority**: Stable application integration must not depend on Python internals or one host bridge.

**Independent Test**: Use only the published TypeScript package against an isolated loopback server to capture and query synthetic memory.

**Acceptance Scenario**: **Given** a compatible client and server, **when** a scoped mutation is retried, **then** one canonical outcome and one idempotency receipt result.

### User Story 2 - Separate agent and admin authority (Priority: P2)

Credentials/transport identity authorize an explicit operation set. Agent clients cannot reach administrative configuration, broad audit, review policy, migration, or destructive operations.

**Why this priority**: Public APIs otherwise risk turning integration convenience into administrative authority.

**Independent Test**: Execute the full operation matrix with agent and administrator principals.

**Acceptance Scenario**: **Given** agent credentials, **when** an administrative operation is attempted, **then** it fails without disclosing the target resource.

### Edge Cases

- Replayed idempotency keys with different payloads, expired cursors, concurrent page mutations, client cancellation, and version mismatch produce stable structured errors.
- Unauthorized resource IDs do not disclose existence through status, timing metadata, totals, or pagination.
- Partial client generation or unavailable optional transport cannot change server authority semantics.

## Requirements

### Functional Requirements

- **FR-001**: Publish an OpenAPI-described versioned API for memory, query/context, review, audit, configuration, health, and capabilities.
- **FR-002**: Resources MUST use stable IDs, schemas, version negotiation, structured errors, request IDs, and deprecation policy.
- **FR-003**: List endpoints MUST provide bounded cursor pagination, filtering, stable ordering, and scope-safe totals/metadata.
- **FR-004**: Mutations MUST support scoped idempotency keys, preconditions, replay semantics, and conflict errors.
- **FR-005**: Server and SDK MUST enforce configurable connect/read/overall timeouts and safe cancellation.
- **FR-006**: Agent and administrative operations MUST be distinct in schema, authorization, documentation, and audit.
- **FR-007**: TypeScript and Python clients MUST preserve API semantics and never hide authority, egress, review, or deletion outcomes.
- **FR-008**: MCP tools MUST map to the same service layer and declare narrower tool-only proof boundaries.
- **FR-009**: Default binding MUST remain loopback with explicit activation; responses/logs MUST redact secrets and inaccessible content.
- **FR-010**: CLI and dashboard MUST consume or contract-test against the same public response models.
- **FR-011**: SQLite idempotency or API metadata schema changes MUST pass real persisted upgrades from every supported published AtMem upgrade floor with rollback/forward-recovery evidence.
- **FR-012**: Python components MUST support Python 3.10–3.13; npm/Python generated and runtime dependencies MUST have Apache-2.0-compatible enterprise licensing.

### Key Entities

- **API Principal**: Authenticated identity and allowed agent/admin operations.
- **Public Resource**: Versioned memory, query, review, audit, configuration, health, or capability representation.
- **Idempotency Receipt**: Scoped request identity, canonical payload digest, outcome, and expiry.
- **Cursor Page**: Stable ordered authorized slice plus opaque continuation state.

## Success Criteria

### Measurable Outcomes

- **SC-001**: OpenAPI validation and language contract tests cover every operation/error class.
- **SC-002**: Idempotency retries never duplicate canonical mutations; pagination never crosses scope.
- **SC-003**: Agent credentials fail every administrative conformance case.
- **SC-004**: A sample TypeScript app performs capture, query, review-status, and health without internal Python/OpenClaw dependencies.
- **SC-005**: Cross-version persisted-state, Python 3.10–3.13, generated-client reproducibility, clean-install, and dependency-licence gates all pass.

## Out of Scope

Internet-facing production hardening (Spec 013), browser-specific SDKs, or hiding explicit review/authority outcomes behind convenience methods.

## Assumptions

- The initial API binds to the existing loopback control server.
- `atmem/service/` becomes the only transport-neutral application-service package.
- Spec 013 supplies non-loopback production authentication and deployment controls.
