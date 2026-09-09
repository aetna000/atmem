# AtMem unified product roadmap

**Updated**: 2026-09-09
**Status**: Implementation backlog; product capabilities below require their acceptance gates.

> Agent memory is just a start. Governance gives us control. Investigation turns that control and evidence into something people can use every day.

AtMem helps agents remember, controls the context they receive, and makes their work understandable when things go wrong.

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

## First milestone: find the break

Connect a supported agent, provide native or external context, run a task, introduce a failure, and show the operator where it broke and what to check next.

### Domain-neutral acceptance matrix

AtMem is a general-purpose memory, context-governance and execution-investigation product, not a refund or support workflow product. No single customer story defines the core contracts, interface or launch gate. Core objects are identities, executions, tools, sources, packages, policy decisions, findings and actions; domain-specific business fields remain optional integration data.

The first milestone MUST pass this cross-domain matrix using the same services and default UI:

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

### Delivery order (contract dependencies, not numeric order)

1. Preserve baseline 018 invariants. Finish 007 Amendment B execution identity/link and investigation contracts; existing open task IDs remain authoritative.
2. Freeze 019 provider/package and 020 execution/attempt contracts; adapt 003/004/008/010/011/012 consumers after the owning contracts exist. 020 non-context capture does not wait for provider integration.
3. Deliver durable execution capture and coverage on OpenClaw, Pydantic AI and LangGraph, with MCP explicitly tool-only. Add native and one real supported external provider to the same context evidence contract.
4. Build 021 deterministic incident/resolution services, then 022 execution-first read views and authorized actions. Deliver all three 017 adoption paths.
5. Execute 001 end-to-end fixture campaign, 018 boundary assertions, installed-host checks and 022/021 usability protocol. Publish incomplete capability coverage rather than claiming universal diagnosis.
6. Add 023 revocation, exposure impact and simulation after the first milestone. Add 024 fleet administration on hardened 013 customer deployment primitives.

Old specs' new integration amendments depend on new contracts only; new contracts depend on old baseline services. Do not interpret these as cycles requiring all revised old specs to finish before a new contract can land.

## Target navigation

| Section | User job |
| --- | --- |
| Overview | Active work, executions needing attention and unresolved incidents |
| Executions | Whole job across turns, attempts and child agents |
| Context | Native memory, providers, sources, provenance and delivery |
| Policies | Access, destination, freshness and review requirements |
| Tasks | Goals, progress, blockers and completion evidence |
| Settings | Integrations, identity, deployment and retention |

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

## Acceptance and claim boundaries

- Zero unauthorized egress/delivery, invented external outcomes or unsafe automatic retries in the deterministic campaign.
- Exact known failure/event and affected declared dependencies shown; recovered errors and unknown relationships stay distinct.
- Evidence survives acknowledged capture and restart; missing hooks, spool loss and disconnected coverage are explicit.
- At least 90% of a controlled group of 10 or more operators locates the relevant failure, affected work/uncertainty and justified next action in <=2 minutes; automated tests do not substitute for human measurement.
- Initial 019 policy-only overhead target <=25 ms p95; 020 first-page timeline target <=200 ms p95 at 100,000 events, on documented hardware. Provider/model cost and latency are separate.
- Legacy receipt/flight/task/native/delegated behavior remains compatible; no implicit memory migration or task activation.
- An observation-only integration cannot guarantee it blocked anything. Signed context proves attributed bytes/decisions, not truth or model use. Exposure lineage is not causation. Timeout after dispatch is not proof of no external effect.

## Enterprise direction

Keep local memory and investigation useful without fleet/cloud services. Support embedded, sidecar, customer-hosted and disconnected installations; managed operation is an optional commercial path. Fleet policies and evidence anchoring extend existing services, not a second dashboard or memory authority. Public contracts and independently verifiable evidence support provider partnerships and durable customer trust.
