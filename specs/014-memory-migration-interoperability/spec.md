# Feature Specification: Memory Migration and Interoperability

**Feature directory**: `specs/014-memory-migration-interoperability`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P1.12

## Overview

Let users evaluate and move between AtMem and Mem0 without lock-in through evidence-preserving import, neutral export, dry runs, conflict review, resumability, and digest-bound receipts.

## User Scenarios & Testing

### User Story 1 - Preview and import Mem0 data (Priority: P1)

An operator maps explicit tenant/user/workspace/agent scope, previews adds/updates/conflicts/skips, reviews uncertain mappings, then resumes an idempotent import whose receipt reconciles source counts and digests.

**Why this priority**: Safe evaluation requires importing without accidental scope widening or duplicate mutation.

**Independent Test**: Dry-run, interrupt, resume, and replay a fixed Mem0 fixture and reconcile every count and digest.

**Acceptance Scenario**: **Given** an explicit scope map and unchanged source archive, **when** import resumes, **then** acknowledged batches are not repeated and final counts match the plan.

### User Story 2 - Export neutral evidence (Priority: P2)

An authorized operator exports selected memories, lifecycle/history, scope labels, metadata, sources, and provenance in a documented format without secrets or inaccessible records.

**Why this priority**: Neutral export is the product's lock-in escape hatch and independent evidence format.

**Independent Test**: Export and revalidate a mixed-scope fixture, then round-trip its supported records into isolated state.

**Acceptance Scenario**: **Given** an authorized export selection, **when** export runs, **then** only eligible records appear and the archive digest/provenance verify.

### Edge Cases

- Changed input after checkpoint, duplicate source IDs, missing scope, unsupported vendor fields, malformed/tampered archives, and concurrent canonical changes halt with reconcilable reasons.
- Resume never repeats an acknowledged batch; rollback never removes unrelated records.
- Export redaction and retention apply at execution time, not only when the job was planned.

## Requirements

### Functional Requirements

- **FR-001**: Define a versioned neutral archive manifest and record/evidence/history schemas with canonical serialization and digests.
- **FR-002**: Mem0 import MUST preserve supported metadata/source identity and record import evidence; absent scope MUST require explicit mapping, never a broad default.
- **FR-003**: Every import MUST support no-write dry-run with deterministic add/update/conflict/duplicate/reject/skip counts and reasons.
- **FR-004**: Conflicts, ambiguous identity, sensitive content, and destructive changes MUST enter review before commit.
- **FR-005**: Import MUST use stable source IDs, checkpoints, scoped idempotency, generation preconditions, and atomic batches for safe resume.
- **FR-006**: Completion/rollback receipts MUST bind source/archive digest, options, scope map, counts, affected IDs, checkpoints, and verification outcome.
- **FR-007**: Export MUST apply current authorization, lifecycle, retention, and redaction and include enough provenance for independent verification.
- **FR-008**: Every format version MUST have upgrade, downgrade/unsupported, interrupted-run, and rollback tests.
- **FR-009**: Imports MUST pass normal AtMem policy/admission and must not make foreign vectors/graphs canonical.

### Key Entities

- **Neutral Archive**: Versioned manifest and canonical record/evidence/history stream.
- **Scope Map**: Explicit source-to-AtMem tenant/user/workspace/agent mapping.
- **Import Plan**: Deterministic add/update/conflict/duplicate/reject/skip decisions.
- **Migration Receipt**: Digests, options, checkpoints, counts, affected IDs, and verification.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Dry-run and committed count/reason reconciliation is exact for unchanged input.
- **SC-002**: Replaying or resuming an import produces no duplicate canonical mutations.
- **SC-003**: Round-trip neutral fixtures retain supported scope, evidence, lifecycle, and history fields with documented loss only.
- **SC-004**: Cross-scope, tampered archive, partial failure, and rollback tests produce no unauthorized or unreceipted mutation.

## Out of Scope

Importing credentials, trusting foreign embeddings as authority, or promising lossless mapping for undocumented vendor fields.

## Assumptions

- Spec 006 provides typed proposal validation and review.
- Mem0 input is user-supplied and its exact supported versions are documented.
- Unsupported fields are reported rather than silently dropped.
