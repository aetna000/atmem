# Five-percent no-egress preflight at `b58cc6b`

**Status:** local readiness evidence only. No paid benchmark case was scored and
no quality claim can be made from this report.

## Passed gates

| Gate | Result | Retained evidence |
| --- | --- | --- |
| LongMemEval-V2 | Ready: 23 questions, 200 trajectories, 5,095 trajectory screenshots, 2 query images, pinned reader processor and official checkout | `/Volumes/MEM/atmem-benchmarks/feature-040/1447ebe/longmem-no-egress-preflight.json` |
| DolphinBench AtMem | Ready: official 30-task development split, installed artifact, matched adapter/driver and checkpoint digest validated | `/Volumes/MEM/atmem-benchmarks/feature-040/245bf63/dolphin-atmem-no-egress-preflight.json` |
| DolphinBench Mem0 OSS | Ready: the same 30 tasks and runtime contract with the matched comparator checkpoint | `/Volumes/MEM/atmem-benchmarks/feature-040/245bf63/dolphin-mem0-no-egress-preflight.json` |
| Repository regression | 2,169 passed, 82 skipped | Local test run at `b58cc6b` |

All three preflight receipts record `paid_egress_started: false`. RunPod had no
active pods after validation.

## Work still required before scoring

The AgentRunbook-R LongMem checkpoint remains incomplete. The exact finalization
probe evidence for the pinned reader, judge, agent and grader routes also has
not been produced. The last observed RunPod balance was insufficient to finish
those operations and the complete matched runs, so no partial paid execution
was started.

After sufficient credit is available, resume only AgentRunbook-R formation,
then run finalization and all matched 23-question/30-task arms. Every failed or
missing case remains in the denominator.
