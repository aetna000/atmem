# Feature Specification: Delegated Context-Provider Adapters

**Feature directory**: `specs/004-context-provider-adapters`  
**Created**: 2026-09-04  
**Status**: Implemented  
**Input**: Provide supported adapters that let Mem0, LangGraph, or Pydantic AI remain the context-decision authority while AtMem verifies the signed decision, delivers accepted context exactly once, and records flight evidence.

## Overview

AtMem 2.2.6b2 exposes a provider-neutral delegated context contract, but an
operator currently has to build the provider-side service. This feature makes
that path practical for three common choices: a Mem0 memory deployment, an
operator-defined LangGraph workflow, and a typed Pydantic AI decision agent.

Each adapter receives an AtMem turn request, asks only its configured provider
to select context or withhold it, normalizes that outcome, and returns a signed
v1 envelope. AtMem remains responsible for trusted registration, scope and turn
validation, replay protection, byte-exact host delivery, duplicate-injection
suppression, and evidence. Native AtMem authority remains the default.

## Clarifications

### Session 2026-09-04

- Q: How should the three adapters be packaged? → A: Ship them as independent
  optional AtMem extras: `atmem[mem0]`, `atmem[langgraph-provider]`, and
  `atmem[pydantic-provider]`.

## User Scenarios and Acceptance

### User Story 1 — Use Mem0 with OpenClaw and AtMem verification (P1)

As an existing Mem0 and OpenClaw operator, I can start a local adapter, register
its public key and exact scope with AtMem, and keep Mem0 responsible for
selecting context while AtMem verifies and records delivery.

**Independent test**: Start the adapter with a fake or local Mem0-compatible
client, submit a bound request containing a paraphrased preference question,
and verify that the signed context contains only the returned Mem0 memories and
that AtMem accepts and delivers the exact bytes once.

**Acceptance scenarios**:

1. A successful Mem0 search produces an `inject` decision containing bounded,
   deterministic context and source memory identifiers.
2. No useful Mem0 result produces a signed `withhold` decision rather than
   invented context.
3. Mem0 timeout, authentication failure, malformed results, or unavailable SDK
   produces a safe provider error; AtMem's configured failure policy decides
   whether to withhold or use explicitly enabled native fallback.
4. Different users, agents, or workspaces cannot reuse a decision or receipt.

### User Story 2 — Use a LangGraph workflow as context authority (P1)

As a LangGraph developer, I can wrap a compiled graph or compatible callable
whose final state chooses context or withholding without replacing the graph's
state, checkpoints, tools, or model configuration.

**Independent test**: Invoke a deterministic graph with the AtMem request state,
return an inject decision, and verify the graph output becomes one signed v1
response without a second retrieval or injection.

**Acceptance scenarios**:

1. The adapter supplies the full bound request to the configured workflow using
   documented, versioned state keys.
2. Sync and async workflows can return a typed inject or withhold proposal.
3. Missing, ambiguous, oversized, or unknown output fields fail closed.
4. The adapter does not mutate operator-owned graph state or checkpoint data.

### User Story 3 — Use a Pydantic AI agent as context authority (P1)

As a Pydantic AI developer, I can use a typed decision agent to select exact
context or withhold it, with model choice and egress remaining explicit.

**Independent test**: Run a deterministic Pydantic AI test model returning the
typed decision schema and verify the adapter signs only validated output and
records provider/model attribution without exposing secrets.

**Acceptance scenarios**:

1. The agent receives a bounded representation of the delegated request and
   produces a schema-validated decision.
2. Model or validation failure cannot result in unsigned, partial, or guessed
   context.
3. Provider and model identity are observable without logging API keys, raw
   credentials, or unnecessary prompt content.
4. Local and hosted model configurations use the same adapter contract.

### User Story 4 — Operate every adapter consistently (P1)

As an operator, I can generate signing material, start, inspect, diagnose, and
stop any supported adapter with consistent commands and clear next actions.

**Independent test**: Use each adapter's CLI path from a clean environment,
confirm readiness on a numeric loopback endpoint, register it with AtMem, run a
signed test request, and shut it down without changing native AtMem data.

**Acceptance scenarios**:

1. Setup prints the exact AtMem registration command while never printing the
   private key or an API secret.
2. Status distinguishes missing dependency, invalid configuration, stopped,
   ready, and provider failure.
3. Adapters bind to loopback by default and reject public listening unless a
   future separately approved transport specification permits it.
4. Removing an adapter configuration does not delete provider-owned memory or
   historical AtMem evidence.

## Functional Requirements

- **FR-001**: The product MUST provide provider-side adapters for Mem0,
  LangGraph, and Pydantic AI that emit the existing closed
  `atmem.delegated-context-provider.v1` result contract.
- **FR-002**: All adapters MUST share one request parser, decision model,
  canonical serializer, Ed25519 signer, bounded loopback server, and lifecycle
  interface so security behavior cannot drift by provider.
- **FR-003**: The adapters MUST preserve the exact AtMem request binding fields
  for run, turn, session, agent, workspace, and user, then generate a fresh
  nonce and deterministic idempotency key bound to the signed v1 result.
- **FR-004**: An adapter MUST return either one validated `inject` decision or
  one validated `withhold` decision; absence, ambiguity, or provider failure
  MUST NOT create context.
- **FR-005**: Injected context MUST be deterministic UTF-8 bytes with enforced
  item-count and byte limits, a matching SHA-256 digest, and no truncation that
  can produce malformed evidence.
- **FR-006**: Signing keys MUST be generated and stored with owner-only
  permissions; the private key MUST never enter AtMem registration, status,
  logs, receipts, or provider responses.
- **FR-007**: Each adapter MUST expose provider identity, adapter version,
  instance ID, key ID, health, latency, decision, and provider/model attribution
  without exposing secrets or unnecessary raw content.
- **FR-008**: The Mem0 adapter MUST support an injected compatible client for
  tests and a documented optional Mem0 SDK installation for real deployments.
- **FR-009**: The Mem0 adapter MUST map authenticated AtMem user, agent, and
  workspace scope to configured Mem0 filters and MUST NOT silently drop those
  boundaries.
- **FR-010**: The LangGraph adapter MUST support sync and async compiled graphs
  or compatible callables through a closed input/output state contract.
- **FR-011**: The LangGraph adapter MUST preserve operator-owned workflow state,
  checkpointing, tools, and model selection and MUST reject unknown final
  decision fields.
- **FR-012**: The Pydantic AI adapter MUST use typed structured output and
  support dependency injection so deterministic tests do not require network
  or model credentials.
- **FR-013**: The Pydantic AI adapter MUST make local versus hosted model use and
  resulting egress visible before startup.
- **FR-014**: Base AtMem installation MUST remain free of mandatory Mem0,
  LangGraph, Pydantic AI, model-provider, or web-framework dependencies. The
  adapters MUST ship as independent `atmem[mem0]`,
  `atmem[langgraph-provider]`, and `atmem[pydantic-provider]` optional extras,
  and missing extras MUST produce actionable installation guidance.
- **FR-015**: Native AtMem retrieval MUST remain the default, and installing an
  adapter MUST NOT register or enable delegated authority automatically.
- **FR-016**: AtMem MUST continue to validate trust, scope, time, signature,
  digest, size, identity, replay, and exact delivery independently of adapter
  claims.
- **FR-017**: The CLI and documentation MUST provide copyable end-to-end paths
  for Mem0 + OpenClaw, LangGraph, and Pydantic AI, including safe disable and
  rollback commands.
- **FR-018**: Every adapter MUST pass the same positive, negative, replay,
  concurrency, privacy, poisoning, timeout, and oversized-response conformance
  suite before it is advertised as supported.
- **FR-019**: Python 3.10–3.13 and Apache-2.0-compatible dependency licensing
  MUST be preserved.
- **FR-020**: This feature MUST NOT import provider memory into AtMem, make the
  adapter a canonical store, change existing v1 wire fields, or add a second
  customer dashboard.

## Data and Contract Boundaries

- **Delegated request**: the existing closed v1 request received from AtMem.
- **Provider proposal**: an internal typed inject/withhold result that is not
  trusted until validated, canonicalized, and signed.
- **Signed provider result**: the existing closed v1 result returned to AtMem.
- **Provider-owned state**: Mem0 records, LangGraph checkpoints, or Pydantic AI
  dependencies remain outside AtMem and are never silently copied.
- **Adapter configuration**: provider kind, instance/key identity, loopback
  endpoint, limits, and secret environment-variable names; no secret values.

## Failure and Edge Cases

- Provider output repeats, omits, or contradicts a binding supplied by AtMem.
- Mem0 returns duplicate, deleted, cross-user, unscoped, or unexpectedly shaped
  search results.
- A graph returns both context and withhold, mutates its input, blocks past the
  deadline, or resumes a stale checkpoint.
- A model emits invalid structured output, prompt injection, excessive content,
  or a context claim unsupported by its configured sources.
- The same nonce or idempotency key arrives concurrently or after expiry.
- A key is missing, has unsafe permissions, rotates, or does not match AtMem's
  registered public key.
- The adapter starts successfully but its optional provider dependency or
  credential is unavailable.

## Out of Scope

- Making Mem0, LangGraph, or Pydantic AI a canonical AtMem store.
- Importing or migrating provider-owned memories.
- Remote/public provider transport, multi-tenant server authentication, or TLS.
- Modifying the delegated context v1 wire contract.
- Automatically enabling delegated authority during installation.
- Building a separate provider dashboard or independent-agent product mode.

## Success Criteria

- **SC-001**: One documented command path starts each configured adapter on
  loopback and `atmem delegated doctor` reports `ready` after explicit
  registration and enablement.
- **SC-002**: All three adapters pass every shared conformance vector, including
  invalid shape, cross-scope, replay, timeout, poisoning, privacy, and oversized
  output cases.
- **SC-003**: Accepted inject decisions are delivered byte-for-byte once; signed
  withhold decisions and default failures deliver zero context.
- **SC-004**: Native AtMem and all existing OpenClaw, Pydantic AI host-adapter,
  LangGraph host-adapter, restore, multi-agent, evidence, and deletion tests
  remain green when provider adapters are absent.
- **SC-005**: A clean base install has no provider SDK installed and still
  operates normally; each optional extra installs independently without
  dependency conflicts.
- **SC-006**: Private keys, API keys, and provider credentials have zero
  occurrences in CLI status, logs, signed envelopes, AtMem evidence, and test
  snapshots.
- **SC-007**: A first-time operator can follow each quick start without editing
  AtMem internals and can return to native authority with one disable command.
- **SC-008**: Adapter overhead excluding provider execution is measured, with a
  local p95 target below 25 ms across at least 100 deterministic requests.
