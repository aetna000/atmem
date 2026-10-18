# Click historical replay: does AtMem help a coding agent?

**Status:** reduced v2 completed (20 trials); fresh A/C follow-up completed (10 trials). **Date:** 2026-10-17.
**Worktree:** `feature/atmem-code-2.3.9`; no change to main or Laya.
**Related:** [Code specification](../042-atmem-code/spec.md) and
[knowledge expansion](../042-atmem-code/code-knowledge-plan.md).

## Outcome and scope

**Completed follow-up:** [no-memory versus structure v3](structure-control-v3.md),
five fresh A/C pairs on reused tasks. This does not pool with or replace the
completed v2 experiment. Original four-arm gates remain open.
Results: native 5/5 versus structure 4/5 functional default-suite passes; both
4/5 under all run budgets. See the separate RandD native/structure report.

**Completed owner-requested comparison:** use the distinctly versioned
[two-arm v2 pilot](two-arm-protocol-v2.md) for C versus D. The four-arm design
below remains the v1 reference; v2 explicitly supersedes its arm count/schedule
for this run without weakening its task, safety or evidence gates.

Replay five authentic historical Click coding tasks with a real agent in fresh
sessions. Measure functional benefit, harm and total overhead from AtMem's
existing user-assertion baseline, pending governed coding experience and richer
repository structure, separately and together. The primary B/D configurations
require Spec 042's new coding-experience gates; they are not ready merely because
assertion memory exists. Include exact memories and context receipts so a user can inspect
why a result occurred. No minimum improvement is presumed.

This is a bounded engineering pilot, not a representative coding benchmark,
training corpus, general superiority claim or upstream code-knowledge parity
test. Public tasks may have been seen during model training. The five task IDs
and historical revisions were frozen for v2; the original broader design below
does not imply its remaining gates are complete. The owner's subsequent request authorizes
implementation; paid trials, release and external publication remain separately
gated. Contract tests are not results on historical Click tasks.

## User stories

1. **P1 — Reproduce an honest task.** An operator selects a frozen historical
   window, verifies the original bug and accepted fix using executable grading,
   and supplies only pre-solution requirements to the agent.
2. **P1 — Compare real agent work.** The operator runs matched configurations,
   receives task correctness, failure and resource results, and can identify a
   blocked automatic adapter rather than mistake a direct injection for one.
3. **P2 — Inspect memory's contribution.** A user follows a task result to the
   memories retrieved, their source/applicability, exact delivered context and
   test evidence. Irrelevant or harmful memory is visible too.
4. **P2 — Repeat without contamination.** A new repetition uses a fresh agent
   home, memory lane and permitted source snapshot; earlier target solutions,
   evaluator tests and another arm's memories remain inaccessible.

## Requirements

- **FR-001 — Selection.** Pin a public `pallets/click` revision and inspect the
  first-parent history backwards. Select the latest five eligible functional
  changes within a frozen search horizon of 100 first-parent entries. Eligibility
  requires a pre-solution issue/report with sufficient behavior requirements,
  reproducible parent environment, executable discriminating tests and tractable
  scope. Exclude docs-only, dependency-only, packaging-only, ambiguous multi-feature
  or unreproducible changes. Record every inspected entry and exclusion reason;
  never select on memory helpfulness or measured agent outcomes. If fewer than
  five qualify, report a selection blocker rather than silently widen the rule.
  Chronological first-parent order determines replay; merge tasks pin the mainline
  parent and accepted tree explicitly. "Five tasks" is not `HEAD~5` blindly.
- **FR-002 — Frozen protocol.** Before agent trials freeze task identities,
  inputs, grader hashes, environments, AtMem/extractor/agent/model versions,
  configuration, resource budgets, repetition count, schedule and analysis rules.
  Prototype the harness on disjoint tasks only. Changes after viewing target
  outcomes create a new development protocol and require new confirmation tasks.
- **FR-003 — Leakage barrier.** The solver sees the permitted parent source and
  timestamped pre-solution requirements only. Hide future commits/refs/objects,
  target patches, post-solution messages, release notes and hidden tests. Full
  checkout history is evaluator-only. Omit remote access and isolate host mounts,
  process environment, agent home/caches, memory scopes and grader feedback.
  Network is denied except a narrowly authorized inference transport. The same
  allowed historical documents and native tools are available in every arm.
- **FR-004 — Four arms.** Run A native tools/no AtMem; B experience memory only;
  C structural knowledge only; D both. Use the same pinned solver/model, task
  instructions except the declared memory capability, native instruction files,
  tools and budgets. Start each task in a fresh session; native persistent agent
  memories are disabled uniformly. Configuration must be supported, not a hidden
  experimental activation bypass. Existing AST fallback is not richer structure.
  Until the new extractor/query path is qualified, C/D are blocked or reported
  separately as an explicitly named syntax-index diagnostic, not silently replaced.
  B/D additionally require Spec 042 T049–T051 and installed capability proof for
  governed coding-attempt formation and graph-independent cross-revision recall.
  Existing user-assertion-only memory is a separately named diagnostic, not B/D.
- **FR-005 — Chronology and experience.** Primary mode measures complete learning
  trajectories. Each repetition/arm has isolated state; B/D start empty and form
  memories automatically from their own earlier solver sessions and observed
  outcomes. No human-authored oracle lessons, target commits or evaluator-only
  grading enter formation. A/C do not access stored past sessions. Record differing
  arm histories: B/D comparisons measure whole-policy effects, not a fixed-memory
  causal retrieval effect. Task 1 is cold and cannot evidence cross-task experience
  benefit. Report later tasks separately. Controls may still use permitted older
  source/history documents, not transcripts of their previous attempts.
  Before target trials, qualify product formation and applicability on disjoint
  authentic attempts under Spec 042 T051. Report candidate/admitted/applicable/
  retrieved/delivered counts per task; zero eligible experience is an outcome,
  not permission to hand-label lessons or select different targets.
- **FR-006 — Equal source state.** After each task, the evaluator restores every
  arm to the same authentic pre-target tree for the next task, including legitimate
  intervening history. This is teacher-forced historical replay, not five cumulative
  agent patches. Previous attempts' memory may remain only in its own B/D trajectory;
  revalidate source anchors against the new tree. Capture cannot read the evaluator
  reset or canonical patch. Mark unsupported success claims as assertions; only
  observed permitted test receipts support outcomes. C/D rebuild/update structural
  projections with costs measured. Preserve separate worktree/snapshot identity.
- **FR-007 — Grading.** Seal the grader before solving. A target pass requires all
  selected behavioral tests and applicable baseline regression tests, no forbidden
  changes and no sandbox violation. Grader target tests must fail on the parent
  and pass on the accepted reference tree. Baseline failures/flakiness and any
  justified immutable expected-failure policy are frozen before trials. The agent
  can run ordinary parent tests but cannot read grader tests or receive adaptive
  hidden-test feedback. A semantically valid different patch may pass; exact diff
  matching is not the criterion. Exclude agent-written grader/config bypasses.
- **FR-008 — Measurements.** Record correctness and all attempted-task denominators,
  elapsed time including service overhead, input/output/cached tokens where exposed,
  observed charges with price provenance, file reads/searches/tool calls, context
  bytes, capture/formation/retrieval/index/update latency and resource usage. Include
  setup amortization and cold/warm costs separately; missing telemetry is unknown,
  never zero. Track human intervention, timeouts, stale/wrong context and refusal.
- **FR-009 — Transparency and storage.** Bind every result to source snapshots,
  retained readable agent/tool evidence and exact authorized context; distinguish
  prepared/submitted/acknowledged/model-observed exposure. Explain stored/rejected
  candidates and applicability from receipts, not invented reasoning. Retain evidence,
  semantic metadata, queues/logs/backups and exports under AtMem's required encrypted
  profile and audited view/investigation/export roles; fail closed on unavailable
  protection. Protect transient processing and credential references. No unprotected
  CLI log files or owner data. A partial host is labelled not reconstructable;
  plaintext workspace/source accessibility is limited to the active authorized
  solver sandbox and is not an alternative evidence archive.
- **FR-010 — Reliability and isolation.** Enforce token/tool/time/byte limits and
  kill/stop accounting; never retry a failed solve invisibly. Record infrastructure
  invalidity separately from agent/product failure. Predeclared reruns repeat all
  paired arms in a repetition with new isolated state and retain original records.
  Use exact validated temporary roots, no owner repo resets or user-config changes.
  Tests cover secret/scope leaks, forbidden history, evaluator access, resets and
  stale projections. Export/delete respects all registered derived copies.
- **FR-011 — Analysis.** Default plan is three independent five-task trajectories
  per arm: 60 attempted solver sessions if all four arms are ready. Pair task and
  repetition and use the frozen three-row cyclic schedule in the plan. This is
  partial position balancing, not full position or carryover counterbalancing;
  report residual execution-order effects as a limitation. Freeze seeds/settings
  where supported; do not promise deterministic sampling. Report per-task and per-trajectory results,
  raw paired deltas, harm and failures. Sessions within a trajectory are dependent;
  do not treat 60 sessions as 60 independent tasks or claim significance. Metrics
  include stage p50/p95 with sample counts and small-sample caveats. Report any
  reduced arm/repetition protocol distinctly; do not pool its results. Controlled
  common-history retrieval and uninterrupted cumulative development are separate
  optional future tracks, not mixed into the primary result.
- **FR-012 — Readiness/authorization.** Separate dry-run fixtures, current Code
  assertion-only diagnostics, governed-experience readiness, rich-structure
  readiness and real trial execution. Use Spec 042 T060's versioned capability
  receipt; the harness must not implement substitute formation or applicability.
  Automatic Codex lifecycle integration is a gate: if normal activation/capture/
  recall cannot be qualified, mark it blocked. A visible benchmark harness boundary
  may be tested as a separate integration-labelled track, never called normal-user
  automatic Codex support. No unapproved paid runs or provider egress; a later
  execution authorization must name a total budget, per-run caps and permitted
  provider. No upstream PR, release, paper or public archive is implied.

## Acceptance and success criteria

- **SC-001:** Five selected tasks have immutable manifests, complete eligibility
  logs and reproducible parent-fail/reference-pass graders before any target solve.
- **SC-002:** Isolation tests deny solver access to hidden tests, future Git objects,
  adjacent scopes, owner secrets and other trials; planted evidence is encrypted
  in retained copies and disclosure follows the role matrix.
- **SC-003:** All four configurations validate advertised capability and preserve
  identical permitted source, native tools and resource ceilings. Blocked cells
  are visible; a two-arm pilot cannot masquerade as the four-arm experiment.
- **SC-004:** Every attempted session has result/failure accounting, snapshot and
  context receipts, measured-or-unknown telemetry and inspected experience history.
- **SC-005:** A report shows per-task comparisons and totals, all failures, cold/warm
  overhead, exact received memories and causal limitations. No preset win rate or
  positive result is required. Reports with missing gates cannot claim benefit.
- **SC-006:** An authorized user can navigate result → memory/context → source and
  applicability → observed test outcome; a fresh process can inspect retained
  evidence without the dead solver. Missing boundaries remain explicitly partial.

## Edge cases and boundaries

Changed CLI/model aliases, unavailable historic dependencies, edited issue text
without recoverable timestamped versions, flaky grading, unsupported hook trust,
network-denied failures, expired inference credentials and incomplete accounting
stop or downgrade the exact cell. Infrastructure exclusions remain in an attrition
table. No task replacements after inspecting AtMem performance. Unrelated edits
in this branch are preserved. No Laya training, synthetic training, Cognee parity
claim, schema migration of owner databases or release publication is in scope.

## Sources

Click's [repository](https://github.com/pallets/click),
[contribution guide](https://click.palletsprojects.com/en/stable/contributing/)
and [license](https://github.com/pallets/click/blob/main/LICENSE.txt) are discovery
references checked on 2026-10-17. Implementation must pin historical source,
license, issue snapshots, dependencies and test instructions, not assume current
documentation applies retroactively. Redistribution/egress review includes issue
content separately from source licensing. No claim of upstream endorsement.
