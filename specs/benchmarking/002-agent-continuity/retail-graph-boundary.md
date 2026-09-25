# Public retail evaluation integration boundary

Read-only Claude Opus 5.5 consultation (2026-09-25) accepts a normal LangGraph
application as workload integration, with these binding restrictions:

- Stock file-backed SqliteSaver, synchronous durability and `invoke(None, config)`
  on restart in every arm. No checkpoint patching or custom recovery serializer.
- Native pinned tau2 LLMAgent/UserSimulator prompts and tool schemas. Pure JSON
  conversion of their states, not repair, field removal or recovery decisions.
- Same agent/user/tools graph and ordinary routing in all four arms. Only tool
  dispatch changes to the shipped AtMem governed node; AtFlows uses the shipped
  observer. No rig journal, receipt cache, skip/query/retry decision or fallback.
- Simulator instructions never enter agent prompts. Evaluator reward/actions
  never enter the graph. Environment has its unchanged native semantics, not a
  deduplication or reconciliation endpoint added for this experiment.
- External common tool-response barrier only; observe destination independently.
- No-fault replay qualification must match the preserved native public pilot's
  requests, responses and final environment. Replay is qualification, not new
  autonomous performance evidence. Paid comparisons remain gated on this result.
- Verify graph topology/serde equivalence, source/public API boundary, baseline
  re-execution negative control, product removal, kill symmetry and independent
  scoring. Missing capabilities are recorded, never supplied by workload code.

This amends P006's implementation design, not historical results or held-out
preregistration. Repeated fresh paid/held-out results remain a separate gate.

## External receipt-loss qualification

Fixed exposed task 0, sixth tool invocation, only call in its faulted superstep.
Parent kills the worker with SIGKILL after native exchange returns, before HTTP
response. Native environment and normal AtMem controller survive. Parent records
checkpoint pending-write metadata read-only; none enters the restarted worker.
All arms wait 125 actual seconds after killing, outside any HTTP request, then
use ordinary `invoke(None)`. Each trial has fresh controller storage; namespace
and thread remain stable across restart, while run identity changes. Deriving the
namespace from run identity would incorrectly defeat recovery and is prohibited.

Primary measure: extra tool invocations after restart. Native retail guards can
reject repeated exchanges, so an invocation is not counted as a duplicate effect.
Cassette miss, product refusal and native error are reported separately. No
completion comparison is allowed from recorded responses after divergence.
Worker allows only loopback network in this qualification. A fresh graph invoke
resets LangGraph's recursion safety limit equally in all arms; persisted workload
steps still enforce the original 58-step conversation bound. No paid ledger
reservation is created for a run with zero API dispatches; report paid_calls=0.
