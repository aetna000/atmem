# AtMem unified product roadmap

**Updated**: 2026-09-13
**Status**: Implementation backlog; product capabilities below require their acceptance gates.

**Numbered releases**: [Release roadmap — proposed 2.3 investigation preview through 2.10 model-unlearning research preview](../docs/release-roadmap.md). Its Work group column maps the non-chronological M0–M4 dependency/scope groupings to independently sequenced releases; version numbers are planning targets, not publication claims.

> AtMem is the independent evidence box for agent work: memory, prompts, decisions, models, tools, media and outcomes remain inspectable after the agent and its logs are gone.

AtMem helps agents remember, controls the context they receive, and independently preserves what happened. The AtMem evidence store—not the agent, host logs or an external provider—is the investigation system of record.

## Product requirements that govern every feature

**Agent- and framework-neutral. Multiple agents. Replaceable, governed context providers. Standalone full-fidelity multimodal evidence. Clear explanations and deterministic reconstruction.**

These are binding [product-wide requirements PR-001–PR-008](product-requirements.md), with acceptance cases and named owners. Core operation must not require OpenClaw. Every status explains the actual prompt, memory/context, decision, model exchange, tool call, target, result/error, effect/uncertainty and next action, with exact multimodal artifacts and time provenance available. Counts, colors, hashes, opaque IDs and links back to disposable host logs cannot substitute for retained evidence. Every stored evidence and semantic-metadata object is encrypted; plaintext is available only through an authorized AtMem operation.

### Standalone trust boundary

The mandatory product test starts with only a copied AtMem evidence store on a fresh machine/process. The fixture agent is dead; its logs, workspace and caches are deleted; its original memory/provider stores and model are unavailable. From AtMem alone, an authorized user must see and export the ordered run story:

**user multimodal input → memory state and exact context → governance decisions → model input/output → exact tool requests and targets → exact results/errors and media → observed outcome evidence**.

Text, images, screenshots, audio, video, files, URLs and fetched resources are first-class evidence parts. Derived text may aid search, but never replaces the original bytes. A legacy run containing only hashes is explicitly incomplete and non-reconstructable.

Full-fidelity encrypted capture is on by default. An explicit user choice may disable capture or select encrypted metadata-only capture, but the dashboard and exports must then say `not reconstructable`; reduced capture is not a successful Black Box profile. There is no supported setting that writes plaintext evidence.

OpenClaw is the first M0 host profile, not the product's identity. M0 implements neutral contracts and applicable feedback/time guarantees; shared-memory and broader host support are advertised only after their specific acceptance evidence passes.

## One execution, three moments

| Moment | Behavior | Primary owners |
| --- | --- | --- |
| Before the model call | Retrieve context, authorize query egress and content, check permissions/freshness, prepare an authorized package | 003/004/006/008/015 + 019 |
| During execution | Durably encrypt and capture exact ordered multimodal prompts, context, decisions, model exchanges, tool arguments/targets/results, progress, retries and child executions before disposable host evidence can disappear | 007/011 + 020 + 028 |
| After a problem | Authorize plaintext through AtMem, reconstruct the complete run from encrypted evidence alone, identify observed failures/gaps, render original artifacts and recommend a justified next action or replay manifest | 020 + 021 + 022 + 028; later 023 |

Native memory implements the same provider/package interface as external sources while retaining canonical admission and lifecycle. Switching to Mem0 or a document provider changes neither historic evidence nor investigation semantics and performs no implicit import. Three authority modes are explicit: native, governed external retrieval, and trusted delegation.

## Three explicit authority modes

| Mode | Provider responsibility | AtMem responsibility |
| --- | --- | --- |
| Native memory | AtMem's native provider retrieves candidates | Canonical admission, policy authorization, packaging, delivery controls and evidence |
| Governed external retrieval | External provider proposes context with provenance | Enterprise policy authorizes its use and delivery; provider claims alone do not authorize access |
| Trusted delegation | Registered provider authorizes an exact package | Delegation policy, binding, expiry, replay protection and delivery evidence; no implied independent content-policy authorization |

These are authority modes, not separate products or the three onboarding paths. They share inspectable context and execution references, but preserve who authorized content and which checks AtMem actually enforced. Selection is explicit; a failed governed request cannot silently fall back to trusted delegation. Native memory admission remains exclusively AtMem-owned. Existing signed delegated-v1 payloads remain unchanged; shared projections wrap or reference them without rewriting signed bytes.

## Three adoption paths

| Customer need | Initial setup | Optional expansion |
| --- | --- | --- |
| My agent needs memory | Native capture and recall; no external provider required | Governance and full execution evidence |
| We already have memory/retrieval | Register provider and policy; no memory migration | Source impact and investigation |
| My agent broke and I cannot explain why | Preserve full-fidelity multimodal execution evidence independently of the agent; no memory/embedding/AtBot prerequisite | Reconstruction, controlled replay, context governance and tasks |

Spec 017 owns onboarding mechanics; 022 owns path selection and the common experience. Observation is never labeled enforcement. Task state remains optional and never inferred from prompts.

## M0: investigation-only release, followed by product expansion

The previous hash-and-metadata M0 investigation slice is not sufficient for the Agent Black Box claim. M0 must be re-gated as a standalone encrypted evidence-box preview: capture exact ordered multimodal input, memory/context, decisions, model exchange and tool calls/results; copy only the encrypted AtMem store; prove direct inspection reveals no planted content; destroy the fixture host state; then authorize a fresh AtMem process and complete the investigation without the agent or logs. See the [M0 scope, task mapping and release gates](m0-investigation-preview.md). No provider unification, task activation, embeddings or AtBot is required, but full-fidelity encrypted capture, privilege enforcement and standalone reconstruction are required.

### Domain-neutral acceptance matrix

AtMem is a general-purpose memory, context-governance and execution-investigation product, not a refund or support workflow product. No single customer story defines the core contracts, interface or launch gate. Core objects are identities, executions, tools, sources, packages, policy decisions, findings and actions; domain-specific business fields remain optional integration data.

The M1 unified-product expansion MUST pass this cross-domain matrix. M0 exercises the software/research and successful-run controls that need no provider, with unknown external outcomes explicit; provider composition and enterprise workflows follow in M1:

| Fixture family | Representative work | What must be demonstrated |
| --- | --- | --- |
| Software engineering | Agent edits code and runs a build/test tool | Exact prompt, files/diffs, command arguments, stdout/stderr, failed step and declared dependent work survive host deletion |
| Research and analysis | Agent searches sources and assembles a report | Exact queries, URLs, fetched pages/files/images and tool failure survive source/agent unavailability; no invented source truth |
| Enterprise knowledge | Agent retrieves scoped documents for an answer | Exact authorized records and context bytes, decision inputs/results, model exchange and original document/media artifacts remain independently inspectable |
| Business operations | Agent updates a record, sends a message or requests an external action | Exact request arguments/target and returned receipt/error are retained; unknown side effects remain explicit; replay is reconstructed separately from re-execution |
| Successful everyday work | Native recall, governed retrieval and a completed multimodal job | Complete readable story and original text/image/audio/video/file/link evidence without manufacturing an incident |

Exercise native, governed-external and trusted-delegation modes across the campaign, plus investigation with no context provider. Use a declared coverage map rather than imply every mode/framework/scenario combination was tested. Include failure unrelated to memory. A denied context request must never be converted into delegation or silently broadened access.

Prove one-provider parity first, then explicitly configured native-plus-document composition under Spec 019 FR-010. Preserve required/optional segment handling, omissions and conflicting claims. This is a general context capability, not business-workflow logic.

A 40-minute virtual-clock fixture spans recovered retry, child failure, missing hook, crash/restart and optional task progress. Virtual-clock tests avoid making every CI run sleep 40 minutes; actual host longevity is a separately recorded soak gate.

The refund timeout remains **one optional illustration** of the unknown-side-effect case: check external operation evidence before considering retry. The same rule applies to a deployment, message send or database mutation. Acknowledgment alone neither repairs work nor verifies its outcome.

### Delivery order and independent release points

1. Preserve baseline 018 invariants and land 007 T110, the isolated non-task identity foundation from T088. Keep broad Amendment B work open.
2. Freeze Spec 020 evidence-envelope/artifact contracts together with Spec 028 encrypted-object, quantum-safe key, privilege and application-only plaintext contracts.
3. Implement the transactional encrypted evidence store across user, memory/context, decision, model and tool boundaries, including explicit local quotas, retention and backpressure suitable for consumer hardware. Hash-only or plaintext storage remains legacy evidence, not completion.
4. Implement Spec 021 reconstruction and Spec 022 rendering so an authorized user sees what was asked and attempted before technical identifiers, including original multimodal artifacts and exact calls/results. Settings shows one concise Evidence protection row and a focused action drawer.
5. Run the destructive standalone encryption, privilege, disaster and capacity gates: steal/copy AtMem storage and prove no planted plaintext; remove the fixture agent/logs/workspace/provider/memory sources; authorize a fresh AtMem process and reproduce the complete run story plus deterministic replay manifest; exhaust a small configured quota and prove zero silent evidence loss or downgrade.
6. **Release M0** only after the encrypted standalone disaster gate and cross-domain full-fidelity tests pass. Independent usability validation remains a separate claim gate.
7. **M1 expansion:** 012 explicit shared spaces and membership, 006/015 admission and invalidation, 019 shared native/external governance, broader 021 resolution, 022/025 workspace and connection journeys, all three 017 adoption paths and the 001 cross-domain campaign.
8. **M2 extensibility:** publish the 011 Host Conformance Kit and versioned capture-coverage manifests, including exact multimodal boundaries, plus tested Pydantic AI/LangGraph configurations.
9. **M3 enterprise expansion:** 023 revocation/impact/simulation and optional 024 fleet administration on hardened 013 deployment services.
10. **M4 memory intelligence and unlearning research:** 026 temporal memory and 027 model-unlearning work follow the standalone encrypted evidence foundation.

Old specs' new integration amendments depend on new contracts only; new contracts depend on old baseline services. Do not interpret these as cycles requiring all revised old specs to finish before a new contract can land.

M1 planning must estimate the actual authority work: **012 T016–T032** for persisted spaces/membership and feedback, and **013 T012–T025** for durable credentials and production enforcement. Their old umbrella rows are roll-ups, not single implementation estimates. Stable principal, permission and generation contracts land before dependent provider/UI consumers; fleet completion is not a prerequisite.

## Target navigation

| Section | User job |
| --- | --- |
| Runs | Complete prompt-to-outcome stories that remain readable without the agent or its logs |
| Memory | Exact retained memory state, records and multimodal context used by each run |
| Decisions | Exact governance inputs, rules, authorizer, decision and effect |
| Tools and media | Exact calls, arguments, URLs/paths/commands, results/errors and original images/audio/video/files/pages |
| Audit | Evidence access, exports, replay/re-execution decisions, deletion and integrity history |
| Policies | Access, destination, freshness and review requirements |
| Tasks | Goals, progress, blockers and completion evidence |
| Connections | Provider authentication, credential health, access preview, approval and activation |
| Settings | Concise Evidence protection status/actions plus general integrations, identity, deployment and retention |

Run detail: **User asked → memory/context supplied → decisions made → model exchange → tools/media used → exact result/error → observed outcome → reconstruction/replay options**. Technical IDs and hashes are expandable supporting proof, never the headline or sole retained evidence.

## Shared domain and ownership

Identity (authenticated actor/scope), execution (job/attempt/turn/tool), context (provider/source/package), policy (decision/version), evidence (observations and links), resolution (review/remediation/verification) are shared through Spec 012 services. Native memory, task revisions and event evidence retain their own authorities. Models may explain eligible evidence but never invent links or become required for useful investigation.

See [integration ownership](integration-ownership.md), [implementation review](implementation-review-2026-09-09.md), and each feature's spec/plan/tasks.

## New feature index

- [019 — Provider-Neutral Context Governance](019-provider-neutral-context-governance/spec.md): Before the model call.
- [020 — Durable Execution Evidence and Coverage](020-durable-execution-evidence/spec.md): During execution.
- [021 — Incident Investigation and Resolution](021-incident-investigation-and-resolution/spec.md): After a problem.
- [022 — Unified Agent Workspace and Adoption](022-unified-agent-workspace/spec.md): Before, during and after execution.
- [023 — Context Revocation, Exposure Impact and Policy Simulation](023-context-revocation-impact-and-simulation/spec.md): Before delivery and after source/policy changes.
- [024 — Enterprise Fleet and Evidence Operations](024-enterprise-fleet-and-evidence-operations/spec.md): Operate the same product across deployments.
- [025 — Enterprise Provider Connections and Activation](025-enterprise-provider-connections/spec.md): Ten-stage connection wizard, authentication, effective-access preview, conditional approval and first-delivery monitoring. Spec, plan and tasks are defined; implementation is pending.
- [026 — Temporal Memory Consolidation and Health Review](026-temporal-memory-consolidation/spec.md): Time-valid memory, deterministic derivation and opt-in AtBot-assisted health proposals with AtMem-only authority. Contract/UI foundations are staged across 2.4–2.6; scheduled consolidation is proposed for 2.8.0.
- [027 — Model Influence Revocation and Unlearning Orchestration](027-model-unlearning-orchestration/spec.md): Immediate controlled revocation plus a post-2.9 research preview for lineage-bound open-weight forget jobs, adversarial evaluation, independent approval and exact-artifact deployment. It never equates behavioral suppression with proven weight erasure.
- [028 — Encrypted Evidence and Privileged Access](028-encrypted-evidence-and-privileged-access/spec.md): At every persisted evidence, plaintext access, backup and export boundary.

Spec 025 adds Connections to the earlier six-section target and brings provider authentication out of general Settings. Deliver basic connection setup alongside 019/022 once 012/013 authenticated administration contracts are ready; delivery monitoring consumes available 019/020 evidence. Required enterprise identity and credential checks precede activation claims, while optional fleet operation remains later work.

Spec 026 adds Memory Health inside Context rather than another top-level destination. Specs 006 and 015 retain canonical admission/lifecycle authority, 022 owns the shared presentation, and AtBot remains replaceable proposal intelligence. Deterministic expiry and temporal derivation must work locally; uncertain correction, merge or supersession is review-only in the first supported profile.

Spec 027 consumes rather than broadens 023 revocation and 024 inventory authority. It defines explicit assurance levels: `memory_revoked`, `behaviorally_suppressed`, `provider_deletion_acknowledged` and `weight_unlearning_evaluated`; `weight_erasure_proven` is reserved and unclaimable by the preview. Optional training runs in a separately privileged worker, not AtBot or an ordinary agent process.

## Acceptance and claim boundaries

- Zero unauthorized egress/delivery, invented external outcomes or unsafe automatic retries in the deterministic campaign.
- Exact prompts, memory/context, decisions, model exchanges, tool arguments/targets/results/errors and multimodal artifacts are shown; recovered errors and unknown relationships stay distinct.
- Evidence survives capture, crash, backup/restore and destruction of the agent, logs, workspace and original providers. Missing bytes or hooks are explicit and block full-fidelity claims.
- A copied AtMem store alone reconstructs every planted cross-domain run and produces byte-identical artifact downloads plus a deterministic replay manifest.
- Direct inspection of the copied store, artifacts, indexes, spool, backup and export reveals no planted session content or semantic metadata; only authorized AtMem operations release plaintext under the three-level privilege model.
- No acceptance test may substitute a count, digest, opaque identifier or generic phrase such as “a tool failed” for available execution evidence.
- At least 9 of 10 operators complete the declared two-minute investigation protocol, replicated on a second independent cohort of ten before advertising that usability capability; publish both cohorts separately. See [measurement protocol](usability-protocol.md).
- Initial 019 policy-only overhead target <=25 ms p95; 026 deterministic temporal filtering target <=10 ms p95. With both enabled on one recall path, directly measured added pre-model control overhead must be <=35 ms p95 on the declared profile rather than inferred by summing independent percentiles. Provider, network, retrieval-model and AtBot latency are measured separately. The 020 first-page timeline target remains <=200 ms p95 at 100,000 events on documented hardware.
- Temporal review cannot silently delete or semantically rewrite memory; inaccessible records contribute neither content nor hidden aggregate influence. A model-unlearning result names the exact artifact and evaluation profile and never upgrades missing/adversarially weak evidence into an erasure claim.
- Legacy receipt/flight/task/native/delegated behavior remains compatible; no implicit memory migration or task activation.
- An observation-only integration cannot guarantee it blocked anything. Signed context proves attributed bytes/decisions, not truth or model use. Exposure lineage is not causation. Timeout after dispatch is not proof of no external effect.

## Enterprise direction

Keep local memory and investigation useful without fleet/cloud services. Support embedded, sidecar, customer-hosted and disconnected installations; managed operation is an optional commercial path. Fleet policies and evidence anchoring extend existing services, not a second dashboard or memory authority. Public contracts and independently verifiable evidence support provider partnerships and durable customer trust.

## Named extensibility deliverable

The **AtMem Host Conformance Kit** (Spec 011 FR-013–FR-016) lets a third party implement a host adapter, run the public suite, publish a versioned evidence manifest and submit a compatibility listing. Spec 020 extends the manifest with execution coverage through the existing capability authority. Listings distinguish self-reported, independently reproduced and AtMem-verified evidence; passing a fixture is not proof of a deployed boundary. See [manifest contract](011-framework-adapter-conformance/conformance-manifest.md).
