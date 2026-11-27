# Implementation plan

Build the offline comparator in `tools/benchmark_context_eviction.py`. The
input is one scoped session per entry, with ordered request snapshots,
OpenAI-style messages, and tool-call IDs verified as successful reads by
the trace producer. Each arm uses the same canonical JSON serialization and
the same tokenizer. The bundled fixture uses generated file text and
synthetic request snapshots. The CLI also accepts an equivalent JSON export.

Match exact read arguments and contents, preserve the newest result in full,
and preserve call/result pairs. Treat a matching read as mature after two
subsequent tool-call batches by default. Match only within the same request
and after the latest user message. Hash the normalized corpus in the report.
Keep the benchmark offline and publish aggregate synthetic evidence with the
specification. Run focused tests and give Claude Code the changed source and
the public synthetic evidence through a read-only review session.

The constitution's authority and provenance requirements apply to any future
host connection. Before integrating, qualify a pinned OpenClaw backend at the
actual model-input boundary. Compare native pruning and compaction with the
same setup plus the rule on paired tasks. Record provider cache categories,
cost, time, tool rereads, exact historical recovery, and task outcomes.

## Live comparison protocol

1. Pin one OpenClaw release, backend, model revision, and public coding task
   corpus with an independent grader. Run a small development screen to check
   capture and billing reconciliation. Freeze the rule and task IDs before the
   held-out run. Include both repetitive and read-light tasks and an exact
   historical recovery probe.
2. Run both arms from fresh workspaces and sessions, alternating which arm
   runs first. Match task prompts, tool inventory, native compaction, model
   settings, and request, time, and cost ceilings. Capture the final input at
   the provider boundary and compare it with the host transcript. A candidate
   must keep the transcript recoverable and every tool call paired with its
   result. Verify normal request delivery when evidence is incomplete.
3. Compare total provider cost across all started attempts divided by the
   number of tasks that pass the independent grader. Include cache reads and
   writes, output, compaction, recovery, and failed attempts. Report paired
   task outcomes, full input tokens, wall time, tool rereads, and any
   unavailable usage. If the backend reports usage without prices, report
   token categories and omit the cost estimate. Show paired results and
   uncertainty before making a user-facing claim.

The pilot decision needs evidence of lower measured resource use and review
of every task that passed in only one arm. Separately test concurrent serving
before claiming improved GPU throughput.

## Host adapters

The SDK's `ReadDeduplication` policy uses the replay comparator's rule.
Pydantic AI applies it in `wrap_model_request`. LangChain applies it in
its sync and async model middleware, and a custom LangGraph model node can
call the projection directly. The caller supplies a run-scoped verifier
and a counter. The policy counts normalized tool-message text. Live
provider usage is measured separately.

OpenClaw and Hermes need their own verified request-boundary adapters.
Generic MCP and the ChatGPT plugin can support shorter tool results with
an authorized exact fetch. That response design has its own comparison
against current tool output, with follow-up fetches included in the cost.
