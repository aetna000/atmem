# AtMem release roadmap

**Status**: Proposed release sequence; versions below are planning targets, not published releases or delivery-date commitments.
**Planning baseline**: Source commit `c064d869b7697d29adae6363998e31422afa7a16`, AtMem `2.2.6b11`, OpenClaw bridge `2.2.6-beta.11`, companion pin `atmem-atbot==0.1.0a6`. These identify inspected source metadata, not verified package availability.

AtMem is an agent-neutral product for memory, context governance and execution investigation. Every release follows [PR-001–PR-006](../specs/product-requirements.md): multiple agents, explicit private/shared access, attributable provider decisions, readable feedback and meaningful timestamps. Advertise only the host, provider and deployment profiles actually verified for that release.

## Release overview

| Proposed AtMem version | Customer value and included scope | Primary specs | Readiness boundary |
| --- | --- | --- | --- |
| **2.2.6** — optional maintenance | Stabilize already implemented 2.2 capabilities, including delegated host identity/lifecycle fixes and compatibility checks; publish accurate installation/upgrade guidance | Existing runtime; 003 T049–T053; applicable regression gates | Spec 003 host compatibility work is assigned to 2.2.6; unresolved host profiles remain explicitly blocked/unverified. No claim that the new roadmap capabilities are delivered. This maintenance release is optional and does not block 2.3 development. |
| **2.3.0b1** — investigation preview | Find an observed failure or missing event across an agent run, with exact evidence, agent identity, readable explanations and timestamps, in the existing dashboard | 007 identity subset, 020 capture, minimal 021 findings; M0 | Initial installed host profile plus host-neutral core tests; durable capture/replay, isolation, compatibility and technical UI gates. No provider migration or new memory system required. |
| **2.3.0** — investigation and host extensibility | Stabilize investigation, verify additional host profiles and publish the runnable Host Conformance Kit, coverage manifests and third-party listing process | Scoped 011, 020 and 021; M0 stabilization plus M2 capture-profile deliverables | At least two distinct real host profiles for cross-framework investigation claims; independently installable kit and explicit observed/enforced/missing coverage. Full shared-memory conformance follows in 2.4. |
| **2.4.0** — multi-agent memory and access foundations | Agents use private and explicitly shared spaces with separate read/write/admin permissions, ownership, membership changes and provenance. Establish durable authenticated administration for supported production profiles | 006, 010, 012, 013, 015, applicable 017/019/022 consumers | Membership and credential subsystems pass their decomposed gates; no cross-space leaks, stale-grant delivery or revoked-key resurrection. Local use remains lightweight; broader enterprise/federation claims remain scoped. |
| **2.5.0** — governed provider connections | Native memory and external memory/knowledge share inspection and policy services; provider setup supports access preview, conditional approval, explicit activation and first-delivery monitoring. Deliver the unified seven-section workspace | 019, 022, 025, relevant 003/004/017; M1 context and UI | Native plus one real external provider and declared authentication profiles pass. Preserve all three authority modes, exact delegated bytes and actual credential/delivery assurance. No claim of every authentication method or connector working. |
| **2.6.0** — investigation and resolution | Evidence-backed affected-work views, richer task/execution links, incident assignment and separate acknowledgment, remediation and outcome verification | Remaining applicable 007, 020, 021 and 022; M1 investigation expansion | Impact follows declared dependencies; unknown outcomes stay unknown. Any executable action requires its host checkpoint, authorization, idempotency and verification prerequisites; otherwise offer inspection/manual guidance. |
| **2.7.0** — context lifecycle governance | Revocable context grants, source-exposure impact and policy simulation with explicit evidence and uncertainty | 015, 019, 023 | Revocation races and actual propagation bounds pass; simulations disclose unevaluable cases and cannot mutate live policy. Past disclosure is never described as retracted. |
| **2.8.0** — enterprise fleet operations | Customer-hosted fleet policy distribution, scoped administration, supported federation/workload identity, independent evidence anchoring and verified recovery profiles | Hardened 013, 024, applicable 025 integration; M3 | Real deployment, replica, partition, credential, recovery and evidence-verification gates pass. Managed hosting remains optional. |

The sequence scopes deliverables rather than requiring every task in each named spec to finish. Carry deferred work explicitly; never mark an entire spec complete from a passing release profile. M1 is intentionally split across 2.4–2.6 so memory authority, provider onboarding and incident resolution each reach users separately. The capture conformance subset of M2 lands earlier in 2.3; milestone labels are work groups, not a mandatory numeric delivery order.

## 2.2.6 maintenance scope — delegated host compatibility

Assign [Spec 003 Phase 9](../specs/003-delegated-context-provider/tasks.md#phase-9-host-compatibility-acceptance)
(T049–T053; FR-034–FR-037, SC-013–SC-016) to **2.2.6**, ahead of the
2.3 feature work. This includes retaining attributed Storizon reports, verifying real Mem0, enforcing the
default owner gate and isolated local mapping, exercising identity role-play,
addressing supported read/exec completion-observation gaps, and publishing an
accurate compatibility matrix. The user-authorized real Mem0/dummy-data and
identity role-play substitute now passes local acceptance on latest OpenClaw
2026.9.2 and 2026.9.3. Live shared-channel identity and independent Storizon
verification remain outside that demonstrated scope; publication is separate.

The shared HMAC profile and delegated v1 payload remain unchanged. Missing
`senderIsOwner` must fail closed by default; local text-only success cannot
establish shared-channel identity. Missing tool completion observations must
remain `incomplete_evidence`. Shared-channel and toolful checks are separate
gates: passing both is required for broader readiness claims. An unavailable
host boundary must be documented as blocked/unverified with the exact limitation,
not counted as a passing fix. Apply the normal regression/artifact release gates
to the final implemented changes before publication.

## Immediate next release: 2.3.0b1

Implement [M0](../specs/m0-investigation-preview.md) before publishing the next feature version:

1. **007 T110** — shared authenticated execution identity without requiring task state.
2. **020 T018–T021** — durable capture, scope-filtered projection, coverage and installed-host evidence.
3. **021 T018–T019** — deterministic findings and exact event pivots in existing Activity/Evidence views.
4. **020 T022 + 021 T020** — complete independent technical release gates.

OpenClaw is the initial installed profile because that is the scoped M0 integration; core contracts and tests must run without it. Record other integrations as unvalidated until their own evidence passes. Private/shared-memory administration, the new shell, external-provider setup and fleet are outside this preview.

**021 T024** owns the independent [two-cohort usability protocol](../specs/usability-protocol.md). It gates advertised measured usability, not the engineering preview. Later beta candidates (`2.3.0b2`, etc.) address observed failures and stabilize the chosen scope before `2.3.0`; they do not automatically accumulate the 2.4–2.8 backlog.

## Critical prerequisites for the subsequent releases

- **2.4:** estimate and implement **012 T016–T032** membership/feedback and **013 T012–T025** durable credentials/production enforcement. Their roll-up rows are not implementation estimates. Consumer admission, retrieval, invalidation and UI tasks must pass as well. Core/shared-space tests can develop against frozen contracts; production use requires the real authenticated boundary.
- **2.5:** consume 2.4 authority contracts. The wizard cannot activate an enterprise connection on configuration-only authentication. Native/shared-memory retrieval in 2.4 may use the existing native path with compatible 019 contracts; full external provider unification and composition arrive here.
- **2.6:** preserve M0's useful investigation experience while extending it. Task-state participation remains optional; lack of memory or task activation cannot block tool-failure investigation.
- **2.7–2.8:** basic membership/key revocation is already required in 2.4. These releases extend source/grant lifecycle and fleet administration; they do not postpone foundational access enforcement.

## Versioning, compatibility and publication

These are proposed additive 2.x releases. Preserve public contracts, native behavior, existing scopes, signed delegated payloads and historical evidence through declared supported upgrades. If implementation requires a genuinely incompatible public or persisted-state change, resolve migration/deprecation and reconsider a major version before committing to these numbers.

Use prerelease candidates as needed for each scope. Python `2.3.0b1` maps to an aligned bridge version such as `2.3.0-beta.1`; stable `2.3.0` maps to `2.3.0`. AtBot has an independent version and changes only when its implementation/compatibility requires it; do not invent a companion version to mirror AtMem. Every release must align the actual installer constants and compatibility pins.

Merging reviewed source/specs to `main` and publishing a package are separate decisions. For each actual release: inspect the full candidate diff, run applicable Python/companion/OpenClaw/build/installed-artifact gates, write version-specific release notes with exact upgrade instructions, and tag only the reviewed clean commit. Follow repository release rules for companion-first publication when needed, package workflows and verification of GitHub/PyPI/npm outputs. A pushed tag is not proof of publication.

Store verification under the [per-feature append-only journal](implementation-evidence/README.md) and maintain [current status](current-status.md) as an evidence-linked summary. The dated implementation review remains frozen. Update this planning document when scope or ordering changes; published release notes remain the authority for what a particular version actually shipped.

## 2.2.7b1 beta

The first 2.2.7 beta packages the completed dashboard/evidence and selective
context slices in Specs 020 and 022 plus the scoped Spec 003 fixes. AtBot moves
to stable 0.1.0 independently. This does not complete the broader roadmap.
