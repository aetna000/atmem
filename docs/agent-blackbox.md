# Agent Black Box

AtMem Agent Black Box records a content-minimizing, tamper-evident flight
timeline from lifecycle hooks exposed by a runtime adapter. OpenClaw installs
those hooks automatically; custom runtimes emit the same events through
`atmem control mcp`.

It answers a narrow operational question:

> What did the host observe the agent and its tools doing during this run?

## What is recorded

Depending on which hooks the runtime emits, a flight can contain:

| Event | Retained evidence |
| --- | --- |
| `turn.input` | prompt digest, character count, image/tool counts |
| `model.input` | prompt/system/history digests, provider/model, counts |
| `context.disposition` | injected/empty/withheld/failed/not-applicable disposition, exact placement-envelope digest, candidate IDs and receipt correlation |
| `tool.requested` | tool name/kind, parameter digest and parameter-key names |
| `tool.completed` | result digest, outcome, error category and duration |
| `model.output` | assistant-visible-text digest, model-output-bundle digest, provider/model, size and token usage |
| `turn.ended` | message-bundle digest, success/cancel state and reason |

Raw prompts, responses, tool parameters and tool results are not stored in the
Black Box. Adapters must hash derived local paths before recording an event.
The OpenClaw bridge does this before data leaves the plugin. The timeline is
appended to the control evidence store and protected by a migration- and
kind-scoped hash chain.

Digests are fingerprints, not encryption or anonymization. Someone who can guess a low-entropy value can hash that guess and compare it, and bounded metadata such as model and tool names remains visible. Treat the local evidence database and exported reports as sensitive operational records.

## Inspect and export

```bash
atmem blackbox status
atmem blackbox runs --limit 20
atmem blackbox show RUN_ID
atmem blackbox verify RUN_ID
atmem verify-run RUN_ID
atmem blackbox export RUN_ID --format json --output flight.json
atmem blackbox export RUN_ID --format text --output flight.txt
```

The loopback dashboard starts with three operator checks: whether flights
finished, whether tools and outcomes worked, and whether context/model evidence
is correct. It shows plain-language attention points and recommended next
actions first; healthy flights and the complete evidence timeline remain
available in the collapsed investigation view.

When recent OpenClaw flights came from an older bridge contract, the dashboard offers
**Upgrade bridge & run test** once the installed Python release pins a newer
bridge. The guarded action installs that exact npm version, restarts and
health-checks OpenClaw, runs one fixed no-tools model turn, and opens the new
flight. It requires typing the host name and warns that the self-test may incur
a small model charge.

## What a verified flight means

A structurally complete flight has covered integrity, lifecycle, context, model,
tools, and response-binding components. In particular:

OpenClaw normally observes `turn.input` at `before_model_resolve`. Execution
paths such as `claude-cli` that omit that hook use `before_prompt_build` as an
idempotent fallback. If both hooks fire, the bridge records and stages the
authenticated input only once.

- the retained Black Box hash chain verifies;
- the run has `turn.input` and terminal `turn.ended` events;
- one explicit context disposition records what memory reached the model, or why none did;
- both model input and output were observed and the assistant-visible response digest is bound;
- every observed, correlated `tool.requested` event has a corresponding `tool.completed` event;
- there are no orphan, uncorrelated, or conflicting duplicate tool events.

Failed and cancelled turns have their own lifecycle verdicts. Tool errors remain
visible and produce a separate verdict. Missing hook events produce
`incomplete_evidence`; AtMem does not infer success from the assistant's words.

## What it does not mean

A verified flight does not prove that an external real-world outcome occurred. For example, a completed email tool hook proves that the host observed the tool return; proving delivery requires evidence from the mail system. It also does not semantically validate claims in the assistant response.

Future system-of-record verifiers can bind independently checked outcomes to the same flight without weakening this claim boundary.
