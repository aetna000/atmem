# Feature Specification: Semantic Setup and Health

**Feature directory**: `specs/005-semantic-setup-and-health`
**Created**: 2026-09-05
**Status**: Implemented
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
**Input**: `todo.md` P0.2

## Overview

Make strong local semantic retrieval easy to enable and safe to operate while retaining dependency-free hashing as the offline fallback. Model and index identity must be visible, compatibility must be verified, and model changes must never mix incompatible vectors.

## User Scenarios & Testing

### User Story 1 - Enable local semantic recall (Priority: P1)

A new user runs one guided command, receives hardware-aware model choices, explicitly approves any download, builds an index, and verifies a paraphrase query.

**Why this priority**: Strong semantic recall must be accessible without weakening the offline default.

**Independent Test**: Run setup in a clean isolated environment with a fake local provider and verify the resulting paraphrase query and manifest.

**Acceptance Scenarios**:

1. **Given** a supported clean machine, **when** setup completes, **then** the index is healthy and the synthetic paraphrase is recalled.
2. **Given** download refusal or provider failure, **when** setup exits, **then** hashing remains available and its limitations are stated.

### User Story 2 - Diagnose and repair an index (Priority: P2)

An operator sees the same health state in CLI and dashboard: provider/model identity, dimensions, epoch, source digest, record coverage, and `healthy`, `weak`, `missing`, `stale`, `incompatible`, or `rebuilding` status.

**Why this priority**: Operators must detect unsafe or ineffective derived state before it affects retrieval.

**Independent Test**: Materialize one fixture per health state and compare CLI JSON with the dashboard API projection.

**Acceptance Scenarios**:

1. **Given** a stale or incompatible index, **when** retrieval and status run, **then** the epoch is withheld and a rebuild action is offered.
2. **Given** an interrupted rebuild, **when** health is reevaluated, **then** the prior valid epoch remains active and partial state is explicit.

## Requirements

### Functional Requirements

- **FR-001**: Hashing MUST remain the installed, offline, deterministic fallback.
- **FR-002**: A guided CLI flow MUST discover hardware, recommend supported local models with size/resource caveats, require approval for downloads, configure the provider, build an index, and run a semantic smoke test.
- **FR-003**: Recommendations MUST be deterministic for the same observed hardware and catalog version and MUST allow manual selection.
- **FR-004**: Every semantic epoch MUST bind provider, model, revision, dimensions, normalization, configuration digest, canonical-data generation, record count, and creation status.
- **FR-005**: CLI human/JSON output and dashboard MUST expose the same health vocabulary, evidence, and corrective action.
- **FR-006**: Retrieval MUST reject missing, stale, dimension-mismatched, partially built, or otherwise incompatible epochs and fall back safely.
- **FR-007**: Rebuild MUST be staged, resumable, scope-safe, and atomically activated only after coverage and compatibility checks.
- **FR-008**: Model downloads and any network egress MUST be explicit and recorded without secrets.
- **FR-009**: Deletion and policy changes MUST invalidate or repair affected derived vectors; the index MUST never become canonical.
- **FR-010**: Setup and repair MUST preserve authorization-before-intelligence, shadow mode, exact context delivery, history, and backward-compatible persisted data.

### Edge Cases

Insufficient disk/RAM, model revision drift, changed dimensions, interrupted rebuild, empty authority store, deleted records during rebuild, provider timeout, and a dashboard opened while epochs switch all produce explicit safe states.

### Key Entities

- **Semantic Manifest**: Versioned identity and compatibility facts for one derived index epoch.
- **Semantic Health**: Evaluated state, reasons, evidence, and allowed corrective actions.
- **Rebuild Receipt**: Checkpoints, canonical generation, coverage, validation, and activation outcome.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In a documented controlled usability protocol, at least 90% of representative new users configure local embeddings and pass a paraphrase smoke test in under 10 minutes excluding download duration and without undocumented assistance.
- **SC-002**: Fixtures for every health state yield identical CLI JSON and dashboard API semantics.
- **SC-003**: Fault injection at every rebuild phase never activates a partial epoch or exposes an unauthorized/deleted record.
- **SC-004**: Offline tests prove hashing remains functional when all optional semantic components are absent.
- **SC-005**: An automated clean-environment fixture completes setup, index build, health verification, and paraphrase recall in one resumable command flow with at most six user decisions.

## Out of Scope

Hosted embedding recommendations, changing canonical memory, or guaranteeing a particular third-party model remains downloadable.

## Assumptions

- Supported local model recommendations come from a versioned checked-in catalog.
- Hardware discovery may be incomplete; manual model selection remains available.
- Existing indexes without sufficient identity metadata are treated as legacy/unknown, not healthy.
## Invariant Attestation

Touches INV-003 and INV-010 through `spec005.semantic-health` and `spec005.local-fallback`.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: semantic health. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Staged epochs and health states exist; semantic health is specific to native retrieval.

### Additional functional requirements

- **FR-011**: Report native embedding health as provider-specific readiness, not a global prerequisite for external-context or investigation-only use.
- **FR-012**: Bind native package provenance to epoch/model/generation and expose withheld stale or incompatible index reasons through execution evidence without marking an unrelated tool execution failed.

### Acceptance and success criteria

- **SC-006**: With no local embedding runtime, investigation-only and eligible external-provider flows remain operational; native stale-epoch use is withheld with exact reasons.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019, 022. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.
