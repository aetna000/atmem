# DolphinBench routed-v4: completed 600-task evaluation

On 1 November 2026 the routed-v4 campaign completed all 600 task executions and
grades: **479 passed, 121 failed (79.83%)**. The independent local full-run
validator passed. These are self-tested results, not official leaderboard
acceptance. Public evidence packaging and its action-level export are being
prepared separately; the original 390/600 public artifact remains immutable.

| Recorded run | Passed | Total | Score |
| --- | ---: | ---: | ---: |
| AtMem routed-v4 | 479 | 600 | 79.83% |
| Earlier AtMem | 390 | 600 | 65.00% |
| Historical Mem0 reference | 424 | 600 | 70.67% |

The new run recovered 120 earlier failures and regressed on 31 earlier passes,
for a net gain of 89 passes (+14.83 percentage points). It exceeds the recorded
Mem0 reference by 55 passes (+9.17 points). The public requests match, but the
execution conditions are not a matched memory-only experiment. Public tasks
informed development; this is not an unseen holdout or a learning claim.

| Original cohort | Tasks | Passed now | Failed now |
| --- | ---: | ---: | ---: |
| Prior passes | 390 | 359 | 31 |
| Untraced, zero checks | 83 | 65 | 18 |
| Traced, zero checks | 84 | 31 | 53 |
| Traced, partial checks | 43 | 24 | 19 |

Required actions: 95/96 reads and 510/635 writes passed, totaling 605/731 action
groups. The existing report classifies failed writes as 109 judged-content,
nine no-call, six wrong-value and one unresolved; one read had no call. A task
can require multiple actions. The detailed publication must replay saved judge
responses and show candidate-call/check evidence, rather than infer an atomic
check failure from a failed group flag. A missing required fact does not by
itself prove failed retrieval or that a remembered rule was exposed then omitted.

Paid judging cost was USD 3.905882, with no unresolved charges or reservations,
against the original USD 20 cap. The final ledger retains 602 judge calls and
3,925 subscription reader calls, including interrupted attempts. Subscription,
hardware and energy costs are separate.

## Exact code and release identity

The run used the frozen installed AtMem **2.3.10b1** artifact and the research
`dolphin-routed-v4` / i3 guard and standing-fact source. The final harness source
commit was `bd38c5fcce270033e0e13df0c090592562e6fd38`; its condition identity was
`371fc4aa324910033d1525032e2ed84f67722abf61c4d2090886e88a73618fb6`.
Reader: subscription `openai/gpt-5.6-luna`, high reasoning. Judge:
`gpt-5.6-sol`, medium, OpenRouter with Azure-only routing. Memory and local
embeddings, fixtures, grader and tool isolation remained fixed. Known fixture
limitations Morgan 085 and Morgan 130 remain unchanged.

The shipped **2.3.11b1 remains a beta**. Its source describes formed statements
as source-linked unverified interpretations and includes subsequent privacy
hardening. Quote-occurrence validation is not semantic entailment. This is not
a measurement of that exact published beta artifact, and no stable promotion
or new package version is implied by the benchmark or this merge.

## Evidence-preserving continuation

The first 19 executions/grades were inherited byte-for-byte; Morgan 020 was
reconstructed offline from saved native/app evidence after duplicate read-only
tool suppression broke export. Its app action was not repeated.

At 416 graded tasks, Hermes stopped on Riley 017 because the internal disk was
full and its conversation database could not be saved. Two completed reader
responses requested only memory tools; both independent app logs and app states
were empty. The owner authorized a retry. The original attempt, native home,
costs, authorization and SHA-256 inventories were preserved. A first restart
hit the preserved native directory before making model calls; that startup
attempt was preserved as well. The external launcher passed nine tests and then
used the existing frozen guarded resume entry point. All original 416 grade
hashes were verified unchanged; the retry passed. Results were not selected
between competing scored attempts.

The run executed directly without AtSys management. All 600 scored records,
recovery evidence, final reports and the final accounting snapshot were backed
up to a private Hugging Face dataset and download-hash verified. The ordinary
Hermes launcher was checked after completion. The original source worktree
remains unchanged for audit; the main-branch merge retains the published beta
product code instead of replacing it with earlier research wording.
