# Live process-fault evaluation boundary

P006 continuation after installed product gates and fresh no-fault pilot. This
does not change product recovery contracts or authorize more than USD20 total.

The normal application worker remains stock LangGraph with synchronous SQLite
checkpoints. Only its model transport changes from recorded replies to a
loopback authenticated broker. Provider credentials stay outside the worker;
its environment is allowlisted and its network limited to loopback. The broker
uses the same reviewed single-attempt transport and cumulative reservation ledger.

The broker must never cache, deduplicate, replay, replace or repair a model reply.
Two identical requests mean two independent provider attempts. A restarted worker
does not receive an earlier response from the evaluator. Received request,
provider response and socket-write/orphan status are recorded separately. A
successful socket write is not claimed to prove application consumption. Unknown
spend retains its full reservation. Missing deliveries do not refund paid usage.
One transport instance belongs exclusively to one arm's broker while the worker
is active; no grader or other thread may use it concurrently. Its call cap covers
agent+simulator together, not60per role. Grading may use it only after the broker
has drained/closed. Broker records link to the transport attempt ID and distinguish
pre-dispatch refusal, metered-transport failure and post-completion delivery failure.
The transport—not worker input—pins model, tier, output cap and allowed kwargs.
Socket writes and shutdown are not advertised as hard wall-clock deadlines.

Faults remain outside the product and application: the public native tool HTTP
boundary may kill the worker after a confirmed store change, before returning
the native response. The native tool process and AtMem authority survive. Restart
uses the same thread/checkpoint/namespace/principal and a new run identity, never
an evaluator-selected resume point. Neither tool nor model broker gives the
application access to hidden native snapshots or task grading criteria.

Before any paid fault run: read-only Claude review, broker no-cache/auth/unknown-
charge/disconnected-worker tests, recorded-response regression, frozen task and
fault schedule, exact installed artifacts and held-out registration as applicable.
Count repeated requests separately from duplicate effects, and safe refusal
separately from task completion. Do not fill AtFlows charges from experiment logs.
The normal-run pilot is not a production improvement: its full1/0/0/0 outcomes
remain immutable. Broader qualification must report all outcomes, not tune on
held-out failures or selectively repeat successful cases.

## Exposed-task pilot schedule (frozen before dispatch)

Run exactly one fresh task0 conversation for each arm, in baseline, AtMem,
AtFlows, both order, seed20260925. Use the same installed build005 artifacts,
pinned upstream and model/options as the no-fault pilot. Interrupt the first
successful native call whose before/after store hashes differ, after the effect
and before its HTTP reply. Record the actual call and journal, not an assumed
ordinal. If no such call occurs, retain `fault_boundary_not_reached`; do not
substitute a task, force a tool call, or rerun for a favorable outcome.

Wait125seconds for the real product lease; do not edit timestamps. Restart the
same stock checkpoint once with a new run identity. Allow600seconds per worker
stage and60model calls per arm across both stages, sharing the existing USD20
ledger. A killed worker does not cancel a provider charge. No additional paid
grading is scheduled here: report conversation termination/refusal, resumed
HTTP requests, native errors and actual store changes, not official task scores.
Retain all partial trajectories, provider calls and external snapshots.

This is exposed-task engineering evidence. It neither satisfies the held-out
gate nor tests every fault class or destination capability. Stronger-baseline
and held-out comparisons remain required before production improvement claims.
