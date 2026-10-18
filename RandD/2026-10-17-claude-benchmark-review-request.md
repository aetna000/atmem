# Read-only independent-model review request

Requested reviewer: Claude Opus 5.5, medium effort, local subscription CLI.
No project-editing tools, MCP access, API keys or model fallback are permitted.
Review only the supplied material. This is model feedback, not an independent
experimental replication. State uncertainty rather than inventing results.

## Goal and actual evidence

AtMem Code provides scoped, inspectable current repository structure and source
to coding agents. User target: 50% fewer total input tokens versus native tools,
accept exact 20% if 50% is not demonstrated, with equal or better task test-pass
rate. Preserve governance and distinguish tuning from unscored confirmation.

We repeatedly tuned on five public historical Click bug-fix tasks. Different
source snapshots belong to the same repository. Many candidate revisions were
tested against fresh native controls. Five-task rounds are not stable estimates.
Do not mistake generic code changes for proof against benchmark overfitting.

Best fully measured P9: native/structure 5/5 functional each, inputs 1,126,556 /
906,298 (19.551447% saving, below exact 20%). All-cap passes 4/5 / 5/5; median
setup/index/context/solver 23.755s / 33.670s. This is selected tuning evidence,
not a broad benefit. P10: 5/5 each but native total usage unknown after a hard
tool stop. P11: native 5/5 versus structure 2/5; native input 1,170,061, structure
unknown (four known receipts total 552,917). No accepted saving or confirmation.
Failed patches include a simple logical set-reuse bug, invalid Python syntax,
and pager cleanup failures. Do not assert context caused those errors.

Read-only audit of all 60 P6–P11 attempts found ZERO completed AtMem MCP calls
in all 30 structure-arm traces. The supplied initial source pack was actually
submitted, but the agent used native commands afterward. Separate disjoint
CPython host probes explicitly requested MCP and did observe exact current
source responses, scope refusal and native read isolation. Those are integration
controls, not coding-benefit evidence and not proof of spontaneous uptake.

The architecture: pinned Enola extraction; incorporated Cognee graph traversal;
scoped protected canonical generation and source bytes; exact source hashes and
stale-withholding at query and transport boundaries; bounded source packing.
Packing uses task lexical root selection, graph caller/callee nomination, static
import bindings, class navigation, optional real existing-test excerpts, byte
allocation and explicit omissions. No model-generated summaries or fake tests.
MCP tools: focused code_context, compact code_search, code_explore, code_source.
All read-only; project/database/scope cannot be overridden by model arguments.

Latest UNBENCHMARKED change: fixed operator-authored MCP initialize instructions
recommending focused retrieval when needed, avoiding duplicate complete reads,
and retaining native fallback for stale/insufficient evidence. Source text is
not promoted to instruction. Proposed disjoint uptake diagnostic is supplied.
No scored run with this guidance has started. Do not assume clients consume it.

## Current evaluation constraints

Pinned CLI; Luna low through existing subscription. Fresh isolated homes and
workspaces, no network for solver commands, no owner secrets, sanitized source
Git history, no hidden evaluator/test-patch exposure, paired AC/CA scheduling.
24-tool hard stop, 180 seconds, 4096-byte initial source context, 500k post-turn
input+output audit. Quality floor currently 5/5 on the familiar five-task tuning
round; confirmation separately requires no worse than native. Missing full
usage is UNKNOWN, not zero, estimated or replaced. Interrupt probes retain only
partial counters; no historical totals were backfilled. All negative outcomes,
patches, prompts and declared CLI events are encrypted and archived/recovered.

One still-unscored five-task Click confirmation set exists. Do not inspect or
request its solutions or labels. Its repository is still Click, so success
would not prove cross-repository generalization. Do not quietly weaken gates
or choose favorable native controls to make the target pass.

## External primary-source options checked by the main agent

- SWE-bench official harness: real GitHub issue repair, held-out tests,
  FAIL_TO_PASS and PASS_TO_PASS evaluation; Docker-based reference evaluation.
  https://github.com/SWE-bench/SWE-bench
- SWE-PolyBench: public multi-language repository-level task evaluation and
  curated verified split. https://github.com/amazon-science/SWE-PolyBench
- SWE-bench-Live: aims at newer real issues and broader repository coverage.
  https://github.com/microsoft/SWE-bench-Live
- SWE-rebench V2: broader language/repository task collection; environment
  qualification and exact revision/license checks would still be needed.
  https://github.com/SWE-rebench/SWE-rebench-V2-OpenRewardEnv

No chosen external benchmark has been run or qualified locally yet. Do not
invent affordable feasibility or task counts from these links alone. ARM/Docker
and dependency build constraints matter. Start with feasible Python repositories
but do not claim untested languages. Repository names are candidates, not
availability claims: attrs, pluggy, packaging, HTTPX, Rich, Jinja, pytest.

## Questions to answer candidly

1. Are we benchmark-chasing? Separate real implementation defects from adaptive
   evaluation/selection bias and underpowered measurement. Rank rejection risks.
2. Give the three most promising GENERAL architecture/integration changes and
   the observations that would falsify each. No Click-specific rules, expected
   patches, oracle retrieval or hard-coded task-name tuning.
3. Critique the MCP guidance idea and 0/30 uptake finding. What must be verified
   before claiming tools were unused, unavailable or beneficial? What controls
   distinguish source-pack benefit, retrieval benefit and prompt effects?
4. Propose a practical cross-repository design, separating a small engineering
   diagnostic, repository-disjoint validation, and locked confirmation. Specify
   prospective sampling, authentic tasks, baselines, ablations, repeats/seeds,
   token/latency/quality accounting, missing usage and safety failures. Treat any
   changed five-of-five gate as a proposed versioned design, not approval to
   relax it. Explain why five more Click tasks are insufficient by themselves.
5. Should we reuse an established harness or keep custom replay? What parts of
   the existing isolation/provenance/AtMem integration are worth retaining?
6. Recommend bounded next actions and stopping rules that prevent endless tiny
   revisions until a lucky 20% round. Explicitly say what we CANNOT claim now.

Respond in at most 1800 words. Do not edit files, run tools, hide negative
results, promise 20%/50%, or call your review independent replication.
