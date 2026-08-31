# Current implementation status

Updated: 31 August 2026

Repository metadata remains version **2.1.0**. The `atbot` branch is unreleased
**2.2 development**; none of the 2.2 items below should be described as present
in the published `atmem==2.1.0` package.

The development implementation has four runtime boundaries:

1. AtMem's model-agnostic authority engine and canonical SQLite memory;
2. the host-neutral control, evidence, and adapter contracts;
3. automated host/framework adapters;
4. the separately packaged, headless AtBot intelligence companion, reached only
   through a versioned loopback protocol.

## 2.2 development capabilities

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
| Typed text observations of host-controlled media | Implemented; host retains bytes | Implemented; OpenClaw retains bytes |
| Shadow mode without context influence | Implemented by contract | Automated and verified |
| Explicit active mode and return to shadow | Implemented by contract | Automated |
| Native-memory discovery, historical copy, and continued file sync | Host responsibility | Automated |
| Exact native configuration/file restore | Host responsibility | Automated and verified |
| Model, context, tool, and turn flight events | Implemented when host emits them | Automated bridge hooks |
| Persistent shared, isolated, and nested workspace scopes | Explicit registration | Automatic discovery and mirror binding |
| Memory chat, provenance, storage, review, audit, topology and flight UI | One loopback dashboard | Same dashboard |
| AtBot provider/model/lifecycle configuration | Collapsed dashboard settings and CLI | Same dashboard and CLI |
| Raw prompt/response/tool evidence | Not stored by default | Not stored by Black Box |
| Semantic answer validation | Not implemented | Not implemented |
| Independent external outcome proof | Accepts linked receipts; external verifier required | Same |
| Hosted multi-tenant authentication and isolation | Not provided | Not provided |

## Packaging and runtime status

- `pyproject.toml` requires exactly `atmem-atbot==0.1.0a1` on this development
  branch. The PyPI distribution is `atmem-atbot`; its Python import and command
  remain `atbot`.
- AtBot source lives under `packages/atbot`; it is a separately released
  distribution and process and does not own canonical storage.
- A clean 2.2 package installation can resolve the dependency only after the
  matching AtBot distribution is published. Repository development installs
  both packages explicitly with editable installs.
- Publishing uses the dedicated trusted-publisher workflow documented in
  [Publishing the AtBot companion](atbot-release.md); no PyPI token belongs in
  repository or service configuration.
- Model choice is never automatic. Local Ollama, loopback OpenAI-compatible,
  named hosted providers, custom HTTPS, or deterministic fallback are explicit
  choices. Configuration stores an API-key environment-variable name, never the
  secret value.
- The dashboard renews one expired local CSRF session and retries once; it
  remains loopback-only and has no hosted authentication layer.

## Exact claim boundary

- AtMem verifies retained canonical state, derived-index bindings, memory and
  evidence chains, and closure/correlation of events a runtime reports.
- Semantic or AtBot output may nominate and order records but cannot admit,
  authorize, promote, correct, forget, or inject memory.
- A generic integration cannot independently prove that its host truthfully
  injected context or completed an external action.
- OpenClaw is the only adapter in this repository that automates native-state
  discovery, migration, hooks, activation, and exact restore.
- A SaaS deployment must add authentication, tenant isolation, retention,
  credential management, and system-of-record outcome verification.

## Remaining 2.2 release work

- publish the matching AtBot distribution before publishing AtMem 2.2;
- freeze and document every public protocol response and migration boundary;
- add deletion acknowledgements for AtBot caches and temporary state;
- finish performance, crash-recovery, migration, hostile-adapter, and supported
  Python/encryption test matrices;
- produce 2.2 release notes and perform a clean copied-data upgrade/restore drill.
