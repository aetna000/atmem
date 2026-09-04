# Feature Specification: Cross-Cutting Invariant Conformance

**Feature directory**: `specs/018-cross-cutting-invariants`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` "Do not weaken existing AtMem advantages"

## Overview

Turn the eleven standing AtMem guarantees into a versioned registry of executable invariants with a standing regression suite, per-spec attestation, and a release gate. Every roadmap feature changes authority, retrieval, storage, lifecycle, adapters, or deletion; nothing currently proves that the guarantees survive that change as a product-level property rather than inside each feature's own tests.

## User Scenarios & Testing

### User Story 1 - Prove the guarantees still hold (Priority: P1)

A maintainer runs one suite against the installed package and receives a per-invariant verdict of proven, partially proven with a named gap, or unproven, with the evidence behind each result.

**Why this priority**: An unproven guarantee is indistinguishable from a broken one, and eleven customer-visible claims currently rest on feature-local tests only.

**Independent Test**: Run the suite against the current release with no optional extras and no network, and reconcile every invariant verdict with its named assertions.

**Acceptance Scenario**: **Given** the installed package, **when** the conformance suite runs, **then** each invariant reports a verdict bound to executing assertions and no invariant is claimed without one.

### User Story 2 - Catch a regression at the boundary that made the claim (Priority: P1)

A feature spec that weakens an invariant fails the gate with the invariant ID, the owning spec, and the failing assertion, before release rather than after.

**Why this priority**: The guard is only worth building if it demonstrably fails when the guarantee is broken.

**Independent Test**: Seed one deliberate violation per invariant and verify the suite fails with the correct invariant ID and no false positives elsewhere.

**Acceptance Scenario**: **Given** a seeded violation of one invariant, **when** the gate runs, **then** it fails naming that invariant and leaves every other verdict unchanged.

### User Story 3 - Attest what a feature touched (Priority: P2)

A feature spec declares which invariants its changes affect and extends the matching assertions, so review sees coverage rather than a prose assurance.

**Why this priority**: Attestation makes the constitution's acceptance-evidence requirement checkable, but the baseline suite is useful before every spec attests.

**Independent Test**: Submit a change touching authority and deletion with no attestation and verify the gate rejects it.

**Acceptance Scenario**: **Given** a feature that alters an invariant-bearing surface, **when** it lacks an attestation, **then** the gate fails with the missing invariant IDs.

### Edge Cases

- An invariant whose proof depends on an optional backend or extra reports partially proven with the named uncovered configuration rather than proven.
- A removed or renamed feature surface makes an assertion unrunnable; the invariant becomes unproven rather than silently passing.
- Two specs attest to the same invariant with conflicting expectations; the conflict fails the gate instead of last-writer-wins.
- The suite itself is skipped or filtered in CI; a missing run is a failure, never an implicit pass.

## Requirements

### Functional Requirements

- **FR-001**: Publish a versioned machine-readable invariant registry binding each of `INV-001` through `INV-011` to its guarantee statement, governing constitution principle, owning assertions, and current verdict.
- **FR-002**: Every invariant MUST have at least one executable assertion at the boundary where the claim is made; a documentation-only or comment-only invariant MUST fail validation.
- **FR-003**: `INV-001` canonical authority, `INV-002` authorization before intelligence, `INV-003` ranking revalidation, `INV-004` explicit shadow mode and activation, `INV-005` byte-stable receipt-bound context, `INV-006` human-readable provenance and history, `INV-007` deletion across canonical/graph/vector/derived copies, `INV-008` honest Agent Black Box proof boundaries, `INV-009` reversible OpenClaw migration, `INV-010` local operation and deterministic fallback, and `INV-011` backward-compatible persisted-data upgrades MUST each be represented as a separately addressable invariant.
- **FR-004**: The suite MUST execute against the installed package on every supported Python version, with no optional extras, no configured model provider, and no network access.
- **FR-005**: Each verdict MUST be exactly one of `proven`, `partially_proven`, or `unproven`; `partially_proven` MUST name the uncovered configuration and `unproven` MUST name the missing or unrunnable assertion.
- **FR-006**: A feature specification that changes an invariant-bearing surface MUST record an attestation naming the affected invariant IDs and the assertions it adds or extends.
- **FR-007**: A failing invariant MUST fail the release gate and MUST report the invariant ID, guarantee statement, owning spec, failing assertion, and evidence location.
- **FR-008**: Adding, removing, retitling, or narrowing an invariant MUST require an explicit amendment record citing the constitution principle, reason, compatibility impact, and replacement coverage.
- **FR-009**: The suite MUST use synthetic scoped data only and MUST NOT emit secrets, scoped memory content, raw prompts, or tool payloads into reports, logs, or CI output.
- **FR-010**: The registry baseline MUST be captured from the behavior shipped by Specs 001–004 before any later roadmap spec changes an invariant-bearing surface.
- **FR-011**: Conflicting attestations for one invariant MUST fail validation rather than resolve silently.

### Key Entities

- **Invariant**: Stable ID, guarantee statement, governing principle, owning assertions, verdict, and amendment history.
- **Attestation**: A spec's declaration of the invariant IDs it touches and the assertions it contributes.
- **Conformance Report**: Per-invariant verdict, evidence references, configuration coverage, and run identity.
- **Amendment Record**: Reason, principle, compatibility impact, and replacement coverage for an invariant change.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All eleven invariants carry at least one executing assertion and zero invariants are documentation-only.
- **SC-002**: The suite passes on Python 3.10–3.13 against the installed wheel with no extras, no provider configuration, and no network.
- **SC-003**: A seeded violation of each invariant fails the gate with that invariant's ID and produces no other invariant's failure.
- **SC-004**: Every spec from 005 onward carries an attestation; a change to an invariant-bearing surface without one fails the gate.
- **SC-005**: Report and CI output contain no secrets, scoped content, raw prompts, or tool payloads across the full fixture set.

## Out of Scope

Replacing feature-local test suites, proving semantic truth or real-world outcomes, gating on performance targets owned by Spec 010, or asserting guarantees for unsupported hosts, backends, or Python versions.

## Assumptions

- Specs 001–004 represent the shipped baseline behavior the registry locks in.
- Feature specs own their own assertions; this spec owns the registry, verdict semantics, and gate.
- Optional backends and extras are covered as declared configurations, not assumed.
