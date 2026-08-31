# AtMem

[![Version 2.1.0](https://img.shields.io/badge/version-2.1.0-blue)](./docs/releases/v2.1.0.md)
[![CI](https://github.com/aetna000/atmem/actions/workflows/ci.yml/badge.svg)](https://github.com/aetna000/atmem/actions/workflows/ci.yml)

**AtMem is a host-neutral Agent Black Box and reversible memory control plane.**

> **Development status:** repository metadata remains **2.1.0**, the latest
> published release. The `atbot` branch contains unreleased **2.2 development**
> work. Features identified below as 2.2 development are not available from
> `pip install atmem==2.1.0` until the 2.2 packages are published.

It gives agent runtimes one governed memory source and one tamper-evident record
of what the host observed: memory considered and injected, model boundaries,
tool requests and completions, turn termination, and linked external outcome
receipts. OpenClaw is the first fully automated adapter. Other runtimes connect
through the generic control MCP contract.

AtMem starts in **shadow mode**. It records memory candidates and flight
evidence but never authorizes memory injection. An operator can review the
evidence, activate AtMem explicitly, and return to shadow at any time. The
OpenClaw adapter additionally copies native memory, freezes it during takeover,
and restores it exactly.

## Install

```bash
python -m pip install atmem==2.1.0
atmem --version
```

AtMem requires Python 3.10 or newer. Released 2.1 keeps semantic-vector
dependencies optional:

```bash
python -m pip install 'atmem[semantic]==2.1.0'
```

For the unreleased 2.2 development checkout, install both repository packages
so the exact companion version is satisfied locally:

```bash
python -m pip install -e './packages/atbot[dev]' -e '.[dev]'
atmem atbot setup
```

The 2.2 authority modules remain model-agnostic and do not import AtBot, but the
AtMem distribution requires the separately packaged, exactly pinned AtBot
companion. Consequently a complete 2.2 installation has AtBot's transitive
dependencies even when the user selects AtMem's deterministic fallback.

## Choose an integration

| Runtime | Start command | What AtMem supplies | What the runtime supplies |
| --- | --- | --- | --- |
| Any custom agent, CLI, or SaaS worker | `atmem control shadow --host generic` | memory governance, shadow/active policy, flight store, verification, audit, CLI, MCP, dashboard | authenticated identity and truthful model/tool/context hooks |
| OpenClaw | `atmem openclaw install` | all generic capabilities plus automated native-memory copy, hook installation, gateway checks, activation, and restore | the OpenClaw runtime |
| Memory engine only | `atmem mcp` or Python `Memory` | canonical memory, recall, provenance, lifecycle, deletion, and audit | all agent-flight and prompt-boundary integration |

The dashboard is a view over the same local state used by CLI and MCP. It is
not a separate source of truth.

## Connect any agent runtime

Start a generic control plane against the same canonical database used by the
memory MCP server:

```bash
atmem control shadow --host generic --memory-db ~/.atmem/memories.db
atmem control mcp
```

The host MCP is deliberately non-administrative. It exposes capture, prepare,
context-exposure confirmation, flight-event recording, adapter sync/status,
and cannot approve memory, acknowledge findings, or activate AtMem.
Approving a generic shadow candidate writes the reviewed fact into the bound
canonical database, so `atmem mcp`, CLI, operator MCP, and dashboard see the
same active record and record ID.

For every turn, the runtime must:

1. assign stable agent, workspace, session, run, and turn identifiers;
2. capture authenticated user memory candidates;
3. call `control_prepare` before the model request;
4. inject the returned context only when `inject` is exactly `true`;
5. confirm the exact exposure after constructing the model request;
6. record model input/output, each tool request/completion, and turn end;
7. bind an outcome receipt when an independent system proves a real-world result.

See the [generic adapter contract](docs/generic-adapter.md) for tool names,
multi-agent scopes, event requirements, and trust boundaries.

## Operate AtMem

The operator CLI, operator MCP, and loopback dashboard call the same manager
operations:

```bash
# Read state and verify integrity.
atmem control status
atmem control verify
atmem control memory-sync
atmem control memory-status

# Inspect and decide memory.
atmem control memory-reviews
atmem control memory-search "preferred editor"
atmem control memory-record RECORD_ID
atmem control memory-review RECORD_ID approve
atmem control memory-audit --since 2026-08-15T00:00:00Z
atmem control memory-audit --format ndjson --output audit.ndjson

# Inspect, export, and acknowledge agent flights.
atmem blackbox runs --limit 50
atmem blackbox story RUN_ID
atmem blackbox verify RUN_ID
atmem blackbox export RUN_ID --format json --output flight.json
atmem blackbox ack RUN_ID ATTENTION_CODE

# Explicit influence control.
atmem control activate
atmem control restore
```

To expose those same administrative operations to a trusted local operator
client, run:

```bash
atmem control operator-mcp
```

Do not expose the operator MCP to an agent or untrusted network. It can approve
or reject memory, acknowledge findings, configure generic agent scopes, export
evidence, activate AtMem, and return it to shadow.

## Dashboard

```bash
atmem dashboard daemon start   # http://127.0.0.1:8766/
atmem dashboard daemon open
atmem dashboard daemon status
atmem dashboard daemon restart
atmem dashboard daemon stop
atmem dashboard daemon remove  # service metadata only; memory remains
```

The dashboard shows a concise action timeline first. A flight node is green
when no active finding remains, amber when it needs review, and red when the
observed run failed or its evidence is incomplete. Selecting a node reveals
the request/reply when a protected local adapter reader can supply them,
memory used, tools and websites, model/provider, tokens, latency, risks,
blocking reason, outcome evidence, hashes, and the full timeline. Findings can
be acknowledged without deleting or rewriting evidence.

The governed-memory chat remains the primary dashboard surface. AtBot provider,
model, endpoint, lifecycle, and fallback controls are kept in a collapsed
**Memory intelligence** settings row. The browser renews an expired local CSRF
session once and retries the mutation; persistent failure asks the user to
refresh rather than exposing a raw security error.

Memory search, review, record history, audit filters, downloads, agent topology,
verification, activation, and return-to-shadow use the same operations as the
CLI. The canonical dashboard API is `/api/memory/*`; legacy `/api/mirror/*`
paths remain aliases for older local clients.

The dashboard binds only to loopback, has no login, checks origin and CSRF on
mutations, and should not be placed behind a public reverse proxy.

## Multiple agents and workspaces

Generic runtimes register persistent agents explicitly:

```json
[
  {"agent_id":"main","name":"Main","workspace":"shared","is_default":true},
  {"agent_id":"research","name":"Research","workspace":"shared"},
  {"agent_id":"private","workspace":"private","parent_workspace":"shared"}
]
```

```bash
atmem control configure-agents agents.json
atmem control agents
```

Agents in the same workspace share one memory subject. Different workspaces
are isolated. A parent relationship records nesting but does not merge memory.
Every capture, prepare, and flight event can carry agent, workspace, and subject
identity. OpenClaw topology is discovered from OpenClaw configuration and bound
to the verified memory mirror; generic topology is explicit and local.
Temporary child runs may reuse a registered workspace and subject. They do not
create a new durable scope implicitly; register them when they need persistent
identity or isolated memory.

## Install and migrate OpenClaw

Do not install the npm bridge separately. The Python installer owns the version
pair and validates the result:

```bash
atmem openclaw install
atmem control status
atmem control verify
atmem dashboard daemon start

# Activate only after review.
atmem control activate

# Test restoration without changing live state, then restore when required.
atmem control restore --drill
atmem control restore
```

`atmem openclaw install` installs the pinned npm bridge, binds the exact Python
executable, copies `MEMORY.md` and `memory/*.md` across detected persistent
agent workspaces, starts shadow synchronization, restarts the gateway, and
verifies the loaded integration. Rerunning it refreshes an existing shadow
migration without replacing the original restore snapshot.

See [OpenClaw setup](docs/openclaw-setup.md), the
[OpenClaw control-plane guarantees](docs/control-plane.md), and the
[OpenClaw bridge package](integrations/openclaw/README.md).

## Agent Black Box evidence

The runtime can record these content-minimizing event types:

| Boundary | Retained evidence |
| --- | --- |
| turn input | digest, size, counts, correlation IDs |
| context disposition | injected, empty, withheld, failed, or not applicable; receipt and record IDs |
| model input/output | provider, model, digests, latency, tokens, bounded usage metadata |
| tool request/completion | tool name, argument/result digests, safe key names, duration, error category |
| turn end | success, failure, cancellation, or incomplete state |
| external outcome | opaque receipt ID, digest, status, and safe metadata supplied by a verifier |

A verified flight proves retained chain integrity and closure of the boundaries
the runtime reported. It does not prove that a hook was truthful, semantically
validate an answer, or prove email delivery, payment settlement, or a database
change without independent system-of-record evidence.

Raw prompts, replies, tool parameters, and tool results are not stored in the
Black Box. SHA-256 digests are fingerprints, not encryption or anonymization.
See the [Agent Black Box guide](docs/agent-blackbox.md).

## Use the memory engine directly

```python
from atmem import Memory

memory = Memory("memories.db")
memory.remember("user-1", "My preferred editor is Vim.", session_id="s1")
records = memory.recall("user-1", "preferred editor", limit=5)
verification = memory.verify("user-1")
memory.close()
```

Or run the model-agnostic memory MCP server:

```bash
atmem mcp --db ~/.atmem/memories.db --subject user-1
```

MCP tools: `memory_remember`, `memory_observe`, `memory_recall`,
`memory_get_record`, `memory_get_source`, `memory_recall_block`,
`memory_persona`, `memory_context_pack`, `memory_capture`, `memory_list`,
`memory_forget`, `memory_forget_artifact`, `memory_promote`, `memory_audit`,
`memory_verify`, `memory_graph_status`, `memory_graph_merges`,
`memory_graph_history`, and `memory_log_action`.

See the [integration guide](docs/integration-guide.md),
[audit search](docs/audit-search.md), [semantic search](docs/semantic-search.md),
and [multimodal observations](docs/multimodal-observations.md).

## Data, privacy, and recovery

- Canonical memory, provenance, lifecycle state, and audit evidence use SQLite.
- Every persistent 2.2 memory database has a rebuildable local vector sidecar.
  Its active epoch participates in governed candidate nomination, but every
  vector match is checked against canonical scope, status, digest, exclusions,
  sensitivity, and generation before use. Higher-quality embedding libraries
  and model downloads remain optional.
- External media bytes remain host-controlled; AtMem stores a typed text observation, byte digest, model identity, and host reference.
- External observations remain quarantined until an operator approves them.
- Rejected, superseded, or tombstoned memory is excluded from ordinary search and recall.
- Forget cascades through canonical, graph, media, and vector-derived state and returns a receipt.
- Generic return-to-shadow stops future context injection but does not undo past model outputs or tool actions.
- OpenClaw restore verifies and reinstates the preserved native configuration and files; it also cannot undo past outputs or external actions.

For backups, permissions, and disaster recovery, read
[data storage and backup](docs/data-storage-and-backup.md) and the
[auditing guide](docs/auditing-guide.md). For a custom product deployment, read
[Using AtMem in a SaaS product](docs/saas-integration.md). AtMem does not ship a
hosted multi-tenant control service; your SaaS remains responsible for tenant
authentication, authorization, storage isolation, encryption, retention, and
system-of-record verification.

## Documentation map

- [Current implementation status](docs/current-status.md)
- [Generic runtime adapter](docs/generic-adapter.md)
- [Agent Black Box](docs/agent-blackbox.md)
- [Integration guide](docs/integration-guide.md)
- [OpenClaw setup](docs/openclaw-setup.md)
- [OpenClaw control-plane guarantees](docs/control-plane.md)
- [SaaS integration and go-live checklist](docs/saas-integration.md)
- [Audit log specification](docs/audit-log-spec.md)
- [Audit investigation](docs/audit-search.md)
- [Storage, backup, and recovery](docs/data-storage-and-backup.md)

## Development verification

AtMem and its separately packaged AtBot companion share this repository. They
remain separate processes and communicate only through the loopback companion
protocol; neither package imports the other's runtime code.

On the 2.2 development branch, AtMem declares the exactly pinned AtBot
companion as a required distribution dependency. A clean package installation
will install it automatically after both 2.2 distributions are published;
repository development uses the editable command above. Model setup remains an
explicit user decision:

```bash
atmem atbot setup       # interactive local, hosted API, custom, or skip choice
atmem atbot providers   # list profiles, defaults, and API-key environment names
atmem atbot doctor      # verify runtime, provider, protocol, and safe fallback
```

The dashboard exposes the same provider, model, endpoint, start, stop, and safe
fallback controls in a collapsed settings row below governed-memory chat. It
also shows the equivalent CLI command, so a user can switch between the UI and
terminal without reading a separate setup guide. Local choices include Ollama and any loopback
OpenAI-compatible server. Hosted profiles include OpenRouter, OpenAI, DeepSeek,
xAI Grok, Anthropic Claude, Hugging Face, and a custom HTTPS OpenAI-compatible
endpoint. Configuration stores only the environment-variable name containing a
key; it never stores the key itself. Choosing **Use safe fallback** is remembered
and leaves AtMem's deterministic local ranking active.

```bash
python -m pip install -e '.[dev]' -e './packages/atbot[dev]'
python -m pytest -q
python -m pytest -q packages/atbot/tests

cd integrations/openclaw
npm ci
npm run typecheck
npm test
npm run smoke
```

Current repository metadata is version **2.1.0**. Python and npm release
versions are intentionally kept equal because the OpenClaw installer pins the
matching bridge.

## License

AtMem is licensed under the [Apache License 2.0](LICENSE). It permits
commercial and internal enterprise use, modification, and distribution,
subject to the license terms. Apache-2.0 also provides an explicit contributor
patent grant and does not require an organization to publish private changes
merely because it runs the software as a service.
