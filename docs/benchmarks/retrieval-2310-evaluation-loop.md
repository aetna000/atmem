# AtMem 2.3.10: evaluation-gated retrieval correction loop

Status: implementation and bounded evaluation in progress under
[`specs/046-retrieval-performance-2310`](../../specs/046-retrieval-performance-2310/spec.md).
Experimental implementations and private diagnostic runs do not establish final
acceptance, production-scale qualification or publication readiness.
Owner requirement: improve actual memory utility, using current Mem0 as the
reference, rather than add benchmark-specific rules. This protocol supplements
the completed DolphinBench campaign; it does not replace its results.

## Before implementation

Create the feature's SpecKit spec, plan and tasks, then perform consistency
review before product changes. The active `.specify/feature.json` selects
`specs/046-retrieval-performance-2310`; do not silently select another feature.

Freeze a machine-readable experiment manifest before paid evaluation. It must
identify source versions, eligible task IDs, split roles, scope and chronology,
sampling seed, difficulty strata, metrics, thresholds, model/embedding revisions,
reader/judge settings, budgets, candidate commit and installed wheel hash.
Research current Mem0 OSS and hosted behavior separately; do not describe
undocumented hosted internals or assume the earlier OSS comparator is current.

## Four ordered pillars

| Pillar | Product change | Targeted evaluation | Primary diagnostic |
| --- | --- | --- | --- |
| 1 | Hybrid semantic/lexical retrieval and reranking | Implicit preferences, paraphrases, entity ambiguity, lexical distractors | Recall of required supporting evidence within a fixed context budget |
| 2 | Agent-callable read-only search and bounded follow-up | Missing initial evidence, multi-hop discovery, reformulated searches | End-to-end fully correct tasks under fixed total tool/token limits |
| 3 | Grounded preference and temporal-state views | Explicit versus inferred preferences, corrections, effective dates, recurring entities | Correct applicable state with supporting provenance |
| 4 | Semantic coverage verification and complementary packing | Multiple facts, exclusions, qualifications, linked result episodes | Complete required-evidence coverage within a fixed context budget |

Every pillar also measures fully correct task success, evidence precision,
unsupported assertions, stale-state errors, correct refusal, p50/p95 latency,
tokens, provider cost and failures. Report raw numerator/denominator and per-type
results. No metric may silently replace task utility as the final objective.

## Sampling and leakage controls

1. Define task-type eligibility from request characteristics and independent
   task requirements before inspecting candidate outcomes. Cover all personas
   where applicable. Do not select only cases the candidate passes.
2. Define difficulty from frozen baseline evidence: baseline-failed relevant
   cases plus a separately sampled baseline-passed retention/control stratum.
   A hard-case-only score is not an estimate of suite-wide success.
3. Randomly sample within type/persona/difficulty strata using a committed seed.
   Freeze tuning, validation and confirmation IDs before implementation. Prevent
   equivalent questions and shared evidence/episode clusters crossing roles;
   preserve authorized chronology and prevent future-history leakage.
4. The existing 600 outcomes have been inspected. Any partition of them is a
   known-benchmark diagnostic, not a genuinely untouched test. The owner's
   amendment fixes 60 sampled tasks and an 18-task recurring subset; do not
   collect another corpus or require external transfer data for this workflow.
   A later generalization study would need separately qualified evidence and
   its own authorization. Do not invent or rewrite scored conversations.
5. Fix confirmation sample sizes using baseline class counts and paired power
   analysis for a stated minimum useful effect. If budget/availability is too
   small, label evidence inconclusive; do not declare a gate passed from a few
   favorable questions.

## Bounded iteration loop

For each pillar, in order:

1. State the failure hypothesis and one bounded architectural change.
2. Evaluate unchanged baseline on the exact frozen sample and environment.
3. Implement the change with contract, authorization, migration and fallback
   tests. Smoke questions validate wiring only, not quality claims.
4. Run paired tuning evaluations; keep every failure and trial identity.
5. Compare baseline, this pillar alone, previous accepted stack and new stack.
   Use leave-one-out ablations when interactions make attribution ambiguous.
6. Advance only if targeted utility improves without unacceptable safety,
   control-stratum, latency or token regressions. Freeze numeric guardrails before
   results; do not choose them retrospectively.
7. Select one candidate from validation, then open one confirmation shard once.
   A failed shard becomes development evidence, never a reusable sealed test.
   Maximum three candidate evaluations per pillar initially; reassess hypothesis
   and spending rather than silently extending the search.
8. Record accept, reject or inconclusive with receipts. Do not tick a pillar
   merely because code exists. A failed gate blocks progression to the final run,
   not safe offline diagnosis or work on independent tests.

Use identical reader, judge, app state, memory scope, corpus and resource limits
within paired comparisons. Fix seeds/settings where supported and disclose
remaining nondeterminism. Report paired confidence intervals (clustered by
conversation/evidence episode when appropriate), discordant wins/losses and
predeclared multiplicity handling. For small sets use repeated paired trials
within the reserved budget; never select the best stochastic execution.

## Targets and final gate

The requested pillar target is 3x its frozen targeted baseline on a predeclared
bounded higher-is-better metric. Where that would exceed 100%, do not silently
substitute another target: record the ceiling and propose a separately named
error-reduction criterion before evaluation. Zero baselines require absolute
effect criteria rather than undefined ratios. Report actual effects even when
they miss the desired target.

After four pillars pass, freeze the combined candidate and evaluate all 60
working-set tasks, including broad regression controls and component ablations.
Do not call this fixed, previously inspected set sealed or untouched confirmation.
Target: 2.5x task accuracy relative to the baseline on that *same* confirmation
set. The historical overall 192/600 = 32% makes 80% the corresponding full-suite
aspiration, not the baseline of an arbitrarily selected hard subset.

Only after the approved combined gate passes, execute the complete 600-task campaign once
with the frozen candidate. Preserve all attempted tasks in the denominator.
This is a known-benchmark rerun, not untouched confirmation. The published
Mem0 424/600 reference is descriptive; architectural superiority requires a
matched current-Mem0 arm or explicit qualification of unmatched comparisons.
If current matched comparison is unaffordable, do not claim it happened.

`research.retrieval_2310.evaluate.working_set_readiness` implements this
known-benchmark dispatch scope without requiring a new transfer corpus. Complete
fixed-set outcomes, accepted components and all operational gates are mandatory.
Its positive decision does not establish generalization or Mem0 superiority;
the stronger historical claim-qualification helper remains separate.

## Failure localization before expensive runs

For a bounded diagnostic sample compare actual context against independently
verified sufficient evidence using the same reader and app state. Oracle evidence
is evaluator-only, never available to the product planner, memory index or
training process. Attribute failures separately to source formation, candidate
recall, ranking, temporal resolution, packing, authority rejection and reader/tool
execution. Verify which stage lost evidence before coding a remedy.

## Budget, storage and release discipline

- USD 250 is the existing total campaign ceiling, not a new allocation. Reconcile
  its ledger first; the completed run reported USD 3.200023 in paid API spend.
  Include later charges, uncertain requests, rentals, judging, storage and transfer.
- Before paid tuning, price and reserve the final 600 run, confirmation, and any
  matched Mem0 comparison. If projected total exceeds the remainder, stop paid
  calls and report the constraint; cheaper offline checks may continue.
- Preserve benchmark evidence, frozen databases, raw exchanges, test inputs,
  outputs, grades and dependencies required for correction runs.
- Large artifacts may move to an authorized Hugging Face repository only after
  license/privacy review and download/hash verification. Keep local commit-pinned
  manifests and recovery commands. Delete only verified redundant copies that
  are not active dependencies; hashes never substitute for retained evidence.
- Do not prune original evidence to improve the score. Derived indexes/views
  remain rebuildable, authorized and traceable to original evidence.
- Beta publication is permitted for 2.3.10 work, but each publication must follow
  repository release coordination, compatibility, migration and installed-artifact
  gates. No benchmark target justifies weakening governance.

## Required per-iteration report

Publish a table with baseline / pillar-only / cumulative candidate / paired delta,
sample IDs and sizes, exact task passes, primary diagnostic, regression controls,
uncertainty, latency, tokens, cost, decision and immutable evidence links. Maintain
a cumulative spend ledger and a registry of every candidate, including failures.
No open-ended code changes or full-suite reruns without evidence of benefit.
