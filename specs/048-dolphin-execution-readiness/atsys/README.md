# AtSys pilot supervision

Prepared task: `.atsys/tasks/dolphin-readiness-pilot.json` (repository tracked).
**Prepared only, not submitted.** This task cannot authorize a full 600 run.
Original full-run readiness remains NO GO until the fixed pilot passes.

## Objective already included in the task

> Qualify and execute the fixed 60-task pilot using the frozen AtMem 2.3.10b1
> condition. Preserve local/subscription/API routes and all settings. Retain
> independent app evidence, report costs/regressions and stop for unresolved
> actions. Validate real evidence before reporting readiness. Do not launch 600.

## Pinned orchestration settings

| Role | Model | Reasoning | Limits |
| --- | --- | --- | --- |
| AtSys Codex worker | `gpt-6.1-sol` | medium | 12-hour attempt; 24-hour task |
| Read-only supervisor | `gpt-6.1-sol` | high | At most two supervisor calls |
| Benchmark reader | `gpt-5.6-luna` | high | Existing subscription, frozen original settings |
| Benchmark judge | `gpt-5.6-sol` | medium | OpenRouter Azure-only; US$10 pilot incremental API cap |

AtSys/worker/supervisor billing is separate from the benchmark ledger. Do not
claim the benchmark cap covers orchestration or that subscription usage is free.
`preparation.json` records task/validator hashes. AtSys records task configuration
and execution state. Do not change configuration/validator during an active task.

The watchdog is installed/loaded. Automatic repairs are off. Two supervised
worker recovery attempts permit inspection and reattachment, not another paid
pilot. Only one benchmark launch is permitted, at the fixed fresh output path
specified by the configuration. Existing output/inflight markers stop relaunch.
A legitimate long provider wait is not grounds to create another scored attempt.
No per-output-silence timeout is set; liveness and the overall deadlines remain.

## Start

1. Sign Hermes in explicitly (do not copy Codex refresh tokens into Hermes):

```sh
hermes auth add openai-codex --type oauth
```

2. Submit once from the implementation worktree:

```sh
cd /Users/javadtaghia/gitlab/atmem-dolphin-execution-audit-20261025
atsys service status
atsys task submit --config .atsys/tasks/dolphin-readiness-pilot.json
```

3. Save the returned task ID. Inspect the new task's actual state and heartbeat:

```sh
atsys task show TASK_ID
atsys ui
```

If submit output is lost, use `atsys task list` before doing anything else.
Do not resubmit the same task to get a new ID. The old 20-task experiments in
AtSys are unrelated and do not establish readiness for this pilot.

## What it does and what acceptance means

The worker reads the durable Spec Kit artifacts, checks mounted inputs and local
Ollama, reruns zero-model-call native profile/app/crash qualification under the
existing frozen condition, and issues fresh evidence-bound receipts. It then
invokes the installed-product guarded launcher for exactly the fixed 60 IDs.
Failed authentication, changed artifacts or an existing uncertain run require
operator attention; no cloud fallback, receipt fabrication or in-place repair.

Its independent command validator verifies full-admission evidence (no execution):
exact 60 IDs, original condition, preserved artifact hashes, reconciled costs,
no control regressions and a handoff matching the real pilot report. All60 tasks
must be graded; not all tasks must pass. Known fixture failures remain included.
A worker's success message and a zero shell exit alone cannot establish success.

Expected outputs:

- New pilot directory:
  `/Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot-atsys-20261026-v1`.
- Fresh private receipts:
  `~/.local/share/atmem-dolphin-readiness-20261026/receipts-atsys-v1/`.
- Matching handoff: `specs/048-dolphin-execution-readiness/atsys/pilot-handoff.json`.

After a passing pilot, review recoveries, regressions, cohort results, latency,
costs and fixture limitations. A fresh 600 needs its own owner authorization and
separate AtSys task/configuration; this pilot task stops after the handoff.
