# AtSys — fixed 20-task pilot

The owner reduced the unstarted 60-task pilot to exactly 20 on 2026-10-26.
The old selection, task configuration and failed attempt are retained.
Active config: `.atsys/tasks/dolphin-readiness-pilot-20.json`.

## Execution and isolation

- Worker: an exact command, not an AI coding worker. It runs the frozen pipeline
  with the controller account's existing private/MEM access. The previous Codex
  worker's workspace-only sandbox blocked those paths before benchmark launch.
- Benchmark agent: native Hermes remains sandboxed with the qualified MCP-only
  profile. Reader is Luna/high subscription; judge Sol/medium OpenRouter Azure-only;
  memory/retrieval/embeddings local. Reader max_turns stays 60.
- Independent validator: `validate_pilot.py` requires20 matching real outcomes,
  receipts/artifacts, reconciled costs, no control regressions and matching handoff.
- Supervisor: read-only Codex gpt-6.1-sol/high, at most two calls; repair disabled.
- Retries: at most two inspect-only invocations; `resumeArgv` cannot dispatch
  another benchmark. A durable one-launch intent prevents repeated launch.
- Time bounds:12-hour attempt,24-hour task,120-second heartbeat. Activity/progress
  deadlines are disabled explicitly; goalMonitoring=false avoids automatic 600s
  milestone deadline injection. Task counts are in saved pipeline logs/evidence.
- Pilot incremental API cap US$10. Supervision/subscription economics are separate.

## Selection

6 Notes-routing failures +3 GitHub-routing failures +2 fixture limitations
+2 recovered-Notes passes +2 other missing-action/log cases +2 traced-zero failures
+2 traced-partial failures +1 other passed control =20.

The20 is post hoc and smaller than the original 60, with only three passed
controls; it is not an accuracy estimate for 600 or proof of broad generalisation.

## Launch after fresh preparation

The new source requires a new condition and fresh zero-model-call qualification.
See verification.md for actual completion status; do not infer it from this guide.
The intended private condition is
`~/.local/share/atmem-dolphin-readiness-20261026/condition-pilot20-v3.json`,
with fresh receipts under `pilot20-v3/receipts`.

```sh
cd /Users/javadtaghia/gitlab/atmem-dolphin-execution-audit-20261025
atsys task submit --config .atsys/tasks/dolphin-readiness-pilot-20.json
```

Submit once, save its task ID and inspect it with `atsys task show TASK_ID` or
`atsys ui`. If output is lost use `atsys task list`, not another submission.
Do not retry the old 60-task task. Do not run a full600 without a separate owner
decision after reviewing the pilot. All20 must be graded; known fixture failures
remain in the denominator and not all 20 must pass.

## Immutable outputs

- Pilot: `/Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot20-atsys-20261026-v1`.
- Handoff: `specs/048-dolphin-execution-readiness/atsys/pilot20-handoff.json`.
- Retries inspect the same output and never choose a new scored attempt.
- Benchmark result remains 390/600 until an actual new full run establishes another.

The exact-command worker propagates stop/timeout signals to its isolated benchmark
process group and detects loss of its AtSys parent. Interrupted provider calls
remain uncertain and cannot be automatically replayed. Fresh receipts are issued
immediately before launch; handoff/validation must remain within their24h window.
