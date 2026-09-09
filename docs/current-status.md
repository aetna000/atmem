# Current implementation status

Verification history is retained in the [per-feature evidence journal](implementation-evidence/README.md).
This page is a maintained capability summary; new test runs create immutable
journal entries, and summary changes link to the relevant evidence. Dated
reviews under `specs/` remain historical snapshots.

Updated: 9 September 2026

Repository metadata is **2.2.7b1** and the matched OpenClaw bridge is
**2.2.7-beta.1**. This repository state is the release candidate; package and
tag availability must be checked independently until the release workflow has
published them. Native AtMem authority remains the default after installation
or upgrade. The required `atmem-atbot==0.1.0` companion is packaged
separately and installed automatically with AtMem.

Spec 003's 2.2.6 local identity and tool-observation fixes pass real Mem0/Claude
CLI acceptance on latest OpenClaw 2026.9.2 and 2026.9.3. Inject/withhold, exact
digests/deliveries, default-owner refusal, successful/error tool closure and
missing-result refusal are recorded in the [latest-host evidence](implementation-evidence/003/20260909T052000Z-740c5c89d63c-mem0-latest-hosts.md).
Identity role-play passes; live shared-channel authentication and independent
Storizon verification remain unverified. See the [compatibility matrix](context-provider-adapters.md#226-delegated-host-compatibility).

The release has four runtime boundaries:

1. AtMem's model-agnostic authority engine and canonical SQLite memory;
2. the host-neutral control, evidence, and adapter contracts;
3. automated host/framework adapters;
4. the separately packaged, headless AtBot intelligence companion, reached only
   through a versioned loopback protocol.

## 2.2 capabilities

| Capability | Generic/framework runtimes | OpenClaw |
| --- | --- | --- |
| SQLite memory, provenance, lifecycle, deletion, hash-chained audit | Implemented | Implemented |
| Always-created derived vector sidecar | Implemented for persistent memory; dependency-free local hashing baseline | Implemented for every mirror workspace |
| Governed lexical, fact-key, graph, semantic, trust and recency fusion | Implemented | Implemented |
| AtBot content-free expansion and eligible-candidate reranking | Implemented with deterministic fallback | Implemented with deterministic fallback |
| AtBot-assisted typed extraction followed by AtMem admission | Implemented for authenticated capture | Implemented through the adapter capture path |
| Candidate authorization before AtBot and ID revalidation afterward | Implemented | Implemented |
| Byte-stable context preparation and exact exposure receipt | Implemented by contract | Implemented by bridge hooks |
| Pydantic AI and LangChain/LangGraph automatic lifecycle adapters | Packaged optional adapters | Not applicable; OpenClaw uses its bridge |
| Shared calibrated direct/background/no-useful retrieval decision | Dashboard, control, Pydantic AI, LangGraph, governed MCP | Native OpenClaw control path |
| Delegated exact-byte context delivery | Pydantic AI and LangChain/LangGraph | OpenClaw bridge |
| Governed Task State revisions, lifecycle, provenance, expiry, and safe context | Exact-ID delivery through packaged adapters | Exact-ID delivery when OpenClaw supplies `taskId` |
| AtBot task observation proposals with AtMem revalidation | Implemented through the loopback companion | Same authority boundary |
| Task dashboard and complete task CLI | Implemented | Same dashboard and CLI |
| Typed text observations of host-controlled media | Implemented; host retains bytes | Implemented; OpenClaw retains bytes |
| Shadow mode without context influence | Implemented by contract | Automated and verified |
| Explicit active mode and return to shadow | Implemented by contract | Automated |
| Native-memory discovery, historical copy, and continued file sync | Host responsibility | Automated |
| Exact native configuration/file restore | Host responsibility | Automated and verified |
| Model, context, tool, and turn flight events | Implemented when host emits them | Automated bridge hooks |
| Persistent shared, isolated, and nested workspace scopes | Explicit registration | Automatic discovery and mirror binding |
| Memory chat, provenance, storage, review, audit, topology and flight UI | One loopback dashboard | Same dashboard |
| AtBot provider/model/lifecycle configuration | Collapsed dashboard settings and CLI | Same dashboard and CLI |
| Optional signed delegated context authority | Provider-neutral control contract; host must prove exact delivery | Implemented for compatible local providers; disabled by default |
| Optional provider-side Mem0, LangGraph, and Pydantic AI adapters | Independent extras; shared signed loopback runtime; disabled until separately trusted | Available to any host using the delegated contract |
| Raw prompt/response/tool evidence | Not stored by default | Not stored by Black Box |
| Semantic answer validation | Not implemented | Not implemented |
| Independent external outcome proof | Accepts linked receipts; external verifier required | Same |
| Hosted multi-tenant authentication and isolation | Not provided | Not provided |

## Packaging and runtime status

- `pyproject.toml` requires exactly `atmem-atbot==0.1.0`. The PyPI
  distribution is `atmem-atbot`; its Python import and command remain `atbot`.
- AtBot source lives under `packages/atbot`; it is a separately released
  distribution and process and does not own canonical storage.
- AtBot's built-in Ollama and OpenAI-compatible provider uses the standard
  library and adds no model-SDK dependency to a default AtMem install.
- A clean 2.2 installation resolves the published companion automatically.
  Repository development installs both packages explicitly with editable
  installs.
- Publishing uses the dedicated trusted-publisher workflow documented in
  [Publishing the AtBot companion](atbot-release.md); no PyPI token belongs in
  repository or service configuration.
- AtMem recommends a hardware-compatible local embedding profile during
  onboarding, but model download and activation remain explicit. Local Ollama,
  loopback OpenAI-compatible, named hosted providers, custom HTTPS, or
  deterministic fallback remain operator choices. Configuration stores an
  API-key environment-variable name, never the secret value.
- The dashboard renews one expired local CSRF session and retries once; it
  remains loopback-only and has no hosted authentication layer.
- `atmem[mem0]`, `atmem[langgraph-provider]`, and
  `atmem[pydantic-provider]` are independent provider-side extras. They do not
  alter the base import graph or the existing host-side framework adapters.
  The Mem0 extra supports and continuously checks the current Python 2.x SDK
  contract (`mem0ai>=2.0.20,<3`) for both OSS and Platform scoped search.

## Exact claim boundary

- AtMem verifies retained canonical state, derived-index bindings, memory and
  evidence chains, and closure/correlation of events a runtime reports.
- In native mode, semantic or AtBot output may nominate and order records but
  cannot admit, authorize, promote, correct, forget, or inject memory. In the
  separately named delegated mode, a scoped provider authorizes context while
  AtMem enforces trust, binding, replay, exact delivery, and evidence contracts.
- A generic integration cannot independently prove that its host truthfully
  injected context or completed an external action.
- OpenClaw is the only adapter in this repository that automates native-state
  discovery, migration, hooks, activation, and exact restore.
- A SaaS deployment must add authentication, tenant isolation, retention,
  credential management, and system-of-record outcome verification.

## Upgrade and support status

- The release workflow creates persisted data with public AtMem 2.1.0, 2.2.3,
  2.2.4, and 2.2.5, upgrades each environment to 2.2.7b1, and verifies record identity, recall, audit
  integrity, control migration identity, candidate retention, schema migration,
  and automatic vector-sidecar creation as a protected publication gate.
- Existing OpenClaw installations upgrade the bridge with
  `atmem openclaw upgrade`; the command preserves shadow or active mode, restarts
  a running dashboard under the upgraded isolated Python runtime, restarts the
  gateway, runs a test flight, and restores the previous bridge on failure. The
  command remains safe to rerun when the bridge is already current.
- OpenClaw 2026.7.1-2, 2026.8.1 and 2026.9.2 are tested declaration-shape
  versions; the locked 2026.8.1 bridge suite also exercises runtime hooks. On OpenClaw 2.0
  (2026.8.1), the managed installer supplies the host's explicit third-party
  capability-consent flags for the exact pinned bridge.
- The framework gate exercises Pydantic AI 2.36.0, LangChain 1.3.18, and
  LangGraph 1.2.11 together in a clean environment. Package bounds permit
  compatible later releases within the same major generation.
- Python 3.10 through 3.13, the AtBot wheel, the AtMem wheel, and the npm bridge
  are tested by the release workflow.
- The exact trust and hosted-service limitations above remain product boundaries,
  not hidden release claims.

The 2.2.7b1 beta includes selective automatic context, improved evidence
diagnostics, precise local timestamps and the dashboard colour legend. See
[release notes](releases/v2.2.7b1.md) for configuration changes and limitations.
