# Implementation Plan: Delegated Context-Provider Adapters

## Technical Context

- **Runtime**: Python 3.10–3.13.
- **Existing boundary**: AtMem already sends
  `atmem.delegated-context-request.v1` over bounded loopback HTTP and verifies
  `atmem.delegated-context-provider.v1` responses.
- **Packaging**: provider implementations live in AtMem but SDKs install only
  through `atmem[mem0]`, `atmem[langgraph-provider]`, or
  `atmem[pydantic-provider]`.
- **Dependencies**: `cryptography` remains the only signing dependency in the
  base package. Optional extras use `mem0ai`, `langgraph`, and
  `pydantic-ai-slim`; model-provider packages remain operator choices.
- **Official API basis**:
  - Mem0 `search(query, filters=...)` with entity IDs inside filters;
  - LangGraph/Pregel `invoke` and `ainvoke` with caller-owned configuration;
  - Pydantic AI `Agent(..., output_type=...)` and validated
    `AgentRunResult.output`.
- **Transport**: numeric loopback HTTP only, no redirects, closed request and
  response shapes, bounded body size, deadline-aware execution.
- **Persistence**: provider keys/configuration/PID state are provider-runtime
  files, not canonical AtMem memory. Existing AtMem delegated trust remains the
  only activation source of truth.

## Constitution Check

- **Authority Before Intelligence**: delegated mode is already the named
  exception where the external provider owns the decision. Adapters cannot
  write AtMem memory, enable delegation, or bypass AtMem verification.
- **Provenance and Exact Evidence**: context bytes, source references, receipt,
  signing digest, and full turn binding enter the signed v1 envelope.
- **Safe Defaults and Reversibility**: setup and start do not enable authority;
  provider errors return no unsigned result and AtMem fails closed unless its
  separate native fallback was explicitly configured.
- **Scope and Privacy**: Mem0 requires all three mapped boundaries; graph and
  agent receive the authenticated binding unchanged. Status excludes secrets
  and raw context.
- **Contract-First Host Neutrality**: one runtime serves all implementations and
  depends only on the existing provider-neutral v1 contract.
- **Executable Claims**: shared contract, adapter, server, CLI, clean-extra,
  security, concurrency, performance, and regression tests gate completion.
- **Local-First and Explicit Egress**: the runtime binds locally; Mem0 platform
  and hosted Pydantic models require explicit configuration and report egress.

No constitution exception is required.

## Architecture

```text
AtMem / host adapter
  → closed delegated request over loopback
  → shared provider runtime
      → Mem0 adapter OR LangGraph adapter OR Pydantic AI adapter
      → typed inject/withhold proposal
      → deterministic context builder
      → receipt + time window + nonce + idempotency key
      → Ed25519 signer
  → closed signed v1 result
  → existing AtMem verification, reservation, delivery and evidence
```

The shared runtime owns protocol mechanics only. Provider adapters own selection
logic. AtMem owns trust and delivery verification. A provider exception never
falls through to a fabricated signed decision; the HTTP request fails and the
existing AtMem failure policy runs.

## Design Decisions

### 1. Shared provider SDK and runtime

Create `atmem/provider_adapters/` with:

- `models.py`: strict `ProviderRequest`, `ProviderProposal`, `ContextItem`, and
  `ProviderRuntimeIdentity` dataclasses with closed parsing and validation;
- `signing.py`: Ed25519 key generation/loading, owner-only permission checks,
  receipt creation, canonical envelope construction, idempotency calculation,
  and signing using existing canonical helpers;
- `runtime.py`: sync/async provider invocation, deadline enforcement,
  deterministic byte construction, metrics, and safe error translation;
- `server.py`: bounded `ThreadingHTTPServer` handler restricted to numeric
  loopback addresses and the exact v1 path;
- `lifecycle.py`: private config/PID files plus start, foreground serve, stop,
  status, and doctor operations;
- `loading.py`: safe `module:attribute` loading for operator-owned graph/agent
  factories without evaluating arbitrary configuration text.

The runtime accepts dependency-injected providers in code and factory paths in
CLI. Unit tests therefore require no external service, SDK, API key, or model.

### 2. Deterministic context and proposal contract

The internal proposal shape is closed:

```text
decision: inject | withhold
items: ordered ContextItem[]
source_refs: ordered unique opaque IDs (maximum 32)
withhold_reason: {code, retryable} | null
metadata: bounded operational attribution, never emitted as context
```

For `inject`, the context builder serializes ordered items into a stable,
human-readable memory block, escapes structural delimiters, normalizes neither
item content nor final bytes, and admits whole items only until the request's
byte limit. Empty output becomes `withhold`. It never cuts a UTF-8 sequence or
partially includes an item. The signer hashes those final bytes.

The receipt body is not returned or persisted by AtMem. Its digest covers the
provider identity, binding, query digest, decision, final context digest,
source references, adapter kind/version, and provider/model attribution. The
envelope carries only receipt ID, receipt contract ID, and digest.

### 3. Mem0 provider

`Mem0ContextProvider` accepts either an injected object with `search`/async
`search`, or creates an OSS/platform client when the extra is installed.

Scope mapping is mandatory and closed:

```text
AtMem user_id      → Mem0 user_id
AtMem agent_id     → Mem0 agent_id
AtMem workspace_id → Mem0 app_id
```

The adapter calls `search(query, filters=..., top_k=...)`; it never retries
without filters. Both documented `{results: [...]}` and list response
containers are normalized. Each selected result must have a nonempty memory
text and opaque ID; duplicates, malformed rows, overlong items, and rows whose
returned entity fields contradict the binding are rejected. No useful result
returns `NO_USEFUL_MEMORY` withholding.

Platform egress is explicit via a mode/config flag and secret environment
variable name. Secret values are read only by the provider process.

### 4. LangGraph provider

`LangGraphContextProvider` wraps a compiled graph or compatible callable. It
passes a fresh closed input dictionary under `delegated_request` and provides a
thread ID derived from the bound turn in a fresh config object. It does not
reuse or mutate caller dictionaries.

It supports `invoke`, `ainvoke`, ordinary sync callables, and async callables.
The final output must contain exactly one `context_decision` matching the closed
proposal schema. LangGraph v2 `GraphOutput.value` is supported without relying
on deprecated dict access. Interrupts, missing decisions, or extra decision
fields fail closed.

### 5. Pydantic AI provider

`PydanticAIContextProvider` wraps an injected agent. A helper creates an agent
with the adapter's strict Pydantic output model when Pydantic AI is installed;
operators may instead provide their own compatible agent factory.

The adapter supports `run_sync` and `run`, reads only validated `result.output`,
and converts it to the shared proposal. Dependencies are passed through an
operator factory rather than owned by AtMem. Status reports local/hosted egress,
provider, and model identifiers supplied by configuration. TestModel or an
injected fake provides deterministic offline coverage.

### 6. CLI and lifecycle

Add a top-level `atmem provider` command family:

```text
atmem provider init --kind mem0|langgraph|pydantic-ai ...
atmem provider serve <instance>              # foreground
atmem provider start <instance>              # managed background process
atmem provider stop <instance>
atmem provider status [<instance>] [--json]
atmem provider doctor <instance> [--json]
atmem provider remove <instance> --yes
```

`init` generates an owner-only Ed25519 private key and base64 public-key file,
writes secret-free provider configuration, and prints a copyable
`atmem delegated register` command. It never registers or enables delegation.
`doctor` sends a local health request and explains missing extras, factory
errors, credentials, unsafe permissions, port conflicts, and AtMem's next
registration/enable step.

Configuration lives under `~/.atmem/providers/<instance>/` by default and can
be redirected in tests. Private key and config are mode `0600`; directories are
`0700`; symlinks and unsafe ownership/permissions fail closed. PID state is
validated before signals are sent, and stop targets only the recorded provider
process.

### 7. Packaging and compatibility

Add these independent extras:

```toml
mem0 = ["mem0ai>=1,<2"]
langgraph-provider = ["langgraph>=1.1.5,<2"]
pydantic-provider = ["pydantic-ai-slim>=2,<3", "pydantic>=2,<3"]
```

The existing `pydantic-ai`, `langgraph`, and `frameworks` extras remain host
adapter compatibility aliases. Importing `atmem` or using native delegated
verification never imports optional SDKs. No SQLite migration or wire-contract
change is planned.

## File Structure

```text
atmem/provider_adapters/
  __init__.py
  models.py
  signing.py
  runtime.py
  server.py
  lifecycle.py
  loading.py
  mem0.py
  langgraph.py
  pydantic_ai.py
tests/
  test_provider_runtime.py
  test_mem0_provider.py
  test_langgraph_provider.py
  test_pydantic_provider.py
  test_provider_cli.py
docs/
  context-provider-adapters.md
specs/004-context-provider-adapters/
  spec.md
  plan.md
  tasks.md
```

Existing files changed: `atmem/cli.py`, `pyproject.toml`, `README.md`,
`docs/delegated-context-provider.md`, `docs/capabilities.json`,
`docs/current-status.md`, `tests/test_documentation.py`, and release/CI scripts
only if required by packaging validation. The v1 schemas remain unchanged.

## Test Strategy

1. **Shared contract**: request parsing, query digest/deadline, deterministic
   bytes, receipt digest, signature verification, time window, nonce,
   idempotency, item/byte limits, and withhold semantics.
2. **Mem0**: OSS/platform response shapes, exact three-axis filters, no
   filter-dropping fallback, duplicate/malformed/cross-scope rows, empty
   results, async client, timeout, credentials, and missing extra.
3. **LangGraph**: invoke/ainvoke/callables, v1 dict and v2 output objects,
   immutable input/config, checkpoint thread binding, interrupt, unknown/mixed
   decisions, timeout, and missing extra.
4. **Pydantic AI**: structured output, sync/async runs, injected deterministic
   agent, invalid output, usage attribution, local/hosted egress display,
   timeout, and missing extra.
5. **Server/lifecycle**: loopback/path/method/content-type/body limits,
   concurrent requests, slow provider, safe files, PID validation, start/stop,
   status/doctor, secret redaction, and exact registration command.
6. **AtMem integration**: each adapter's envelope passes existing verifier and
   delivery reservation; altered scope/signature/context/replay fails; no
   native double injection occurs.
7. **Packaging**: clean base and each independent extra; current host adapter
   extras; Python 3.10–3.13; dependency and license checks.
8. **Performance**: at least 100 deterministic runtime-only requests with local
   p95 below 25 ms, excluding provider execution and network scheduling.
9. **Regression**: full Python, OpenClaw prepack, native/delegated, restore,
   multi-agent, evidence, deletion, and documentation suites.

## Rollout and Rollback

- Ship behind explicit provider initialization plus existing delegated trust
  registration and enablement; installation alone changes no authority mode.
- Operators roll back immediately with
  `atmem delegated disable <registration-id>`, then stop/remove the provider.
- Provider removal retains AtMem historical authorization/delivery evidence and
  does not modify Mem0 memory, graph checkpoints, or agent dependencies.
- No persisted canonical-memory migration is needed. Provider configuration is
  additive and removable.

