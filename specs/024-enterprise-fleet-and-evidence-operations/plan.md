# Implementation Plan: Enterprise Fleet and Evidence Operations

**Date**: 2026-09-09
**Status**: Planned; no implementation claim
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13; current SQLite/control evidence stores and optional declared backends; current dashboard JavaScript/CSS; optional framework/provider integrations. Reuse `atmem/server/`, `atmem/service/`, `atmem/invariants/`, `atmem/control/store.py`. No new mandatory model dependency or frontend framework. All new paths below are proposed until implemented.

## Foundation prerequisites

Baseline 010/012/013/015/018 and their production hardening gaps; 019–023 resource schemas as relevant. Fleet administration is optional and never a prerequisite for local milestones.

## Architecture and file ownership

- **FR-001** → `atmem/fleet/profiles.py`: Support explicit local/embedded, sidecar, customer VPC/on-premises and disconnected deployment profiles with a tested capability matrix; no cloud account is required for local memory or investigation.
- **FR-002** → `atmem/fleet/runtime.py`: Separate local policy/enforcement/evidence execution from optional fleet administration. Fleet outages follow a declared unexpired cached-policy or withhold rule; expired policy cannot silently retain enforcement authority.
- **FR-003** → `atmem/server/auth.py`: Integrate enterprise human federation and workload identity through standard authenticated boundaries, least-privilege roles and scope mappings; principal identity never comes from model arguments. Persist key rotation/revocation through restart and replicas.
- **FR-004** → `atmem/fleet/policies.py`: Distribute signed versioned policy/provider registrations with authenticity, anti-rollback generation, explicit activation, bounded expiry and observed rollout status. A node's last acknowledgment is not proof of current online enforcement.
- **FR-005** → `atmem/fleet/egress.py`: Keep content and detailed evidence local by default; aggregate only approved scoped metadata with customer-controlled retention, encryption-key references and egress policy.
- **FR-006** → `atmem/fleet/checkpoints.py`: Export independently verifiable evidence bundles with hash-chain identities and periodically signed checkpoints anchored in customer-controlled append-only storage. Document trust roots and that a local chain alone cannot detect a privileged complete rewrite.
- **FR-007** → `atmem/service/fleet.py`: Provide scoped incident assignment, administrative audit and integration hooks through Spec 012 services; external notification destinations are explicitly configured and payload-minimized.
- **FR-008** → `atmem/server/recovery.py`: Exercise backup/restore, tenant deletion, partial rollout, queue replay, disk exhaustion, policy expiry and credential revocation in actual deployment paths; publish measured RPO/RTO and coverage before production claims.
- **FR-009** → `docs/production-service.md`: Keep transport profiles, SDK compatibility, migration order and rollback documented; test supported Python/host/package artifacts and license optional dependencies before advertising them.
- **FR-010** → `atmem/fleet/health.py`: Expose fleet availability, enforcement freshness and evidence completeness as distinct metrics. Define quotas/backpressure behavior that cannot silently drop acknowledged evidence or bypass authorization.

Shared router edits go through Spec 012; shared shell edits through Spec 022; canonical schema allocations through Spec 010; existing flight-store schema evolution through its current registry coordinated by Spec 020. Preserve existing task authority and reuse Spec 007 identities. Do not allocate duplicate public resource schemas in two feature packages.

## Contracts and persistence

Freeze required fields, optionality, authority provenance, reason-code enums, state transitions, time units, bounds, preconditions and schema negotiation before implementing consumers. Use independently authored golden vectors under `tests/fixtures/product/024/`. Public transport descriptions extend `docs/contracts/atmem-api-v1.openapi.yaml` through Spec 012; closed incompatible envelopes receive separately versioned schemas under `atmem/schemas/`. Clients project the same service decisions.

Persist only state requiring durable authority/evidence or rebuildable projections. Transactional mutations include scoped idempotency and expected generation; evidence and resolution append rather than overwrite. Allocate actual migration IDs at implementation after inspecting the current registries. Upgrade old rows without invented links, and test restart, rollback compatibility/forward recovery and retention. Read-only simulations and projections cannot write canonical memory.

## Execution sequence

1. Freeze contracts and failure vectors; resolve ownership with prerequisite specs.
2. Implement FR-001–FR-010 in requirement order, sharing baseline services. Commit contract/persistence primitives before adapter or UI consumers.
3. Exercise SC-001–SC-004 through public boundaries, then applicable migration/privacy and installed-host gates.
4. Record exact versions, commands, measurements, gaps and activation/rollback guidance; enable only supported capabilities.

## Verification strategy

Primary boundary suite: `tests/server/test_fleet_operations.py`. Add fixture-level golden inputs and assertions per requirement before implementation. Cross-interface golden tests verify scope, IDs, reason codes and state parity. A fake provider/host supports deterministic tests but does not establish live compatibility. Browser tasks require actual keyboard, viewport and navigation checks; human timing remains a separate controlled protocol.

- **SC-001**: A customer-hosted disconnected test completes memory capture and incident investigation without hosted services; expired policy withholds protected delivery as configured.
- **SC-002**: Across restart and two replicas, revoked identities cannot submit events, access incidents or activate policy; cross-tenant API/job/export/metrics tests reveal zero forbidden data.
- **SC-003**: An offline verifier detects bundle mutation and checkpoint inconsistency using customer trust roots; unavailable external anchoring is visibly unproven rather than green.
- **SC-004**: A published reference restore drill demonstrates RPO <=60 seconds and RTO <=30 minutes for its declared dataset/deployment; failures remain failed targets and are not generalized to untested scale.

## Constitution check

| Principle | Planned enforcement |
| --- | --- |
| I — Authority before intelligence | Existing canonical admission remains exclusive; external proposals are checked; trusted delegation stays explicitly named. |
| II — Provenance and exact evidence | Stable scoped references and digests; observed, inferred and independently verified are distinct. |
| III — Safe defaults and reversibility | Non-influencing initial state, explicit activation, bounded failure and no silent replay. |
| IV — Scope, privacy and deletion | Authorize joins/actions/exports; retain minimum evidence and verify controlled derivative deletion. |
| V — Host neutrality | Extend shared contracts and service; preserve host checkpoints, tools and histories. |
| VI — Executable claims | Boundary and installed-artifact evidence required; planned tests are not proofs. |
| VII — Local operation and explicit egress | No required hosted model, no unapproved provider query, optional extras and deterministic explanation. |

No constitutional amendment is proposed. The separately named trusted-delegation exception remains governed by Principle VII and existing Spec 003; it does not transfer canonical native-memory authority.

## Rollout and rollback

Ship contracts and non-influencing inspection first. Negotiate capability per deployed adapter/configuration, validate the milestone fixtures, then enable supported influence or actions explicitly. Preserve legacy wire/CLI paths, add redirects where applicable and keep old evidence inspectable. Rollback stops new feature actions and preserves audit; it does not undo prior model disclosure or external effects.
