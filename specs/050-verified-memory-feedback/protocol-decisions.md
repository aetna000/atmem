# Generic RAG/MCP scope amendment — 2026-11-09

Owner requested easy external document/law RAG integration, generic MCP access
and enforcement alongside Hermes, autonomous ordered implementation and consistent
code/documentation. This amends the existing owner-approved Spec 050 directory;
no new directory, paid campaign, production deployment or release is requested.

## Verified protocol references and decision

- [MCP 2026-07-28 versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning): modern requests carry version/capability metadata, with no initialize handshake.
- [MCP 2026-07-28 authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization): HTTP transport authorization and environment credentials for stdio are distinct.
- [MCP 2025-11-25 tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools): legacy handshake-based tool listing, calls and annotations.
- [MCP 2025-11-25 transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports): newline-delimited stdio, protocol-only stdout, and separate Streamable HTTP requirements.

Decision: the initial new governed server explicitly supports legacy stdio
revisions 2025-06-18 and 2025-11-25 for compatibility with existing clients. It
rejects unsupported/modern revisions rather than echoing an unimplemented one.
It does not advertise latest/2026 support, public HTTP, OAuth hosting or generic
control of a client's unrelated tools. The older memory MCP server remains
unchanged; its behavior is not the new authentication boundary.

## Data and authority decisions

Reuse the existing encrypted evidence vault and application-mediated identity/
key release. Provider and agent grants belong there; no separate memory system.
Owner registration chooses trusted adapter objects/collections, not model-supplied
URLs, SQL, Python paths or credentials. Source search is read-only and explicit
egress. The local reference provider persists encrypted documents and builds a
SQLite FTS5 index only in RAM after authorization. This supports real retrieval
without adding a hosted embedding service or plaintext search index.

External hits carry exact content, scope, revision, citation and temporal metadata.
Requested jurisdiction/as-of filters reject missing metadata; unfiltered unknowns
stay visible. Dates use ISO calendar dates and half-open validity intervals.
No bundle of actual legislation or legal correctness claim is included.

MCP tools share the same service as API/CLI. A registered server-side proxy can
stop its own handler; an advisory check cannot stop another host tool. Atomic
admission, single-use approval, uncertain-write recovery and outcome verification
remain separately tested requirements. Hermes is one optional adapter, not a core
dependency or the only route to this feature.
