# Feature Specification: HTTP API and TypeScript SDK

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/012-http-api-and-typescript-sdk`
**Created**: 2026-09-05
**Status**: Implemented
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
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
## Invariant Attestation

Touches INV-001, INV-002, INV-005, and INV-008 through `spec012.application-authority`, `spec012.api-auth`, `spec012.idempotency`, and `spec012.transport-proof`.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: public services and transports. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Shared application facade and clients exist; execution, incident and resolution services are not exposed as one public surface.

### Additional functional requirements

- **FR-013**: Expose execution, context-package, policy-decision, incident and resolution resources through one transport-neutral service with equivalent SDK, HTTP, CLI, MCP and dashboard semantics.
- **FR-014**: Separate runtime context/evidence operations from operator provider/policy/resolution actions; derive scopes from authenticated principals and enforce pagination, idempotency and non-disclosing errors across all new resources.

### Acceptance and success criteria

- **SC-006**: Cross-language and MCP golden fixtures reconcile response identities and outcomes; agent credentials cannot acknowledge organizational findings, edit policies, approve retries or inspect other scopes.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019–021. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.

## Product-wide requirements — agent neutrality and clear evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-001–PR-006. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-015**: Extend the existing scope authority with a versioned MemorySpace and SpaceMembership service: tenant/workspace-bound owner, private/shared visibility, independent read/write-propose/admin grants, expected revision, authenticated actor, audit and idempotency. New spaces default private; legacy scope behavior remains unchanged. Publish one feedback contract containing readable reason, accessible resource/agent references, assurance, known effect/uncertainty, event/received/evaluated/verified timestamps with provenance, evidence links and authorized action or absence reason. All transports authorize joins/counts/exports and share these semantics.
- **SC-007**: SDK, HTTP, MCP, CLI and dashboard fixtures agree on membership, space visibility and feedback facts across restart and concurrent revisions; agents cannot select another principal, administer their own grants, read inaccessible histories or leak private metadata through summaries.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.

### FR-015 implementation and acceptance decomposition

FR-015 is a persisted authority subsystem. Tasks T016–T032 separately deliver contracts, migrations, scoped repositories, independent grants, revisioned membership/owner changes, admission, provider retrieval, revocation races, cross-space lineage, independent log/credential visibility, feedback, transports, clients and installed acceptance. T014 is their roll-up; T015 remains the final SC-007 gate. The detailed plan defines atomic generation/audit/invalidation boundaries and the 013 principal-contract handoff. No single façade change satisfies this requirement.
