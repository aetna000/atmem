# Current implementation status

Repository metadata is version 2.1.0. The implementation has three layers:
the model-agnostic memory engine, the host-neutral control/evidence contract,
and automated host adapters.

| Capability | Generic runtime | OpenClaw |
| --- | --- | --- |
| SQLite memory, provenance, lifecycle, deletion, hash-chained audit | Implemented | Implemented |
| Lexical, graph, and optional semantic search | Implemented | Implemented |
| Typed text observations of host-controlled media | Implemented; host retains bytes | Implemented; OpenClaw retains bytes |
| Shadow mode without context influence | Implemented by contract | Automated and verified |
| Explicit active mode and return to shadow | Implemented by contract | Automated |
| Native-memory discovery, historical copy, and continued file sync | Host responsibility | Automated |
| Exact native configuration/file restore | Host responsibility | Automated and verified |
| Model, context, tool, and turn flight events | Implemented when host emits them | Automated bridge hooks |
| Flight inspect, story, export, and finding acknowledgement | CLI, operator MCP, dashboard | CLI, operator MCP, dashboard |
| Persistent agents with shared, isolated, or nested workspace scopes | Explicit configuration | Automatic discovery and mirror binding |
| Memory search, review, record, audit, verification, and export | CLI, operator MCP, dashboard | CLI, operator MCP, dashboard |
| Raw prompt/response/tool evidence | Not stored by default | Not stored by Black Box |
| Semantic answer validation | Not implemented | Not implemented |
| Independent external outcome proof | Accepts linked receipts; verifier required | Accepts linked receipts; verifier required |
| Hosted multi-tenant authentication and storage isolation | Not provided | Not provided |

The exact boundary is:

- AtMem can verify its retained memory and evidence chains.
- It can verify closure and correlation of the events a runtime reports.
- A generic MCP process cannot independently see whether a host truly injected
  context or whether an external action occurred.
- OpenClaw is the only adapter in this repository that automates native-state
  discovery, migration, hook installation, activation, and exact restore.
- A SaaS deployment must add authentication, authorization, tenant isolation,
  encryption/retention policy, and system-of-record outcome verification.
