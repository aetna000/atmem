# AtBot: AtMem intelligence companion specification

Status: approved product direction for implementation

## Product definition

AtBot is the intelligent processing companion of AtMem. It provides the
model-backed inference and retrieval functions commonly associated with
systems such as Mem0, while AtMem remains the sole authority and storage owner.

> AtBot proposes and ranks; AtMem authorizes and stores.

AtBot is not a customer-facing independent agent. It retains model routing and
bounded inference orchestration for memory work, but contains no general task
loop, task tools, direct database gateway, or independent authority identity.

AtBot has no independent product memory, dashboard, user identity, workspace,
or authority plane. It operates only on work authorized and scoped by AtMem.

## Product composition

```text
Any supported agent
  <-> agent adapter
  <-> AtMem authority, storage, lifecycle, and dashboard
  <-> AtBot local-first intelligence companion
```

OpenClaw is the first maintained reference adapter. Hermes and other agents use
the same host-neutral contracts. OpenClaw-specific discovery, Safe Switch,
shadow mode, restore, and topology behavior remain adapter responsibilities and
must not leak into AtBot.

## Responsibilities

### AtBot owns intelligence

- durable-fact extraction from AtMem-bound authenticated sources;
- proposed entities and relationships;
- proposed duplicate, support, contradiction, and supersession relationships;
- private-content-free query expansion;
- reranking of candidates already authorized by AtMem;
- selection and compression proposals within an AtMem-declared budget;
- local-model and explicitly permitted remote-model routing;
- bounded memory-maintenance jobs and quality evaluation;
- structured explanations of inference and ranking decisions.

### AtMem owns authority and product state

- source capture and source-binding assurance;
- subject, agent, workspace, tenant, and adapter identity;
- canonical memory, entity graph, vectors, and provenance;
- admission, quarantine, promotion, conflict, supersession, and rejection;
- candidate eligibility and content-release policy;
- byte-stable context construction and injection authorization;
- correction, exclusion, forgetting, and deletion verification;
- audit chains, retrieval evidence, exposure receipts, and response evidence;
- shadow mode, multi-agent topology, Safe Switch, restoration, and dashboards.

AtBot must never write AtMem tables, approve its own proposal, expand its own
scope, or introduce a record ID that AtMem did not authorize.

## Deployment and installation

AtMem installs and manages a compatible pinned AtBot companion. Package code
remains separate to avoid framework dependencies inside the AtMem authority
engine. The supported installation experience is:

```text
atmem install or atmem openclaw install
  -> install or verify pinned AtBot companion
  -> detect/configure a local model
  -> start loopback companion service
  -> negotiate protocol capabilities
  -> run inference and retrieval test flights
  -> keep deterministic AtMem fallback available
```

Installation must not silently download a large model, enable a remote API, or
permit remote egress. Local model setup requires visible status and action.

AtBot must not create a second canonical `atmem.db` in companion mode. AtMem
sends typed work to AtBot; AtBot returns proposals or rankings. AtMem owns all
durable memory state.

The AtBot package therefore has no dependency on the AtMem Python package.
AtMem calls the loopback companion protocol, which prevents AtBot from opening
authority storage directly and keeps intelligence replaceable.

## Unified interface

There is one customer interface: the AtMem dashboard. The standalone AtBot chat
UI is merged into it and removed as a separate product surface.

The unified dashboard uses AtBot's dark, simple, chat-oriented visual language
while retaining AtMem functionality:

- natural-language memory query;
- readable memory results and explanations;
- status, storage, and vector health;
- decisions and review queue;
- provenance and lifecycle controls;
- correction, exclusion, and verified forgetting;
- agent and workspace topology;
- shadow/active mode, OpenClaw restore, and bridge verification;
- audit, Black Box, and exposure evidence.

Dashboard chat is a memory-query interface, not a general assistant. It answers
questions about governed memory and explains missing or weak recall.

## Automatic storage

```text
authenticated agent user turn
  -> existing adapter
  -> AtMem captures and binds the source
  -> AtMem asks AtBot for typed extraction
  -> AtBot proposes facts, entities, relationships, confidence, and sensitivity
  -> AtMem validates scope, evidence, policy, and lifecycle
  -> AtMem admits, quarantines, or rejects
  -> AtMem updates canonical, graph, and vector representations
```

AtBot does not decide whether a proposed memory becomes active.

## Retrieval, injection, and return

```text
user asks the host agent
  -> adapter sends query + subject + agent + workspace to AtMem
  -> AtMem validates identity, scope, permissions, sensitivity, and egress
  -> AtMem searches lexical + graph + vector storage
  -> AtMem removes inaccessible, deleted, excluded, or sensitive candidates
  -> AtBot receives only eligible candidates
  -> AtBot reranks, expands relationships, and selects useful record IDs
  -> AtMem revalidates membership, generation, policy, scope, and budget
  -> AtMem creates byte-stable authorized context
  -> adapter injects context into the host agent
  -> host agent generates the response
  -> adapter confirms exact context delivery
  -> AtMem records retrieval, exposure, and response evidence
  -> response returns to the user
```

The critical security boundary is:

```text
AtMem authorization
  before
AtBot sees candidate content
```

AtBot may expand a query before content access:

```text
"What cars do I like?"
  -> car preference
  -> preferred vehicle
  -> favorite automobile
```

AtMem runs every expansion under the original scope and policy.

Semantic retrieval is required on the AtMem dashboard query path. AtBot sees
only the query while expanding it; it receives candidate content only after
AtMem has fused lexical, canonical fact-key, graph, and vector results and
applied authority policy. Literal-only retrieval is a defect because it can
prevent AtBot from ranking memory it was never allowed to see. Acceptance
includes abbreviation and synonym cases such as `fav food` retrieving an
eligible `likes burgers` memory.

AtBot must not rely on a fixed list of product-specific synonym rules. A real
local embedding epoch handles related concepts such as `lunch`, `food`, and
`burgers`; content-free expansion remains an additional recall signal rather
than a substitute for semantic vectors.

## Ranking contract

AtBot receives a candidate-set identifier, immutable candidate record IDs,
eligible content, score evidence, declared provider, egress class, budget, and
expiry. It returns only an ordering or subset of those IDs plus explanation
metadata.

```text
AtMem -> [memory A, memory B, memory C]
AtBot -> [memory C, memory A]
AtMem -> revalidates C and A
AtMem -> creates final authorized context
```

Unknown IDs, stale generations, expired sets, provider changes, scope changes,
and budget violations fail closed.

## Failure and fallback

AtBot is not a single point of failure. If it is missing, unhealthy, slow, or
returns invalid output:

```text
agent query
  -> adapter
  -> AtMem lexical + graph + local-vector ranking
  -> AtMem authorized context
  -> adapter injection
  -> host agent response
  -> AtMem exposure receipt
```

Failure reduces intelligence. It must not weaken authority, stop verified
baseline memory, enable remote egress, or corrupt canonical state.

## Local-first model policy

- Local Qwen/Ollama is the default inference route.
- Deterministic rules are the no-model fallback.
- Remote models require explicit configuration and AtMem egress authorization.
- Restricted candidates never reach a remote provider without policy approval.
- Provider changes invalidate candidate and cache authorization.
- Traces contain digests and structural metadata, not raw private content.

## Agent-agnostic adapters

Every adapter implements the same logical hooks:

- `source.capture`;
- `memory.prepare`;
- `context.exposed`;
- `model.completed`;
- `tool.completed`;
- `turn.completed` or `turn.failed`.

Adapters authenticate host identity and map it into AtMem scope. They do not
contain AtBot prompts or bypass AtMem policy. OpenClaw remains the conformance
adapter for multi-agent topology, shadow mode, activation, restore, and flight
evidence.

## Acceptance criteria

AtBot is product-ready when:

1. it has no independent-agent product mode or separate customer dashboard;
2. AtMem can install, discover, start, stop, and diagnose it;
3. it never owns canonical memory or an independent authority database;
4. automatic extraction produces typed proposals bound to AtMem sources;
5. candidate content is AtMem-authorized before AtBot sees it;
6. rankings cannot add unknown or stale records;
7. AtMem revalidates every ranking before context construction;
8. the unified dashboard supports natural-language memory query;
9. AtMem works safely when AtBot is unavailable;
10. OpenClaw shadow mode, multi-agent support, restore, and evidence remain green;
11. the same contracts can support Hermes and other adapters;
12. extraction, retrieval, poisoning, privacy, and fallback evals pass.
