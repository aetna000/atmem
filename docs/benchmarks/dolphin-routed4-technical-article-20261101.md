# AtMem routed-v4 on DolphinBench: 479/600, and what the failed actions show

We ran all 600 DolphinBench tasks with AtMem's routed-v4 execution condition. The campaign finished on 1 November 2026: 479 tasks passed (79.83%) and 121 failed. Our earlier AtMem run passed 390 of the same 600 tasks (65.00%). The new run recovered 120 earlier failures and regressed on 31 earlier passes, a net gain of 89 tasks (+14.83 percentage points). We ran and graded it ourselves. It is not an official leaderboard entry, and it is not evidence that an agent learned anything. This report covers how the run was set up, how the grader decides a task passes, how the condition works, what the per-action replay shows about the remaining failures, and how to check the numbers yourself.

**TL;DR**

- 479/600 passed (79.83%), 121 failed. The earlier AtMem run passed 390/600: 120 tasks recovered, 31 regressed, net +89 tasks (+14.83 pp).
- We replayed the unchanged upstream grader offline against the recorded judge answers. It reproduced all 600 task verdicts with zero new model calls and found **727 required action groups**. Reads passed 98/100 and writes passed 504/627, so 602/727 groups passed and 125 failed. Four separate trace-wide constraints were also checked: 3 passed, 1 failed.
- We gave each of the 123 failed writes a diagnostic label: 68 missing a required fact, 25 wrong values, 20 wording or precision failures, 8 with no call, and 2 that left out a remembered fact we can show was delivered. That last count of 2 is a lower bound, not a full account of causes.
- The code under test is frozen research commit `bd38c5fcce270033e0e13df0c090592562e6fd38` with the installed AtMem 2.3.10b1 package. The current published beta, 2.3.11b1, is a different artifact, so 479 is not a score for that beta.
- Paid judging cost USD 3.905882, against an original cap of USD 20. Mem0's recorded 424/600 is a historical reference point, not a matched comparison.

## What was measured, and what was not

In DolphinBench, each task gives an agent one user message inside a persona's simulated world. That world includes connected applications (documents, email, chat, calendar, code review, slides, travel) and the persona's earlier conversation history. A task passes only if the agent makes the required application calls with the required content. A good answer in chat earns nothing.

The run configuration:

- **Reader:** `openai/gpt-5.6-luna` at high reasoning effort, through a subscription route, inside the Hermes native agent.
- **Judge:** `gpt-5.6-sol` at medium effort, through OpenRouter restricted to Azure routing.
- **Memory:** a frozen AtMem memory store with local embeddings. Memory, embeddings, fixtures, grader and tool isolation did not change during the campaign.
- **Code under test:** the frozen installed AtMem **2.3.10b1** package, plus the research `dolphin-routed-v4` / i3 guard and standing-fact source. The final harness source commit was `bd38c5fcce270033e0e13df0c090592562e6fd38`, with condition identity `371fc4aa324910033d1525032e2ed84f67722abf61c4d2090886e88a73618fb6`.
- **Apps:** simulated application tools only. No real Notes, GitHub or Google account was used.
- **Upstream:** DolphinBench pinned at commit `81cb6f8405b40a9e76089cef650806a80af06ea2`.

Read the results with these limits in mind:

1. **Self-tested.** We ran, graded and validated everything ourselves. The independent local full-run validator passed. The upstream maintainers have not accepted the result, and we make no claim that they have.
2. **Development used the public benchmark.** Public tasks shaped how the condition was built. The full-600 number is not a held-out or unseen-task score.
3. **Not a measurement of the published beta.** The run tested the research commit above, not the published AtMem 2.3.11b1 beta. In 2.3.11b1, formed statements are described as *source-linked unverified interpretations*, and later privacy hardening is included. Checking that a quote occurs in the source is not the same as checking that the statement follows from it. 2.3.11b1 is still a beta. Neither this benchmark nor the main-branch merge implies a stable release or a new package version.
4. **No learning claim.** The improvement is an end-to-end execution result. The measured condition combines routing, a commit checkpoint, completion tracking and memory delivery; this campaign does not isolate their individual effects. It does not isolate a memory-only effect. Memory retrieval, exposure to lessons, model-generated scores and repeated runs are not evidence that an agent learned.

## How a task passes

The rest of the report depends on how the grader works. The upstream explicit grader groups each task's checks into **action groups** keyed by `action_id`. A group is satisfied only when **one** recorded application call passes every check in that group. Each required action needs its own complete call. Separately, some tasks carry **trace-wide constraints**: conditions on the whole trace, not on any single call. The grader evaluates these too.

For task \\( t \\), let \\( C_t \\) be the recorded application calls, \\( A_t \\) the required action groups, and \\( T_t \\) the trace-wide constraints. Each group \\( a \\) has a tool and a set of checks \\( K_a \\). Some checks are mechanical (field equality, date matching). Others are judged: a model reads a field against a criterion. The calls eligible to satisfy \\( a \\) are

$$
E_a = \{\, c \in C_t \;:\; \mathrm{tool}(c) = \mathrm{tool}(a) \ \text{and}\ k(c) = 1 \ \text{for all}\ k \in K_a \,\}
$$

A task passes only if every action gets its own eligible call **and** every trace-wide constraint holds over the full trace:

$$
\mathrm{pass}(t) = \mathbb{1}\Big[\ \exists\ \sigma : A_t \to C_t \ \text{injective, with}\ \sigma(a) \in E_a \ \text{for all}\ a \in A_t \ \Big] \cdot \prod_{g \in T_t} g(C_t)
$$

Here \\( g(C_t) \in \{0, 1\} \\) is the result of constraint \\( g \\) on the whole trace. If the eligible sets share no calls, the first factor reduces to a plain conjunction, \\( \prod_{a \in A_t} \mathbb{1}[E_a \neq \emptyset] \\). The rule is strict. Calendar events, review comments and messages usually carry several checks each. A task with two write actions fails if either write misses a single check, and it also fails if a trace-wide constraint fails.

Two consequences follow for reporting:

- A "failed task" and a "failed action" are different units. Of the 121 failed tasks, some failed more than one action group, and a trace-wide constraint can fail a task even when all its action groups pass. We do not break down how the 125 failed groups and the one failed constraint are spread across the 121 failed tasks.
- When a group fails, the grader's saved per-check flags do not show which check broke. Answering that requires a replay at the level of individual calls, described below.

## Headline results

| Recorded run | Passed | Total | Score |
| --- | ---: | ---: | ---: |
| AtMem routed-v4 | 479 | 600 | 79.83% |
| Earlier AtMem | 390 | 600 | 65.00% |
| Historical Mem0 reference | 424 | 600 | 70.67% |

Both differences are measured in percentage points over \\( N = 600 \\):

$$
\Delta_{\text{earlier}} = 100 \cdot \frac{479 - 390}{600} = 100 \cdot \frac{120 - 31}{600} = 100 \cdot \frac{89}{600} \approx 14.83\ \text{pp}
$$

$$
\Delta_{\text{Mem0}} = 100 \cdot \frac{479 - 424}{600} = 100 \cdot \frac{55}{600} \approx 9.17\ \text{pp}
$$

We report recoveries (120) and regressions (31) separately because the net +89 hides the regressions. The 55-task gap over Mem0's recorded result compares two historical end-to-end runs. The public requests are the same, but the execution conditions differ, and this is not a matched memory-only experiment. It does not show that one memory system is better than the other.

### Results by original cohort

Our audit of the earlier 390/600 run split its outcomes into four cohorts. We keep them separate here.

| Original cohort | Tasks | Passed now | Failed now |
| --- | ---: | ---: | ---: |
| Earlier passes | 390 | 359 | 31 |
| Untraced, zero checks passed | 83 | 65 | 18 |
| Traced, zero checks passed | 84 | 31 | 53 |
| Traced, partial checks passed | 43 | 24 | 19 |
| **Total** | **600** | **479** | **121** |

Most of the gain came from the untraced/zero cohort, where 65 of 83 tasks recovered. In the earlier run, these tasks mostly never produced a traced application call. In Notes tasks, for example, the original audit found 35 attempts to write through local `memo`/`osascript` commands when the connected document tool should have been used. That is exactly the failure mode routing targets. The traced cohorts had already reached the application, and fewer of them recovered: 31 of 84 traced/zero and 24 of 43 traced/partial. Getting a call to the right tool does not fix what the call says.

### Results by required action

| Unit | Passed | Failed | Total | Pass rate |
| --- | ---: | ---: | ---: | ---: |
| Read action groups | 98 | 2 | 100 | 98.00% |
| Write action groups | 504 | 123 | 627 | 80.38% |
| **All action groups** | **602** | **125** | **727** | **82.81%** |
| Trace-wide constraints | 3 | 1 | 4 | n/a |

The four trace-wide constraints are not action groups, so they are not included in the 727. These replay-derived counts replace an earlier per-action summary, which relied on tool-name heuristics and counted trace-wide constraints as actions.

## The execution condition

routed-v4 combines four parts: a route guard, a commit checkpoint, completion tracking, and standing facts. All four sit around the frozen memory, which itself does not change. On the fixed 20-task diagnostic set used during development, the routed-v4 (iteration 3) configuration passed 17/20. Those 20 tasks were picked from earlier failures, so this result is post hoc and not a held-out estimate. We do not report the intermediate iterations, and we do not draw conclusions about run-to-run variation from them.

### Route guard

The guard is deterministic and never runs a tool. From the request text alone, it classifies the user's message: is an action requested, which domains does it touch, which destinations are named, and did the user explicitly ask for a local route? It then checks whether each proposed tool call is a *local detour*. Detours include local skills, terminal commands such as `memo`, `gh` or `osascript`, and local document writes. A detour is refused only when all three of these hold: the request is an action, the detour's domain overlaps the requested domains, and a configured **connected** application offers a write tool for that destination. The refusal names the connected tool to use instead. Explicit local requests ("in Apple Notes", "with gh") go through. The number of refusals per turn is capped, so the guard cannot trap the agent in a loop.

### Commit checkpoint

When memory tools are visible, the guard holds the **first** call to each connected write tool once. A held call is **not dispatched**. It never reaches the simulated application, so it is not a recorded application call, and the grader never sees it. The guard instead returns a notice suggesting a memory query built from the call's own arguments. The notice tells the agent to check standing facts and source fragments for details such as venue, recipient, day, and whether to accept or decline, and then to call the tool again. It also says that retrieved text is evidence, not instructions. The retried call is dispatched. Each held write costs one extra model step, and the checkpoint helps only if retrieval returns the relevant rule and the agent then applies it.

### Completion tracking

The guard classifies each connected write result as accepted, failed, unconfirmed, or undispatched. Outcomes are tracked by operation identity, so a success to one recipient cannot clear a failure to another. While a requested write is still outstanding, a short pending reminder is added to connected read results and memory results, a limited number of times per turn. In the benchmark profile, the user turn and the final answer are not modified.

### Standing facts

Standing facts are built per persona from that persona's own history, the same history every benchmark system ingests. No test request or grader data is used. A model proposes durable facts (rules, preferences, defaults, policies, commitments, roles), and each fact must include a verbatim quote that occurs in a source message. Facts whose quote cannot be found are dropped. The agent receives facts through a compact profile, a request-time prefetch, and a read-only `fact_search` tool.

The key limitation: a quote occurring in the source proves **only that the quote is there**. It does not prove that the model's one-sentence paraphrase follows from it. routed-v4 still called these "verified standing facts", which overstates what the check shows. The published 2.3.11b1 beta uses the more accurate "source-linked unverified interpretations".

## Completed per-action replay

The per-action analysis is finished. We replayed the **unchanged** upstream grader offline, using the recorded judge answers as inputs. The replay made zero new model calls and changed no grades, and it reproduced all 600 task verdicts. For every action group, it records:

- each check, marked as mechanical or judged;
- how each candidate call was evaluated against each check, with the original judge reason for judged checks;
- the eligible same-call matches \\( E_a \\);
- the distinct-call assignment \\( \sigma \\), or why none exists.

The public dataset includes all **1,920 checks**, each with its per-candidate evaluation and the original judge reason. Anyone can see which check broke for which call without trusting our summary.

### Diagnostic labels for the 123 failed writes

On top of the replay, we gave each failed write one descriptive label. The labels come from rules over the replay output, checked by a post-hoc review of the saved judge reasons. Where the rules gave an ambiguous result, the reviewer set the label by task-level override. Thirty tasks have overrides: 13 to `wrong_value`, 12 to `missing_required_fact` and 5 to `wording_or_precision`. These labels are diagnoses, not grades, and they never change a task verdict.

| Label | Failed writes | Meaning |
| --- | ---: | --- |
| `missing_required_fact` | 68 | The write omits a fact the criterion requires. Memory delivery is not established. |
| `wrong_value` | 25 | The write contains an incorrect value. |
| `wording_or_precision` | 20 | The right subject, but wording or precision falls short of the criterion. |
| `no_call` | 8 | The required write was never dispatched. |
| `missing_remembered_fact` | 2 | The write omits a fact whose source quote was verifiably delivered before the dispatched write. |
| **Total** | **123** | |

The two failed reads are counted in the action table above. This label set covers writes only.

Two rules govern how these labels should be read:

- **A missing fact does not show the fact was never retrieved.** For the 68 `missing_required_fact` writes, the required content is absent from the write, but we have not shown whether the relevant memory reached the agent. The agent may have retrieved it and then paraphrased it, overridden it or dropped it. Or retrieval may have failed. The label leaves the cause open.
- **"Remembered fact not applied" needs delivery evidence.** We use `missing_remembered_fact` only when the trace shows that a memory tool result delivered a source quote before the dispatched write, the quote matches the source message exactly, and the saved judge criterion for that write failed. Only two writes meet that standard. Across all 123 failed writes, the summary records the remembered-rule-not-in-write cause as **confirmed for 2** and **not established for 121**.

So 2 is a **lower bound** on delivery-to-write failures, not a complete causal accounting. Some of the 68, 25 and 20 may be the same kind of failure, but we lack the evidence to say so.

### Two confirmed examples

**Morgan 010.** Before the write, a memory tool result (message index 3, source session `001452`) delivered this source quote:

> any invoice/payment over $5,000 stays on manual review before payment.

The agent then sent an email. The saved judge reason says the email did not clearly state the required broader payment boundary or that review applies every time. The rule was in the agent's context, and the dispatched write still did not carry it.

**Morgan 026.** Before the write, a memory tool result (message index 5, source session `001429`) delivered this source quote:

> Kibo only gets pre-portioned food and treats Jamie or I have already approved. No samples, no substitute treats, and no label-guessing in the moment

The agent then sent an SMS. The saved judge reason says the SMS did not name the required approvers. Again, the rule was delivered and then left out of the dispatched write.

In both cases, "before the write" means before the **dispatched** write. If the checkpoint held a first call, that held call was never sent and is not the write being graded. These two examples show that delivering a rule does not guarantee the agent applies it. They do not show how common that failure is.

### What the residual failures suggest

Write content dominates what remains. Of the 123 failed writes, 115 are about content (`missing_required_fact`, `wrong_value`, `wording_or_precision`, `missing_remembered_fact`), and only 8 are missing calls. That matches the cohort picture. Routing targets whether a write reaches the connected application; routing alone does not guarantee correct content. The checkpoint and standing facts can help only when the relevant rule is retrieved and then actually applied, and the two confirmed cases show the second step can fail on its own. The levers we would examine next are retrieval quality and how faithfully a remembered rule ends up as concrete wording. The current evidence does not rank them.

Two known fixture limitations, Morgan 085 and Morgan 130, remain unresolved. Neither the fixtures nor the grader was changed for this run.

## The 31 regressions

Thirty-one tasks that passed in the 390/600 run failed in this one. The replay shows where each one failed (no call, mechanical miss, judged miss, or trace-wide constraint), but that locates the failure without explaining it. We have not established a cause for any individual regression. Possible mechanisms include:

- **Changed trajectories.** Detour refusals, checkpoint holds and prefetched facts all change what the agent does, and a different trajectory can produce different wording at the same tool.
- **Stochastic variation.** Each task ran once with a stochastic reader. Some regressions and some recoveries may not repeat on a rerun.

On the second point we can only describe the uncertainty. Results like these may vary between runs, but this campaign ran each task once, and **we have no run-to-run variance estimate**. The 479/600 is a single measurement, and the 14.83 pp and 9.17 pp differences carry no measured error bars.

## Cost and accounting

Paid API spend was **USD 3.905882**, all of it for judging, against the original USD 20 cap. The final ledger has no unresolved charges or reservations. It keeps 602 judge calls and 3,925 subscription reader calls, and the reader count includes interrupted attempts. Subscription, hardware and energy costs are separate and not included.

One schema detail could mislead: the public submission's `tests.json` shows `total_cost_usd` as `0`. That follows the submission schema's convention for subscription-routed ingestion and reader calls. It does not mean the run cost nothing. The USD 3.905882 of cash judging spend is recorded in the separate accounting ledger described above.

## Recovery provenance

The 600 tasks did not run as one uninterrupted, exactly-once pass. The campaign continued from preserved evidence after interruptions:

- The first 19 executions and grades were inherited byte-for-byte from the earlier evidence.
- Morgan 020 was reconstructed offline from saved native and app evidence, after duplicate read-only tool suppression broke its export. Its application action was not repeated.
- At 416 graded tasks, Hermes stopped on Riley 017 because the internal disk was full and the conversation database could not be saved. Its two completed reader responses had requested only memory tools, and both independent app logs and app states were empty. The owner authorized a retry. We preserved the original attempt, its native home, costs, authorization and SHA-256 inventories. A first restart hit the preserved native directory before making any model calls, and that startup attempt was preserved as well. The external launcher passed nine tests and then used the existing frozen, guarded resume entry point.
- We checked all 416 earlier grade hashes and found them unchanged. The retry passed. No result was chosen from among competing scored attempts.

The run executed directly, without AtSys management. All 600 scored records, the recovery evidence, the final reports and the final accounting snapshot were backed up to a private Hugging Face dataset, and their downloads were hash-verified. The original source worktree remains unchanged for audit. The AtMem main-branch merge ([`97eb820`](https://github.com/aetna000/atmem/commit/97eb82051014bf04f4c53597ad0a4c8d9212879e)) keeps the published 2.3.11b1 beta product code rather than replacing it with the earlier research wording. The tested commit `bd38c5f` and the published beta are therefore different code.

## Practical guide: using the public dataset

The release is at [`atmem/dolphinbench-routed-v4-20261101`](https://huggingface.co/datasets/atmem/dolphinbench-routed-v4-20261101), and this article is hosted there as `ARTICLE.md`. It has four configs:

- **`tasks`**: per-task rows for the 600 tasks.
- **`actions`**: per-action-group rows for the 727 required action groups.
- **`checks`**: per-check rows for the 1,920 checks, including the per-candidate evaluation and the original judge reason.
- **`trace_constraints`**: the four trace-wide constraints, separate from required actions.

Load them like this:

```python
from datasets import load_dataset

repo = "atmem/dolphinbench-routed-v4-20261101"

tasks = load_dataset(repo, "tasks")
actions = load_dataset(repo, "actions")
checks = load_dataset(repo, "checks")

print(tasks)
print(actions)
print(checks)
```

The dataset card documents the column names and splits. A useful first sanity check is to recompute these totals and compare them with this article:

- 600 tasks, 479 passed, 121 failed;
- 727 action groups: reads 98/100 and writes 504/627, so 602 passed and 125 failed;
- 4 trace-wide constraints, 3 passed, reported separately from action groups;
- 1,920 checks;
- failed-write labels: 68 / 25 / 20 / 8 / 2.

Some analyses you can run from the configs:

1. **Find which check broke.** Take the failed action groups, match them to their checks, and read the per-candidate evaluations. A group fails when no single call passes all its checks, or the grader cannot assign a distinct eligible call to each required action. Look for the call that came closest and the check it missed.
2. **Read the judge's reasoning.** For judged checks, the original judge reason is attached to each candidate evaluation. The post-hoc review that set the diagnostic labels worked from these saved reasons.
3. **Inspect the two confirmed cases.** Look up `morgan/010` and `morgan/026` and compare the delivered quotes above with the dispatched writes and the failed criteria.
4. **Separate cohorts.** Tag each task with its original cohort (earlier pass, untraced/zero, traced/zero, traced/partial) and keep the cohorts separate when you aggregate.

## Reproducing the grading

Reproducing the grades requires upstream DolphinBench at the exact pinned commit `81cb6f8405b40a9e76089cef650806a80af06ea2`, so that grading semantics match this run. The replay described here ran the unchanged upstream grader offline against the recorded judge answers, with zero new model calls. Done the same way, it should reproduce all 600 verdicts without any judge spend.

To validate the submission archive, use the offline submission-validation function in the upstream harness at that pinned commit, following that repository's own instructions for the invocation. The graded submission has SHA-256 `4e3130b5be2ba2aab4fa23570c69867fe1cfa1289be735f782a658170e559a05`, so you can confirm you are validating the same file.

## What this result establishes

The configuration combined a connected-write route guard, a one-time hold on the first write so the agent checks remembered rules, completion tracking, and delivery of source-quoted standing facts. With memory held fixed, it went from 390 to 479 of 600 tasks: 120 recoveries, 31 regressions, net +14.83 pp. Most of the gain came from tasks that previously never reached the application. The completed offline replay shows what remains: 125 of 727 required action groups failed, 123 of them writes, plus one of four trace-wide constraints. The failed writes are mostly about content. For two of them we can show the rule was delivered and still left out, which is a lower bound. For the other 121, delivery is not established either way. The result is a single self-tested run on a public benchmark, from a research commit that is not the published 2.3.11b1 beta, with no variance estimate and no claim of official acceptance or of learning.

## Links

- Public dataset for this run (article hosted as `ARTICLE.md`): https://huggingface.co/datasets/atmem/dolphinbench-routed-v4-20261101
- AtMem main-branch merge: https://github.com/aetna000/atmem/commit/97eb82051014bf04f4c53597ad0a4c8d9212879e
- AtMem source: https://github.com/aetna000/atmem
- Upstream DolphinBench, pinned: https://github.com/mem0ai/dolphinbench/tree/81cb6f8405b40a9e76089cef650806a80af06ea2

The [dataset card](https://huggingface.co/datasets/atmem/dolphinbench-routed-v4-20261101) includes a concrete offline Python validation example, the full accounting and provenance records, and links to the [original 390/600 evidence](https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench) and [maintainer-review PR](https://github.com/mem0ai/dolphinbench/pull/10).
