# Claude Opus 5.5 — benchmark review

Read-only model feedback, requested through the local Claude CLI at medium effort.
Returned model metadata: `claude-opus-5-5`. Tools were disabled.
This is not independent replication. Input/output provenance is retained in
`claude-opus55-medium-review-20261017`. See the adoption notes for corrections;
not every statement or recommendation below is endorsed.

# Read-only review of the AtMem Code Click benchmark evidence

*Model feedback on the supplied material only. This is not independent replication. I made no edits and called no tools. The request forbids writes and tool calls, so I have not created the plan-mode file or called ExitPlanMode.*

## 1. Are you benchmark-chasing?

**Yes, in part.** The evidence mixes three problems: adaptive selection, measurement that cannot resolve the effect, and real defects.

**Adaptive selection.** Many revisions were scored against the same five Click tasks, and the best one (P9) is being reported. That invites the winner's curse. P9's 19.55% is a maximum chosen across rounds, so you should expect it to shrink on fresh tasks. `packing.py` shows signs of fitting to those tasks even though the code is written generically:
- The stopword list includes "both, currently, instead, normally, ordinary, preserve", which look like issue-prose words.
- `_cleanup_sites` handles generator `finally` blocks, which coincides with the pager-cleanup failures.
- `_assertion_groups` and the comment about "update/default/value" read like reactions to observed failures.

Generic-looking code is not evidence against overfitting.

**Mechanism mismatch.** No AtMem MCP call completed in any of the 30 structure-arm traces. So the graph traversal, `code_context`, search, explore and source tools did not take part in any scored result. The only active intervention was a roughly 1k-token initial pack plus the prompt differences. Any saving belongs to "pack plus prompt", not to the retrieval architecture.

**Measurement too weak to resolve the target.**
- Native totals alone moved about 4% between rounds (1.127M vs 1.170M). Per-task variance is almost certainly larger.
- The gap between 19.55% and 20% is far inside the noise.
- 5/5 pass rate has a 95% Clopper-Pearson lower bound of about 48%. It cannot detect quality regressions, and P11's 2/5 shows how volatile pass rate is.

**Real defects.**
- Hard stops produce *unknown* usage. That is informative censoring: it correlates with difficult or looping runs and differs by arm, which makes P10 and P11 unusable.
- Native runs hit caps (4/5 all-cap pass), so the caps truncate the very costs being compared.
- Root selection uses only the single top lexical hit (`executable[:1]`). One wrong root wastes the whole graph nomination step.
- Structure-arm median latency was higher (33.7s vs 23.8s).

**Rejection risks, highest first:**
1. Selection and reuse of the five tuning tasks.
2. The retrieval mechanism was never exercised.
3. Missing usage under caps is informative, and caps interact with token totals.
4. Single-repository evaluation, with possible Click memorization.
5. The quality gate cannot detect regressions.
6. Pack-length and prompt confounds.
7. The definition of "total input tokens" is unspecified: are cache-read and cache-creation tokens included?

## 2. Three general architecture changes, each with a falsifier

**A. Uncertainty-aware multi-root packing with abstention.**
- Score the top-k roots. When the lexical score margin is small, spend the budget on a compact location map (`path:line`, names, signatures) across several candidates instead of 4KB of one root.
- Report a mechanism metric: does the pack's file set overlap the files the agent later reads or edits? Use gold patch files only on dev splits.
- *Falsified if:* on repository-disjoint dev tasks, localization recall does not improve over single-root packing, or the agent's number of native read/search turns is unchanged.

**B. Turn reduction as the target, not byte reduction.**
- Input tokens grow with turns, because each turn re-sends the accumulated context. A 1k-token pack saving about 44k tokens per task can only work by removing turns.
- First decompose native traces into: repeated reads, broad search output, test output, and per-turn re-send. Then aim the pack and tools at the largest avoidable category, for example "already-supplied ranges" metadata so complete excerpts are not re-read.
- *Falsified if:* the decomposition shows source reads are a minor share of native input, or turn counts do not fall in the structure arm on disjoint tasks.

**C. Make retrieval reachable in the host before evaluating its benefit.**
- Verify tool exposure (see §3).
- Run a budget and ablation sweep: pack 0/1k/4k/8k bytes, with and without MCP.
- Prune every heuristic (cleanup sites, assertion groups, compound segmentation, test excerpts) by ablation on non-Click dev repositories. Keep only those that survive.
- *Falsified if:* uptake is still near zero once exposure is confirmed, or uptake occurs but extra calls and listed tool schemas add tokens without reducing turns.

## 3. The MCP guidance idea and the 0/30 finding

"Zero completed calls" is an observation. It is not yet "unused", "unavailable" or "rejected". Before claiming any of those, establish per run:
- The server launched and the initialize handshake succeeded within client timeouts.
- `tools/list` returned all four tools.
- The client actually put the tool names into the model's tool list. Check prefixing, lazy or deferred MCP loading, and allowlists.
- Non-interactive permission mode did not silently deny MCP calls. Separate attempted-but-denied calls from calls never attempted.
- The server's own `code.knowledge_tool_prepared` audit count agrees with the client trace.

The two claims need different evidence:
- **"Unavailable"** needs exposure evidence.
- **"Unused"** needs exposure plus zero attempts.
- **"Beneficial"** needs uptake plus a paired quality and token effect against controls.

Critique of the guidance idea:
- `instructions` is an optional client hint. Many hosts ignore or truncate it.
- When it is consumed, it is also a prompt intervention. "Prefer one focused query before broad reads" can reduce native reads even if the tools add nothing.
- Listed tool schemas cost input tokens every turn.

Critique of the proposed P12 diagnostic:
- `logging.getLogger` is trivially solvable with a native grep and likely answerable from model memory, so the incentive to use MCP is low.
- One turn per arm in fixed order supports no inference either way.
- Prefer several retrieval-heavy read-only tasks, repeated, with randomized order, after the exposure checks pass.

A factorial control set that separates the effects:

| Arm | Purpose |
|---|---|
| Native | Baseline |
| Native + tools listed, no pack, no guidance | Cost of tool presence |
| Prompt-only (structure wording, no pack) | Prompt effect |
| Placebo pack (equal bytes of same-repo source, chosen by a fixed non-task rule) | Content vs. length/salience |
| Real pack, no MCP | Source-pack benefit |
| MCP, no pack (guidance none / bounded) | Retrieval benefit and guidance effect |
| Pack + MCP | Combined |

Only the real-pack vs placebo-pack contrast isolates content benefit.

## 4. Cross-repository design

**Why five more Click tasks are insufficient on their own:**
- Same repository, same identifier style, and the code the heuristics were tuned on.
- Possible model familiarity with Click.
- n=5 cannot bound quality or token ratios meaningfully.
- The set is single-use: it cannot support both choosing and confirming.

At most it can estimate how much P9's tuning result shrinks on fresh same-repository tasks.

**Stage 0 – engineering diagnostic (unscored, no claims).**
- Exposure verification.
- Usage capture that survives hard stops. Fix this so totals are recorded rather than inferred.
- Trace token decomposition.
- Environment qualification of the candidate harness on ARM. Record every qualification failure.

**Stage 1 – repository-disjoint validation (dev).**
- Prospective, seeded sampling from a *qualified* Python pool that excludes Click, stratified by repository. List the pool before sampling.
- Pre-declare at most 2–3 candidate variants plus the ablations above. Allow no other edits.
- Run each task × arm with ≥3 repeats, randomized AB/BA order, and fresh homes.
- Use this stage to estimate variance for sizing Stage 2.

**Stage 2 – locked confirmation.**
- Sample new repositories, disjoint from Stage 1 and Click.
- Freeze in advance and hash: wheel, prompts, caps, the token definition (uncached, cache-creation and cache-read reported separately and summed), and the analysis script.
- Primary endpoint, pre-declared: paired ratio of summed total input tokens per task, with a bootstrap CI over tasks. The exact 20% and 50% thresholds apply to the point estimate, and the CI is reported alongside it.
- Run once. Any change creates a new version that needs a new disjoint sample.

**Quality.**
- Measure with FAIL_TO_PASS / PASS_TO_PASS.
- "Equal or better" with zero margin is not testable at feasible n. A non-inferiority margin would be a *proposed versioned gate change* needing your explicit approval. Until then, keep the current gate and report pass rates with CIs.

**Missing usage.**
- The primary analysis requires complete totals.
- Report the missing rate per arm.
- Run a worst-case sensitivity analysis: assign missing runs the cap value or the arm maximum.
- If missingness exceeds a pre-declared threshold, the round is invalid.

**Latency.**
- Report setup, indexing (also amortized per snapshot), context and solver time separately, as medians and tails.

**Safety and governance failures.**
- Count: network attempts, out-of-workspace reads, secret or evaluator-test access, stale-source delivery, and instruction-promotion incidents.
- Any one of these during confirmation fails the governance gate, whatever the token result.

## 5. Established harness vs custom replay

**Reuse an established harness** for task sourcing, base commits, environments and grading. SWE-bench-style FAIL_TO_PASS / PASS_TO_PASS grading removes custom-grading doubt. Qualify ARM and Docker builds before counting any task as available. Do not assume the published images work.

**Keep the custom pieces** as the agent-runner layer:
- Fresh isolated homes.
- Network denial for solver commands.
- Sanitized Git history. This matters: base checkouts can carry future commits.
- Paired scheduling.
- Encrypted archiving of all outcomes.
- The "unknown, not zero" usage policy.
- The hash and freshness checks at query and transport (`_write`) boundaries.
- Scope-locked, read-only MCP.
- The audit events.

**Drop** bespoke task curation and bespoke pass judgments.

## 6. Bounded next actions and stopping rules

**Next actions:**
1. **Stop Click tuning now.** Record P9 as the final tuning result: 19.55%, which does not meet the exact 20%. Score no further revisions against those five tasks.
2. Fix usage capture under hard stops and add exposure logging. Test both in Stage 0.
3. Run the improved exposure and uptake diagnostic. Treat its outcome as decision input, not evidence of benefit.
4. Qualify a small external Python pool and publish what failed qualification.
5. Pre-register Stage 1 variants, then lock and run Stage 2 once.
6. Hold the unscored Click set. Use it only on the locked candidate, as a same-repository shrinkage check, and never to choose among variants.

**Stopping rules:**
- Set a fixed revision budget, for example ≤3 variants in Stage 1, with no mid-stage edits.
- If exposure is verified and uptake stays near zero across repeated tasks, drop all MCP-benefit claims and evaluate the product as pack-only.
- If Stage 1 shows the effect clearly below 20% for every variant, stop and report. Do not iterate toward a lucky round.
- If locked confirmation misses either gate, report the failure. Do not re-run.
- Any gate change must be a versioned proposal made *before* data, never after.

**What you cannot claim now:**
- Any 20% or 50% saving, including P9.
- Any saving beyond the five selected tuning tasks.
- Any benefit from retrieval, MCP, graph traversal or guidance.
- That the tools were unavailable, or that clients consume the guidance.
- Quality parity in general.
- Cross-repository or cross-language generalization.
- A latency benefit; the observed median was slower.
- That context caused the failed patches.
- That this review is independent replication.

