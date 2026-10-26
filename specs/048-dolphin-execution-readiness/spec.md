# 048 — DolphinBench execution readiness

## Overview

Implement the six readiness requirements accepted on 2026-10-26. Preserve the
original 390/600 record and failure cohorts 83/84/43. The 20-case selection is a
post hoc diagnostic, not a holdout. Improve the host with memory held fixed.

## User stories and functional requirements

- **FR-001 / P1:** An operator selects a versioned, isolated MCP-only profile.
  Simulated apps and authorized read-only memory tools remain available; local
  skills, terminal, real-app accounts and deferred discovery cannot hijack writes.
  Qualify the actual outgoing model tool array before provider forwarding.
- **FR-002 / P1:** Verify actual simulated mutations through the upstream app
  bridge: tool result, persisted state and independent app log agree. Use synthetic
  data with no reader/judge calls. Preserve sandbox/credential isolation.
- **FR-003 / P1:** On crash/resume preserve original state/logs and uncertain
  interaction markers. Refuse destructive setup or duplicate action execution.
- **FR-004 / P1:** Execute exactly the frozen 20 pilot IDs, separating original
  traced-zero and traced-partial cases and passed controls. Retain original
  grades, actual usage/cost uncertainty, regressions and fixture limitations.
  Missing original checkpoints/configuration blocks live execution, not coding.
- **FR-005 / P1:** Freeze a JSON configuration binding model/judge settings,
  profile, benchmark, product artifact, source, memory checkpoints, selection,
  budget and fixture disposition to on-disk SHA-256 identities. Configuration or
  input changes invalidate prior qualification. No secrets in public receipts.
- **FR-006 / P1:** Enforce receipts at actual launch/dispatch boundaries. Pilot
  requires profile/app/recovery evidence; a full campaign additionally requires
  complete passing pilot qualification. Reject absent, failed, stale, malformed,
  changed-artifact, different-condition and partial-pilot evidence before calls.
- **FR-007 / P1:** Evidence and instructions are Git-tracked, rehydratable without
  Codex cache. A fresh session locates spec/plan/tasks and sees incomplete gates.
- **FR-008 / P1:** Obtain a read-only Claude Opus 5.5 medium review, record model
  metadata/findings, remediate applicable findings and rerun focused verification.
- **FR-009 / P1:** Freeze a per-role local/subscription/API runbook against the
  completed Luna 600-task campaign, not an abandoned Sol launcher. Preserve local
  memory/index/embedding work; disable both state assessors; reader is subscription
  Luna/high and judge is API Sol/medium via Azure-only OpenRouter. Reject settings,
  role, endpoint, artifact or local embedding digest drift before forwarding.
  Record omitted provider sampling controls and unsupported provider output cap
  honestly; no silent fallback or claim of bit-identical hosted inference.

## Acceptance scenarios

1. Given a model request advertising `terminal` or `skill_view`, the provider is
   never called; a request with only declared MCP apps and memory can proceed.
2. A synthetic create/read/mutate operation has matching result/state/log after
   reconnect. A crash after mutation preserves that single action and refuses replay.
3. Editing a pinned checkpoint or receipt artifact, expiring a receipt, using a
   receipt from a different configuration or completing 19 pilot tasks blocks launch.
4. Known fixture mismatches are documented evaluator-side; actor inputs never
   receive expected action names, check labels or reference answers.
5. Missing MEM storage leaves the live pilot explicitly incomplete and full
   campaign blocked. Synthetic qualification is never represented as pilot accuracy.

## Success criteria

- **SC-001:** FR-001–003 and FR-006 positive/negative boundary tests pass.
- **SC-002:** Reproduce actual upstream app and crash checks with zero model calls.
- **SC-003:** Pilot report reconciles exactly 20 unique selected tasks, historical
  regressions, current grades, trace status and costs before it can authorize full.
- **SC-004:** Claude review and remaining operational blockers are retained.

## Constraints

No release, new full 600 run, changed rubric, silently repaired fixtures, real-app
credentials or promised score. Use original model/memory settings for the pilot.
Owner-authored local receipts provide accidental-staleness protection, not
adversarial attestation against the operator controlling files and source code.
Research qualification files contain public simulated content; production AtMem
evidence encryption/authority contracts remain unchanged.

## Historical owner amendment — 2026-10-26 (retry restrictions superseded below)

The owner reduced the unstarted diagnostic to exactly 20 tasks. Use the immutable
`pilot-selection-20-20261026.json` revision3; preserve the original 60 selection
as historical evidence. Reader max_turns remains 60; it is not the pilot size.
The new condition and fresh qualification supersede the old unstarted 60 condition.
The smaller pilot is a post hoc execution diagnostic, with fewer routing/control
examples and wider uncertainty. It does not estimate a new 600 accuracy.

Use an AtSys exact-command worker for this benchmark execution, with independent
validation and read-only supervisor diagnosis. This removes the accidental
Codex workspace-only controller restriction; the benchmark's native agent
sandbox, tool allowlist and credential isolation must stay enforced. Retries use
an inspect-only command and may not start another scored attempt.


## Owner amendment — bounded exporter repair and supervised continuation

Accepted 2026-10-26 following AtSys pilot task
`task-b243ee72-b222-4e59-937c-d46b59565ce7` (needs_attention; workload exited).
The prior read-only/no-repair and inspect-only retry restrictions are superseded
only for reviewed harness/export/recovery code, focused tests and documentation.
Historical tasks, conditions, receipts and results remain unchanged.

- **FR-010:** Export exact finite JSON numeric equivalence recursively, with
  booleans/strings distinct, large-integer precision, ordered calls/targets and
  original wire arguments retained. No invented defaults or semantic changes.
- **FR-011:** Verify the old condition against retained before-repair source
  snapshots without weakening ordinary `load_condition` or launch admission.
  Create a separate immutable recovery epoch; bind both source revisions and
  unchanged scientific configuration. Never rewrite the read-only parent.
- **FR-012:** Import completed023/085 executions and grades byte for byte.
  Reconstruct129 offline only from exact lifecycle/gateway/process, original
  dated user boundary, independent state/log and completed budget proofs.
  Preserve `completed:false`; report accepts a hash-bound reproducible recovery
  receipt instead. Installed API context delivery may prove the native memory
  provider was disabled; never invent a missing provider shutdown observation.
  Native result duration must be labelled as excluding controller overhead.
- **FR-013:** Resume only untouched selected tasks; never repeat saved actions,
  completed grades or uncertain provider calls. Keep the same selection20,
  installed wheel, read-only memory, Luna/high subscription, local Ollama,
  Sol/medium Azure-only OpenRouter and cumulative USD10 cap. Lock each epoch;
  persist exclusive dispatch/grade intents before side effects. Verify inherited
  pins and charges before startup, dispatch and report. Unknown effects escalate.
- **FR-014:** A usable supervisor handoff requires tests, fresh real zero-model-
  call profile/app/crash qualification on executing source, new freeze and new
  immutable epoch before each of at most two bounded coding repairs. The coding
  worker writes only this workspace. The trusted parent executes reviewed
  private/MEM commands outside that sandbox. No arbitrary command approval,
  hidden hash update, nested AtSys task, app reset, grader/fixture/model/memory
  change, original-grade overwrite or full600 launch is authorized.

The implementation worker must not launch scored work, call reader/judge models,
commit or push. Root owns Claude review, final qualification/freeze and actual
supervised continuation. A completed pilot with a regressed control still
produces its complete report and blocks promotion. Original390/600 and cohorts
83/84/43 remain unchanged;75.4% remains conditional. See
[recovery implementation](recovery-implementation.md) for executable contracts.
