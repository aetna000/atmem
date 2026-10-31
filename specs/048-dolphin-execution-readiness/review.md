# Claude review and remediation

Requested reviewer: **Claude Opus 5.5, medium**, read-only. Invoked installed
Claude CLI with `--model claude-opus-5-5 --effort medium --safe-mode`.
Retained JSON metadata identifies `claude-opus-5-5`; no substitute reviewer used.

## Evidence

- `review/opus-5.5-medium-review.json`: initial source-reading review hit its
  24-turn limit. This is not a completed verdict.
- `review/opus-5.5-medium-findings.json`: resumed session produced full findings.
- `review/opus-5.5-medium-followup.json`: review of supplied revised source.
- `review/opus-5.5-medium-final.json`: successful final follow-up; reports no
  definite blockers and four confirmations, addressed below.
- Earlier empty-output interrupted attempt is retained, not counted as a verdict.
  Review usage/cost fields remain in raw JSON; do not equate review billing with
  pilot API spend or sum potentially cumulative session totals blindly.

## Implemented fixes

1. Freshness checked at launch, then process/run-bound admission; immutable
   condition, source and receipt hashes still checked during every dispatch.
2. Upstream payload hashes verified, not just the manifest file; historical
   ledger/selection, orchestration, interpreter binaries, controller/package
   RECORD inventory and source indexes pinned.
3. Remove hardcoded export path, bind qualified app/runtime/controller paths,
   explicitly pass the original reader model, split pilot/full budget caps.
4. Issue receipts from retained native capture and real bridge/crash artifacts;
   reject source/options/runtime mismatch. No manual passing-check issuance in
   the operator runbook.
5. Crash qualification creates its workspace through actual `Runner._apps`;
   nonempty sent bodies must be present in persisted state.
6. Qualify the actual installed host profile builder and identical isolation,
   retry and timeout settings; remove builtin writable memory tool.
7. Per-task completed journal, raw persisted state/log and actual request evidence
   required. Legitimate gate-only refusals need an explicit ruling.
8. Full report uses the same task-ID, grade-layout, uncertainty and cost checks;
   reports real regressions. Unknown zero-cash subscription calls block promotion.
9. Native model ingestion disabled; local source-episode import retained.
10. Journal intent precedes gateway startup. Freeze validates before publishing.
    Listener path is within service output and partial JSON is retried boundedly.
11. Actual subscription wire model/reasoning/host and actual judge routing/inference
    bodies verified before a pilot receipt can be issued.

## Final reviewer confirmations

- **Judge replay scope:** inspected pinned `graders/judge_recording.py` and
  `harness/runner.py`. Replay is a process-local ContextVar defaulting to `None`,
  not a filesystem/global cache. Fresh launch imports a new process; paid grading
  sets `allow_paid=True`, using `nullcontext`, not `replay_judge`. No historical
  responses are loaded. Mechanical failures legitimately require no model judge.
- **Reader inference body:** actual native capture has
  `model=openai/gpt-5.6-luna`, `reasoning_effort=high`, no sampling overrides and
  no CLI cap; the existing gateway explicitly inserts 4096. Native subscription
  output cap remains unsupported and disclosed. Gateway negative tests verify
  incompatible inference controls stop before forwarding/reservation.
- **Gate-refusal schema:** pinned upstream Runner writes `attempts` at top level,
  independently of `row`; report matches it. Integer `check` indices likewise
  match actual upstream grade output.
- **Index mutability:** installed factory opens existing SQLite indexes with WAL;
  selection does not call `build` or update vectors. Frozen file hashes enforce
  drift refusal. Live pilot is still required to demonstrate this stays stable;
  synthetic profile capture is not evidence of completed retrieval performance.

The final review preceded a CLI alias correction: service CLI accepts prefixed
`openai/gpt-5.6-luna`; actual provider wire remains bare `gpt-5.6-luna` as frozen.
That failed startup made no task/model calls and was retained. Qualification was
rerun under new source/condition identities. Full launch remains NO GO until the
live pilot and every operational gate pass.

## Fixed20 amendment review

`review/opus-5.5-medium-pilot20.json` records Claude Opus 5.5 medium reviewing the
20-ID cardinality change and exact-command worker. It found no scored-retry or
false-success path. Receipt freshness is addressed by immediate fresh issuance
and the 12h worker limit (still fail closed after 24h). Installed AtSys only sends
termination to its immediate child, so the new direct Python command worker
propagates stop to an isolated workload process group and checks parent liveness.
A synthetic real descendant-process test passed. AtSys snapshots config into its
operations store, not the pinned source JSON; goalMonitoring=false prevents
automatic progress-file/deadline injection.68 focused tests and fresh actual
profile/app/crash qualification passed. The20 pilot is not an estimate for600.
