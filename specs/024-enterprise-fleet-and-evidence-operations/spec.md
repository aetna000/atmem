# Feature Specification: Enterprise Fleet and Evidence Operations

**Feature directory**: `specs/024-enterprise-fleet-and-evidence-operations`
**Created**: 2026-09-09
**Status**: Specified; not implemented
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

An enterprise operates AtMem in its own network, distributes policies to agent runtimes, investigates failures and independently verifies retained evidence during a control-plane outage.

Product moment: **Operate the same product across deployments**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

An enterprise operates AtMem in its own network, distributes policies to agent runtimes, investigates failures and independently verifies retained evidence during a control-plane outage.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

## Functional requirements

- **FR-001**: Support explicit local/embedded, sidecar, customer VPC/on-premises and disconnected deployment profiles with a tested capability matrix; no cloud account is required for local memory or investigation.
- **FR-002**: Separate local policy/enforcement/evidence execution from optional fleet administration. Fleet outages follow a declared unexpired cached-policy or withhold rule; expired policy cannot silently retain enforcement authority.
- **FR-003**: Integrate enterprise human federation and workload identity through standard authenticated boundaries, least-privilege roles and scope mappings; principal identity never comes from model arguments. Persist key rotation/revocation through restart and replicas.
- **FR-004**: Distribute signed versioned policy/provider registrations with authenticity, anti-rollback generation, explicit activation, bounded expiry and observed rollout status. A node's last acknowledgment is not proof of current online enforcement.
- **FR-005**: Keep content and detailed evidence local by default; aggregate only approved scoped metadata with customer-controlled retention, encryption-key references and egress policy.
- **FR-006**: Export independently verifiable evidence bundles with hash-chain identities and periodically signed checkpoints anchored in customer-controlled append-only storage. Document trust roots and that a local chain alone cannot detect a privileged complete rewrite.
- **FR-007**: Provide scoped incident assignment, administrative audit and integration hooks through Spec 012 services; external notification destinations are explicitly configured and payload-minimized.
- **FR-008**: Exercise backup/restore, tenant deletion, partial rollout, queue replay, disk exhaustion, policy expiry and credential revocation in actual deployment paths; publish measured RPO/RTO and coverage before production claims.
- **FR-009**: Keep transport profiles, SDK compatibility, migration order and rollback documented; test supported Python/host/package artifacts and license optional dependencies before advertising them.
- **FR-010**: Expose fleet availability, enforcement freshness and evidence completeness as distinct metrics. Define quotas/backpressure behavior that cannot silently drop acknowledged evidence or bypass authorization.

## Key entities

- **DeploymentProfile**: Local/sidecar/customer-hosted/disconnected mode, supported capabilities, policy-expiry behavior, retention, quotas and recovery targets.
- **WorkloadPrincipal**: Authenticated service/user/tenant scope, role mapping, credential reference/expiry/revocation generation and identity issuer.
- **SignedPolicyBundle**: Bundle ID/generation, policy and provider-registration versions, scope, signing-key identity, expiry and activation/rollback references.
- **FleetNodeStatus**: Node/deployment identity, last acknowledged bundle, observed enforcement freshness, connectivity, evidence coverage and bounded health.
- **EvidenceCheckpoint**: Chain ID/range/head digest, signature/key identity, anchor destination receipt and independent verification status.
- **RecoveryDrill**: Dataset/deployment/schema versions, backup and restore digests, recovery point/time measurements, isolation/deletion checks and pass/fail limits.

## Success criteria

- **SC-001**: A customer-hosted disconnected test completes memory capture and incident investigation without hosted services; expired policy withholds protected delivery as configured.
- **SC-002**: Across restart and two replicas, revoked identities cannot submit events, access incidents or activate policy; cross-tenant API/job/export/metrics tests reveal zero forbidden data.
- **SC-003**: An offline verifier detects bundle mutation and checkpoint inconsistency using customer trust roots; unavailable external anchoring is visibly unproven rather than green.
- **SC-004**: A published reference restore drill demonstrates RPO <=60 seconds and RTO <=30 minutes for its declared dataset/deployment; failures remain failed targets and are not generalized to untested scale.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

Baseline 010/012/013/015/018 and their production hardening gaps; 019–023 resource schemas as relevant. Fleet administration is optional and never a prerequisite for local milestones.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links. No default raw transcript, chain-of-thought or secret retention. Evidence metadata and hashes still require access control and retention.

## Out of scope

Operating a managed SaaS business as part of this implementation, multi-region consensus, certification claims without assessment, or mandatory cloud telemetry.

## Invariant Attestation

Touches INV-001, INV-002, INV-004, INV-007, INV-008, INV-010, INV-011 through `spec024.scope`, `spec024.evidence`, `spec024.compatibility` and `spec024.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.
