# Feature Specification: Context Revocation, Exposure Impact and Policy Simulation

**Feature directory**: `specs/023-context-revocation-impact-and-simulation`
**Created**: 2026-09-09
**Status**: Specified; not implemented
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

A policy document is revoked. Future governed deliveries are blocked, affected past exposures are listed, and an operator previews a replacement policy without changing production.

Product moment: **Before delivery and after source/policy changes**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

A policy document is revoked. Future governed deliveries are blocked, affected past exposures are listed, and an operator previews a replacement policy without changing production.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

## Functional requirements

- **FR-001**: Extend Spec 019 delivery grants with scoped source/provider/policy revocation generations; revalidate at the last supported pre-dispatch boundary and document the remaining dispatch race and propagation bound.
- **FR-002**: Invalidate controlled package caches and derivative consumers through Spec 015; distinguish local completion, external requested/acknowledged/verified cleanup and unknown/unmanaged copies.
- **FR-003**: Maintain provider-qualified source-version to package to exposure to execution links; direct exposure and explicitly supplied derivative lineage remain different relationship types with coverage.
- **FR-004**: Report authorized historical executions exposed to a revoked/corrected source and associated declared dependent work without claiming source causation or retracting past disclosure.
- **FR-005**: Simulate a versioned candidate policy over retained authorized attributes or explicitly authorized source re-fetch; do not reconstruct raw content from hashes. Missing or expired inputs are unevaluable and reported in the denominator.
- **FR-006**: Simulation MUST NOT activate policies, inject context, mutate provider memory or execute tools. Re-fetch is an explicit egress/read operation with a receipt and remains optional.
- **FR-007**: Compare current and candidate allow/withhold/routing outcomes, counts and reason changes; redact inaccessible data and distinguish simulated alternatives from observed historical behavior.
- **FR-008**: Require explicit authorized activation after preview with policy-generation preconditions and rollback to a recorded prior policy; older cached decisions cannot silently satisfy the new policy.
- **FR-009**: Authenticate, scope and deduplicate provider revocation notifications; reject replay/conflicting versions and record sequence gaps or unavailable source versions without assuming cleanup.
- **FR-010**: Apply retention/deletion to source-exposure indexes and simulations; document that historical model disclosure and unmanaged backups cannot be undone. Unknown-source lineage remains unknown.

## Key entities

- **RevocationGeneration**: Scoped source/provider/policy ID, monotonically increasing generation, effective time, issuer and authenticated notification identity.
- **SourceExposureLink**: Provider/source/version to package digest to exposure to execution references, link type and provenance/coverage.
- **CleanupAcknowledgment**: Controlled/external consumer, requested/acknowledged/verified/unknown state, scope, generation and verification receipt.
- **ImpactReport**: Revoked version, authorized observed exposures, declared dependent work, unlinked derivatives, coverage and evaluation generation.
- **PolicySimulation**: Candidate/current policy versions, authorized input snapshot references, evaluable/unevaluable counts, per-request verdict differences and no-activation marker.

## Success criteria

- **SC-001**: Revocation between retrieval and dispatch prevents new delivery in every declared enforcing adapter fixture; post-dispatch revocation records the actual earlier exposure without falsification.
- **SC-002**: Impact fixtures return exactly authorized observed source-version exposures; unknown derivative lineage produces explicit incomplete coverage and no causal assertion.
- **SC-003**: Simulation leaves live policy/memory/tool state unchanged, reports all unevaluable cases and performs zero unapproved source egress.
- **SC-004**: Measure and publish notification-to-enforcement p95 and maximum for 1,000 revocations; initial connected-profile target is <=5 seconds, with expired/disconnected grant behavior separately exercised.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

019 package/grant contracts, 020 observed exposures, 021 findings, baseline 015 invalidation and 012 services. Basic incident investigation must ship independently of this later milestone.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links. No default raw transcript, chain-of-thought or secret retention. Evidence metadata and hashes still require access control and retention.

## Out of scope

Guaranteed erasure from third-party models, reconstructing unavailable historical content, general causal inference, or silently replaying historical tools.

## Invariant Attestation

Touches INV-002, INV-003, INV-005, INV-007, INV-008, INV-010, INV-011 through `spec023.scope`, `spec023.evidence`, `spec023.compatibility` and `spec023.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.
