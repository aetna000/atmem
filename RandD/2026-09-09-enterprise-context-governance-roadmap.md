# AtMem enterprise context governance: product direction and roadmap

Date: 9 September 2026 (Australia/Sydney)

Status: Proposed strategy archived from the discussion. This is not an approved
implementation plan or a claim that the proposed capabilities already exist.

Related research: [AtMem vs Mem0 comparison](2026-09-09-atmem-vs-mem0-comparison.md).

## Product direction

Pivot AtMem's primary positioning to **the governance layer for agent context**.
Keep native memory as an included provider, and make connecting an existing
memory or retrieval system equally natural.

The enterprise promise:

> Use your preferred memory and knowledge providers. AtMem controls which
> context an agent may receive, records what reached it, and helps you respond
> when that context changes or becomes invalid.

This builds on existing scoped authority, exact delivery receipts, provenance,
shadow mode, and Black Box evidence.

The commercial opportunity is credible, but governance plus observability alone
is insufficient differentiation. LangSmith markets runtime governance through
an LLM gateway; Portkey offers gateway guardrails and administrative auditing;
Cerbos provides policy decisions with detailed decision logs. AtMem needs a
specific advantage around **context provenance, delivery, and lifecycle across
providers**.

Sources: [LangSmith gateway](https://www.langchain.com/blog/introducing-llm-gateway),
[Portkey guardrails](https://portkey.ai/docs/product/guardrails),
[Cerbos decision logs](https://docs.cerbos.dev/cerbos-hub/audit-log-collection.html).

## 1. Initial customer problem

Initially target enterprise AI platform teams running agents across several
frameworks and knowledge systems. Their problem is concrete:

> Our agent can retrieve information from several places. We cannot consistently
> explain whether it was permitted, whether it was current, what reached the
> model, or which runs are affected when a source is revoked.

A strong initial use case is a customer-support agent using:

- Customer preferences from Mem0.
- Account information from an internal service.
- Procedures from a document search system.
- Temporary investigation state from AtMem tasks.

For each response, the business needs to know which customer scope applied,
whether internal information was exposed to an approved model, and whether
outdated procedures influenced the run.

This customer has a reason to buy governance independently of the memory engine.
OpenClaw remains a useful showcase and integration, while enterprise acquisition
expands through Python SDKs, LangGraph, Pydantic AI, HTTP, and MCP.

## 2. Explicit authority model

The most consequential architectural change concerns delegated providers.

The current [delegated contract](../docs/contracts/delegated-context-provider-v1.md)
says the provider authorizes the context and AtMem verifies its binding and
delivery. That does not establish that enterprise policy independently allowed
the content.

Introduce three explicit modes:

| Mode | Provider responsibility | AtMem responsibility |
| --- | --- | --- |
| Native memory | AtMem's native provider retrieves candidates | Admission, policy, packaging, delivery and evidence |
| Governed external retrieval | External provider proposes context with provenance | Enterprise policy authorizes its use and delivery |
| Trusted delegation | Registered provider authorizes an exact package | Delegation policy, binding, expiry, replay protection and delivery evidence |

For governed external retrieval, provider approval and enterprise approval must
be separate decisions. Mem0 may correctly return an employee memory, while
AtMem refuses to send it to an external model because the workflow or destination
is unauthorized.

Preserve the existing exact-byte delegation contract. If AtMem redacts or
combines provider content, create a new derived package with its own digest and
transformation lineage. The original signature cannot attest to modified bytes.

## 3. Governed context package

A search result should become a package with enough information to make and
explain a decision.

| Information | Purpose |
| --- | --- |
| Authenticated user, service and agent | Establish who is acting |
| Tenant, workspace and task scope | Bound where the context applies |
| Provider and source versions | Identify where it came from |
| Sensitivity and permitted destinations | Control disclosure |
| Purpose and allowed operations | Distinguish support, analytics, personalization and other uses |
| Freshness, expiry and revocation generation | Prevent continued use of invalid context |
| Source references and content digest | Support lineage without mandatory central content storage |
| Policy version and reason codes | Explain authorization |
| Transformation history | Explain redaction, extraction or composition |
| Delivery receipt | Record what reached the model boundary |

Provider-supplied labels are claims, not automatically trusted facts. A connector
must declare whether attributes came from an authoritative source, a model
classifier, an operator, or unverified metadata.

Also govern outbound retrieval requests. Sending a confidential prompt to a
provider may already disclose information before its returned context is checked.

## 4. Consistent API, SDK and MCP experiences

Establish one application service layer used by all interfaces.

| Proposed surface | Core operations |
| --- | --- |
| Runtime API | Prepare context, validate a delivery grant, confirm exposure, append run events |
| Provider API | Declare capabilities, retrieve packages, report source changes and revocations |
| Operator API | Review decisions, manage policies, register providers, acknowledge findings, initiate remediation |
| Evidence API | Explain decisions, trace lineage, export evidence, verify bundles |
| Evaluation API | Simulate policies, compare provider outputs, inspect expected impact |

The common SDK workflow should be small. Illustrative proposed API:

```python
context = await atmem.prepare(request_context)
response = await governed_model.call(messages, context=context)
```

The framework adapter handles validation, placement and exposure recording. An
advanced API remains available for custom runtimes.

For MCP, provide distinct runtime and operator servers with
authentication-derived scopes. Agent tools can request context and inspect
their own task state; administrative capabilities belong to a separately
authorized interface.

MCP alone cannot prove model-boundary delivery. Capability reporting should
make these levels visible:

- Retrieval observed.
- Context returned to host.
- Model placement observed.
- Delivery grant enforced.

Enterprise buyers should see exactly which integration provides which assurance.

## 5. Operational dashboard

The questions "which turn failed?" and "what can I do?" identify the interface
priority. Organize the main screen around actionable findings. Example:

> **Outdated procedure reached 14 runs**
> Provider: Internal knowledge search
> Source revoked: 10:42
> Latest affected run: 10:47
> Enforcement: observation only

Provide specific actions:

- Inspect affected turns.
- Disable the provider for this scope.
- Revoke future context grants.
- Request source correction.
- Assign an investigation.
- Simulate a replacement policy.
- Acknowledge review.

Keep finding status, remediation status, and verification status separate.
Acknowledge must never imply repaired.

Every detail view should answer, in order:

1. What happened?
2. Why was it allowed or blocked?
3. What is affected?
4. What can I do?
5. What evidence supports the conclusion?

IDs, signatures and raw events belong in expandable technical evidence.

## 6. Three distinctive capabilities

### A. Revocable context grants

Authorize context for a specific principal, task, destination, package digest
and expiry. Revalidate immediately before model dispatch.

If permissions change after retrieval, the integration can refuse delivery.
Revocation prevents future governed delivery; it cannot retract information
already sent to a model or erase copies outside AtMem's control.

### B. Context impact analysis

Connect source versions to context packages, exposures, turns and linked
actions. When a document is corrected or memory deleted, answer:

> Which observed runs received this version, and which associated actions
> require review?

Start with direct exposure lineage. Later add derivative lineage for summaries,
caches and memories where providers supply that evidence.

Call this an exposure impact report, not proof that the source caused an answer.
That distinction increases credibility.

### C. Policy simulation before enforcement

Extend shadow mode into a policy change workflow. Example:

> This proposed policy would have withheld context from 28 of the last 1,000
> observed requests. Twelve would have had an approved alternative provider.

Let operators inspect differences and approve rollout.

Historical hashes alone cannot reconstruct content-dependent decisions.
Simulation needs retained policy attributes, permission to reread sources, or
a customer-controlled evidence store. Display unavailable cases explicitly.

Together, these capabilities connect prevention, investigation and remediation.
That is more valuable than accumulating additional traces.

## 7. Enterprise deployment beyond SaaS

Separate a local enforcement service from fleet administration.

| Deployment | Suitable customer |
| --- | --- |
| Embedded library | Developers and application teams |
| Sidecar or local service | Existing enterprise agent applications |
| Customer VPC or on-premises | Organizations requiring infrastructure and data control |
| Disconnected installation | Restricted environments |
| Managed service | Teams prioritizing operational convenience |

The local service evaluates signed policy bundles, validates context grants and
records evidence. Fleet administration distributes policies, manages identities
and providers, and aggregates permitted metadata.

If fleet administration is unavailable, local behavior follows a declared policy:
continue using an unexpired policy bundle, withhold specific context, or stop a
protected operation.

The repository already has some production configuration and backup primitives
in [production-service.md](../docs/production-service.md). Harden and integrate
these foundations.

Enterprise requirements include identity federation, workload identities, role
separation, customer-managed keys, reliable upgrades, backup restoration,
evidence export, and tested availability. These are purchase requirements;
they are not the central differentiator.

## 8. Phased roadmap and acceptance gates

The schedule is illustrative. Staffing and pilot feedback should determine dates.

| Phase | Focus | Concrete exit condition |
| --- | --- | --- |
| 0: Validate the focus — first month | Interview platform teams; select one workflow; inventory current assurance gaps | Three design partners identify the same costly problem and agree on pilot success criteria |
| 1: Provider-neutral foundation — months 1–3 | Stable runtime/provider contracts, native provider, current Mem0 adapter, one document-search connector, shared SDK workflow | The same application can switch providers while preserving policy and evidence behavior |
| 2: Enforced delivery — months 3–6 | Context grants, destination policy, revocation checks, provider request controls, framework enforcement | Supported adapters reject expired, revoked, mis-scoped and modified packages in conformance tests |
| 3: Enterprise operations — months 6–9 | Fleet policy management, customer deployment packaging, investigation workflow, independent evidence export | Paying pilots operate through upgrades, outages and restore exercises with agreed service objectives |
| 4: Differentiation — months 9–12 | Exposure impact analysis, policy simulation, governed multi-provider composition | Customers demonstrate faster incident resolution and safer policy changes against their baseline |

Measure progress through:

- Time to integrate an existing provider.
- Percentage of model calls with observed, enforced delivery.
- Policy decision overhead, separately from provider retrieval latency.
- False withholding rate on customer workloads.
- Revocation propagation time.
- Evidence completeness.
- Investigation and remediation time.
- Pilot conversion and continued production use.

Passing a synthetic safety suite supports a release decision; it does not
establish zero risk in production.

## 9. Defensible advantage

A hash chain, provider adapter or attractive dashboard is easy to reproduce.
Build the advantage through the accumulated system around them:

- A public context-governance contract that provider vendors can implement.
- A rigorous conformance suite testing identity, expiry, replay, revocation,
  transformation and delivery.
- Reliable adapters at actual execution boundaries, including published
  coverage limits.
- Useful lineage across providers and runs, built over sustained production
  operation.
- Customer-tested investigation and remediation workflows.
- Independent verification so customers can inspect evidence without trusting
  the dashboard alone.

For stronger tamper evidence, periodically sign and externally anchor evidence
checkpoints in customer-controlled storage. A local hash chain alone does not
prevent a sufficiently privileged actor from rewriting the chain and its head.

Partner with memory vendors, retrieval systems and existing policy engines.
Let them provide retrieval intelligence or general authorization decisions while
AtMem specializes in applying and proving decisions at context boundaries.

## 10. Commercial offering and engineering focus

Keep the local runtime, basic native memory, public contracts and verification
tools open. Charge for enterprise fleet administration, identity integration,
policy workflows, supported private deployments, advanced impact analysis and
contractual support.

Test an annual platform subscription with deployment or governed-usage bands.
Avoid making per-memory pricing the primary model when customers can bring
memory stored elsewhere.

Narrow engineering effort:

- Maintain native memory as a dependable default and reference provider.
- Keep AtBot focused on optional classification and review assistance.
- Use governed tasks to express purpose, constraints and completion evidence.
- Prioritize three excellent integrations over ten shallow ones.
- Integrate with existing observability and policy products where practical.

## Positioning to test with customers

> AtMem governs the context your agents receive—from any provider—and gives
> your team the evidence and controls to manage it throughout its lifecycle.

This direction is close enough to the current architecture to be achievable,
and specific enough to guide engineering investment and enterprise buying
conversations.
