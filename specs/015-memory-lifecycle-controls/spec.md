# Feature Specification: Memory Lifecycle Controls

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/015-memory-lifecycle-controls`
**Created**: 2026-09-05
**Status**: Implemented
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
**Input**: `todo.md` P2.14

## Overview

Make aging, validity, review, archival, correction, and forgetting explicit governed transitions so stale memory cannot accumulate or remain retrievable silently.

## User Scenarios & Testing

### User Story 1 - Understand current validity (Priority: P1)

Users can inspect learned-at, valid-from/to, replaced-at, last-used, retention/expiry/review policy, current lifecycle state, evidence, and why a record is eligible or withheld.

**Why this priority**: Eligibility must be understandable before lifecycle automation is trusted.

**Independent Test**: Evaluate one record at boundary times through CLI/dashboard/API and reconcile the same state/timeline.

**Acceptance Scenario**: **Given** an explicit evaluation time, **when** lifecycle is inspected, **then** state, policy, timestamps, and eligibility reason agree across surfaces.

### User Story 2 - Govern transitions and deletion (Priority: P2)

Authorized users preview and perform correct, merge, split, exclude, approve, reject, archive, restore, or forget. Optional decay/promotion only proposes evidence-based changes and never silently deletes or expands scope.

**Why this priority**: Lifecycle changes can be destructive and must be governed and verifiable.

**Independent Test**: Exercise every allowed/forbidden transition and verify all registered derived invalidations.

**Acceptance Scenario**: **Given** an authorized transition with current preconditions, **when** it commits, **then** canonical state and derived verification agree in one receipt.

### Edge Cases

- Clock boundaries, paused schedules, concurrent corrections, overlapping policies, failed invalidation workers, and backup retention produce explicit evaluated-time and verification states.
- Restore cannot revive an expired, rejected, excluded, superseded, or forgotten record without a new authorized transition.
- A missing derived backend is reported in the deletion receipt rather than silently treated as verified.

## Requirements

### Functional Requirements

- **FR-001**: Define versioned lifecycle states/transitions and timestamps for learned, validity interval, replacement, last use, review, expiry, archive, and deletion.
- **FR-002**: Eligibility MUST use an explicit evaluation time and distinguish event validity from storage/retention state.
- **FR-003**: Retention, expiry, archive, and review policies MUST be scope-bound, ordered, previewable, and auditable.
- **FR-004**: Correction, merge, split, exclude, approve, reject, forget, archive, and restore MUST have typed preconditions, evidence, actor, reason, and receipt.
- **FR-005**: Decay/promotion MUST be optional, versioned, explainable proposals based on declared evidence; policy validation controls acceptance.
- **FR-006**: Transitions MUST atomically update canonical eligibility/generation and invalidate graph, vector, cache, and prepared-context derivatives.
- **FR-007**: Forget verification MUST check all active derived stores and enforce documented backup-retention/crypto-erasure policy.
- **FR-008**: CLI/dashboard/API MUST show identical current state, timeline, allowed actions, preview impact, and verification status.
- **FR-009**: Legacy records MUST receive safe default lifecycle values through backward-compatible migration.
- **FR-010**: SQLite lifecycle schema changes MUST pass real persisted upgrades from every supported published AtMem upgrade floor and MUST include rollback and forward-recovery evidence.

### Key Entities

- **Lifecycle State**: Current eligibility/storage state plus learned, validity, replacement, use, review, expiry, archive, and deletion times.
- **Lifecycle Policy**: Scoped ordered rules for review, retention, expiry, archive, decay, and promotion.
- **Transition Receipt**: Preconditions, actor, reason, evidence, canonical generation, invalidations, and verification.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A transition matrix test proves every allowed/forbidden state change and concurrent precondition.
- **SC-002**: Time-travel fixtures answer temporal eligibility consistently at boundary instants.
- **SC-003**: No expired, rejected, superseded, excluded, forgotten, or unauthorized record reaches final context.
- **SC-004**: Forget receipts reconcile canonical, graph, vector, cache, and applicable backup policy checks.

## Out of Scope

Unexplained autonomous deletion, rewriting immutable evidence, or claiming physical removal from backups before their declared retention/erasure boundary.

## Assumptions

- Canonical evaluation uses a trusted explicit clock supplied to policy code.
- Spec 010 registers non-SQLite derived stores and cache invalidators.
- Backup deletion claims follow the documented retention or cryptographic-erasure boundary.
## Invariant Attestation

Touches INV-001, INV-003, INV-006, INV-007, and INV-011 through `spec015.lifecycle-authority`, `spec015.eligibility`, `spec015.timeline`, `spec015.forget`, and `spec015.migration`.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: lifecycle and revocation. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Canonical lifecycle and invalidation registry exist; provider-wide source exposure impact and grants are extensions.

### Additional functional requirements

- **FR-011**: Publish scoped source lifecycle/generation changes to Spec 023 through the existing invalidation registry, identifying controlled derivatives and external consumers separately.
- **FR-012**: Distinguish a deletion request, local invalidation, external acknowledgment and verified deletion; never describe revocation as erasing past model exposure or unmanaged backups.

### Acceptance and success criteria

- **SC-005**: Revocation races prevent future supported governed delivery; local and external cleanup statuses remain distinct and historical evidence follows retention without resurrecting deleted content.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019, 023. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.

## Product-wide requirements — agent neutrality and clear evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-003–PR-006. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-013**: Register memory-space membership changes with existing invalidation/generation services. Removal blocks future authorized reads and affected controlled cache/prepared-context use; supported dispatch rechecks current membership. Preserve source and contributor lineage and separately report local invalidation, external acknowledgments, in-flight uncertainty and retained historical evidence access.
- **SC-006**: Concurrent member removal versus retrieval/dispatch cannot deliver unauthorized content at supported controlled boundaries; caches cannot resurrect removed access, while prior exposure and uncontrolled external copies are explicitly reported with real check timestamps.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.
