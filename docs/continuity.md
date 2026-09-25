# Resume work with AtMem and AtFlows

Available in AtMem 2.3.7 with AtFlows 0.1.3. Continuity requires the explicit
setup below; installing the packages alone does not enable recovery.

AtMem saves what your connected agent is doing before it calls a tool. When the
agent restarts, a saved success receipt lets it reuse the result. If an action
may have happened but its receipt was lost, AtMem checks the tool's declared
capabilities: query the destination, repeat with a still-valid idempotency key,
or stop safely. AtFlows shows the received attempts and reported costs.

This is an opt-in SDK integration, not automatic recovery for arbitrary agents.
AtMem does not run your agent or replace LangGraph's scheduler/checkpointer.

## Try a real document

Install `python -m pip install "atmem[langgraph-provider]==2.3.7"`.
Run `atmem init`, then `atmem status` to find your
dashboard URL. Sign in and replace any temporary administrator password. Commands
below assume the reported URL is `http://127.0.0.1:8768`; add `--url` otherwise.
They do not use development/test accounts. Passwords are prompted without echo.

Create an operator credential in the current shell (macOS/Linux bash or zsh):

```sh
export ATMEM_EVIDENCE_TOKEN="$(atmem continuity credential --principal document-operator --token-only)"
python -m atmem.continuity.example prepare --workflow-key publish-my-document \
  --document README.md --output ./published
```

Keep the returned `workflow_id`. In **Decisions → Resume work**, review the work
and select **Enable recovery**. Alternatively, set `WORKFLOW_ID` to that ID and
run `atmem continuity enable "$WORKFLOW_ID"`.

Create a narrower worker credential, then publish:

```sh
export ATMEM_EVIDENCE_TOKEN="$(atmem continuity credential "$WORKFLOW_ID" --principal document-worker --token-only)"
python -m atmem.continuity.example run --workflow-id "$WORKFLOW_ID" --output ./published
```

Run the last command again. It returns the saved result without publishing a
second document. **Resume work** shows the operation, attempts and receipt. The
output file is real; its receipt includes its SHA-256 and byte count.

Use a new workflow key for genuinely new work. Reusing a key with different
arguments is rejected. Use the same output directory on subsequent runs: it is
part of the reviewed definition. DirectoryPublisher is a local-filesystem tool;
moving an agent to another machine requires the same destination to be accessible.
Keep that directory private. It is not an untrusted multi-user file service.

PowerShell environment assignment uses
`$env:ATMEM_EVIDENCE_TOKEN = atmem continuity credential --principal document-operator --token-only`.
The Python module works on supported platforms. The two installed receipt-window
crash checks were reproduced on macOS and native Windows; Linux crash
qualification remains separate. See the release evidence for exact builds.

## Connect your own agent

```python
from atmem.continuity.client import ContinuityClient, Tool, langgraph_node

client = ContinuityClient(atmem_url, worker_token)
tools = {"upload": Tool(execute=upload, query=find_upload)}

# Host-neutral: product service decides execute/query/reuse/stop.
result = client.run_operation(workflow_id, "upload", tools)

# Optional LangGraph: use this as a normal graph node. Your graph keeps its own
# ordinary checkpoint configuration and scheduler.
node = langgraph_node(client, workflow_id, "upload", tools, result_key="document")
```

Callbacks receive `(arguments, operation_id, idempotency_key, timeout_seconds)`.
They must enforce the declared destination and timeout. A success receipt is:

```json
{"outcome":"confirmed_succeeded","operation_id":"op_from_callback",
 "effect_id":"actual_destination_identifier","result":{"url":"destination-result"}}
```

Return `{"outcome":"unknown"}` when the destination outcome is unknown. A timeout
is not proof of failure. Query must not perform the original side effect. Never
declare idempotency unless the real destination enforces that key and retention
window. AtMem validates the receipt binding but labels it **host-reported**: it
cannot independently establish whether an arbitrary callback is truthful.

## What happens after a failure?

For dynamically chosen tool calls, use `GovernedToolRunner` and
`governed_langgraph_tools` from `atmem.continuity.integrations`. The application
supplies an explicit `RegisteredTool` registry and opts in with `enabled=True`.
Give this middleware a `continuity_coordinator` credential scoped to one workspace,
not an administrator credential. It can create/use its own operation workflows,
but cannot re-enable work paused by the operator, read other workflows, grant
credentials, rotate keys or delete evidence.

```sh
export ATMEM_EVIDENCE_TOKEN="$(atmem continuity credential --coordinator \
  --workspace my-project --principal my-agent-tools --token-only)"
```

The supported dynamic LangGraph node currently requires a file-backed SqliteSaver
and `graph.invoke(..., durability="sync")`. An in-memory checkpointer or async
durability is rejected before dispatch. The assistant message, its stable ID and
tool calls must be checkpointed first. The node serializes a message's calls and
raises on uncertainty; it never sends an ordinary tool-error message that lets the
model retry an uncertain side effect under a new ID. Keep the governed node and
namespace on restart. Deliberately changing thread lineage represents new work.
Keep the coordinator principal ID unchanged when renewing its credential. Each
coordinator has a separate workflow-key namespace; a new principal is a new
authority, not an automatic continuation of another principal's work.

### Run the persistent LangGraph example

Use the coordinator credential above, then install the optional profile:

```sh
python -m pip install 'langgraph==1.1.5' 'langgraph-checkpoint-sqlite==3.0.3'
python -m atmem.continuity.langgraph_example start --enabled \
  --thread my-document --checkpoints ./agent-state/checkpoints.db \
  --document ./README.md --output ./published
```

After interruption, keep the same checkpoint file, thread and output directory:

```sh
python -m atmem.continuity.langgraph_example resume --enabled \
  --thread my-document --checkpoints ./agent-state/checkpoints.db --output ./published
```

LangGraph restores its saved position; AtMem supplies a saved result or authorizes
the registered destination query. A live attempt lease can require waiting up to
120 seconds before a replacement worker proceeds. Neither command changes the
operator's pause or permission decisions. This is a document workflow example,
not a claim that arbitrary agents become restart-safe without integration.

The host's checkpoint contains conversation/tool input and result data. Protect
its directory and backups with filesystem encryption/access controls; AtMem's
encrypted evidence vault does not encrypt LangGraph's separate database.

Each coordinator can have at most 500 unfinished workflows in its workspace.
Completed or operator-abandoned work frees capacity; its identity and receipts
remain protected against replay. Deletion retains a tombstone, not a reusable
identity. This is a guardrail, not a measured large-deployment capacity.
Coordinator admission uses a 64 MiB retained-history budget, including reserved
space for each granted attempt's maximum receipt. At capacity, reads and admitted
completion remain available; new work stops until an operator exports/deletes
finished workflows through normal evidence controls. Operator stop actions have
bounded additional headroom. This is not a physical disk quota; an actual disk
or key failure can still prevent persistence and must never license a repeat.
The qualified LangGraph versions are 1.1.5 and 1.2.12. Set a stable application
`configurable.continuity_namespace` if using several governed nodes; do not use
LangGraph's task-scoped `checkpoint_ns`. Editing arguments under an existing
message/call identity is rejected. A new message is new work, not semantic deduplication.

| What happened | What AtMem does | What you do |
| --- | --- | --- |
| Success receipt saved; worker dies | Returns that result; no new dispatch | Restart the connected agent |
| Destination acted; worker lost receipt | Uses the declared query, or a valid destination idempotency key | Restart after the old attempt lease expires |
| Outcome cannot safely be established | Stops; does not guess or repeat | Inspect destination and workflow evidence |
| Another worker still holds the attempt | Blocks a competing dispatch | Wait for the worker/lease; inspect its health |
| Worker credential revoked | Denies its next authenticated call | Operator reviews access; do not bypass revocation |
| Workflow paused | Blocks new attempts; accepts correctly bound in-flight receipts | Operator can enable again after review |
| AtFlows unavailable | Work continues; observer errors returned to caller | Restore observer; missing events remain missing |

The lease is 120 seconds; renewal is bounded to ten renewals. An expired,
unsuperseded attempt can still submit its correctly bound receipt. A superseded
late receipt is retained as evidence but cannot complete newer work. There are
at most 200 operations, 100 attempts per operation and no new dispatch after
2,000 workflow revisions. This is a bounded sequential workflow profile, not a
distributed workflow engine. A lost `begin` response is not automatically retried:
AtMem cannot know whether the first grant reached another executing worker.

If a controller clock moves backwards, dispatch pauses. Correct the controller
clock to at least its saved high-water time; do not reset timestamps or force a
retry. A live external action cannot be cancelled merely by changing local state.
**Stop this work** records operator abandonment after the live lease ends; it
does not claim completion, and dependent operations remain blocked.

## Connect AtFlows

Set `ATFLOWS_CONTINUITY_TOKEN` in the AtFlows server environment and the agent
environment. Use one secret per installation; do not put it in URLs or prompts.
`ATFLOWS_CONTINUITY_SCOPE` is a server-configured observation domain (default
`local`), never accepted from event payloads. Restart the server after configuring.

```python
from atmem.continuity.client import AtFlowsObserver, ContinuityClient

observer = AtFlowsObserver(atflows_dashboard_url, producer_token)
client = ContinuityClient(atmem_url, worker_token, observer=observer)
```

For the document example, add `--atflows-url` with the URL reported by
`atmem status`. In AtFlows open **Activity → Resume work**. This view requires Investigator
access or higher. An observer credential can only submit this allowlisted event
schema; it cannot approve AtMem actions or read the dashboard.

Events contain opaque workflow/operation/run/attempt IDs and optional usage/price
provenance, not document text, tool arguments or full receipts. Keep exact evidence
in AtMem. The default document tool reports no provider price, so AtFlows shows
missing cost, not an invented zero. Reported totals are not a complete invoice.

Inside a governed callback, use `record_charge` with the actual provider response
ID and usage. Price may be omitted; if supplied, give the rate-source/version.
This emits product telemetry bound to the active operation/run/attempt. It does
not ask the benchmark ledger to fill in a product price:

```python
from atmem.continuity.client import record_charge

record_charge(charge_id=response.id, charge_source="your-provider-account",
              input_tokens=response.usage.prompt_tokens,
              output_tokens=response.usage.completion_tokens)
```

This example deliberately reports usage without guessing its price. Optional
`cost_microusd` and `price_source` record your actual supported price calculation.
The helper returns false when no observer is active or delivery fails. Calls
outside a governed callback need explicit normal instrumentation; this helper
does not automatically discover every model call in your application.

`client.observation_error_count` counts delivery failures; `observation_errors`
retains the first 100 types. A timeout means delivery is unknown: a pending sender
may finish later. Caller waiting is bounded to two seconds per event, but DNS or
a slow response can occupy one of eight process-wide worker slots indefinitely.
Exhaustion reports failure without changing tool authority. This is best-effort
observation, not a guaranteed delivery queue; allow for its per-event waiting
when setting application deadlines.

## Storage, privacy and compatibility

Operation definitions, leases and receipts use the existing encrypted evidence
vault. Creation requires full capture and explicitly opts that vault into schema
3; old schema-2 readers refuse it. Normal evidence-only use stays schema 2. Keep
a pre-upgrade backup before opting in; there is no in-place downgrade command.
Key lock blocks continuity calls. Deletion removes workflow content and leaves an
encrypted minimal tombstone to prevent accidental resurrection of its key.

Active or uncertain work prevents reducing capture: pause workflows and resolve
or abandon uncertain operations first. Workflow operations do not silently mark
Spec 007 governed tasks complete. That task authority and memory lifecycle remain
separate. Recall relevance alone never grants permission to execute a tool.

The installed crash tests and their exact scope are recorded in the continuity
benchmark reports. Those product acceptance checks are not an autonomous retail
agent benchmark or a claim that every long-running workflow will recover.
