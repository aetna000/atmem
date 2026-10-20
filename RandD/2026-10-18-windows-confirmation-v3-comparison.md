# Structural context confirmation: the 20% token goal is not met

All nineteen fixed issues, two repeats and both arms are retained: 76 model
attempts, 76 private grades and 38 complete matched pairs. No model or private
grading outcome was retried. The candidate is the frozen unpublished preview
`e8d98dadfa98554ba38311096a7b90dac815bbbe03c6c35dae430bed54ee7bf6`.
This is repository-disjoint, qualification-informed confirmation, not an
untouched-implementation or general coding-superiority claim.

Authoritative comparison:
`external-windows-confirmation-v3-comparison-v1-20261018`, object
`obj_eae40b942cdf46f5b1c932a4577698a4`, canonical payload SHA-256
`4d26e43a67e2ea9c5b0cd043493ceb89d6efbded890f34bc934f0ac0bfb013d8`.

## Matched measured results

| Metric | Native tools | AtMem structure + tools |
|---|---:|---:|
| Attempts / complete usage / available grades | 38 / 38 / 38 | 38 / 38 / 38 |
| TOTAL input tokens, including cached input | 9,056,063 | 8,576,097 |
| Cached input tokens | 8,399,104 | 7,814,528 |
| Uncached input tokens | 656,959 | 761,569 |
| Output tokens | 54,891 | 47,564 |
| Fully correct tasks, including source authority | 12/38 | 13/38 |
| Target checks passed / failed | 17 / 33 | 18 / 32 |
| Regression checks passed / failed / skipped | 3,632 / 54 / 0 | 3,659 / 27 / 0 |
| Source-policy violations | 3 | 2 |
| CLI-visible Code MCP calls | 0 | 2 |
| Public-test MCP calls | 40 | 40 |
| Solver p50 / p95 | 24.005 s / 73.200 s | 22.602 s / 41.424 s |
| Supervisor p50 / p95 | 24.913 s / 74.098 s | 24.239 s / 44.050 s |
| Fresh preparation p50 / p95 | 0.269 s / 1.306 s | 16.622 s / 35.609 s |

The exact pooled TOTAL-input reduction is **5.299941045021440332294508110%**.
Observed full-task quality is one pass higher, so the observed-count quality
condition passes. Neither the 50% target nor the exact 20% fallback passes.
Uncached input increases by 104,610 tokens; do not turn the TOTAL-input result
into a claim of lower uncached use or lower billed cost. No cache-pricing
conversion is made.

Preparation, supervisor and solver timings are separately measured components.
Their medians must not be added or described as a measured end-to-end median.
Fresh structural preparation is substantially more expensive here. Steady-state
warm-project latency is not established by this table.

## Repository breakdown — no exclusions

| Repository | Attempts per arm | Native / AtMem full passes | Native input | AtMem input | Input reduction |
|---|---:|---:|---:|---:|---:|
| Seaborn | 8 | 2 / 3 | 2,108,154 | 1,835,934 | 12.91% |
| Flask | 8 | 5 / 4 | 1,051,709 | 1,312,931 | -24.84% |
| Xarray | 8 | 2 / 3 | 2,010,289 | 1,714,687 | 14.70% |
| Pylint | 8 | 3 / 3 | 2,293,579 | 1,962,683 | 14.43% |
| PyVista | 6 | 0 / 0 | 1,592,332 | 1,749,862 | -9.89% |

Negative reductions mean MORE input. Flask regresses in both token use and
observed full-task quality; PyVista does not solve a full task in either arm.
These outcomes stay in the primary denominator. The method is not reliably
beneficial across this small repository set.

## Paired uncertainty and interpretation

The prospectively fixed 10,000-resample analysis uses seed
`atmem-windows-confirmation-cluster-audit-20261018-v2`.

| Cluster unit | Units | TOTAL-input reduction, 95% percentile interval | Full-task pass-rate difference, 95% interval |
|---|---:|---:|---:|
| Issue | 19 | -10.17% to 16.69% | -7.89 to +13.16 percentage points |
| Repository | 5 | -9.55% to 14.23% | -5.56 to +10.53 percentage points |

There are nine both-pass pairs, three native-only passes, four AtMem-only
passes and twenty-two neither-pass pairs. Repeats stay paired inside clusters.
Five repository clusters are a small sample. These intervals do not establish
equivalence, a reliable quality improvement or a graph-specific causal effect.

The earlier reused-task 24.817175% saving, with 4/10 full passes in both arms,
remains tuning evidence. It is not reproduced as a 20% saving by this cohort.
The two CLI-visible Code MCP calls are a reason to inspect actual traces and
context usefulness, not proof by themselves that the graph was ignored or that
an on-demand variant will improve the result.

## Status and next action

The goal and T062 remain open because the 20% efficacy gate fails. T086's
execution/report/recovery work is complete with this negative result.

Independent Mac recovery from the encrypted MEM collection verifies all 590
runs, 3,033 events, 304 model/public full streams, 76 candidates, 76 private
grades and 76 public vaults, without opening original source vaults. Collection
SHA-256: `89d24f65b6279d5e19a04a4210215930b3306d0dbacec895b152708101c57fd7`.
The separate request audit reconstructs and binds all 76 original requests,
including twelve chunked records (802,141,548 canonical dispatch bytes), with
zero model or grade retries. The collection contains 1,223 actual encrypted
archive files; an earlier glob count also included 1,223 Mac metadata sidecars.
Keys remain internal, not on MEM.

Archive: `/Volumes/MEM/AtMem-Code-Replay-20261017/windows-confirmation-v3-protected-20261018`.
Proof runs: `external-windows-confirmation-v3-MEM-transfer-v1-20261018` and
`external-windows-confirmation-v3-archive-request-audit-v1-20261018`.
Preserve this failed-target result regardless of the next iteration.

Inspect all retained traces for large/repeated native reads, actual tool use
and relevance of the initial context. Any new candidate informed by these
results must treat this cohort as reused development evidence, not label a
rerun as untouched confirmation. Keep the existing frozen comparison intact;
do not lower the 20% threshold, discard Flask/PyVista or change to uncached-only
accounting to obtain acceptance.
