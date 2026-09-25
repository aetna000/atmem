# Continuity implementation status — 2026-09-25

> **Attribution correction:** recovery in this historical smoke run was supplied
> by `benchmarks/agent_continuity/runtime.py`, not a complete shipped AtMem
> feature. The 24/6 outcomes demonstrate that fixture design only. Raw evidence
> remains unchanged. The active product-first work is tracked in
> [the corrected plan](../../../specs/benchmarking/002-agent-continuity/product-first-correction.md).

**Implemented: offline foundation. Not completed: public-corpus benchmark or
product continuity improvements.** Nothing was released or deployed.

This is the preserved first-foundation validation record. Later retail-tool and
AtFlows HTTP milestones are tracked separately in [milestones-20260925.md](milestones-20260925.md);
they do not modify the original raw smoke bundle or its claim level.

## Branches

- AtMem: `feat/agent-continuity-benchmark`, based on
  `3ca2733a4d5b641b8eb887aacf5cd9c6277e0c59`.
- AtFlows: `feat/continuity-observability`, based on
  `be131c9633e732ec39ef2f9b55422e4e042518eb`.

Existing planning changes were preserved. Work is isolated on these feature
branches; no merge, release or deployment is implied. Production runtime sources
and package versions are unchanged.

## Final corrected-source validation

| Check | Result |
| --- | --- |
| Python continuity + existing walking-skeleton/host-boundary suites | 103 passed, 170.59 seconds |
| AtFlows dedicated-process characterization | 6 checks passed; wrapper passed |
| AtFlows server TypeScript check | Passed |
| Formatting / whitespace / Python compilation | Passed |
| Isolated built-wheel version checks | AtMem 2.3.7b2; AtFlows 0.1.2 |
| Final frozen-source offline matrix | 61/61 expected cells passed; exit 0 |
| Claude final read-only review | Approved bounded foundation and final clean-control fix; rerun condition satisfied |

Commands:

```sh
python -m pytest tests/benchmarking/test_agent_continuity.py tests/test_task_state_walking_skeleton.py tests/test_task_state_host_boundary.py -q
python -m benchmarks.agent_continuity.runner --output FRESH_DIRECTORY --include-atmem
# AtFlows repository:
bun test tests/continuity/current-product.test.ts
bunx tsc --noEmit -p apps/server/tsconfig.json
```

Environment/packages and exact source hashes are in the result manifest. No remote
CI run is claimed. Wheel checks used an isolated environment with dependency
access; they are not full clean-install artifact gates.

## What the 61 cells show (smoke only)

- 48 completed with the expected external effect.
- 12 correctly blocked under the fixture's declared uncertainty/capabilities.
- 1 deliberate naive-restart control produced duplicate effects and was classified
  `invalid_effects`, even though its worker claimed success.
- No duplicate or wrong effects in the 60 non-negative-control cells.
- All six clean controls completed without a kill or restart.
- Baseline and AtMem use the same competent reconciliation runtime. **No
  AtMem-specific benefit, production readiness or leaderboard position is shown.**

Raw records, schedule, environment and checksums:
[offline-smoke-20260925](../results/offline-smoke-20260925/manifest.json),
[trials](../results/offline-smoke-20260925/trials.jsonl),
[summary](../results/offline-smoke-20260925/summary.json),
[checksums](../results/offline-smoke-20260925/SHA256SUMS.json).
These contain generated fixture data only, not user Home or API credentials.

## Invalidated development evidence

Claude found a clean-control bug in an earlier supervisor: absent event.barrier
compared equal to `fault=None`. Earlier clean rows actually contained early kills.
Those development outputs are invalid as clean-control evidence. They are not in
the canonical passing bundle. The guard and six actual-process regression tests
were added, then all final results above were regenerated on unchanged source.

Other runs interrupted for review or rejected by the source-change guard are
partial diagnostics, not qualification. In particular the attempted twenty-repeat
development run is **not** a completed SC-001 qualification.

## Next implementation gates

1. Native pinned retail adapter and upstream no-fault equivalence; freeze exact
   live prompt hashes and operational evaluation limits.
2. Current-policy/context and standalone evidence integration; current AtFlows
   live observation with unsupported authentication/accounting stated explicitly.
3. Four-arm public pilot; preserve all current-product raw evidence before fixes.
4. Preregister held-out evaluation and propose bounded fixes from measured gaps.
5. Final-source repeated qualification, paired held-out rerun, resource/cost and
   completeness reporting. Only then consider a production-scoped claim.

No paid model call or held-out task evaluation has run. Temporary upstream
checkout, environments, fixture stores and development diagnostics are retained
under `/private/tmp/atmem-continuity.PaU9SG` (approximately 1 GB during development).
They can be reviewed/cleaned later; no existing user files were removed.
