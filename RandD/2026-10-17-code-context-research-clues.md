# Code context: external clues for the active efficiency loop

Owner requested open-source and arXiv review alongside—not instead of—the
running benchmark. Reviewed 2026-10-17; links point to primary sources. These
are design hypotheses, not evidence that AtMem meets the requested savings.

| Source | Mechanism worth testing | AtMem implication |
|---|---|---|
| [Cognee CodeRetriever](https://github.com/topoteretes/cognee/blob/main/cognee/modules/retrieval/code_retriever.py) | Bounded graph exploration/traversal and query operations | Continue using the incorporated licensed traversal over authorized snapshots; do not build a parallel graph engine. |
| [Aider repository map](https://aider.chat/docs/repomap.html), [implementation](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py) | Dependency-ranked symbols fitted within an active context budget | Keep compact navigation separate from implementation bodies; prioritize task-mentioned symbols, deduplicate source spans. Current byte ceiling is not a tokenizer guarantee. |
| [LocAgent, arXiv:2503.09089v1](https://arxiv.org/html/2503.09089v1) | Typed contain/import/invoke/inherit graph; exact-name then sparse search; fold/preview/full retrieval | Diagnose entity localization separately from task resolution. Use bounded call paths and method inventories; consider progressive detail in a subsequent experiment rather than stuffing whole classes. |
| [RepoGraph, arXiv:2410.14684v1](https://arxiv.org/html/2410.14684v1) | Definition/reference structure and dependent context; integration into existing repair workflows | Keep native coding tools and identical solver settings; supply connected source evidence rather than repeated unrelated matches. |
| [RepoCoder, arXiv:2303.12570v3](https://arxiv.org/html/2303.12570v3) | Refine retrieval using a generated completion in subsequent rounds | Potential later on-demand refresh, not a free optimization: extra rounds cost tokens/latency, and generated code must not become authoritative evidence. Its completion results do not establish repair-task performance. |

## Decisions for this loop

Already implemented and frozen: reuse upstream call traversal; select concrete
method bodies behind class navigation; nominate statically import-bound helpers;
retain source locations, visible omissions, authorization and freshness checks.
No new LLM, embeddings, training or owner installation is required.

Do not alter the currently running candidate based on paper claims. If its
quality/token gates fail, examine retained source exposure and solver behavior
before selecting a new bounded experiment. Promising later changes include
dependency-weighted budget allocation and progressive detail retrieval. Neither
is accepted until measured end-to-end against fresh native controls with no
quality loss. Count all input tokens across turns, not just the injected map.

The historical Click tasks remain small engineering evidence; neither upstream
paper scores nor a successful five-task cohort justify a general 50% claim.

## Usage observability follow-up (P8 remains frozen)

The [official Codex App Server documentation](https://learn.chatgpt.com/docs/app-server)
lists incremental `thread/tokenUsage/updated` notifications and `turn/interrupt`.
The pinned local CLI 0.162.1 independently generated a schema containing
thread/turn-bound usage updates with `last` and `total` breakdowns, input/output/
cache counters, and thread/turn-bound interruption parameters. Schema generation
used no model call, changed no owner configuration and did not alter P8.

This suggests a future benchmark-only observation route without raising caps.
It is not yet a qualified runner or proof that an interrupted inference's entire
usage arrives. A disjoint real-host diagnostic must verify update timing, terminal
versus partial coverage, identity, sandbox and hard-stop behavior. Cumulative totals
must not be summed as independent calls. Never backfill old missing usage from
these schemas or treat the last partial update as a complete receipt. Switching
transport requires a separately frozen protocol and matched controls; no mid-cohort
switch, extra API billing or retroactive percentage is permitted.
