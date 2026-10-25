# DolphinBench execution audit and rerun plan — 2026-10-25

## Decision

Prioritize an execution-only investigation before changing AtMem retrieval again.
The recorded 65% result is a mechanically reproduced end-to-end result under its
disclosed setup; maintainer acceptance remains unconfirmed. It does not isolate
memory quality. The evidence supports a substantial
execution confound, not the claim that permissions alone caused the remaining
failures or that a repaired run will score 75.4%.

This document plans the next campaign. No new reader or judge calls, application
operations, permission changes, fixture changes, release, or external publication
were performed during this audit.

## Evidence and verification

- [Public recorded run](https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench).
- [Immutable submission](https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench/resolve/5ef528c499aa26b765fff9d8ed8f2c2e6ee52912/submission.zip),
  SHA-256 `78788ad3455d04407c037706d3ff129d56eafff89beaac101f2a461cb58d7538`.
- [Pinned benchmark source](https://github.com/mem0ai/dolphinbench/tree/81cb6f8405b40a9e76089cef650806a80af06ea2).
  The audit verifies task YAML and runtime JSON against its release manifest.
- [Machine-readable summary](evidence/dolphin-execution-audit-20261025/summary.json).
- [All 600 task audit rows](evidence/dolphin-execution-audit-20261025/task-ledger.jsonl).
- [Fixed 60-task diagnostic selection](evidence/dolphin-execution-audit-20261025/pilot-selection.json).
- [Offline audit script](../../scripts/audit_dolphin_execution_20261025.py).

The script checks public task outcomes against ZIP grading, checks the public
trace flag against the presence of recorded `app_calls`, and extracts the app
catalog actually presented to the reader. It handles submission-level default
settings as well as message-level overrides. Runtime-error detection examines
terminal `output`, not source files returned by `read_file`. Evaluator-required
tools and graders are used only for this audit; they must never enter actor
prompts or memory.

Reproduce using the retained inputs and qualified controller Python:

```sh
/private/tmp/atmem-dolphin-controller-v3-20261021/bin/python \
  scripts/audit_dolphin_execution_20261025.py \
  --submission /private/tmp/atmem-2310-dolphin-submission-review.zip \
  --rows /private/tmp/atmem-2310-dolphin-rows-review.json \
  --upstream /Users/javadtaghia/gitlab/benchmark-sources/dolphinbench \
  --output docs/benchmarks/evidence/dolphin-execution-audit-20261025
```

`--rows` accepts a JSON array parsed from the public `data/tasks.jsonl` file.
The ZIP digest is enforced; original outcomes and trace flags must reconcile
for all 600 tasks. Neither input nor the benchmark checkout is modified.

## What the 600 records establish

| Group | Tasks | Passes | Failures |
| --- | ---: | ---: | ---: |
| Independent app trace present | 517 | 390 | 127 |
| Independent app trace absent | 83 | 0 | 83 |
| Full run | 600 | 390 | 210 |

The 127 traced failures split into **84 zero-check failures** and **43 partial
successes**. Across all failures, 167/210 passed zero checks; none of the 127
traced failures was one check short. Keep these three cohorts separate in
classification, pilot controls and future reports. A trace is not evidence of
successful mutation, and a zero-check score does not isolate a memory cause.

- 61 of the 83 untraced requests start with “Create”, after the date prefix.
- All 83 scored zero checks. None has a recorded LLM judge response. Their
  zero scores do not tell us whether their prose would satisfy the content
  criteria: the requested application action was missing from grading evidence.
- 35 have actual `memo notes` commands plus runtime `osascript` permission
  errors. **All 35 had `create_doc` advertised to the model.**
- Six have actual GitHub CLI “not logged in” errors. **All six had their
  expected benchmark tools advertised.** These six and the 35 Notes tasks
  are disjoint.
- The trace flag is an evidence-presence flag, not an action-success flag.
  Morgan/129 contains booking calls and returned booking IDs, but its separate
  backend log was lost during recovery. It must not be classified as definitely
  “no action executed.”

The wider run helps distinguish permission errors from inevitable failure:

| Observed error anywhere in transcript | All tasks | Passed | Failed |
| --- | ---: | ---: | ---: |
| `memo notes` plus `osascript` permission error | 40 | 5 | 35 |
| GitHub CLI unauthenticated | 32 | 18 | 14 |

Five Notes-error tasks recovered and passed: Morgan/180, Riley/015, Riley/019,
Riley/087 and Riley/196. Of the 14 GitHub-error failures, eight have app traces
and six do not. A successful recovery is therefore possible under the same
boundary. The audit does not infer the absence of other errors in those tasks.

## Root causes and confidence

### 1. Wrong destination selected despite an available app tool — confirmed

Alex/041 asks for a historical note. The reader's actual deferred catalog lists
`mcp__dolphinbench_apps__create_doc`. Nevertheless its first tool call loads
`apple-notes`, followed by `memo notes -a` and a genuine permission error.
It ends with drafted text and no benchmark application call.

Morgan/058 loads the GitHub skill, searches for a vendor-specific GitHub
capability, and runs `gh auth status`. Its actual catalog exposes
`post_pr_comment` and `list_open_prs`. Authentication to the user's real GitHub
account is unnecessary for those simulated tools.

The general workflow instruction already exists in **all 600** conversations:
use connected tools; drafts/local files are not application operations; unrelated
OS applications are not fallback destinations. Adding that same instruction
again is not an adequate repair. Investigate supported skill filtering,
app-tool presentation, and the routing behavior that ignored the existing rule.

### 2. Unsupported local skills compete with benchmark tools — observed;
causal effect requires an experiment

The model-visible skills list advertises Apple Notes via `memo`, GitHub CLI
workflows, and Google Workspace workflows, while the sandbox deliberately
provides no real application credentials or OS automation. All 35 untraced
Notes-error tasks load an Apple Notes skill. The reader is offered procedures
for destinations it cannot and should not use in this benchmark.

The macOS boundary explicitly denies `/usr/bin/osascript`, `/usr/bin/security`
and `/usr/bin/open`; it also excludes real user credentials. This predates both
campaigns. Earlier archived 192/600 research transcripts contain 21 tasks with
`memo notes` and permission errors. That older artifact was based on 2.3.9,
not an unchanged published 2.3.9 wheel.

**Do not solve this by granting Apple Notes Automation access, authenticating
real GitHub/Google accounts, or weakening the boundary.** Real app writes would
not create the benchmark's simulated state or its required server log.

### 3. Tool discovery has a lexical trap — implementation confirmed;
per-task causal impact not fully quantified

The archived runtime identifies Hermes commit
`d0288be5b3330d2442e3907185b8e9d0958297bb`, which matches the inspected local
source. Its deferred-tool search uses a rarest-token admission gate: a word
absent from every catalog entry can make a query return no tools. The actual
reader-facing tool description explicitly warns about this.

Service-specific searches such as “github pull request comment post review
comment” can fail even when generic `post_pr_comment` is visibly listed. Empty
search results are not proof that the catalog lacks the capability. By contrast,
the known exact tool name can be loaded directly with `tool_describe`.

Plan separate checks for MCP registration, model-visible presentation, search
discoverability, schema loading, dispatch, backend mutation, and log persistence.
The previous audit checked declared tools versus delivery; it did not establish
that the declared fixture matched the requested/graded action.

### 4. Two pinned fixture/tool mismatches — confirmed

| Case | Request and grader require | Actual advertised action tools |
| --- | --- | --- |
| Morgan/085 | Send an email reply; `send_email` | `archive_email`, `list_inbox`; no `send_email` |
| Morgan/130 | Send Sarah a Slack DM; `send_slack_dm` | `update_crm_row`, `list_crm_rows`; no Slack sender |

Both the authenticated upstream runtime configuration and the recorded
model-visible catalogs corroborate these mismatches. Morgan/085 made an inbox
read and is among the 127 **traced** failures; Morgan/130 is among the 83
untraced failures. This illustrates why “has a trace” is insufficient to decide
whether a task was executable or failed because of memory.

Do not silently add tools using grader information or change these fixtures
locally and present the result as the identical benchmark. Prepare a minimal
maintainer report. Use an upstream-approved revision if fixed. If retaining the
old pin, explicitly preserve these cases and the full denominator, documenting
their known limitation. A changed upstream revision requires its own corpus
identity and a disclosure that comparisons are historical.

An apparent third mismatch, Morgan/136, disappears when effective tool
registration is considered: `post_pr_comment` automatically exposes
`list_open_prs` in the repair server. Qualification must inspect effective
`tools/list`, not only the initial `active_tools` list.

### 5. Missing independent logs and grading short circuits — confirmed

The source runner can reset an app log when setting up an interaction. Its
normal inflight guard protects uncertain tasks, but recovery paths must also
preserve original state and logs before setup. We have not attributed the
specific Morgan/129 loss to a particular line in that runner.

The upstream grader checks application results; with no matching action it
can fail a field check without calling a content judge. Consequently, the
83 zero-check rows do not measure standalone memory-answer correctness.
Any optional blind review of drafts must be reported as a separate diagnostic,
not substituted for task grades.

### 6. Many missing actions have neither the Notes nor GitHub error — confirmed

Removing the 35 Notes and six GitHub cases leaves 42 untraced failures. Of
those, 33 had `create_doc` advertised. Twenty-six are explicit “Create” requests
with no loaded skill at all. Their absence of action evidence is not explained
by the measured Notes/GitHub CLI failures. Examples include Morgan/120 and
Riley/104, where the final reply provides note/card text without a corresponding
app operation. Alex/049 instead creates a local workbook; that is not the
graded connected-document operation. Riley/075, Riley/085 and Riley/185 load
Google Workspace workflows although the simulated document tool is available.

These findings widen the hypothesis from “blocked CLI” to destination selection
and completion discipline. Do not assume draft-only replies are factually
correct: their missing actions prevented the original content checks.

## Published reference: rows are available

The pinned repository includes all 600 Mem0 reference task records, not just
its README. The audit reads their committed bytes, verifies 424 passes, and
checks that all 600 requests match after removing our date prefix.

| Our diagnostic subset | Reference passes |
| --- | ---: |
| 83 tasks without our independent trace | 58/83 |
| 35 failed Notes-route tasks | 24/35 |
| Six failed GitHub-auth tasks | 5/6 |

The reference also fails Morgan/085 and Morgan/130. The rows support investigation
of the same tasks, but its transport, host/runtime and memory setup differ.
This is descriptive task-level evidence, not a new matched Mem0 run or a causal
estimate of the gains AtMem would get from repairing execution.

## Correct the 75.4% expectation

390/517 = 75.4% is conditioned on an outcome of execution. It is not a repaired
600-task score, and not a measured memory-only success rate.

- Even recovering all 35 Notes plus six GitHub untraced failures, with no
  regressions, yields **431/600 = 71.8%**. That is an optimistic arithmetic
  scenario, not a forecast.
- A full 600-task score at or above 75.4% requires **453 passes = 75.5%**,
  which is 63 additional passes if all current passes are retained.
- Keep 390/600 = 65.0% as the original result. Rerun outcomes can include both
  recoveries and regressions. Passing a failed task is not guaranteed merely
  because a tool can now run.

## Rerun plan

### Phase 0 — completed offline audit

- [x] Verify original ZIP digest and reconcile 600 task outcomes.
- [x] Extract actual tools, skills, runtime errors and evidence status per task.
- [x] Authenticate upstream task/runtime files and distinguish helper tools.
- [x] Identify two fixture mismatches and the missing-log exception.
- [x] Inspect committed reference rows without running another model.
- [x] Save a deterministic 60-task diagnostic selection before new model calls.

### Phase 1 — freeze the experimental contract before implementation

- [ ] Pin the installed AtMem 2.3.10 artifact, Hermes source/dependencies,
  reader/judge identity and transport, inference settings, budgets, benchmark
  revision, persona memory checkpoints, retrieval options and state hashes.
- [ ] Freeze a baseline configuration reproducing the old host setup and an
  execution-repair configuration. Do not combine retrieval/model changes with
  the first execution experiment.
- [ ] Record a disposition for the two fixture mismatches. Prefer an upstream
  correction before a new leaderboard submission; otherwise keep the old
  cases counted and explicitly unavailable. Do not patch answer-key-derived
  tools into actor inputs.
- [ ] Define successful full-run improvement as original all-checks success
  across all 600, reporting paired recoveries **and regressions**, per-persona
  results, action-family results, latency and evidence coverage. The historical
  comparison is still stochastic and post-development, not a clean causal A/B.
- [ ] Set a paid-judge budget and uncertain-charge rules for this new campaign.
  This planning task has not launched paid work or allocated a new spend budget.

### Phase 2 — qualify an isolated execution profile without model calls

- [ ] Use supported Hermes profile configuration to disable unavailable local
  Apple Notes, real GitHub/Google Workspace, OS messaging and GUI workflows.
  Verify both the displayed skills list and `skill_view` access; test aliases
  and external skill directories. Do not change the user's normal profile.
  `skills.disabled` exists in the pinned source; qualify exact names rather
  than assuming category aliases are sufficient.
- [ ] Inventory the exact per-case MCP tools and schemas as the model sees
  them. Verify action tools and automatically exposed lookup dependencies.
  Use an evaluator-side audit to detect fixture contradictions; never forward
  its required-tool labels to the agent.
- [ ] Compare supported eager app schemas (`tools.tool_search.enabled=off`)
  with the existing deferred mode. Turning deferral off may change other tool
  presentation and token cost: record the entire resulting tool array, test
  dispatch, and disclose the change. Prefer existing supported configuration
  over editing Hermes search semantics during this experiment.
- [ ] If retaining deferral, test short generic and exact-name searches against
  declared tool metadata; verify zero lexical matches do not imply absence.
  No evaluator-selected answer/action may be injected into this process.
- [ ] Run synthetic round trips against disposable, controller-owned mock
  state for documents, PR comments/reviews, Slack/Discord, email, calendar,
  runbooks and the other action families observed in the suite. Check returned
  IDs, persisted state and independent log entries through the real bridge.
  These use synthetic facts, not benchmark solutions.
- [ ] Keep `osascript`/credential boundaries intact. The profile should never
  need real application authentication to mutate a simulated app.
- [ ] Fault-inject a process failure and recovery: logs and state must be
  preserved, successful actions must not be replayed, and missing independent
  evidence must remain explicitly missing rather than reconstructed as fact.

The Mac no longer has Colima installed after the requested disk cleanup.
Do not assume a Docker daemon exists or silently reinstall it. The isolated
macOS bridge can be qualified first; a later Linux/Docker host is a separate
runtime condition and needs its own declared identity.

### Phase 3 — fixed diagnostic pilot, then freeze one candidate

The accompanying `pilot-selection.json` records the 60 diagnostic IDs. Before
model calls, add the exact baseline and candidate configuration hashes:

1. All 35 formerly untraced Notes permission-error cases.
2. All six formerly untraced GitHub-auth cases.
3. The two fixture mismatch cases, as negative/environment controls until resolved.
4. The five Notes-error cases that already passed, testing preservation of recovery.
5. Four other untraced controls: two “Create” requests with no loaded skills,
   one Google Workspace detour, and Morgan/129's missing-log recovery case.
6. Two other traced/zero-check failures and two traced/partial failures, chosen
   within their separate strata deterministically by SHA-256 of
   `dolphin-execution-pilot-20261025:<persona>/<id>` from eligible IDs.
7. Four other passes using the same selector, excluding earlier groups.

The draft and Google controls use the same hash selector within their strata.
The latter traced controls exclude every earlier group and earlier picks.
Selection revision 2 (2026-10-26) adds the two traced-failure strata before any
pilot model calls; the 2026-10-25 selection is retained as historical evidence.
Publish the selected IDs before the pilot. They are public tasks already used
for development: this is diagnostic qualification, not a sealed test.

- [ ] Run the unchanged-memory old host and the execution-repair host on the
  fixed pilot with fresh independent app state for every arm/task.
- [ ] Record per-step discovery, schema, dispatch, backend result, state change,
  log persistence and original rubric grades. Treat routing and content success
  as separate measurements. Grade preserved real results only.
- [ ] Require no unsupported real-app CLI routes, no unreported fixture gaps,
  and complete consistent evidence for successful app calls before scaling.
  Content failures can remain failures; do not keep changing prompts to chase
  100% pilot accuracy. Investigate regressions among the known passes.
- [ ] Freeze one qualified candidate. Disclose any further pilot-driven edits
  and their development use; retain every attempted condition and cost.

### Phase 4 — a genuinely new full 600-task campaign

- [ ] Use new run directories, immutable identities and clean per-task app
  state. Keep persona memory frozen. Preserve the original run and every
  previous failed attempt; no replacement of bad rows with pilot outcomes.
- [ ] Execute all 600 tasks exactly once for the selected condition, with
  explicit reconciliation of uncertain transport/action failures.
- [ ] Record no-call, attempted, backend-rejected, backend-success and
  evidence-missing statuses independently. “Has app trace” remains separate
  from “action succeeded” and “content correct.”
- [ ] Apply the original upstream grading and saved-judge replay/ZIP gates.
  Retain task counts, all checks, timing/cost uncertainty, raw transcripts,
  app logs, schemas, actual provider requests and provenance hashes.
- [ ] Report total score first. Then paired recoveries/regressions, conditional
  diagnostics, known fixture gaps, and whether real-app routing errors fell.
  A higher score after a host repair is an end-to-end improvement; it does not
  establish a memory-only improvement.

The prior recorded task durations sum to about 15.8 hours, before any new
qualification or grading overhead. Treat this as historical scheduling evidence,
not a runtime guarantee. Avoid scheduling a costly full rerun until the bridge,
catalog and evidence gates pass.

### Phase 5 — memory work after execution is trustworthy

- [ ] Classify residual failures using their actual action and judge evidence:
  evidence never retrieved, evidence retrieved but omitted/truncated, source
  interpretation/state/temporal errors, wrong destination, wrong arguments,
  backend rejection, or missing attestation. Allow multiple contributing causes.
- [ ] Evaluate retrieval changes with the execution profile held fixed.
  To compare memories causally, run both memory arms under the same repaired
  host, corpus, model settings and tool environment. The old 192/600 and public
  424/600 reference remain historical conditions until such a matched run exists.

## Implementation map

| Work | Likely location | Verification |
| --- | --- | --- |
| Supported skill and tool-disclosure settings | `benchmarks/dolphinbench/driver.py`, isolated profile | Actual model-visible schemas/skills and dispatch qualification |
| Immutable execution-profile identity | `campaign_v3.py`, campaign entry point | Changed profile cannot resume an old identity |
| Effective app capability preflight | Separate evaluator preflight; upstream `_apps`/repair server unchanged | Full declared/effective catalog; fixture mismatch report |
| App state/log durability and recovery | Adapter, bridge, recovery utilities | Injected failure preserves state/logs and prevents duplicate action |
| Expanded audit/report | `scripts/audit_dolphin_execution_20261025.py` | Digest checks, outcome reconciliation and reproducible ledger |

Implementation and a new scored campaign should follow the frozen contract above.
