# What the three builds measured

## Ten frozen tasks

The task definitions and acceptance rule were committed in `346f919` before the parser changed. Six synthetic tasks had an exact answer and four required abstention. Each policy ran on a separate copy of the same seeded database for that task. Policy order rotated by task. Ollama ran the pinned `qwen2.5:1.5b` model at temperature zero with seed 7. The exact-answer grader uses the declared answer after case and outer whitespace normalization. No model graded another model. [Frozen inputs](held-out.json) · [All 30 traces and grades](measured.json)

| Policy | Correct | False abstentions | Correct abstentions | Stale answers | Model calls | Input tokens | Output tokens | Total tokens per correct task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single reader | 10/10 | 0/6 | 4/4 | 0 | 6 | 1,306 | 51 | 135.7 |
| Adaptive review | 10/10 | 0/6 | 4/4 | 0 | 8 | 1,471 | 76 | 154.7 |
| Mandatory review | 9/10 | 0/6 | 4/4 | 0 | 12 | 1,813 | 142 | 217.2 |

| Retrieval measurement | Single reader | Adaptive review | Mandatory review |
| --- | ---: | ---: | ---: |
| Lookup attempts | 10 | 16 | 20 |
| Typed record rows returned by storage, counting repeat reads | 45 | 90 | 105 |
| Distinct typed records per task, summed across tasks | 18 | 21 | 21 |
| Calls to the raw source lookup API | 0 | 0 | 0 |

Storage instrumentation counted rows returned by `typed_units_for_records` and calls to `get_protocol_source_by_id`. Opening an original excerpt later in the dashboard is a separate, authorized source read.

Mandatory review returned `BR-814 (positive)` on the corrected identifier case. The expected answer was `BR-814`. The extra annotation failed exact grading. It contained no stale identifier. Three tasks declared specific stale values in advance. None appeared in a returned answer. All three policies abstained on conflict, expiry, a similar name with no exact assignment, and a missing assignment. Adaptive review added 190 total tokens over the single reader. The declared automatic-review criterion required higher accuracy and no increase in tokens per correct task. Review stays opt-in. This small synthetic set measures these decisions on one model. [Scoring and storage instrumentation](../../tools/benchmark_agent_team.py)

**Atlas was a development case.** Before the fix all three policies abstained even though the five code fields included the correct one. With the full field obligation, all three policies returned `AX-745`. This development result is reported outside the ten frozen tasks. [Atlas traces after the fix](atlas-development.json) · [Original pilot](../057-multi-agent-evidence-routing/spec.md)

## One cross-host correction with an independent engineering check

OpenClaw's installed MCP runtime read the sender's evidence and offered the reviewer's quote. Hermes' installed MCP registry received and completed the handoff. The qualification driver selected the tools and called the pinned local model once per role. It restarted the broker between the first offer and receipt. A separate pytest process checked the returned answer against a fixed contract requiring `AX-745`. AtMem imported its actual JUnit output. [Host traces and outcome receipts](host-qualification.json)

| Execution | Reader answer | Source | Memory generation | Pytest | Model calls | Input / output tokens | Broker elapsed | Model charge |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| Original | AX-100 | routing-v1 | 1 | Failed | 2 | 183 / 29 | 14,700 ms | Unreported |
| After correction | AX-745 | routing-v2 | 4 | Passed | 2 | 180 / 26 | 13,610 ms | Unreported |

The original run remains inspectable with its failing result and its original source. The rerun points back to that run and to the corrected source. Measured broker time starts at offer registration and ends at completion. It includes scheduling delay and the first run's restart. The driver separately recorded 41,762 ms and 34,170 ms from the start of host preparation through completion, including subprocess startup. These timings describe the two executions and do not establish a latency improvement.

## Transport coverage

| Integration | Boundary exercised | Verified result |
| --- | --- | --- |
| OpenClaw 2026.9.1 | Installed bundle MCP materializer and native tool execution in an isolated profile | `team_review` and `team_offer` for original and corrected sources |
| Hermes, commit `d0288be5b` | Installed MCP discovery and registry dispatch in an isolated profile | Inbox after broker restart, independent receive, quoted completion, revoked grant denied |
| MCP SDK 1.28.1 | Separate stdio server process, MCP initialization, tool discovery and calls | Received the corrected passage and returned `AX-745` |
| Pydantic AI 2.61.0 | Real `Agent.run_sync`, registered tools and a deterministic `FunctionModel` selecting calls | Received the corrected passage and returned `AX-745` |
| LangGraph 1.2.7 | Compiled `StateGraph` with a `ToolNode` consuming actual tool-call messages | Received the corrected passage and returned `AX-745` |
| ChatGPT plugin transport, MCP SDK 1.30.0 | Plugin's streamable HTTP server, OAuth 2 PKCE and isolated Firebase Auth/Firestore emulators | Bound account completed a handoff. A foreign account and a read-only grant were denied |

Framework tool fixtures establish interoperability. The live ChatGPT.com conversation UI and autonomous tool selection by the host models were outside the measurement. Host coverage and answer accuracy have separate denominators. [Framework and cross-host evidence](host-qualification.json) · [ChatGPT OAuth receipt](oauth-transport.json)
