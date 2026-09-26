# The memory was saved. The confirmation was lost. What happens when the agent retries?

**Javad Taghia · AtMem.Ai Lab · 27 September 2026**

An agent asks its memory system to save a fact. The system saves it, but the confirmation never reaches the agent. The agent sees a timeout and tries again.

What does it read back afterward: one complete memory, two duplicates, a conflicting version, or a record with missing metadata?

We tested this failure sequence with AtMem and OpenClaw. In the tested configuration, the retry returned the **original record**, marked `already_stored`. Reading it back returned the complete original fact. The final store contained one active record, with no duplicate or conflicting record and a valid audit chain.

The result comes from a small, reproducible engineering test: five isolated bridge crash trials, three actual OpenClaw gateway crash trials, and one gateway no-fault control. All final qualification trials passed. The agent's tool-call sequence was scripted through a local model endpoint; this was not an evaluation of an autonomous model's recovery decisions.

## Why recall accuracy cannot answer this question

A recall test typically asks whether the system can retrieve the information needed to answer a question. That is useful, but it does not necessarily reveal what happened during a failed write request.

A system might retrieve the right sentence while storing it twice. It might preserve the text but change its source linkage. Or the agent might mistake a timeout for proof that nothing was saved and repeat an operation that already completed.

To answer the retry question, we need to inspect both the result presented to the agent and the persistent state behind it.

## The exact sequence we tested

The synthetic user request was:

> Remember that I prefer cobalt blue notebooks.

The memory tool received this fact:

> User prefers cobalt blue notebooks.

It used the memory slot `notebook_preference`.

We then exercised the five steps directly:

1. **The agent sends the write.** OpenClaw calls the real AtMem `memory_remember` tool.
2. **The memory system saves it.** The backend finishes the operation and produces a successful response containing the new record.
3. **The acknowledgement is lost.** A test proxy intercepts that response, saves it as evaluator evidence, withholds it from OpenClaw, and kills the memory backend with `SIGKILL`.
4. **The agent sees a timeout and retries.** The bridge's real request deadline expires after 2,000 milliseconds. OpenClaw subsequently retries the same fact with a new tool-call identifier, using a fresh backend connection to the same database.
5. **The agent reads the memory back.** OpenClaw calls `memory_get` using the record identifier returned by the retry.

The evaluator's saved copy of the lost response is not given to the agent. OpenClaw sees the timeout and obtains the record identifier through its retry.

The process killed in this experiment is the memory backend. OpenClaw's gateway and the operating system remain running.

## What OpenClaw received

The first write call returned a timeout to OpenClaw:

```text
atmem tools/call timed out after 2000ms
```

The retry then returned these values:

| Field | Observed value |
| --- | --- |
| `stored` | `true` |
| `status` | `already_stored` |
| `record_id` | The original record's identifier |
| `fact` | `User prefers cobalt blue notebooks.` |

The subsequent `memory_get` returned:

```text
User prefers cobalt blue notebooks.
```

That answers the immediate question: **the agent read the complete original memory, and the retry was recognized as already stored.**

## What we checked beyond the returned text

We did not stop at checking that the expected sentence appeared in the tool response.

The final store contained exactly one record, even when enumeration included inactive records. It remained active and retained its original identifier, source turn, episode linkage, fact key, and trust metadata. There was no superseding record, and the record generation remained zero.

The bridge trials additionally compared the complete record dictionaries before and after retry. They were identical, including the creation timestamp and metadata. Each bridge trial tested a retry with the original tool-call ID and then another retry with a new ID.

Each final trial retained one `memory.record_created` audit event and passed audit-chain verification. The gateway trials also passed SQLite integrity and foreign-key checks.

Retries were still visible in the audit history: the bridge trials recorded two semantic duplicate events, and the gateway trials recorded one. One preserved memory record does not mean that only one tool invocation occurred.

## Results and controls

| Final qualification condition | Runs | Passed |
| --- | ---: | ---: |
| Isolated OpenClaw bridge: lost acknowledgement, same-ID and new-ID retries | 5 | 5 |
| Actual OpenClaw gateway: lost acknowledgement, new-ID retry and read-back | 3 | 3 |
| Actual OpenClaw gateway: no-fault control | 1 | 1 |

Every trial used a fresh store and the same synthetic fact. The no-fault control deliberately repeated a successful write; it also returned the existing record and read back the complete fact.

These counts describe repeated deterministic tests at one failure boundary. They are not a measured production failure rate, a comparison against competing memory systems, or evidence that every possible write is safe to retry.

The final qualification used a clean source snapshot at commit `da046dc59fd41fdd77ed407d8f196cfc434b478c`. The bridge declares version 2.3.7, and the installed OpenClaw runtime reports 2026.9.1 (`ad6fe23`). The evidence bundle records source hashes and runtime details. This qualifies that source and configuration, rather than certifying a newly published package release.

## What “actual OpenClaw” means here

The gateway trials ran the installed OpenClaw runtime, the real registered memory tools, the production bridge, and the real Python MCP backend with a file-backed SQLite store. OpenClaw's normal lifecycle hooks staged the source message.

A local OpenAI-compatible endpoint supplied a fixed tool-call sequence: write, retry, read, finish. OpenClaw performed the calls and supplied their actual results to that endpoint. The endpoint chose the read identifier from the observed retry result.

This made the failure sequence repeatable without paid model inference. It demonstrates that the integration handles this sequence. It does not demonstrate that an autonomous model will always choose to retry correctly or preserve the same fact wording.

The gateway driver waited 600 milliseconds before each scripted response, allowing the bridge's 250-millisecond idle-close interval to dispose of the failed connection. Immediate retry on a still-open failed connection was not tested.

## We also retained the unsuccessful setup runs

Before final qualification, two embedded OpenClaw CLI attempts could not establish the current typed user-message binding. The memory tool rejected their writes, no record was created, and the fault was never injected.

Those attempts are recorded as setup failures. They are not counted as successful crash tests. An isolated gateway startup subsequently reached the intended write and fault sequence. The study does not establish the root cause of the embedded CLI behavior or claim that it was fixed.

The published development evidence also includes six earlier passing bridge trials and one passing gateway trial. These are kept separate from the final qualification counts above.

## What this test does not establish

The test interrupted delivery of a response **after the write had completed**. It did not kill the backend halfway through a SQL transaction. Consequently, it does not establish that a partially written memory record cannot occur at another failure point.

It also did not test sudden power loss, a whole-machine crash, damaged storage, concurrent writers, or distributed replicas. Retries used identical fact bytes, the same slot, and the same source binding. Paraphrased facts and conflicting updates require separate tests.

The tested direct-memory tool profile is one OpenClaw integration configuration. Results should not be generalized to every managed control-plane setup or arbitrary external tool.

The supported claim is precise: **when this exact memory write completed but its response was lost, a retry after reconnection returned the original complete record without creating a duplicate.**

## Paper, source, and evidence

The three-page technical note provides the protocol, assertions, results, and limitations in the same LaTeX format as our earlier memory-integrity paper.

- [Read the paper: *When the Write Lands but the Acknowledgement Is Lost*](https://huggingface.co/datasets/atmem/memory-integrity-continuity/blob/main/paper/openclaw-lost-ack/atmem-openclaw-lost-ack-retry.pdf)
- [LaTeX source](https://huggingface.co/datasets/atmem/memory-integrity-continuity/blob/main/paper/openclaw-lost-ack/main.tex)
- [Per-run evidence, test programs, checksums, and reproduction instructions](https://huggingface.co/datasets/atmem/memory-integrity-continuity/tree/main/openclaw-lost-ack-20260927)
- [Earlier paper: *Beyond Recall Accuracy*](https://huggingface.co/datasets/atmem/memory-integrity-continuity/blob/main/paper/atmem-memory-integrity-and-continuity.pdf)

The new supplement leaves the earlier paper and its benchmark results unchanged.
