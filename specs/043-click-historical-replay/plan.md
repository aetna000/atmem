# Click replay implementation plan

**Status:** phase 0 implementation started under the subsequent owner request;
real trials remain gated by capabilities, explicit budget and egress authorization.
**Inputs:** [spec.md](spec.md), Spec 042 implementation/knowledge plans and the
AtMem constitution. Build a harness around existing product services; do not
implement a second memory engine or treat this as Code expansion completion.

## Implementation progress

The first bounded efficiency loop is complete but failed its acceptance goal;
see `RandD/2026-10-17-structural-efficiency-loop.md`. The second loop saved
20.44% input but lost quality; no transfer solver calls were dispatched. Active
continuation follows `covered-navigation-loop-v10.md`. P4 recovered 5/5 functional
passes each but has unknown C usage. P5 completed with 4/5 each, unknown C usage
and insufficient source exposure. P6 qualified the one-request interface but
finished 4/5 each with unknown native total usage. P7's compact navigation and
caller-priority corrections passed installed transport/host controls and
completed ten attempts: 4/5 each, unknown native usage, no accepted saving.
All eleven cohort archives recovered independently; no transfer dispatched.
P8 addressed verified attrition of the highest-ranked usage source at the byte
limit without changing budgets/grader; installed checks pass, but scoring failed
(3/5 each, unknown C usage). Its example reservation displaced a relevant method
in task 3. Joint source-budget prioritization is the next concrete defect to
address under P9; the field-flow and incremental-usage hypotheses remain
unimplemented. P9 passed installed/actual-host qualification and completed ten
attempts: 5/5 functional each, all usage known, 19.551447% input saving. It misses
the unchanged 20% threshold; all archives recovered, no transfer dispatched.
P10 removes navigation redundant with complete included bodies. Qualification
and ten attempts completed: 5/5 functional each, all-cap native 3/5 versus
structure 5/5; delivered source equivalence passes, native total usage unknown.
No saving accepted. `usage-transport-diagnostic.md` now defines a separate
bounded accounting investigation; zero-inference actual source/denial controls
passed, and the frozen scored transport/caps remain unchanged.
P11 completed ten frozen attempts under `producer-linked-usage-loop-v11.md`:
native 5/5 functional versus structure 2/5, unknown structure usage. No benefit
accepted or confirmation dispatched. The requested external-model review and
tool-use audit retire further scored tuning on the familiar Click five. Keep
all historical results and the unscored Click set; it is not repository-disjoint
confirmation. Spec 042 `cross-repository-evaluation-plan.md` defines the separate
prospective generalization work; no external repair benchmark has run.
Secret-screened/stale source remains withheld.
First-loop transfer tasks remain retired; old outcomes are never overwritten.

The current owner follow-up adds five fresh A/C pairs under
[structure-control-v3.md](structure-control-v3.md). Both arms use corrected
native Git and 2 GiB scratch; experience is disabled. Results are separate from
the completed v2 C/D pilot. T025–T026 completed this reused-task engineering test:
both 4/5 all-budget passes, native 5/5 versus structure 4/5 functional passes;
no net structural benefit demonstrated. See the RandD native/structure report.

The active requested comparison is [two-arm v2](two-arm-protocol-v2.md):
five tasks × C/D × two repetitions, 20 sessions if all gates pass. Versioned
contracts reject excluded arms/repetitions. The four-arm schedule below is v1,
not a claim that those additional arms have been requested or executed now.

Phase-0 T001/T002 provide closed metadata contracts and first-parent selection.
The explicit reduced-v2 path froze five authentic tasks, qualified parent/
reference full-suite grading, ran all twenty installed-product benchmark sessions
and retained a comparison plus verified encrypted archives. See T021–T024,
`benchmarks/code_replay/qualification.md` and the RandD final report. Eight
observations were stored but none exposed later; no memory advantage is shown.
Original T003/read-only preflight still blocks the broader v1 normal-host claim;
these narrower results do not complete the four-arm or general product gates.

## Technical context and proposed files

Python 3.10–3.13 harness and tests; Git only in evaluator preparation; a pinned
agent process behind a host-neutral runner interface; immutable JSON manifests
and encrypted evidence through the existing authorized AtMem service. Runtime
environment/container digest is recorded per historical task; do not assume the
historical Click version supports AtMem's entire Python range. Initial real
pilot platform is macOS, only if qualified sandbox/agent support exists; unsupported
cells block, not fall back silently. Harness contracts/unit tests cover supported
Python versions; installed sandbox/host qualification is platform-specific.

Proposed root `benchmarks/code_replay/`:

| File/module | Responsibility |
| --- | --- |
| `contracts.py` | Protocol, task, run, result and receipt validation |
| `select.py` | Frozen first-parent eligibility/exclusion ledger |
| `prepare.py` | Evaluator source acquisition, issue cutoffs, environments and task packaging |
| `sandbox.py` | Approved mounts/egress, sanitized source-only solver workspaces, credential broker and cleanup |
| `grade.py` | Isolated sealed tests and parent/reference qualification |
| `runner.py` | Host-neutral process launch, session limits, scheduling and terminal accounting |
| `atmem_bridge.py` | Existing authorized intake/query/exposure/snapshot boundaries; no manual oracle labels |
| `history.py` | Separate arm/repetition memory trajectories and source-reset transitions |
| `metrics.py`, `report.py` | Cost/resource accounting, bounded summaries and readable comparison via authorized encrypted artifacts |
| `cli.py` | Plan/preflight/run/inspect/report controls; execution requires explicit budget/egress configuration |
| `protocols/`, `tasks/` | Frozen manifests and hashes; no secret evidence or unsealed solver-visible solutions |
| `tests/test_code_replay_*.py` | Safety, fairness, deterministic grader and product-boundary tests in repository `tests/` |

## Versioned data contracts

- **ProtocolManifest:** immutable protocol ID/hash, discovery anchor/horizon,
  selected task IDs/order, chronology/cutoffs, four arms, repetitions=3, model/CLI/
  product/extractor versions, sampling configuration, identical budgets, schedule,
  hardware, analysis rules and allowed egress. Freeze before target runs.
- **TaskManifest:** mainline parent and accepted reference commits/tree hashes,
  issue content/version/time and license reference, allowed source manifest,
  prompt hash, dependency/runner image hashes, baseline expected failures and
  evaluator-only grader/test/reference hashes. Public manifest has references;
  solver package contains only permitted pre-solution bytes.
- **RunManifest:** task/arm/repetition/trajectory IDs, source hash, isolated lane,
  effective configuration, adapter readiness, start/end, budgets and result state.
- **ExperienceReceipt:** source session and timestamp, admitted/rejected candidates,
  claims versus observed outcomes, snapshot applicability and retrieved record IDs.
- **TrialResult:** functional/infra/safety status, graded checks, artifact references,
  usage provenance, stage durations/resources, tool statistics, intervention and
  exact context/exposure receipts. Keep missing/unknown values nullable.

Persist all retained human-readable operational evidence in the existing encrypted
vault. Extend registered derived/export handling rather than write a plaintext
parallel JSONL archive. The dead-solver investigation test must use the evidence
store alone plus authorized AtMem keys/service, not original agent-home logs.

## Experimental arms and interpretation

| Arm | Experience retained for later tasks | Structural context |
| --- | --- | --- |
| A | No solver access | Native file/search tools only |
| B | Automatically formed from own earlier sessions | No additional graph |
| C | No solver access | Qualified rich graph |
| D | Automatically formed from own earlier sessions | Same graph/config as C |

All arms retain evidence for the operator, never a backdoor for the solver.
Use identical prompts except explicit available-memory tools/settings. Keep
native instruction files and tools equal; record automatic tool schema overhead.
Native search is not intentionally weakened to make structural context helpful.

At target task 1 all experience lanes are empty. Later experience consists of
that arm's own eligible attempts. B versus A measures experience-policy effect;
D versus C measures adding experience-policy to rich structure, including its
history effects. C versus A measures structural augmentation. D versus B also
includes history effects, not a pure fixed-history structure ablation. A richer
common-history experiment is optional future work and cannot be inferred here.

## Ordered lifecycle and fairness

1. Offline evaluator pins anchor and reviews up to 100 mainline entries in
   reverse order; retain exclusions and select five eligible changes. Replay
   chronologically. Do not score memory relevance during selection.
2. Recover timestamped issue requirements. A current issue body without reliable
   historical version is ineligible if it may include the solution. Pin licenses
   and allowed model-egress scope before packaging.
3. Build task environments and verify parent baseline and reference behavior.
   Grading never exposes reference patch or tests to the solver. Missing historic
   dependencies or unresolved flaky expectations block eligibility pre-freeze.
4. Freeze complete protocol/budgets before target solving. Choose total execution
   budget only under a subsequent authorization; absent authorization is a hard
   run gate, not an inferred zero-cost plan.
5. Build source-only archives with a sanitized local Git repository containing
   the permitted tree, no alternates, remotes, future objects or hidden worktrees.
   Original revision is carried in a signed evaluator-to-AtMem mapping so freshness
   still works. A `.git` worktree pointing at the full evaluator clone is forbidden.
   Block network/host filesystem routes to the upstream history and graders.
6. Preflight normal agent enablement/intake/recall and the exact versioned product
   capability receipt from Spec 042 T060. B/D require T049–T051: governed coding
   experience, graph-independent applicability and disjoint authentic diagnostics,
   plus installed host/storage proof. C/D require T046/T047/T053 and installed rich
   structural delivery; D additionally requires T054 unified assembly. A current
   user-assertion-only path or syntax index is not a primary B/C/D substitute.
   Neither missing product behavior nor Codex activation is solved by a harness
   implementation or benchmark-only trust bypass. Full upstream parity and the
   human Explorer study remain separate completion/claim gates, not prerequisites
   for a minimal honestly qualified capability receipt.
7. Use the frozen partial-position schedule below, not a claim of full
   counterbalancing. Each arm stays chronological but uses separate persistent memory and fresh
   agent session/home per target. No cross-arm warm caches containing source or
   memory. Shared immutable tool/dependency caches contain no target solutions.
8. Execute within token/tool/time limits; record complete failures and inspectable
   receipts. Solver may use ordinary tests. Hidden grades are evaluator-only,
   withheld until the whole trajectory completes; no adaptive solver reruns.
9. Capture eligible memories from the attempt before reset. Reset to the next
   authentic pre-target tree; no reference patch is observed by capture. Revalidate
   old anchors, update structure and charge maintenance overhead. Code preferences
   do not become invalid merely because an unrelated file changed.
10. Grade each patch in a clean evaluator sandbox with frozen tests/regressions
    and modified-file policy. Verify grader/environment unchanged; never accept
    deletion of tests or tampered configuration as solving a task.
11. Report each attempt and trajectory, including invalidity and attrition. Freeze
    timeout/infrastructure classifications before execution. A solver or product
    crash is a failure, not an infrastructure exclusion. Infrastructure rerun
    repeats all four arms of that repetition from empty lanes, retaining originals.

### Frozen partial-position schedule

For each task, execute the arms serially in the row for its repetition before
advancing to that repetition's next chronological task. Each repetition starts
with four isolated lanes. Retain the same row for all five tasks:

| Repetition | Position 1 | Position 2 | Position 3 | Position 4 |
| --- | --- | --- | --- | --- |
| 1 | A | B | C | D |
| 2 | B | C | D | A |
| 3 | C | D | A | B |

Each arm runs once per task/repetition and occupies three distinct positions
across repetitions. Each arm necessarily misses one position: three repetitions
cannot fully balance four positions. This truncated cyclic schedule also does
not balance carryover effects. Freeze and hash the schedule before trials, log
actual start/end order and retain deviations explicitly. Do not rearrange after
seeing outcomes. The report must state that time/provider drift and residual
order effects remain possible. Infrastructure reruns preserve the assigned row.
The pilot remains 5 tasks × 4 arms × 3 repetitions = 60 sessions; adding the
fourth cyclic row would require a separately versioned 80-session protocol.

## Measurements and inspectable report

Provide per-task rows and a summary with columns A/B/C/D for passed tasks,
regression failures, elapsed solver+service time, total tokens/observed cost,
tool calls/files/searches, indexing/update time, retrieval p50/p95/count, context
bytes and intervention. Show task 1 cold separately from tasks 2–5. Setup/index
cost and amortization denominator are explicit; do not subtract failed overhead.

An operator opens a result and follows exact prepared/delivered context, memory
content, source session, applicability and observed test evidence through the
same authority service. Include judged helpful/irrelevant/harmful annotations
as attributed post-run analysis, not training truth or proof of causality.
Report measured pilot-specific correctness/time/cost benefit or harm, with
denominators and overhead. Do not infer calibrated probabilities or population-wide
user benefit from five tasks alone.

No p-values or general superiority; use raw paired deltas and trajectory-level
summaries. Agent pretraining familiarity remains a limitation despite sandbox
leakage controls. Repeat execution cannot remove public training contamination.

## Delivery phases and exit gates

| Phase | Deliverable | Gate |
| --- | --- | --- |
| 0 | Protocol/contracts, selection rules, cost/egress controls | Schema rejects missing pins/budgets; no paid dispatch |
| 1 | Historical task selection and sealed graders | Five eligibility records, frozen prompt cutoffs and parent-fail/reference-pass evidence |
| 2 | Sandboxes and encrypted evidence | Negative leakage/secret/scope checks, audited access and dead-solver reconstruction |
| 3 | Product bridge and four-arm readiness | Existing service used, qualified host or explicit blocked cell, rich graph not AST relabel |
| 4 | Scheduler/history/metrics and disjoint dry run | Fresh sessions, authentic tree resets, bounded termination, cost/unknown accounting and paired rerun behavior |
| 5 | Authorized real pilot and report | Budget/egress authorization plus frozen gates; 60 attempts or distinct blocked/reduced protocol; no preset win |

The subsequent owner request authorizes implementation, not paid trials. No owner
installation, upstream write, training, Code engine expansion, release or public
publication. An unavailable prerequisite may block real trials while independent
harness tests continue. Do not use these five targets for iterative product tuning
and later call them untouched confirmation.

## Constitution check

| Principle | Required enforcement |
| --- | --- |
| I Authority | Existing product intake, authorization and result revalidation; no direct memory writes |
| II Provenance | Exact retained evidence, truthful exposure levels and observed test receipts; no claim that host text proves success |
| III Reversibility | Isolated opt-in harness, no owner trust/config changes, fail-closed preflight |
| IV Transparency/deletion | Required encrypted profile, audited role-based inspection, scopes and derived cleanup |
| V Host neutrality | Runner interface separate from memory service and host-specific setup |
| VI Executable claims | Validated graders, product-boundary probes and honest blocked states |
| VII Local/egress | Offline source tools; narrowly authorized inference and no inherited broad credentials |
| VIII Evaluation | Authentic histories, leakage barriers, paired quality/systems accounting; five-task pilot not production benchmark |
