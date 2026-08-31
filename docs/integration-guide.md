# Integration guide

AtMem separates the model-agnostic memory engine, a host-neutral control
contract, and automated host-specific adapters.

## Python

```python
from atmem import Memory

memory = Memory("memories.db")
memory.remember("user-1", "My preferred editor is Vim.", session_id="s1")
records = memory.recall("user-1", "preferred editor", limit=5)
report = memory.audit("user-1")
memory.close()
```

The canonical database remains usable without an external embedding provider.
In 2.2 AtMem creates a dependency-free local vector sidecar
automatically; installing a higher-quality local embedding provider is optional.

## MCP

```bash
atmem mcp --db ~/.atmem/memories.db --subject user-1
```

| Tool | Purpose |
| --- | --- |
| `memory_remember` | Admit authenticated text through policy and provenance checks. |
| `memory_observe` | Admit a typed, quarantined text observation of host-controlled media. |
| `memory_recall` | Return bounded active memories for a query. |
| `memory_get_record` | Read one canonical record by ID. |
| `memory_get_source` | Read the source episode associated with a record. |
| `memory_recall_block` | Render bounded recall for direct context injection. |
| `memory_persona` | Render a bounded subject persona. |
| `memory_context_pack` | Render a cache-aware persona and recall context pack. |
| `memory_capture` | Record an interpreted memory and bind it to source evidence. |
| `memory_list` | List canonical memories and lifecycle status. |
| `memory_forget` | Delete matching memory and return a receipt. |
| `memory_forget_artifact` | Delete all memory derived from one exact media byte-stream digest. |
| `memory_promote` | Approve a quarantined memory for recall. |
| `memory_audit` | Read the evidence timeline for a subject. |
| `memory_verify` | Verify audit and storage integrity. |
| `memory_graph_status` | Inspect the derived graph index. |
| `memory_graph_merges` | List reviewer-gated graph merge proposals. |
| `memory_graph_history` | Inspect graph entity and merge history. |
| `memory_log_action` | Bind a host action or response digest to the audit timeline. |

An MCP connection alone does not authenticate the user or prove that returned context reached the model. The host must supply authenticated identity and bind actual context delivery and response evidence.

## Generic control adapter

```bash
atmem control shadow --host generic --memory-db ~/.atmem/memories.db
atmem control mcp
```

The generic host MCP records authenticated memory candidates, returns a bounded
context decision, confirms exact exposure, and records model/tool/turn events.
It starts fail-closed in shadow and returns `inject: false` until an operator
activates it. Use `atmem control operator-mcp` only from a trusted operator
process for search, review, verification, export, acknowledgement, topology,
activation, and return-to-shadow actions.

The MCP process cannot observe the model request by itself. The host must emit
truthful events and inject only the exact context AtMem authorized. See the
[generic adapter contract](generic-adapter.md).

## OpenClaw control adapter

```bash
atmem openclaw install
atmem control status
atmem control activate
atmem control restore
```

The OpenClaw adapter automates the host-specific parts: complete native-memory
discovery, historical copy, ongoing shadow synchronization, prompt and response
binding, semantic model interpretation, native-path protection, gateway
verification, and exact native-state restore.

## Pydantic AI and LangGraph

AtMem ships optional automatic lifecycle adapters for Pydantic AI and
LangChain agents running on LangGraph. See the
[framework adapter guide](framework-adapters.md) for installation, identity,
capture, injection, exposure, tool, failure, and multi-agent examples.

## AtBot intelligence companion

AtBot is maintained in this repository under `packages/atbot`, but ships as a
separate process and wheel so model-framework dependencies never enter AtMem's
authority runtime:

```bash
# 2.2 repository development
python -m pip install -e './packages/atbot' -e '.'
atmem atbot setup
```

The 2.2 AtMem distribution declares the exact AtBot version as a required
dependency. There is no longer a separate AtBot opt-in extra; model selection
and remote egress remain explicit user choices. The packages remain separate
wheels and processes, and AtMem authority code does not import AtBot.

AtMem discovers and calls AtBot over its loopback companion protocol. AtBot
does not import AtMem or open its database, and AtMem retains deterministic
capture and hybrid-retrieval fallback when the companion is unavailable.

## Building another host adapter

A complete adapter must implement:

1. authenticated user and session identity;
2. enumeration and verified copy of all existing host memory;
3. shadow synchronization without changing model context;
4. model-semantic capture of user intent rather than transcript keyword scraping;
5. bounded recall and proof of actual context injection;
6. response/tool receipt binding;
7. atomic activation with capability checks;
8. restore material captured before mutation;
9. verified restore, including handling divergent files or state;
10. honest reporting of any evidence the host cannot expose.

The generic adapter supplies the control and evidence protocol but cannot prove
that an implementation reports its boundaries truthfully. Describe native-state
migration and restore as complete only when the host adapter also meets the
copy, mutation, and restore requirements above.
