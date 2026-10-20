# Query-nomination structural-context screen (CD2)

## Result: token reduction passes numerically, quality requirement fails

The complete 19-pair comparison uses **26.231768438% fewer TOTAL input tokens**,
but AtMem fully passes **7/19** tasks against native tools' **8/19**. It therefore
fails the combined >=20% saving / equal-or-better task-pass requirement. The
50% target also remains unmet. This is reused-issue development evidence, not
untouched confirmation, and cannot complete T062 or the overall goal.

| Metric | Native tools | AtMem structure preview |
| --- | ---: | ---: |
| Attempts / normal usage receipts / grades | 19 / 19 / 19 | 19 / 19 / 19 |
| Full tasks passed, including source authority | 8/19 | 7/19 |
| TOTAL input tokens, including cached input | 5,110,437 | 3,769,879 |
| Cached input tokens | 4,688,640 | 3,380,352 |
| Uncached input tokens | 421,797 | 389,527 |
| Output tokens | 29,213 | 22,055 |
| Solver latency p50 | 30.952 s | 24.125 s |
| Solver latency p95 | 70.515 s | 39.593 s |
| Solver latency mean | 39.232 s | 24.834 s |
| Preparation latency mean | 0.477 s | 17.861 s |
| Mean preparation + solver, not full end-to-end latency | 39.709 s | 42.695 s |
| Supervisor elapsed mean, separate from solver | 40.142 s | 26.948 s |
| Source-policy violations | 2 | 1 |
| Completed Code MCP calls | 0 | 0 |
| Completed public-test calls | 19 | 20 |
| Observed fix-check successes / failures | 11 / 14 | 10 / 15 |
| Observed preservation-check successes / failures | 1,822 / 21 | 1,829 / 14 |

Solver latency is lower in this cohort, but cold preparation removes that
advantage in the displayed preparation-plus-solver means. Those sums are not
full user-experienced latency. No warm-cache measurement or ordinary installed
workflow speedup follows. Partial checks are not independent tasks. Normal
receipts exist for all 38 attempts; no missing-token value is imputed.

## Every repository, including token and quality regressions

| Repository | Tasks | Native input | AtMem input | Native full passes | AtMem full passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seaborn | 4 | 1,116,030 | 785,882 | 3 | 2 |
| Flask | 4 | 490,526 | 753,486 | 2 | 3 |
| Xarray | 4 | 1,517,850 | 731,912 | 0 | 1 |
| Pylint | 4 | 1,308,307 | 1,012,725 | 3 | 1 |
| PyVista | 3 | 677,724 | 485,874 | 0 | 0 |

Five pairs pass in both arms, three only natively, two only with AtMem and nine
in neither. Native-only outcomes are Seaborn-3069, Pylint-6358 and Pylint-6517;
AtMem-only outcomes are Flask-4544 and Xarray-3095. These identify differences
to investigate, not their cause. Zero completed Code MCP calls again prevents
claiming routine on-demand retrieval use or a graph-specific causal effect.

The issue-cluster 95% token-saving sensitivity interval is [0.890%, 44.725%];
the repository-cluster interval is [-4.836%, 43.508%], with only five repository
clusters. Task-pass-rate difference intervals are respectively [-26.316, 15.789]
and [-31.579, 21.053] percentage points. These are paired percentile sensitivity
analyses, not proof of generalization or statistical noninferiority. Omitting
Xarray-3095 lowers the observed saving to 17.636%; that is a fragility diagnostic,
not permission to exclude a case or substitute a different denominator.

## Frozen design and provenance

All nineteen original v3/CD1 identities, one fresh native/candidate pair each;
38 total attempts with fresh scopes, workspaces, DBs and CLI homes. The fixed
SHA-256 identity ordering seed and alternating arm order are defined in
`specs/042-atmem-code/query-nomination-development-screen-v1.md`. CLI/model,
600-second / 100-tool caps, 4,096-byte initial pack, native/public-test tools,
private graders and one model worker remain unchanged. All 38 actual MCP and
sandbox controls and descendant containment pass before the exact execution
lock. Grading uses two workers only after all 38 model captures are terminal.

The unpublished wheel is
`c3e6bb211082b6f962869ed4a60945cb3c90d99c784ce7629d423045b8190326`.
Only packing.py differs from the original full frozen e8d98dad source job;
candidate source is
`004a4ff9f66843206456f28d2bd08b59c09196ecee16c88a25b51dc85fa62020`.
The added changes are bounded generic heading weighting, syntactic-call
recognition and authorized source-URL line nomination. All nineteen installed
packs match the complete Mac archive-only static replay; five fresh real-source
scope/storage/freshness/audit/bundle/MCP controls also pass. These prerequisites
do not prove the fixes caused the aggregate saving.

Authoritative comparison root:
`external-windows-query-nomination-development-comparison-v1-20261018`,
event `external.v3_comparison_completed`. Its complete authenticated event is
retained on Mac under the result-import root, alongside the original SSH
transport; all 38 per-attempt rows and uncertainty resamples remain protected.
The original model and postprocessing execution exits zero; all 38 actual
public-vault recoveries complete. No model or private-grade outcome is rerun.

CD1's 9.317165272% saving / 6 versus 6 passes and v3's 5.299941045% saving /
12 versus 13 passes remain unchanged. Different native runs vary materially;
subtracting their percentages does not measure the causal effect of these
three corrections. No favorable subset or old native result replaces CD2.

## Recovery and next gate

The archive waiter is live and retains the original full helper sources before
export. Exact-path MEM transfer and standalone Mac recovery are implemented and
tested, but not yet verified for CD2. Keys stay internal. T098 remains open for
full independent recovery; T062 remains open because the combined requirement
fails and untouched confirmation is absent. Before selecting another candidate,
inspect every recovered trace and all discordant pairs, distinguish navigation
and patch failures from stochastic variation, and preserve this negative result.

Independent recovery subsequently completes successfully: **310 runs, 1,597
events, 152 full streams, 38 candidates, 38 private grades and 38 public vaults**.
The fresh reader verifies all 38 original requests, including six chunked
requests and 401,073,882 canonical dispatch bytes. Original-vault access is
denied, models_repeated=0 and model_or_grade_retries=0. Collection SHA-256:
`6462f65d591f2b8a186e6d743bfb67aa676836de2856e13ec55f09d86842e247`.

Archive:
`/Volumes/MEM/AtMem-Code-Replay-20261017/query-nomination-development-protected-20261018`.
Private keys remain under the separate internal benchmark directory, never MEM.
The transfer/recovery proof is retained in
`external-windows-query-nomination-development-MEM-transfer-v1-20261018`.
T098 closes as completed execution with a failed combined efficacy gate; T062
and the overall goal remain open unchanged. Next is T099's archive-only all-case
diagnostic, not an unchanged-candidate rerun or favorable-subset comparison.

## Archive-only descriptive diagnostic

The separate CD2 reader reuses the prior all-case audit functions against this
recovered collection. It verifies every original CLI usage receipt against the
completed comparison, reads all 38 traces, and opens no operational vault.
Its protected result is
`external-windows-query-nomination-development-trace-audit-v1-20261018`.

| Descriptive measure | Native | AtMem structure |
| --- | ---: | ---: |
| Shell commands, all kinds | 165 | 134 |
| Returned shell UTF-8 bytes | 621,432 | 454,990 |
| Exactly duplicated output bytes, outputs >=1 KB | 9,332 | 0 |
| Completed Code MCP calls | 0 | 0 |
| Attempts with nontrivial initial-pack text also returned by shell | N/A | 10/19 |
| Summed distinct matching source-text bytes per attempt | N/A | 7,961 |

These are descriptive byte/command proxies, not token attribution, attention,
same-file redundancy, waste or causality. Fewer commands/returned bytes coexist
with one fewer full pass; the aggregate cannot establish why the patches fail.

The full comparison further shows that **all five discordant pairs pass source
authority and their declared preservation checks**. The three AtMem-only losses
are target-fix failures, not scope/governance refusals: Seaborn-3069 fixes 0/2
target checks, Pylint-6358 fixes 0/1 and Pylint-6517 fixes 0/1, while their native
counterparts fix all. Conversely, AtMem fixes the target in Flask-4544 and
Xarray-3095 where native does not. This classifies outcomes, not causes, and
does not justify bypassing governance or changing test/acceptance policy.
T099 remains open for direct discordant-trace/patch inspection and checking any
proposed mechanism across the remaining cohort before another product change.
