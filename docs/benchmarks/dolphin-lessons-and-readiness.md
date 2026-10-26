# DolphinBench: durable lessons and next-run prerequisites

Updated: 2026-10-26. Scope: the recorded AtMem 2.3.10b1 600-task run.

## Start here after losing the chat, cache, or agent context

1. Read this file, the [full audit and plan](dolphin-execution-audit-and-rerun-plan-20261025.md),
   and [machine-readable evidence](evidence/dolphin-execution-audit-20261025/summary.json).
2. Find the execution-readiness Spec Kit feature via `.specify/feature.json`
   and the repository instructions. Read its spec, plan, tasks and launch checklist.
   If that pointer has since changed for another feature, use the feature path
   recorded here once confirmed. An unrelated active feature does not supersede
   these benchmark prerequisites.
3. Check Git state, task completion and evidence receipts. Do not interpret
   a previous chat assertion, a checked box, or a cached process as a passed gate.
4. Resume the first incomplete readiness task before starting scored work.

The accepted feature is [048 — execution readiness](../../specs/048-dolphin-execution-readiness/spec.md).
Read its [frozen local/API runbook](../../specs/048-dolphin-execution-readiness/runbook.md),
[role policy](../../specs/048-dolphin-execution-readiness/routes.json),
[tasks](../../specs/048-dolphin-execution-readiness/tasks.md) and
[verification](../../specs/048-dolphin-execution-readiness/verification.md).

**Current readiness: NOT READY for a new full scored campaign.** The runtime
guard, isolated profile, synthetic persisted writes and crash checks are
implemented. Original MEM checkpoints were recovered and verified in an isolated
copy; the original image is read-only. Live pilot completion and reviewed
promotion evidence are tracked in verification, not inferred from these notes.

## Lessons we must retain

- **L01 — Preserve the full result.** The original result is 390/600 (65.0%),
  self-tested and not independently accepted. Do not remove inconvenient rows.
- **L02 — Keep three failure cohorts.** 83 are untraced/zero-check, 84 are
  traced/zero-check, and 43 are traced/partial. Overall, 167/210 failures passed
  zero checks. None of the 127 traced failures was one check short.
- **L03 — A trace does not establish completion.** It can be a lookup, failed
  call, wrong operation or wrong destination. Track discovery, attempted call,
  accepted action, persisted state, content correctness and independent evidence
  separately. Check counts are correlated and do not measure repair difficulty.
- **L04 — Permission errors exposed wrong routing.** All 35 untraced Notes
  failures attempted `memo notes`, hit `osascript` errors, and had simulated
  `create_doc` advertised. All six untraced GitHub-auth failures had their
  expected simulated app tools advertised.
- **L05 — Recovery was possible.** Across all 600, 40 tasks hit the measured
  Notes error: five passed. GitHub-auth errors occurred on 32 tasks: 18 passed,
  eight failed with traces and six failed without traces. An error is not a
  sufficient causal explanation for a task failure.
- **L06 — Do not grant real-app permissions to fix simulated app tasks.** A real
  Apple Notes write does not create a DolphinBench document. Real GitHub or Google
  credentials are unnecessary for the benchmark's simulated operations.
- **L07 — The model chose the first route.** There was no deterministic router
  prioritizing `create_doc` over the Apple Notes skill. Local operational skills
  competed with connected app tools. Qualify the displayed skill inventory and
  access controls in an isolated profile; leave the user's normal profile alone.
- **L08 — Generic instructions were already present.** All 600 conversations
  contained the connected-app workflow instruction. Merely repeating it does
  not demonstrate a repair. Measure actual routing and completion.
- **L09 — Tool discovery is distinct from memory retrieval.** The Hermes
  deferred catalog uses lexical search with a rare-token gate. Empty search
  results do not establish capability absence. Exact visible names can be
  described directly. Test actual schemas, search results and dispatch.
- **L10 — Other omissions remain.** Outside the 35+6 cases, 42 untraced failures
  remain; 33 had `create_doc` available. Twenty-six were “Create” requests with
  no loaded skill. Include draft-only replies, Google Workspace detours and
  local-file substitutions in the next analysis.
- **L11 — Two fixtures contradict their required action.** Morgan/085 needs
  `send_email` but supplies inbox/archive tools; Morgan/130 needs a Slack DM but
  supplies CRM tools. Both also fail in the published reference. Obtain an
  upstream disposition; do not secretly patch grader-derived tools into inputs.
- **L12 — Effective catalogs matter.** Lookup tools can be automatically added.
  Compare actual `tools/list` and reader-visible tools, not just `active_tools`.
- **L13 — Missing logs need their own classification.** Morgan/129 has recorded
  booking calls/IDs but lost its independent backend log. Preserve app state,
  log bytes and uncertain actions across recovery. Never manufacture attestation
  or blindly replay a possibly completed operation.
- **L14 — Missing actions hide content quality.** None of the 83 untraced cases
  has a recorded content-judge response. Good-looking drafts are not demonstrated
  memory successes. Draft evaluation, if done, is a separate diagnostic.
- **L15 — 75.4% is conditional.** 390/517 is not a corrected full score or a
  memory-only score. Recovering all 35+6 without regressions yields 431/600
  (71.8%); reaching at least 75.4% requires 453/600 (75.5%), 63 additional passes.
- **L16 — Reference rows exist, but conditions differ.** The committed reference
  has 424/600 passes on matching requests. It passes 58 of our 83 untraced tasks,
  24 of our 35 Notes cases and five of our six GitHub cases. These are descriptive
  comparisons, not a matched causal experiment or a first-place claim.
- **L17 — Freeze memory for the first repair experiment.** Hold product artifact,
  persona memories, retrieval and model settings fixed while qualifying the host.
  Measure recovered failures and regressed passes. Later memory changes need
  the repaired execution profile held fixed.
- **L18 — Preserve honest provenance.** Public tasks informed development.
  The pilot is diagnostic, not a sealed holdout. The earlier 192/600 artifact
  was a research build based on 2.3.9; stable 2.3.10 was not a new 600-task run.
- **L19 — Freeze one full-run condition.** Use a new run identity, all 600 cases,
  fresh app state, unchanged grading and archived attempts. Do not combine the
  best rows from different pilots, prompts or configurations.
- **L20 — Readiness must survive cache loss.** Git-tracked instructions, spec,
  task list, public source hashes and durable qualification receipts are the
  source of truth. Temporary paths, chat summaries, live processes and model
  memory are optional conveniences. Remote Git publication is reported separately
  from a local commit or merge to main.

- **L21 — Identify the completed campaign by evidence.** Published 600 used
  subscription Luna/high and API Sol/medium judging, with both state assessors
  disabled. Abandoned similarly named Sol-reader campaigns are different conditions.
  Never reuse their launcher as the published baseline.
- **L22 — Freeze execution routes as well as model names.** Storage, retrieval
  and exact-digest Ollama embeddings remain local. A local failure stops work;
  it never enables paid inference. Sampling defaults and unsupported native
  output caps must be disclosed. Every setting change needs new qualification.

## Before starting the next full run

- [ ] Reconstruct the audit from immutable public inputs on a fresh process.
- [ ] Freeze the execution-only experimental contract and fixture disposition.
- [ ] Qualify an isolated supported skill/tool profile with real displayed inputs.
- [ ] Verify synthetic app mutations, persisted state and independent logs through
  the same bridge and sandbox used by the campaign.
- [ ] Qualify crash/resume behavior without lost evidence or duplicate actions.
- [ ] Run the fixed pilot, including both traced-failure cohorts and passed controls;
  report routing, action success, content correctness, regressions and costs.
- [ ] Freeze one candidate and archive receipts bound to source, profile, schemas,
  artifacts, memory checkpoint and environment identities.
- [ ] Implement and integrate a launch guard that refuses missing, failed or
  identity-mismatched receipts. Merely adding a checker script is insufficient.
- [ ] Record a candidate GO decision and budget before any full scored dispatch.

These are prerequisites for benchmark integrity and useful optimization, not
permission to tune against hidden grader labels or to promise a particular score.

## Reconstruct the audit after deleting every cache

Use a fresh checkout of this Git branch. These commands download only public
benchmark evidence and dependencies; they make no model or application calls.
The recovery helper pins the dataset revision, checks the ZIP hash and refuses
to overwrite existing inputs with different bytes.

```sh
python3 -m venv .venv-dolphin-audit
.venv-dolphin-audit/bin/python -m pip install 'PyYAML==6.0.3'
.venv-dolphin-audit/bin/python scripts/recover_dolphin_audit_inputs.py \
  --output ../dolphin-audit-inputs
git clone https://github.com/mem0ai/dolphinbench.git ../dolphin-audit-upstream
git -C ../dolphin-audit-upstream checkout 81cb6f8405b40a9e76089cef650806a80af06ea2
.venv-dolphin-audit/bin/python scripts/audit_dolphin_execution_20261025.py \
  --submission ../dolphin-audit-inputs/submission.zip \
  --rows ../dolphin-audit-inputs/rows.json \
  --upstream ../dolphin-audit-upstream \
  --output ../dolphin-audit-reproduced
```

Use fresh sibling paths if those directories already contain unrelated work.
The regenerated summary must reconcile 600 tasks, 390 passes, failure cohorts
83/84/43, 35 untraced Notes errors, six untraced GitHub-auth errors, and two
catalog/rubric mismatches. The archived ledger itself remains readable with no
runtime or dependency installation at all.

## Active pilot size amendment

On2026-10-26 the owner reduced the unstarted diagnostic from60 to20 tasks.
Use `pilot-selection-20-20261026.json`, the new private20 condition and
`.atsys/tasks/dolphin-readiness-pilot-20.json`; original60 artifacts are retained
and superseded for new dispatch. Do not retry the stopped60-task AtSys job.
The exact-command worker keeps the benchmark agent sandbox unchanged.
See the feature verification and AtSys runbook for current evidence and state.


## Bounded exporter recovery amendment — 2026-10-26

The owner authorizes reviewed harness/export/recovery repair and an evidence-
preserving continuation of the same20. Prior no-repair/inspect-only restrictions
are superseded within this scope; the original parent remains read-only.023/085
executions and grades are preserved;129 must be reconstructed offline or remain
blocked, never replayed. Root owns review, fresh source-bound zero-call ARM
qualification, new freeze/epoch and remaining17 dispatch. The implementation
worker must not launch scored work or commit/push. Read
[the recovery contract and CLI](../../specs/048-dolphin-execution-readiness/recovery-implementation.md)
before any continuation. Full600 remains unauthorized and NO GO.

The active **automatic** trusted-parent policy and exact task IDs are in
[Automatic recovery](../../specs/048-dolphin-execution-readiness/atsys/AUTOMATIC-RECOVERY.md).
The trusted parent performs qualification/freeze/continuation without a human
issuing each retry. The coding repair worker retains workspace scope.

## Fixed20 final outcome — 2026-10-26

[Final pilot report](dolphin-pilot20-20261026-report.md):20 executed/graded,13 passed,7 failed;10 recoveries,zero control regressions. Independent final validation passed and recorded the handoff digest. Recorded cumulative API cost USD0.083317; supervisor/subscription costs remain separate. The completed workflow is not a20/20 task pass. Full600 remains unauthorized; do not infer a new full score from this post hoc selection.

Future supervised work must include an explicit goal, success criteria, meaningful progress/observer signals and a human-readable final outcome report as part of the launch contract. Raw logs and a successful process exit do not provide that handoff. The general AtSys correction is tracked in its specs/007-goal-workflow; do not alter frozen benchmark configuration to retrofit reporting.
