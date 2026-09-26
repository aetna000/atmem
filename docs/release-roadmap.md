# AtMem release roadmap

**Status**: 2.3.7 stable release line; 2.3.8b4/0.1.4b2 is the current beta
release candidate. Future versions remain planning targets.
**Release baseline**: AtMem `2.3.7`, OpenClaw bridge `2.3.7`, companion pins
`atmem-atbot==0.1.0` and `atflows==0.1.3`. Publication status is recorded by
the matching GitHub release and registry artifacts, not this roadmap alone.

**Next planned maintenance release:** AtMem/bridge `2.3.8`, including official
MCP Registry registration ([issue #8](https://github.com/aetna000/atmem/issues/8))
and coordinated AtFlows **0.1.4** secret redaction
([AtFlows #6](https://github.com/aetna000/atflows/issues/6)).
AtMem `2.3.7` and AtFlows `0.1.3` are the stable baseline. Preserve their opt-in continuity
behavior and benchmark provenance; held-out qualification stays open. Companion
versions change only when their implementation or compatibility requires it.
This roadmap update schedules work; it does not authorize publication.

AtMem is an agent-neutral, standalone encrypted evidence authority for memory, context governance and execution investigation. Every release follows [PR-001–PR-008](../specs/product-requirements.md), including default full-fidelity multimodal capture, application-only privileged plaintext and store-only reconstruction after the agent and its logs are gone. Advertise only the host, provider, capture-boundary, cryptographic and deployment profiles actually verified for that release.

## Release overview

### Planned host integration: Hermes and DolphinBench qualification

Planned 2026-09-26 under [Spec 037](../specs/037-hermes-integration/spec.md).
Deliver a reusable Hermes memory provider, explicit setup/activation/restore,
scoped governed recall and truthful dashboard coverage before any benchmark run.
Then use the installed integration through an inert DolphinBench driver: no-cost
checks, a separately budget-approved pilot, and complete 600-task qualification
with matched configurations and retained cost/latency/action evidence.

**Beta target: AtMem `2.3.8b4`**, selected 2026-09-27 for the opt-in Hermes
integration. The release note is the authority for this beta's shipped subset;
scoped activation remains a follow-up gate. Finish packaged provider discovery,
status/help and installed fresh/upgrade tests; pass existing adapter, security,
build and documentation gates before tagging.
The core provider alone is not a user-installable beta. Keep AtBot and AtFlows
pins unchanged unless their separately tested changes are included. Align the
OpenClaw bridge's matching prerelease metadata during release preparation.

Benchmark accuracy is not a prerequisite for a usable integration beta, and no
benchmark win or leaderboard placement may be claimed without completed runs.
No leaderboard result is currently claimed. This beta does
not displace the 2.3.8 MCP Registry/AtFlows redaction commitments or existing
continuity qualification gates. Hermes memory support does not imply whole-agent
capture or restart safety. Website docs and any submission need their normal
review/publication approvals; planning authorizes no paid calls or deployment.

### 2.3.8 companion security scope: AtFlows 0.1.4

Scheduled 2026-09-26: fix secret retention in AtFlows telemetry before storage,
logging and export. AtFlows owns the implementation and its bounded Spec Kit
feature; [AtFlows #6](https://github.com/aetna000/atflows/issues/6) records the
reproduction, coverage and acceptance gates. Preserve original provider requests
and responses, continuity accounting and existing authentication behavior.

Require fake-secret regression tests, installed fresh/upgrade checks, explicit
legacy-data handling and honest detection limits. Publish and verify AtFlows
0.1.4b2 on PyPI before merging AtMem's exact companion pin. Then verify the paired
AtMem installation/upgrade, update both release notes and the website guides.
Do not silently clean historical databases or claim an upgrade removes secrets
already present in backups/exports. Current runtime pins stay unchanged until
the new artifact passes its release gates.

### 2.3.8 maintenance scope: official MCP Registry registration

Scheduled 2026-09-26 for [issue #8](https://github.com/aetna000/atmem/issues/8).
Make the existing local stdio memory server discoverable as
`io.github.aetna000/atmem`, without changing its authority or runtime defaults.
This bounded distribution task accompanies, rather than replaces, ongoing
continuity qualification.

- [ ] Add the `mcp-name` ownership marker to the README included in the PyPI description.
- [ ] Add `server.json` using the official schema verified during implementation, with exact AtMem `2.3.8` metadata, PyPI identifier `atmem` and stdio transport.
- [ ] Represent `atmem mcp` and its database/subject configuration; do not expose operator-only MCP to agents.
- [ ] Check version alignment across registry metadata, package metadata and the built/published artifact. Keep future release checks aligned too.
- [ ] Test initialization and tool discovery over stdio from a clean installed artifact, and pass `mcp-publisher validate server.json`.
- [ ] Document installation, discovery and the distinct canonical-memory, control-plane and operator-only MCP boundaries. Verify and describe the registry's current stability status rather than assuming it.
- [ ] Run the normal compatibility, security, install/upgrade and release gates. Publish PyPI first, then authenticate as `aetna000` and publish matching registry metadata.
- [ ] Verify the exact server/version and launch configuration through the registry API and search UI; retain validation/publication evidence before closing #8.
- [ ] Refresh AtMem.ai documentation through its owner-reviewed main-only publication process.

Registry listing is not full Agent Black Box observation, automatic continuity,
or endorsement by an MCP client. Host observation still requires a supported
adapter. If registry publication is blocked, report package publication and
registry registration separately and leave #8 open.

### Immediate priority: agent continuity qualification

Priority updated 2026-09-25: [Benchmarking 002](../specs/benchmarking/002-agent-continuity/spec.md)
and AtFlows Spec 010 take precedence over starting new 2.4.0 Memory Health
features. The experimental baseline is AtMem 2.3.7b2 and AtFlows 0.1.2;
these historical artifact versions are retained for reproducibility.

Corrected delivery order: product contracts; AtMem progress/receipt authority and
shipped host recovery integration; user setup/status; AtFlows recovery/cost views;
installed acceptance without benchmark code; inert test rig; four-arm qualification
and held-out evaluation. The rig must not supply recovery or feature compensation.
See [the correction](../specs/benchmarking/002-agent-continuity/product-first-correction.md).
Keep historical artifacts/results unchanged. Product work is approved; every
milestone requires read-only Claude review, corrective tests and compatibility
gates. No more paid comparisons before installed product acceptance.

No release is authorized by this track. Select a beta version for approved product
work only after product/artifact gates; stable promotion requires paired reruns and
existing compatibility, security, documentation and installed-artifact gates.
The numbered capability targets below remain proposals, not execution priority.

| Proposed AtMem version | Work group | Customer value and included scope | Primary specs | Readiness boundary |
| --- | --- | --- | --- | --- |
| **2.2.6** — optional maintenance | Baseline maintenance | Stabilize already implemented 2.2 capabilities, including delegated host identity/lifecycle fixes and compatibility checks; publish accurate installation/upgrade guidance | Existing runtime; 003 T049–T053; applicable regression gates | Spec 003 host compatibility work is assigned to 2.2.6; unresolved host profiles remain explicitly blocked/unverified. No claim that the new roadmap capabilities are delivered. This maintenance release is optional and does not block 2.3 development. |
| **2.3.2** — stable standalone encrypted evidence box | M0 | Reconstruct exact host-observed text and supported multimodal agent evidence from one portable encrypted AtMem Home; govern memory/context exposure with four local roles | 020, 021, 022, 028, 029, 030; scoped 003/007 | OpenClaw is the verified installed full-fidelity host profile. Pydantic AI and LangChain/LangGraph have governed native/delegated context delivery, not the full OpenClaw multimodal capture claim. Viewer is content-free; Investigator reconstructs; Evidence Collector exports; Administrator manages the installation. |
| **2.3.4b1** — Jev benchmark lab beta | Production benchmark evidence | LoCoMo adapter, Jev reranking comparison, explicit egress and claim gates; LongMemEval/BEAM staged | New 035 benchmark track; applicable 001/003/019 contracts | Existing defaults, evidence encryption, scope, delegated authority and exact delivery remain intact. Results remain exploratory until corpus anomalies and all production gates are resolved. |
| **2.3.4b2** — AtFlows-installed review-lead beta | M4 preparation | AtMem installs the pinned AtFlows Python package by default; an explicitly started AtFlows instance can supply exact session-linked trace-error leads for a read-only local evidence review report. The versioned report can feed the 2.4.0 Memory Health queue after that queue exists | 020/028 evidence and access boundaries; future 026 consumer | Source candidate, not published. Installed AtFlows 0.1b6 handoff passes the local smoke gate. No automatic server start, shared login, Memory Health queue, automatic admission, raw-trace import, inferred run link or causal claim. AtMem works without a running AtFlows server. |
| **2.3.4** — stable follow-up | Beta stabilization | Preserve verified retrieval scope, install AtFlows 0.1.1 by default, and offer optional AtMem-owned login plus read-only review leads | 031/035 and applicable 020/028/026 contracts | AtFlows remains separately started; standalone login remains compatible. No promotion of exploratory Jev results, automatic Memory Health, or causal telemetry claims. Stable release requires its own reviewed gates and notes. |
| **2.3.6** — memory-integrity qualification | Canonical safety boundaries | Secret-bearing proposal refusal, direct-parent taint propagation, issued scoped procedure-review authority, portable locking, and frozen before/after public benchmark evidence | Benchmarking 001 and existing memory/evidence authority contracts | Stable. No schema migration; retrieval defaults and companion pins unchanged. Candidate result: 400 PASS and 300 NOT_REPRESENTABLE across 700 trials, with zero failures/errors; upstream placement remains pending. |
| **2.4.0** — local memory health | M4 memory intelligence, local profile | Native single-owner memory gets time-valid recall, deterministic expiry and duplicate checks, a review queue, bounded opt-in background cycles and optional AtBot semantic proposals. Review works without a running AtFlows server or model | 001, 006, 008, 015, 026; applicable 020/022/028 local contracts | Ship only after local admission/lifecycle, scope, encrypted evidence, generation, deletion, restart and installed-artifact gates pass. Default disabled; first activation preview-only. No shared-space, external-provider propagation or automatic semantic changes claimed. |
| **2.5.0** — multi-agent memory and access foundations | M1 | Agents use private and explicitly shared spaces with separate read/write/admin permissions, ownership, membership changes and provenance. Establish durable authenticated administration for supported production profiles; extend memory-health authorization to shared spaces | 006, 010, 012, 013, 015, applicable 017/019/022/026 consumers | Membership and credential subsystems pass their decomposed gates; no cross-space leaks, stale-grant delivery, hidden health-count leakage or revoked-key resurrection. Local 2.4 memory health remains available. |
| **2.6.0** — governed provider connections | M1 | Native memory and external memory/knowledge share inspection and policy services; provider setup supports access preview, conditional approval, explicit activation and first-delivery monitoring. Complete the nine-destination workspace: Runs, Memory, Decisions, Tools and media, Audit, Policies, Tasks, Connections and Settings | 019, 022, 025, relevant 003/004/017/026 | Native plus one real external provider and declared authentication profiles pass. Preserve all three authority modes, exact delegated bytes and actual credential/delivery assurance. No claim of every authentication method or connector working. |
| **2.7.0** — investigation and resolution | M1 | Evidence-backed affected-work views, richer task/execution links, memory-health finding links, incident assignment and separate acknowledgment, remediation and outcome verification | Remaining applicable 007, 020, 021, 022 and 026 | Impact follows declared dependencies; unknown outcomes stay unknown. Any executable action requires its host checkpoint, authorization, idempotency and verification prerequisites; otherwise offer inspection/manual guidance. |
| **2.8.0** — context lifecycle and health propagation | M3 and M4 expansion | Revocable context grants, source-exposure impact and policy simulation; extend memory-health invalidation and review across declared shared/provider profiles | 015, 019, 023, 026 | Revocation races and actual propagation bounds pass for each claimed profile; simulations disclose unevaluable cases and cannot mutate live policy. Past disclosure is never described as retracted. Local memory health has already shipped in 2.4.0. |
| **2.9.0** — enterprise fleet operations | M3 enterprise expansion | Customer-hosted fleet policy distribution, scoped administration, supported federation/workload identity, independent evidence anchoring and verified recovery profiles | Hardened 013, 024, applicable 025 integration | Real deployment, replica, partition, credential, recovery and evidence-verification gates pass. Managed hosting remains optional. |
| **2.10.0b1** — model unlearning research preview | M4 unlearning research | Coordinate external-memory revocation, scoped behavioral suppression and evaluated post-training forget jobs for registered open-weight models with exact lineage | 015, 020, 021, 023, 024, 027 | The intended single-consumer-GPU profile uses Apache-2.0 `Qwen/Qwen2.5-0.5B-Instruct` at pinned revision `c89bee90d9f811437d9735454613c35b4a3c4dc8` and completes end to end. Results are `weight_unlearning_evaluated`, never proof of erasure; closed-source and lineage-unknown models receive only the provider/runtime assurances actually verified. No broad model-efficacy claim. |

The sequence scopes deliverables rather than requiring every task in each named spec to finish. Carry deferred work explicitly; never mark an entire spec complete from a passing release profile. The Work group column maps each release explicitly: M0–M4 are dependency/scope groupings, not a second chronological sequence. M1 is intentionally split across 2.5–2.7, the capture conformance subset of M2 lands in 2.3, and M3/M4 deliverables interleave only where the table states. Bringing the entire shared/provider Spec 026 profile into 2.4.0 would depend on 012/013/019/023 work assigned to later releases; 2.4.0 therefore completes a useful native single-owner profile first rather than claiming unsupported shared or external effects.

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
work between stable 2.3.3 and the planned 2.4 capability. Beta 2.3.4b1 ships
unchanged retrieval defaults. See the
[release notes](releases/v2.3.4b1.md) for the precise shipped subset. The initial 12-case Mem0 2.0.20 baseline
had an unmatched `limit`/`top_k` call and is preserved only as historical
evidence. The [corrected same-corpus calibration run](implementation-evidence/031/matched-v2.md)
is still too small and narrow for a general win. Native comparative preparation,
held-out comparative quality and benchmark dashboard integration remain future
work. Correctness, security, UI regression and artifact gates remain mandatory
for the stable scope; optional fusion/graph is not promoted to the default.

## 2.3.4b2 source candidate: default AtFlows install, opt-in review leads

Keep **AtFlows and AtMem as independent pip packages**, but install pinned
`atflows==0.1b6` with the base AtMem wheel. AtFlows observes local
traces, sessions, costs, latency and outcome signals; AtMem owns encrypted run
evidence, access decisions, memory admission and memory lifecycle. The optional
handoff is a versioned, read-only review-lead contract, not a shared database or
an automatic log-to-memory pipeline. Initial compatibility must name the exact
AtFlows and AtMem package versions tested when implementation lands. The old
`atmem[atflows]` extra remains valid. AtMem's ordinary memory retrieval must
work without an AtFlows server or Bun runtime; installation must not start
AtFlows, change existing Home data, or alter AtBot behavior.

For the 2.3.4b2 preview, an operator explicitly selects an AtMem run, AtFlows
session ID and bounded time window. AtFlows provides stable trace IDs and
trace-error signals for that session. AtMem treats these as untrusted leads,
resolves only exact authorized
run/evidence links, checks current scope and deletion state, and produces a
read-only local review report with source references, coverage gaps and uncertainty. A
missing exact link remains uncorrelated; matching names or timestamps cannot
manufacture one. The handoff does not copy raw prompts, logs, memory content or
trace payloads by default, and makes no non-loopback network request.

The 2.3.4b2 candidate deliverable is a local Python/CLI review report and a versioned
handoff contract, subject to applicable 020 execution-evidence and 028
encryption/access gates. It does not create the Spec 026 Memory Health queue or
offer memory review actions before 2.4.0. When the 2.4.0 queue exists, it may
consume the same authorized leads; canonical admission, correction and deletion
remain under Specs 006/015 and the Spec 026 review workflow.
Comparing outcomes with and without a supplied memory can prioritize review,
but an observational trace does not establish that the memory caused an outcome;
causal claims require a separately controlled evaluation.

Acceptance must exercise an installed two-package profile with authorized and
out-of-scope runs, missing/duplicate links, revoked access, deleted evidence,
incomplete traces and AtFlows unavailable. The preview must disclose gaps,
avoid unauthorized content/count leakage and produce zero automatic canonical
memory changes. If these gates or the prerequisite contracts are not ready,
2.3.4b2 cannot claim the handoff. This source
candidate is distinct from the existing 2.3.4b1 beta and does not rewrite its
shipped scope. The local consolidation cycle and
review experience are independent 2.4.0 deliverables; 2.5–2.8 add shared-space, provider, investigation and
propagation coverage.

## 2.3.4 stable scope

Stable 2.3.4 pins AtFlows 0.1.1 and preserves the optional read-only handoff.
AtFlows 0.1.1 can delegate dashboard authentication to a same-host loopback
AtMem dashboard: AtMem owns users, passwords and roles, while AtFlows checks
each protected request against the live AtMem session. Standalone AtFlows
accounts remain available when delegation is off. The command-line handoff
uses AtMem credentials in delegated mode and the AtFlows Administrator in
standalone mode. Neither mode turns observational telemetry into canonical
memory or automatic Memory Health findings. See the [release note](releases/v2.3.4.md).

## Deferred next capability: 2.4.0 local memory health

Continuity qualification above now takes engineering priority. This scope is
retained, not cancelled or implicitly shipped.

Bring the useful native single-owner Spec 026 cycle forward from 2.8.0. Deliver
temporal assertions, time-valid retrieval, deterministic derivations, exact
duplicate/expiry and overlap-conflict findings, an authorized review queue,
bounded resumable preview cycles, and optional AtBot semantic proposals. The
common service must expose the local Memory Health journey through supported
API/CLI/MCP/dashboard paths. AtMem alone selects review evidence and decides
whether an approved proposal changes canonical memory. The base capability
works locally with no running AtFlows server, AtBot model or network service.

This is a release-profile boundary, not a dependency waiver. Finish the local
Spec 006/015 admission and lifecycle work, encryption/access checks, generation
revalidation, derivative deletion, migration and installed-artifact evidence
needed for this profile before shipping. Background review defaults off; first
enablement is preview-only. Automatic eligibility changes require separate
explicit deterministic policy; semantic correction, merge, supersession and
deletion always require authorized review. Shared-space scheduling and counts,
external-provider propagation and fleet policy remain later gated profiles.
Preserve 2.3.2 portable-home recovery and exact capture contracts; do not
broaden cross-host multimodal claims without another verified host.

## Critical prerequisites for the subsequent releases

- **2.4:** deliver the complete native single-owner Memory Health profile against existing local authority, or keep the release unshipped. No shared-space, external-provider or remote-model claim may stand in for missing 012/013/019/023 contracts. AtBot remains optional and remote egress requires an implemented policy gate.
- **2.5:** estimate and implement **012 T016–T032** membership/feedback and **013 T012–T025** durable credentials/production enforcement. Their roll-up rows are not implementation estimates. Shared-space health counts, review and scheduling require the real authenticated boundary; preserve the 2.4 local behavior.
- **2.6:** consume 2.5 authority contracts. The wizard cannot activate an enterprise connection on configuration-only authentication. Complete 003 T054–T058 so delegated providers feed the same standalone exact-evidence store across OpenClaw, Pydantic AI and LangChain/LangGraph.
- **2.7:** preserve M0's useful investigation experience while extending it. Task-state participation remains optional; lack of memory or task activation cannot block tool-failure investigation.
- **2.8–2.9:** extend source/grant lifecycle, memory-health invalidation/propagation and fleet administration. Do not treat local expiry as verified external cleanup or shared-space access enforcement as optional.
- **2.10 preview:** consume verified revocation/impact, authenticated administration, execution evidence and model/deployment inventory from 2.8–2.9. Keep heavyweight training dependencies in separately registered workers. A memory deletion, refusal, provider acknowledgment or small-model benchmark cannot be promoted into a weight-erasure claim.

## Versioning, compatibility and publication

Hermes 2.3.8b2 acceptance includes the coordinated first-class setup and AtFlows
experience in Spec 037 T023–T026 and AtFlows Spec 006 T055–T059. The provider
binding alone is insufficient: require installed CLI/dashboard setup, explicit
reversible provider switching, upgrade/restore, actionable status and real-event
observation checks. Track evidence in `specs/037-hermes-integration/parity.md`;
do not imply historical-memory import, full capture or continuity from a working
recall hook. Preserve the stable 2.3.8 maintenance commitments.

These are proposed additive 2.x releases. Preserve public contracts, native behavior, existing scopes, signed delegated payloads and historical evidence through declared supported upgrades. If implementation requires a genuinely incompatible public or persisted-state change, resolve migration/deprecation and reconsider a major version before committing to these numbers.

Use prerelease candidates as needed for future scope. Published beta AtMem `2.3.4b1` maps
exactly to bridge `2.3.4-beta.1`; source candidate `2.3.4b2` maps to bridge
`2.3.4-beta.2`. AtBot has an independent version and changes only when
its implementation/compatibility requires it; do not invent a companion version
to mirror AtMem. Every release must align actual installer constants and pins.

Merging reviewed source/specs to `main` and publishing a package are separate decisions. For each actual release: inspect the full candidate diff, run applicable Python/companion/OpenClaw/build/installed-artifact gates, write version-specific release notes with exact upgrade instructions, and tag only the reviewed clean commit. Follow repository release rules for companion-first publication when needed, package workflows and verification of GitHub/PyPI/npm outputs. A pushed tag is not proof of publication.

Store verification under the [per-feature append-only journal](implementation-evidence/README.md) and maintain [current status](current-status.md) as an evidence-linked summary. The dated implementation review remains frozen. Update this planning document when scope or ordering changes; published release notes remain the authority for what a particular version actually shipped.
