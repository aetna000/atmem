# Generic agent runtime adapter

AtMem's generic control plane starts in shadow mode. It records candidate
memory and agent-flight evidence, but `control_prepare` always returns
`inject: false` until an operator explicitly activates AtMem.

## Start the runtime and operator trust surfaces

```bash
atmem control shadow --host generic --memory-db ~/.atmem/memories.db
atmem control mcp
```

For a generic adapter, the host MCP exposes exactly `control_capture`,
`control_sync_memory`, `control_prepare`, `control_exposure_shown`,
`control_record_blackbox_event`, and `control_status`. It cannot approve
memory, acknowledge findings, export evidence, or activate AtMem.

Point `--memory-db` at the same database used by `atmem mcp`. Canonical memory
and shadow candidates then appear together in dashboard, CLI, and operator MCP
search and audit views. If the option is omitted through the Python API, AtMem
creates an isolated database inside the control directory.
Approving a shadow candidate canonicalizes that exact reviewed fact into this
database; future context receipts prefer the canonical record ID. Rejection
leaves no active canonical record.

Operators use the CLI, dashboard, or the parity-complete operator MCP:

```bash
atmem control operator-mcp
atmem dashboard daemon start
```

These surfaces call the same `ControlPlaneManager` operations. Host-neutral
memory, flight, verification, acknowledgement, topology, activation, and return
to shadow operations are available through CLI and operator MCP. Adapter
installation and OpenClaw restore drills remain adapter-specific maintenance
commands.

## Turn contract

For every turn the adapter must:

1. assign stable `agent_id`, `workspace_id`, `session_id`, `run_id`, and
   `turn_id` values;
2. call `control_capture` for authenticated user memory candidates;
3. call `control_prepare` before the model request;
4. inject the returned context only when `inject` is exactly `true`;
5. call `control_exposure_shown` after placing that exact context in the model
   request;
6. emit `control_record_blackbox_event` for turn input, context disposition,
   model input/output, every tool request/completion, and turn termination;
7. attach an `outcome_id` when an independent system proves a consequential
   real-world result.

MCP transports memory and evidence; it cannot independently see the model
request. The runtime hook is responsible for reporting the boundary truthfully.

## Multi-agent topology

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

Agents using the same workspace share a memory subject. Different workspaces
receive separate subjects. A nested workspace records its parent relationship
but remains isolated. A temporary child run may reuse an existing registered
workspace by reporting that workspace and subject; it does not silently create
a new durable memory scope. Register a child as an agent when it needs a stable
identity or its own persistent workspace. AtMem rejects agent/workspace/subject
combinations that point to different scopes and rejects cyclic nesting.

## CLI/operator MCP parity

The CLI and operator MCP cover:

- memory sync/status, search, review queue, record inspection, audit
  search/export, and review decisions;
- agent and workspace topology;
- adapter verification;
- flight list, verified detail, concise story, export, and acknowledgement;
- activation and return to shadow;
- portable flight evidence through CLI export or the returned MCP report.

The dashboard is a presentation layer over the same operations; it is not the
source of truth. The control state, evidence chains, and memory records are.

## Proposed delegated context-provider mode

A provider-neutral delegated mode is under design for runtimes that need an
external system to remain the sole context-decision authority while AtMem owns
host delivery and flight evidence. The proposal binds one signed inject or
withhold result to the exact run, turn, session, agent, user, and workspace. It
also keeps provider authorization distinct from AtMem's observation that the
host exposed the approved bytes.

This mode is **not implemented** by the current generic or OpenClaw adapters.
See the [delegated context-provider v1 proposal](contracts/delegated-context-provider-v1.md)
for the closed schema, signed fixtures, replay rules, and conformance cases.
