# Implementation Plan: Context Revocation, Exposure Impact and Policy Simulation

**Date**: 2026-09-09
**Status**: Planned; no implementation claim
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13; current SQLite/control evidence stores and optional declared backends; current dashboard JavaScript/CSS; optional framework/provider integrations. Reuse `atmem/lifecycle/invalidation.py`, `atmem/retrieve/cache.py`, `atmem/incidents/`, `atmem/service/application.py`. No new mandatory model dependency or frontend framework. All new paths below are proposed until implemented.

## Foundation prerequisites

019 package/grant contracts, 020 observed exposures, 021 findings, baseline 015 invalidation and 012 services. Basic incident investigation must ship independently of this later milestone.

## Architecture and file ownership

- **FR-001** → `atmem/context/lifecycle/revocation.py`: Extend Spec 019 delivery grants with scoped source/provider/policy revocation generations; revalidate at the last supported pre-dispatch boundary and document the remaining dispatch race and propagation bound.
- **FR-002** → `atmem/lifecycle/invalidation.py`: Invalidate controlled package caches and derivative consumers through Spec 015; distinguish local completion, external requested/acknowledged/verified cleanup and unknown/unmanaged copies.
- **FR-003** → `atmem/context/lifecycle/lineage.py`: Maintain provider-qualified source-version to package to exposure to execution links; direct exposure and explicitly supplied derivative lineage remain different relationship types with coverage.
- **FR-004** → `atmem/context/lifecycle/impact.py`: Report authorized historical executions exposed to a revoked/corrected source and associated declared dependent work without claiming source causation or retracting past disclosure.
- **FR-005** → `atmem/context/lifecycle/simulation.py`: Simulate a versioned candidate policy over retained authorized attributes or explicitly authorized source re-fetch; do not reconstruct raw content from hashes. Missing or expired inputs are unevaluable and reported in the denominator.
- **FR-006** → `atmem/context/lifecycle/simulation.py`: Simulation MUST NOT activate policies, inject context, mutate provider memory or execute tools. Re-fetch is an explicit egress/read operation with a receipt and remains optional.
- **FR-007** → `atmem/context/lifecycle/comparison.py`: Compare current and candidate allow/withhold/routing outcomes, counts and reason changes; redact inaccessible data and distinguish simulated alternatives from observed historical behavior.
- **FR-008** → `atmem/context/lifecycle/activation.py`: Require explicit authorized activation after preview with policy-generation preconditions and rollback to a recorded prior policy; older cached decisions cannot silently satisfy the new policy.
- **FR-009** → `atmem/context/lifecycle/notifications.py`: Authenticate, scope and deduplicate provider revocation notifications; reject replay/conflicting versions and record sequence gaps or unavailable source versions without assuming cleanup.
- **FR-010** → `atmem/context/lifecycle/retention.py`: Apply retention/deletion to source-exposure indexes and simulations; document that historical model disclosure and unmanaged backups cannot be undone. Unknown-source lineage remains unknown.

Shared router edits go through Spec 012; shared shell edits through Spec 022; canonical schema allocations through Spec 010; existing flight-store schema evolution through its current registry coordinated by Spec 020. Preserve existing task authority and reuse Spec 007 identities. Do not allocate duplicate public resource schemas in two feature packages.

## Contracts and persistence

Freeze required fields, optionality, authority provenance, reason-code enums, state transitions, time units, bounds, preconditions and schema negotiation before implementing consumers. Use independently authored golden vectors under `tests/fixtures/product/023/`. Public transport descriptions extend `docs/contracts/atmem-api-v1.openapi.yaml` through Spec 012; closed incompatible envelopes receive separately versioned schemas under `atmem/schemas/`. Clients project the same service decisions.

Persist only state requiring durable authority/evidence or rebuildable projections. Transactional mutations include scoped idempotency and expected generation; evidence and resolution append rather than overwrite. Allocate actual migration IDs at implementation after inspecting the current registries. Upgrade old rows without invented links, and test restart, rollback compatibility/forward recovery and retention. Read-only simulations and projections cannot write canonical memory.

## Execution sequence

1. Freeze contracts and failure vectors; resolve ownership with prerequisite specs.
2. Implement FR-001–FR-010 in requirement order, sharing baseline services. Commit contract/persistence primitives before adapter or UI consumers.
3. Exercise SC-001–SC-004 through public boundaries, then applicable migration/privacy and installed-host gates.
4. Record exact versions, commands, measurements, gaps and activation/rollback guidance; enable only supported capabilities.

## Verification strategy

Primary boundary suite: `tests/test_context_lifecycle.py`. Add fixture-level golden inputs and assertions per requirement before implementation. Cross-interface golden tests verify scope, IDs, reason codes and state parity. A fake provider/host supports deterministic tests but does not establish live compatibility. Browser tasks require actual keyboard, viewport and navigation checks; human timing remains a separate controlled protocol.

- **SC-001**: Revocation between retrieval and dispatch prevents new delivery in every declared enforcing adapter fixture; post-dispatch revocation records the actual earlier exposure without falsification.
- **SC-002**: Impact fixtures return exactly authorized observed source-version exposures; unknown derivative lineage produces explicit incomplete coverage and no causal assertion.
- **SC-003**: Simulation leaves live policy/memory/tool state unchanged, reports all unevaluable cases and performs zero unapproved source egress.
- **SC-004**: Measure and publish notification-to-enforcement p95 and maximum for 1,000 revocations; initial connected-profile target is <=5 seconds, with expired/disconnected grant behavior separately exercised.

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
