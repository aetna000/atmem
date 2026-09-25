# AtMem and AtFlows: preserving work after a restart

## The practical result

The recovery feature now lives in the products. An ordinary installed LangGraph
application can use AtMem's saved operation state and receipts. AtFlows observes
the attempts without deciding what the application may do.

| Situation | Observed result | How it works | How a user sees it |
| --- | --- | --- | --- |
| Document was published and its receipt saved, then the process was killed | Restart finished with **one document**, not a second publication | AtMem returned the stored result; no second execute attempt | Decisions → Resume work, or `atmem continuity show WORKFLOW_ID` |
| Document was published, but the process died before saving its receipt | Restart finished with **one document** | After the real lease expired, AtMem authorized a destination query; the registered tool checked the existing file | Same view shows execute then query, with the receipt |
| No reliable query or valid idempotency contract exists | Product tests show a safe stop | AtMem refuses to assume the action failed or repeat it | Needs confirmation with the next action explained |
| Observation service is unavailable | Application result is unchanged | Observer errors are counted; they do not authorize, suppress or repeat tools | SDK error count; missing events/prices remain missing |

Use [the installation and example guide](../../../docs/continuity.md). Continuity
is explicitly enabled, not automatically applied to arbitrary OpenClaw/AtBot
tools. The supported integration is synchronous, file-backed LangGraph plus
registered tools with declared destination capabilities.

## What was tested

The installed crash gate runs a real document-publishing application from a wheel
in an isolated environment. The source checkout and benchmark are not on the
worker's import path. An external proxy kills the worker at the receipt boundary.
The restarted application invokes ordinary LangGraph resume; the rig does not
choose the next step, repair a checkpoint, supply a receipt or reconcile work.

The document bytes come from the pinned public tau2-bench README. The external
effect is the actual published file, independently counted and hashed. In the
lost-receipt case the gate waits approximately 120 seconds for the real lease;
it does not alter the clock or shorten product safety rules.

Raw installed acceptance and wheel hashes:
[build 005](../results/product-acceptance-20260925-005/summary.json).
These are development artifacts, not newly published package versions.

## Public retail integration check

The preserved real native retail conversation was replayed through four
configurations using identical native prompts and tools:

| Configuration | Matching native model requests | Native tool calls | Conversation and final store state |
| --- | ---: | ---: | --- |
| Baseline: ordinary durable LangGraph | 18/18 | 6 | Identical |
| Baseline + AtMem | 18/18 | 6 | Identical |
| Baseline + AtFlows | 18/18 | 6 | Identical |
| Baseline + both | 18/18 | 6 | Identical |

This is a compatibility result: adding the products preserved this normal run.
It is not four fresh model runs or a higher task-success score. The original
native task reward remains zero; matching it does not turn it into a success.

[Raw public results and provenance](../results/public-retail-parity-20260925-007/README.md).
The earlier parity001 observer capture retained 24 tool-attempt events across 12
observed attempts. That capture is not a measurement of parity007. Its prices
are unknown; no evaluator costs were substituted.

## Fresh conversations: retain the full result

Four subsequent conversations used the live provider, not recorded replies.
All terminated normally; normal termination alone does not mean the requested
exchange was correct.

| Configuration | Native task reward | Model calls | Tool calls | Estimated provider cost |
| --- | ---: | ---: | ---: | ---: |
| Durable LangGraph | 1 | 14 | 6 | $0.053470 |
| With AtMem | 0 | 18 | 6 | $0.060450 |
| With AtFlows | 0 | 18 | 6 | $0.056462 |
| With both | 0 | 18 | 6 | $0.056226 |

In this one exposed task, the baseline selected the expected replacement keyboard;
the other conversations selected another keyboard. Identical first model requests
already produced different replies before tools ran. One conversation per arm
cannot establish which product caused a quality difference. All outcomes are
retained, with no selective reruns. This is a check of fresh execution, not proof
of better task accuracy or restart safety.

[Raw requests, responses, grading and accounting](../results/public-retail-live-20260925-001/README.md).
These four runs cost an estimated $0.226608; cumulative spend through them was
$0.283932 of the authorized $20, including the earlier native pilot. Prices are
usage-based estimates, not independently verified invoices.

## What happened when the retail agent was interrupted

The public retail store accepted an exchange, then an external fault killed the
application before it received the reply. After125 seconds every configuration
resumed through its normal checkpoint interface.

| Configuration | Repeated exchange request | Second store change |
| --- | ---: | ---: |
| Durable LangGraph | 1 | 0 |
| With AtMem | 0 | 0 |
| With AtFlows | 1 | 0 |
| With both | 0 | 0 |

AtMem stopped the uncertain request and asked for confirmation. The baseline
repeated it, but the store rejected it. The supported claim is **avoiding the
repeat request**, not preventing a second exchange or finishing automatically.
AtFlows observes execution; it is not supposed to decide whether to retry.
This used recorded native responses and one fault cell, not fresh held-out
conversations. [Exact journals and protocol](../results/public-retail-fault-20260925-003/README.md).

## Implementation details

- **AtMem authority:** encrypted definitions, operation identity, attempt leases,
  run/attempt binding and original receipts, stored atomically in the existing
  evidence vault. Full capture is required; first use advances the vault to schema
  3. Previous schema-2 readers refuse it.
- **Restart handling:** the host owns its native checkpoint. The installed
  governed node keeps stable message/call identity, requests an AtMem decision,
  and either uses a saved result, executes an authorized attempt, queries the
  registered destination or stops. It has no fallback journal.
- **Permissions:** narrow workflow hosts and workspace coordinators authenticate
  each call. Revocation, operator pause, key lock and conflicting arguments
  prevent further dispatch. Coordinator keys cannot claim operator-created work.
- **AtFlows:** authenticated allowlisted ingest, immutable scoped event IDs,
  attempt/charge binding, unique reported charges, retry/recovery overlap counted
  once, and explicit unknown prices. It has no execution authority.
- **Capacity:** open-work and retained-history limits, bounded leases/renewals,
  reserved completion/stop headroom, and event-only late reports. This remains
  a local sequential profile; it does not claim distributed exactly-once effects.

## Scientific interpretation and remaining gates

The installed tests demonstrate the specified receipt failure windows for the
document tool. Unit/integration tests exercise permissions, uncertainty, expiry,
concurrency, deletion and accounting. The retail cassette establishes no-fault
parity for one exposed development conversation. These answer different questions
and must not be combined into a production success rate.

Fresh faulted four-arm runs, stale/revoked-context scenarios, repeated qualification
and held-out task-cluster analysis remain required before claiming general
production gains. Optional Spec 007 task projection is not implemented; operation
completion does not silently complete governed tasks. Automatic instrumentation
of every model/tool call is also not claimed.

The earlier benchmark-owned recovery fixture is retained as historical design
evidence only. New product checks do not import it. Product/replay checks used no
new paid inference; the separate fresh-conversation pilot above did. The shared
USD20 ledger and all prior raw evidence remain intact. No release, tag, push or
deployment was performed.
