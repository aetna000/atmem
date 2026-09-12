# Current implementation status

Verification history is retained in the [per-feature evidence journal](implementation-evidence/README.md).
This page is a maintained capability summary; new test runs create immutable
journal entries, and summary changes link to the relevant evidence. Dated
reviews under `specs/` remain historical snapshots.

Updated: 13 September 2026

Repository metadata is **2.3.0b1** and the matched OpenClaw bridge is
**2.3.0-beta.1**. Those values identify the current source build, not a
release-ready candidate: the standalone full-fidelity M0 profile is reopened
and its gates remain incomplete. Package and tag availability must be checked
independently. Native AtMem authority remains the default after installation
or upgrade. The required `atmem-atbot==0.1.0a6` companion is packaged
separately and installed automatically with AtMem.

## 2.3.0b1 investigation preview — reopened, not release-ready

The earlier M0 source slice implements producer-sequenced, content-minimizing
execution capture with a bounded persistent OpenClaw spool, durable
acknowledgement, idempotent replay, conflict retention, explicit capacity and
retention gaps, event/receive timestamps, indexed scope-filtered reads, and
deterministic evidence-linked findings in the existing Activity/Evidence UI.
That slice is a legacy foundation, not the revised Agent Black Box: it cannot
reconstruct exact prompts, context, model exchanges, calls/results or original
multimodal artifacts after the agent and logs are gone. The implementation
preserves 2.2.x Black Box chains and does not activate task
state, change canonical memory, or require AtBot for investigation.

The revised source now contains the first Spec 028 vertical slice: AES-256-GCM
exact evidence objects with encrypted semantic metadata and access audit,
default full/data-plus-metadata capture, encrypted metadata-only and recorder-off
modes, Viewer/Investigator/Evidence Collector enforcement, Collector-only
confirmed plaintext export, optional ML-KEM-768/ML-DSA-65 recipient bundles,
three explicit development test identities, encrypted OpenClaw spool content,
exact prompt/context/model/tool capture and bounded exact inbound media bytes.
The compatible legacy evidence projection remains content-minimizing and its entire
control database is now stored as an application-encrypted container. Other memory,
mirror, backup or historical plaintext sources still require inventory and verified
cleanup before an installation can make a product-wide encrypted-store claim.

This is not yet the complete encrypted evidence-box release gate. Spec 020
T042–T053, Spec 021 T025–T028, Spec 022 T026–T029 and the remaining Spec 028
rotation/recovery, migration and verified legacy cleanup, capacity, secure production key-source,
cross-platform installed-artifact, complete rendering and destructive
stolen-store/dead-agent gates remain open. Until those pass, no source, wheel,
tag or dashboard should claim complete full-fidelity Black Box readiness.

Core identity, replay/restart, scope, loss, late-recovery, 40-minute virtual
trace, retention and 100,000-event lookup gates are recorded in the
[Spec 020 M0 evidence](implementation-evidence/020/20260912-m0-investigation-preview.md).
The tag-blocking timestamp, identity, replay, receipt, paging, coverage and
presentation corrections are recorded in the
[Spec 020 correctness-hardening evidence](implementation-evidence/020/20260912-release-candidate-correctness-hardening.md).
The technical findings/UI results are recorded separately in
[Spec 021 M0 evidence](implementation-evidence/021/20260912-m0-findings-ui.md).
The installed-host record names the exact local OpenClaw and bridge artifacts;
other hosts remain unverified. Independent two-cohort human usability is not
claimed and remains tracked by 021 T024.

Spec 003's 2.2.6 local identity and tool-observation fixes pass real Mem0/Claude
CLI acceptance on latest OpenClaw 2026.9.2 and 2026.9.3. Inject/withhold, exact
digests/deliveries, default-owner refusal, successful/error tool closure and
missing-result refusal are recorded in the [latest-host evidence](implementation-evidence/003/20260909T052000Z-740c5c89d63c-mem0-latest-hosts.md).
Identity role-play passes. The Storizon operator separately reports the same
host matrix passing against the published 2.2.6 artifacts, including v2 receipts
and toolful closure; this is retained as attributed partner evidence. Live
shared-channel authentication remains unverified. See the
[compatibility matrix](context-provider-adapters.md#226-delegated-host-compatibility).

The release has four runtime boundaries:

1. AtMem's model-agnostic authority engine and canonical SQLite memory;
2. the host-neutral control, evidence, and adapter contracts;
3. automated host/framework adapters;
4. the separately packaged, headless AtBot intelligence companion, reached only
   through a versioned loopback protocol.

## 2.2 baseline capabilities

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
| Raw prompt/response/tool evidence | Protected-vault producer contract implemented; automatic boundary coverage remains adapter-specific | OpenClaw source captures exact prompt/context/model/tool values into the encrypted vault; installed-host release gate remains open |
| Semantic answer validation | Not implemented | Not implemented |
| Independent external outcome proof | Accepts linked receipts; external verifier required | Same |
| Hosted multi-tenant authentication and isolation | Not provided | Not provided |

## Packaging and runtime status

- `pyproject.toml` requires exactly `atmem-atbot==0.1.0a6`. The PyPI
  distribution is `atmem-atbot`; its Python import and command remain `atbot`.
- AtBot source lives under `packages/atbot`; it is a separately released
  distribution and process and does not own canonical storage.
- AtBot's built-in Ollama and OpenAI-compatible provider uses the standard
  library and adds no model-SDK dependency to a default AtMem install.
- A clean supported installation resolves the published companion automatically.
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

- The 2.2.6 release workflow created persisted data with public AtMem 2.1.0, 2.2.3,
  2.2.4, and 2.2.5, upgraded each environment to 2.2.6, and verified record identity, recall, audit
  integrity, control migration identity, candidate retention, schema migration,
  and automatic vector-sidecar creation as a protected publication gate.
- The 2.3.0b1 candidate additionally migrates control evidence schema v5 to v6
  without rewriting signed events and verifies a clean installed candidate
  artifact against a published 2.2.6 starting point.
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
