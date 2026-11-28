# Multi-agent evidence routing

## Product direction

Give an operator one question to answer when agents disagree. Which memory reached which agent, and what happened next? The starting workflow is a short factual question in one authorized workspace. It runs from the Python SDK and from **Sessions → Agent handoffs** in the local dashboard. The branch is based on v2.3.16b3.

Entelligence connects agent sessions to step-level usage and engineering outcomes. Its replay UI turns a transcript into an inspectable sequence. AtMem can carry that interaction one step further by linking a handoff to a memory revision, its source and the authority that allowed delivery. A support engineer investigating a wrong assignment should be able to follow the answer back to the assignment the reader saw. [Agent Insights](https://www.entelligence.ai/agent-insights) · [agentplay](https://www.entelligence.ai/agentplay)

MeterRouter makes agent and model selection conditional on the remaining budget, including a reserve for a final answer. This implementation borrows the reserve idea. AtMem already has a five-state evidence sufficiency decision, so the pilot uses deterministic routing and one model. The paper’s results cover a different task distribution and pricing model. [MeterRouter, sections 4–5](https://arxiv.org/html/2611.34327v1)

## What runs today on this branch

1. Open the dashboard from this checkout with `python -m atmem.cli dashboard`, sign in, and choose **Sessions → Agent handoffs**. Recorded examples show all eighteen measured executions. Select a benchmark case and policy, select a graph node, then open its evidence.
2. To ask a workspace question, choose **My workspace**. This requires active native AtMem memory, a local account with workspace memory access, and Ollama serving the installed `qwen2.5:1.5b` GGUF on loopback port 11434 for model calls. The workspace comes from the signed-in identity. Run-scoped and viewer accounts cannot open live workspace memory. The request accepts a question, policy and model-call limit. Live trace text stays in the page for the current run. AtMem records native preparations and confirmed deliveries in its governed store.
3. The SDK entry point below accepts an already-authorized memory instance and authority scope. Both model roles operate within that exact scope. The initial use case is an extractive question for which a short answer can be quoted from one supporting memory.

```python
from atmem.agent_team import run_agent_team

result = run_agent_team(memory, scope, "What is my favorite city?", max_calls=2)
print(result["outcome"], result["answer"], result["source_ids"])
```

| Stage | Executed behavior |
| --- | --- |
| Memory lookup | Core reciprocal-rank fusion uses lexical and graph channels. The first window nominates up to 4 of 24 candidates, allows 16 graph visits and uses depth 1. Native v2 packs evidence into at most 4,096 UTF-8 bytes. |
| Routing | A sufficient bundle with spare room in the nomination window goes straight to the reader. Partial, stale, contradictory, unsupported or full-window results request a second search. The pilot reserves one call for the final reader. |
| Expanded lookup | Search the same workspace with up to 16 of 64 candidates, 64 graph visits and depth 2. The evidence byte cap is identical. An unresolved result or a still-full window ends the run. This checks the records available to AtMem. |
| Source reviewer | If the expanded lookup passes, a separate local model invocation selects a quotation. AtMem checks the quotation against answer-bearing memory entries in the serialized package and resolves the source IDs. |
| Answer reader | Receives either the initial package or just the reviewed quotation. The output must be an exact substring of the eligible evidence. A semantic error can still be a valid substring, so answer correctness is graded separately. |
| Delivery | Scope, generation and expiry are checked at handoff. AtMem confirms the exact original package after the local model returns. The trace reports the narrowed reviewer-to-reader handoff separately, including actual model input and output tokens. |

The dashboard runs one live team at a time. The two roles use separate stateless requests to the same local model. They share workspace authority. The cap limits generation attempts. Failed generations retain their attempt count and expose incomplete usage. The UI displays live and recorded runs separately.

## First paired measurement

The six synthetic cases and answer keys were fixed before the scored inference run. Each arm started from a copy of the same per-case seeded database, with the same record IDs. Each used the same model digest, question, byte cap, temperature, seed, maximum of two calls, and answer grader. The execution order rotates across cases. A correct result is a case-insensitive exact match for an answerable question, or an explicit abstention on an unanswerable one. Model and lookup failures are scored incorrect. Source and question text in this pilot is synthetic. [Fixtures](cases.json) · [Per-case handoffs, returned quotes and measured usage](../../atmem/control/assets/team-examples.json) · [Runner and grader](../../tools/benchmark_agent_team.py)

| Policy | Correct tasks | Correct answers on answerable tasks | Correct abstentions | Memory lookups | Model calls | Input tokens | Output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single reader | 5/6 | 2/3 | 3/3 | 6 | 2 | 425 | 16 |
| Always request review | 5/6 | 2/3 | 3/3 | 12 | 4 | 581 | 37 |
| Evidence-aware review | 5/6 | 2/3 | 3/3 | 10 | 2 | 425 | 16 |

Evidence-aware review saved 156 input tokens (26.9%) against always requesting review. The single reader used the same tokens and four fewer lookups. All arms answered the corrected value, abstained on the expired, conflicting and missing inputs, and missed the answerable Atlas routing-code question. On Atlas, widening the first window from four returned candidates to five still left the native decision at partial. These six cases support keeping review opt-in. Production accuracy and monetary savings remain open measurements. The traces include cold-start timings. The pilot measured token use and did not estimate model price or electricity cost.

Run the benchmark from this checkout with Ollama running and the model installed.

```sh
PYTHONPATH=. python tools/benchmark_agent_team.py --output /tmp/atmem-team-results.json
```

A separate live browser check used an encrypted workspace containing five preference records. The initial candidate window filled, the expanded search recovered sufficient evidence, and the reviewer and reader returned Tallinn on two model calls. This checks that the conditional handoff works. It is outside the six scored cases. [Dashboard preview](handoffs.png)

## Next engineering milestones

| Priority | Build | Acceptance evidence |
| --- | --- | --- |
| 1. Prove when review helps | Freeze unseen answerable and unanswerable tasks with corrections, competing assignments, and similar entity names. Diagnose the Atlas sufficiency failure on development examples. Compare adaptive, fixed and single-reader policies with the same authorized tools. | Publish per-task answers, false abstentions, stale answers, actual source reads and tokens per independently correct task. Require an improvement over the single-reader baseline on a declared target before enabling review automatically. |
| 2. Make a run portable across hosts | Add a common run ID, parent step ID, host/agent identity, scoped evidence receipt, and observed usage to existing execution events. Start with one real cross-host reviewer-to-reader handoff. Link encrypted evidence and enforce the recipient’s memory grants independently. | Replay the same run after restart, follow both host events, and show a denied handoff when the recipient lacks access. Qualify OpenClaw, Hermes, MCP/ChatGPT, Pydantic AI and LangGraph individually. |
| 3. Link memory decisions to engineering outcomes | Add a project-level run list with drill-down to a task, pull request, test result or incident. Show the provenance and revision of the memory used by each step. Add priced model selection once estimated and observed usage can be reconciled. | An operator can trace a failed outcome to the exact evidence used, replay the corrected case, and compare outcome, cost and latency with the previous run. |
