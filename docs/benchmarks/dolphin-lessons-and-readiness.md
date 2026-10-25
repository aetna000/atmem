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

The Spec Kit feature-directory choice is currently pending: the specify skill
requires the user to provide that path before creating a feature. The proposed
directory is `specs/048-dolphin-execution-readiness`; it is not yet an approved
or completed spec. Do not mark the spec/plan/tasks complete until they exist.

**Current readiness: NOT READY for a new full scored campaign.** The historical
audit is complete. Runtime repairs, synthetic app round trips, crash qualification,
paired pilot and an executable launch guard have not been implemented or run by
this audit. The instruction to wait is a repository policy; a machine-enforced
guard must still be wired into the actual launch entry points.

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
