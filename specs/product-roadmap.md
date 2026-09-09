# AtMem unified product roadmap

**Updated**: 2026-09-09
**Status**: Implementation backlog; product capabilities below require their acceptance gates.

> Agent memory is just a start. Governance gives us control. Investigation turns that control and evidence into something people can use every day.

AtMem helps agents remember, controls the context they receive, and makes their work understandable when things go wrong.

## Product requirements that govern every feature

**Agent- and framework-neutral. Multiple agents. Private or explicitly shared memory. Replaceable, governed context providers. Clear explanations and timestamps.**

These are binding [product-wide requirements PR-001–PR-006](product-requirements.md), with acceptance cases and named owners. Core operation must not require OpenClaw. New memory spaces default private; authorized sharing retains ownership, independent permissions and provenance. Every status explains its evidence, effect/uncertainty and next action, with absolute time, timezone and actual check age. Color and page refresh cannot substitute for an explanation or new verification.

OpenClaw is the first M0 host profile, not the product's identity. M0 implements neutral contracts and applicable feedback/time guarantees; shared-memory and broader host support are advertised only after their specific acceptance evidence passes.

## One execution, three moments

| Moment | Behavior | Primary owners |
| --- | --- | --- |
| Before the model call | Retrieve context, authorize query egress and content, check permissions/freshness, prepare an authorized package | 003/004/006/008/015 + 019 |
| During execution | Record context delivery, model/tools, task progress, retries, child executions and missing coverage | 007/011 + 020 |
| After a problem | Identify observed failures/gaps, show affected work and recommend a justified next action | 021 + 022; later 023 |

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
| My agent broke and I cannot explain why | Observe execution hooks; no memory/embedding/AtBot prerequisite | Context governance and tasks |

Spec 017 owns onboarding mechanics; 022 owns path selection and the common experience. Observation is never labeled enforcement. Task state remains optional and never inferred from prompts.

## M0: investigation-only release, followed by product expansion

Release an opt-in OpenClaw investigation preview through the existing Activity/Evidence dashboard. Correlate supplied execution identities, durably capture tool events and gaps, and show minimal deterministic findings with exact evidence links. See the [M0 scope, task mapping and release gates](m0-investigation-preview.md). No provider unification, task activation, embeddings, AtBot or shell rewrite is required.

### Domain-neutral acceptance matrix

AtMem is a general-purpose memory, context-governance and execution-investigation product, not a refund or support workflow product. No single customer story defines the core contracts, interface or launch gate. Core objects are identities, executions, tools, sources, packages, policy decisions, findings and actions; domain-specific business fields remain optional integration data.

The M1 unified-product expansion MUST pass this cross-domain matrix. M0 exercises the software/research and successful-run controls that need no provider, with unknown external outcomes explicit; provider composition and enterprise workflows follow in M1:

| Fixture family | Representative work | What must be demonstrated |
| --- | --- | --- |
| Software engineering | Agent edits code and runs a build/test tool | Exact failed step and declared dependent work; distinguish test failure, recovered retry and missing completion |
| Research and analysis | Agent searches sources and assembles a report | Read-only tool failure, missing evidence and provider unavailability; no invented source truth or context causation |
| Enterprise knowledge | Agent retrieves scoped documents for an answer | Native/external package parity, permission and freshness decisions, visible actual authorizer and delivery coverage |
| Business operations | Agent updates a record, sends a message or requests an external action | Unknown side effects after dispatch, verification prerequisites and no unsafe replay |
| Successful everyday work | Native recall, governed retrieval and a completed multi-step job | Useful memory and context evidence without manufacturing an incident or requiring a failure |

Exercise native, governed-external and trusted-delegation modes across the campaign, plus investigation with no context provider. Use a declared coverage map rather than imply every mode/framework/scenario combination was tested. Include failure unrelated to memory. A denied context request must never be converted into delegation or silently broadened access.

Prove one-provider parity first, then explicitly configured native-plus-document composition under Spec 019 FR-010. Preserve required/optional segment handling, omissions and conflicting claims. This is a general context capability, not business-workflow logic.

A 40-minute virtual-clock fixture spans recovered retry, child failure, missing hook, crash/restart and optional task progress. Virtual-clock tests avoid making every CI run sleep 40 minutes; actual host longevity is a separately recorded soak gate.

The refund timeout remains **one optional illustration** of the unknown-side-effect case: check external operation evidence before considering retry. The same rule applies to a deployment, message send or database mutation. Acknowledgment alone neither repairs work nor verifies its outcome.

### Delivery order and independent release points

1. Preserve baseline 018 invariants and land 007 T110, the isolated non-task identity foundation from T088. Keep broad Amendment B work open.
2. Implement 020 T018–T021 capture/projection and the minimal 021 T018–T019 findings in the existing OpenClaw dashboard. Freeze only contracts needed by this slice.
3. **Release M0** after completed 020 T022 and 021 T020 technical gates. Ship investigation-only to users with explicit coverage and preview limitations. Independent 021 T024 validates the two-cohort protocol before advertising measured usability; it does not block completion of the technical tasks or preview availability.
4. **M1 expansion:** 012 explicit private/shared spaces and membership, 006/015 admission and invalidation, 019 shared native/external governance, broader 021 resolution, 022/025 workspace and connection journeys, all three 017 adoption paths and the 001 cross-domain campaign. These do not block M0; shared-memory claims require the PR-002–PR-004 gates.
5. **M2 extensibility:** publish the 011 Host Conformance Kit and versioned coverage manifests, third-party submission/listing rules and additional tested Pydantic AI/LangGraph configurations. Work may proceed alongside M0/M1; their completion does not block the single-host preview.
6. **M3 enterprise expansion:** 023 revocation/impact/simulation and optional 024 fleet administration on hardened 013 deployment services.

Old specs' new integration amendments depend on new contracts only; new contracts depend on old baseline services. Do not interpret these as cycles requiring all revised old specs to finish before a new contract can land.

M1 planning must estimate the actual authority work: **012 T016–T032** for persisted spaces/membership and feedback, and **013 T012–T025** for durable credentials and production enforcement. Their old umbrella rows are roll-ups, not single implementation estimates. Stable principal, permission and generation contracts land before dependent provider/UI consumers; fleet completion is not a prerequisite.

## Target navigation

| Section | User job |
| --- | --- |
| Overview | Active work, executions needing attention and unresolved incidents |
| Executions | Whole job across turns, attempts and child agents |
| Context | Native memory, providers, sources, provenance and delivery |
| Policies | Access, destination, freshness and review requirements |
| Tasks | Goals, progress, blockers and completion evidence |
| Connections | Provider authentication, credential health, access preview, approval and activation |
| Settings | General integrations, identity, deployment and retention |

Execution detail: **Outcome → important events → affected work → next actions → supporting evidence**. Technical IDs are expandable, timestamps visible and pivots require no manual ID correlation. Spec 022 explicitly replaces the historical four-workspace mandate; runtime navigation changes only through implementation and migration tests.

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

Spec 025 adds Connections to the earlier six-section target and brings provider authentication out of general Settings. Deliver basic connection setup alongside 019/022 once 012/013 authenticated administration contracts are ready; delivery monitoring consumes available 019/020 evidence. Required enterprise identity and credential checks precede activation claims, while optional fleet operation remains later work.

## Acceptance and claim boundaries

- Zero unauthorized egress/delivery, invented external outcomes or unsafe automatic retries in the deterministic campaign.
- Exact known failure/event and affected declared dependencies shown; recovered errors and unknown relationships stay distinct.
- Evidence survives acknowledged capture and restart; missing hooks, spool loss and disconnected coverage are explicit.
- At least 9 of 10 operators complete the declared two-minute investigation protocol, replicated on a second independent cohort of ten before advertising that usability capability; publish both cohorts separately. See [measurement protocol](usability-protocol.md).
- Initial 019 policy-only overhead target <=25 ms p95; 020 first-page timeline target <=200 ms p95 at 100,000 events, on documented hardware. Provider/model cost and latency are separate.
- Legacy receipt/flight/task/native/delegated behavior remains compatible; no implicit memory migration or task activation.
- An observation-only integration cannot guarantee it blocked anything. Signed context proves attributed bytes/decisions, not truth or model use. Exposure lineage is not causation. Timeout after dispatch is not proof of no external effect.

## Enterprise direction

Keep local memory and investigation useful without fleet/cloud services. Support embedded, sidecar, customer-hosted and disconnected installations; managed operation is an optional commercial path. Fleet policies and evidence anchoring extend existing services, not a second dashboard or memory authority. Public contracts and independently verifiable evidence support provider partnerships and durable customer trust.

## Named extensibility deliverable

The **AtMem Host Conformance Kit** (Spec 011 FR-013–FR-016) lets a third party implement a host adapter, run the public suite, publish a versioned evidence manifest and submit a compatibility listing. Spec 020 extends the manifest with execution coverage through the existing capability authority. Listings distinguish self-reported, independently reproduced and AtMem-verified evidence; passing a fixture is not proof of a deployed boundary. See [manifest contract](011-framework-adapter-conformance/conformance-manifest.md).
