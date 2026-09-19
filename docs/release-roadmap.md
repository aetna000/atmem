# AtMem release roadmap

**Status**: 2.3.4b1 beta scope plus proposed future sequence; future versions are
planning targets, not delivery-date commitments.
**Working baseline**: AtMem `2.3.4b1`, OpenClaw bridge `2.3.4-beta.1`, companion pin
`atmem-atbot==0.1.0`.

AtMem is an agent-neutral, standalone encrypted evidence authority for memory, context governance and execution investigation. Every release follows [PR-001–PR-008](../specs/product-requirements.md), including default full-fidelity multimodal capture, application-only privileged plaintext and store-only reconstruction after the agent and its logs are gone. Advertise only the host, provider, capture-boundary, cryptographic and deployment profiles actually verified for that release.

## Release overview

| Proposed AtMem version | Work group | Customer value and included scope | Primary specs | Readiness boundary |
| --- | --- | --- | --- | --- |
| **2.2.6** — optional maintenance | Baseline maintenance | Stabilize already implemented 2.2 capabilities, including delegated host identity/lifecycle fixes and compatibility checks; publish accurate installation/upgrade guidance | Existing runtime; 003 T049–T053; applicable regression gates | Spec 003 host compatibility work is assigned to 2.2.6; unresolved host profiles remain explicitly blocked/unverified. No claim that the new roadmap capabilities are delivered. This maintenance release is optional and does not block 2.3 development. |
| **2.3.2** — stable standalone encrypted evidence box | M0 | Reconstruct exact host-observed text and supported multimodal agent evidence from one portable encrypted AtMem Home; govern memory/context exposure with four local roles | 020, 021, 022, 028, 029, 030; scoped 003/007 | OpenClaw is the verified installed full-fidelity host profile. Pydantic AI and LangChain/LangGraph have governed native/delegated context delivery, not the full OpenClaw multimodal capture claim. Viewer is content-free; Investigator reconstructs; Evidence Collector exports; Administrator manages the installation. |
| **2.3.4b1** — Jev benchmark lab beta | Production benchmark evidence | LoCoMo adapter, Jev reranking comparison, explicit egress and claim gates; LongMemEval/BEAM staged | New 035 benchmark track; applicable 001/003/019 contracts | Existing defaults, evidence encryption, scope, delegated authority and exact delivery remain intact. Results remain exploratory until corpus anomalies and all production gates are resolved. |
| **2.4.0** — multi-agent memory and access foundations | M1 | Agents use private and explicitly shared spaces with separate read/write/admin permissions, ownership, membership changes and provenance. Establish durable authenticated administration for supported production profiles | 006, 010, 012, 013, 015, applicable 017/019/022 consumers | Membership and credential subsystems pass their decomposed gates; no cross-space leaks, stale-grant delivery or revoked-key resurrection. Local use remains lightweight; broader enterprise/federation claims remain scoped. |
| **2.5.0** — governed provider connections | M1 | Native memory and external memory/knowledge share inspection and policy services; provider setup supports access preview, conditional approval, explicit activation and first-delivery monitoring. Complete the nine-destination workspace: Runs, Memory, Decisions, Tools and media, Audit, Policies, Tasks, Connections and Settings | 019, 022, 025, relevant 003/004/017 | Native plus one real external provider and declared authentication profiles pass. Preserve all three authority modes, exact delegated bytes and actual credential/delivery assurance. No claim of every authentication method or connector working. |
| **2.6.0** — investigation and resolution | M1 | Evidence-backed affected-work views, richer task/execution links, incident assignment and separate acknowledgment, remediation and outcome verification | Remaining applicable 007, 020, 021 and 022 | Impact follows declared dependencies; unknown outcomes stay unknown. Any executable action requires its host checkpoint, authorization, idempotency and verification prerequisites; otherwise offer inspection/manual guidance. |
| **2.7.0** — context lifecycle governance | M3 | Revocable context grants, source-exposure impact and policy simulation with explicit evidence and uncertainty | 015, 019, 023 | Revocation races and actual propagation bounds pass; simulations disclose unevaluable cases and cannot mutate live policy. Past disclosure is never described as retracted. |
| **2.8.0** — temporal memory consolidation | M4 memory intelligence | Opt-in background review identifies stale, conflicting, duplicate, expired and time-dependent memories; deterministic derivations and lifecycle boundaries are explainable, while uncertain semantic changes require review | 001, 006, 008, 015, 022, 026; applicable 019/021/023 integration | AtBot remains proposal-only and sees only authorized bounded packages. No semantic deletion or silent correction; every accepted effect has evidence, generation checks, lineage and derivative invalidation. The base path works without a model. |
| **2.9.0** — enterprise fleet operations | M3 enterprise expansion | Customer-hosted fleet policy distribution, scoped administration, supported federation/workload identity, independent evidence anchoring and verified recovery profiles | Hardened 013, 024, applicable 025 integration | Real deployment, replica, partition, credential, recovery and evidence-verification gates pass. Managed hosting remains optional. |
| **2.10.0b1** — model unlearning research preview | M4 unlearning research | Coordinate external-memory revocation, scoped behavioral suppression and evaluated post-training forget jobs for registered open-weight models with exact lineage | 015, 020, 021, 023, 024, 027 | The intended single-consumer-GPU profile uses Apache-2.0 `Qwen/Qwen2.5-0.5B-Instruct` at pinned revision `c89bee90d9f811437d9735454613c35b4a3c4dc8` and completes end to end. Results are `weight_unlearning_evaluated`, never proof of erasure; closed-source and lineage-unknown models receive only the provider/runtime assurances actually verified. No broad model-efficacy claim. |

The sequence scopes deliverables rather than requiring every task in each named spec to finish. Carry deferred work explicitly; never mark an entire spec complete from a passing release profile. The Work group column maps each release explicitly: M0–M4 are dependency/scope groupings, not a second chronological sequence. M1 is intentionally split across 2.4–2.6, the capture conformance subset of M2 lands in 2.3, and M3/M4 deliverables interleave only where the table states.

## 2.2.6 maintenance scope — delegated host compatibility

Assign [Spec 003 Phase 9](../specs/003-delegated-context-provider/tasks.md#phase-9-host-compatibility-acceptance)
(T049–T053; FR-034–FR-037, SC-013–SC-016) to **2.2.6**, ahead of the
2.3 feature work. This includes retaining attributed Storizon reports, verifying real Mem0, enforcing the
default owner gate and isolated local mapping, exercising identity role-play,
addressing supported read/exec completion-observation gaps, and publishing an
accurate compatibility matrix. The user-authorized real Mem0/dummy-data and
identity role-play substitute now passes local acceptance on latest OpenClaw
2026.9.2 and 2026.9.3. A later attributed Storizon rerun against the published
2.2.6 artifacts closes its v2 receipt and local toolful gaps for the same two
hosts and scoped isolated configuration. Live shared-channel identity remains
outside the demonstrated scope.

The shared HMAC profile and delegated v1 payload remain unchanged. Missing
`senderIsOwner` must fail closed by default; local text-only success cannot
establish shared-channel identity. Missing tool completion observations must
remain `incomplete_evidence`. Shared-channel and toolful checks are separate
gates: passing both is required for broader readiness claims. An unavailable
host boundary must be documented as blocked/unverified with the exact limitation,
not counted as a passing fix. Apply the normal regression/artifact release gates
to the final implemented changes before publication.

## Beta research release: 2.3.4b1

[Spec 031](../specs/031-mem0-head-to-head-retrieval/spec.md) and its
[plan](../specs/031-mem0-head-to-head-retrieval/plan.md) define the retrieval
work between stable 2.3.3 and the planned 2.4 foundation. Beta 2.3.4b1 ships
unchanged retrieval defaults. See the
[release notes](releases/v2.3.4b1.md) for the precise shipped subset. The initial 12-case Mem0 2.0.20 baseline
had an unmatched `limit`/`top_k` call and is preserved only as historical
evidence. The [corrected same-corpus calibration run](implementation-evidence/031/matched-v2.md)
is still too small and narrow for a general win. Native comparative preparation,
held-out comparative quality and benchmark dashboard integration remain future
work. Correctness, security, UI regression and artifact gates remain mandatory
for the stable scope; optional fusion/graph is not promoted to the default.

## Next planned foundation: 2.4.0

Build the authenticated shared/private multi-agent space and membership foundation
described in Specs 006, 010, 012, 013 and 015. Preserve 2.3.2 evidence encryption,
portable-home recovery, local roles and exact capture contracts. Do not broaden
cross-host multimodal claims until an additional real host passes the published
capture conformance profile.

## Critical prerequisites for the subsequent releases

- **2.4:** estimate and implement **012 T016–T032** membership/feedback and **013 T012–T025** durable credentials/production enforcement. Their roll-up rows are not implementation estimates. Consumer admission, retrieval, invalidation and UI tasks must pass as well. Core/shared-space tests can develop against frozen contracts; production use requires the real authenticated boundary.
- **2.5:** consume 2.4 authority contracts. The wizard cannot activate an enterprise connection on configuration-only authentication. Native/shared-memory retrieval in 2.4 may use the existing native path with compatible 019 contracts; full external provider unification and composition arrive here. Complete 003 T054–T058 so delegated providers feed the same standalone exact-evidence store across OpenClaw, Pydantic AI and LangChain/LangGraph.
- **2.6:** preserve M0's useful investigation experience while extending it. Task-state participation remains optional; lack of memory or task activation cannot block tool-failure investigation.
- **2.7–2.9:** basic membership/key revocation is already required in 2.4. These releases extend source/grant lifecycle, temporal consolidation and fleet administration; they do not postpone foundational access enforcement. Spec 026 ships temporal contracts and UI foundations earlier where listed, but scheduled consolidation is not claimed before the 2.8.0 gates.
- **2.10 preview:** consume verified revocation/impact, authenticated administration, execution evidence and model/deployment inventory from 2.7–2.9. Keep heavyweight training dependencies in separately registered workers. A memory deletion, refusal, provider acknowledgment or small-model benchmark cannot be promoted into a weight-erasure claim.

## Versioning, compatibility and publication

These are proposed additive 2.x releases. Preserve public contracts, native behavior, existing scopes, signed delegated payloads and historical evidence through declared supported upgrades. If implementation requires a genuinely incompatible public or persisted-state change, resolve migration/deprecation and reconsider a major version before committing to these numbers.

Use prerelease candidates as needed for future scope. Beta AtMem `2.3.4b1` maps
exactly to bridge `2.3.4-beta.1`. AtBot has an independent version and changes only when
its implementation/compatibility requires it; do not invent a companion version
to mirror AtMem. Every release must align actual installer constants and pins.

Merging reviewed source/specs to `main` and publishing a package are separate decisions. For each actual release: inspect the full candidate diff, run applicable Python/companion/OpenClaw/build/installed-artifact gates, write version-specific release notes with exact upgrade instructions, and tag only the reviewed clean commit. Follow repository release rules for companion-first publication when needed, package workflows and verification of GitHub/PyPI/npm outputs. A pushed tag is not proof of publication.

Store verification under the [per-feature append-only journal](implementation-evidence/README.md) and maintain [current status](current-status.md) as an evidence-linked summary. The dated implementation review remains frozen. Update this planning document when scope or ordering changes; published release notes remain the authority for what a particular version actually shipped.
