# Feature Specification: Memory Lifecycle Controls

**Feature directory**: `specs/015-memory-lifecycle-controls`
**Created**: 2026-09-05
**Status**: Draft
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
