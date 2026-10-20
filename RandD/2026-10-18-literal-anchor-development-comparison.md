# Literal-anchor structural-context screen (CD3)

## Result: both token and quality gates fail

The complete nineteen-pair comparison uses **25.899131635% more TOTAL input
tokens** with AtMem structure. Full-task passes are **5/19**, versus native
tools' **8/19**. Neither the 50% target nor the exact 20% fallback is met; the
equal-or-better quality requirement also fails. Preserve this negative result.
This is reused-task development evidence, not untouched confirmation or a
completed efficiency goal. Do not promote this candidate or start confirmation.

| Metric | Native tools | AtMem structure preview |
| --- | ---: | ---: |
| Attempts / normal usage receipts / grades | 19 / 19 / 19 | 19 / 19 / 19 |
| Full tasks passed, including source authority | 8/19 | 5/19 |
| TOTAL input tokens, including cached input | 4,081,577 | 5,138,670 |
| Cached input tokens | 3,650,944 | 4,687,616 |
| Uncached input tokens | 430,633 | 451,054 |
| Output tokens | 24,575 | 26,947 |
| Solver latency p50 | 28.517 s | 30.352 s |
| Solver latency p95 | 46.623 s | 65.746 s |
| Solver latency mean | 30.202 s | 34.670 s |
| Cold preparation latency mean | 0.467 s | 18.191 s |
| Mean preparation + solver, not full end-to-end | 30.669 s | 52.861 s |
| Supervisor elapsed mean, separate component | 31.115 s | 36.771 s |
| Source-policy violations | 2 | 1 |
| Completed Code MCP calls | 0 | 2 |
| Completed public-test calls | 20 | 18 |
| Fix-check successes / failures | 10 / 15 | 7 / 18 |
| Preservation-check successes / failures | 1,821 / 22 | 1,826 / 17 |

All 38 normal usage receipts and grades are available, with no supervisor stop,
missing-as-zero usage or task exclusion. Partial checks are not independent
tasks. Preparation/solver sums are displayed components, not a measured user
end-to-end path; no warm-cache benefit or installed-workflow speedup is claimed.

## Every repository

| Repository | Tasks | Native input | AtMem input | Native passes | AtMem passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seaborn | 4 | 698,330 | 1,073,941 | 1 | 2 |
| Flask | 4 | 508,752 | 677,842 | 3 | 2 |
| Xarray | 4 | 1,104,669 | 1,472,134 | 2 | 1 |
| Pylint | 4 | 1,158,588 | 1,361,371 | 2 | 0 |
| PyVista | 3 | 611,238 | 553,382 | 0 | 0 |

Four pairs pass in both arms, four only natively, one only with AtMem and ten
in neither. Native-only: Flask-4642, Xarray-3812, Pylint-6358 and Pylint-7277.
AtMem-only: Seaborn-2946. AtMem's Pylint-7277 passes the test checks but fails
source authority; it cannot be counted as a full task pass. The other three
native-only cases pass source authority in both arms but AtMem fails target
checks. These classify outcomes, not causes; no governance bypass follows.

The nineteen-issue 95% token-reduction sensitivity interval is
[-56.441%, 4.733%]; the five-repository interval is [-41.402%, -10.486%].
Negative reduction means more input. Task-pass difference intervals are
[-36.842, 5.263] and [-36.842, 6.250] percentage points respectively. The
predeclared 10,000-resample paired cluster analysis is sensitivity evidence,
not generalization, equivalence or a component-specific causal effect.

## Frozen design and actual prerequisites

Protocol: `specs/042-atmem-code/literal-anchor-development-screen-v1.md`.
All nineteen original issues receive one fresh native/candidate pair, with
fresh workspaces, DBs, CLI homes and balanced seeded order. Luna-low subscription
CLI, source tools, 4,096-byte pack, 600-second/100-tool limits, one model worker
and nineteen private graders remain fixed. All nineteen stages, 38 actual MCP
controls, 38 sandbox controls, containment and exact source/grader locks pass.
All 38 model captures become terminal before private grading begins.

Unpublished wheel:
`3b56928a20c07fdbddcca64167ad19efdb80db396e41637d5e837b9e9958ad65`.
Candidate packing.py:
`2d8b53e65f4b3c06628e191bb083ba95064f9fd51d5578c915ba424d68938a97`.
The one-file product delta adds bounded static literal nomination and explicit
name precedence over conflicting revision-unverified line hints. All nineteen
installed packs reproduce and five fresh source/scope/freshness/audit/encrypted
bundle/MCP controls qualify. Static localization does not establish benefit.

Both arms also receive the same exact selector-only repair in their public
server and sandbox worker. All 38 archived programs pass exact-delta checks.
Fresh actual source/traversal denial and nested-node candidate probes pass;
an additional unchanged Xarray-3812 test run returns 16 passed, one expected
failure, while its nested canary patch returns three passed. This fixes a real
infrastructure defect, not the model's repair reasoning. Other public-feedback
failures remain visible. The two-arm design cannot isolate product and common
public-selector effects; different fresh native runs also vary substantially.
Do not interpret CD2-to-CD3 percentage subtraction as a causal effect.

## Provenance, recovery and next gate

Authoritative comparison:
`external-windows-literal-anchor-development-comparison-v1-20261018`, event
`external.v3_comparison_completed`. Complete original envelope and SSH transport
are retained on Mac under
`external-windows-literal-anchor-development-result-import-v1-20261018`.
Original execution exits zero with all 38 public-vault recoveries completed.
No model or private-grade outcome is repeated. Raw rows and analysis remain
protected and inspectable through AtMem's authorized application boundary.

The archive waiter is live; independent encrypted MEM export/transfer/recovery
is still required before T104 execution can close. A successful archive will
not turn this efficacy failure into success. T062 remains open. Preserve all
previous comparisons and inspect the complete recovered cohort before another
product change or scored study. No unchanged-candidate retry or favorable subset.

T105 separately freezes forty metadata-only candidates across five untouched
catalog repository groups before inspecting this result. All metadata verifies,
but no environment is qualified and no confirmation model runs. Because CD3
fails, T106/T107 remain conditional and are not dispatched for this candidate.

Owner stop instruction: finish collecting and independently verifying this
existing evidence, then stop. No subsequent diagnostic, product change,
training or scored benchmark is authorized to continue under this run. Record
the final recovery proof and pause the active goal; do not mark it achieved.

## Final independent recovery and owner-requested stop

Both exact-path copies exit zero. A separate fresh Mac process recovers
**311 runs, 1,601 events, 152 complete streams and all 38 candidates, private
grades and public vaults**. All **38 original grading requests** verify,
including six chunked requests and **401,072,082 canonical dispatch bytes**.
Original-vault access is disabled; models repeated = 0 and model/grade retries
= 0. Collection SHA-256:
`714efebda0662caf0f0cce730de4ec57d8494185679ff2d72e5f4df9cd78dbbc`.

Archive:
`/Volumes/MEM/AtMem-Code-Replay-20261017/literal-anchor-development-protected-20261018`.
Keys remain in the separate internal benchmark directory, not MEM. The complete
copy/standalone-reader proof is retained under
`external-windows-literal-anchor-development-MEM-transfer-v1-20261018`, event
`external.query_nomination_MEM_recovery_completed`. Frozen comparison fields
are not rewritten; this subsequent proof supplies archive verification.
Referenced external runtime images are not claimed to be included in the archive.

T104 is complete as execution/evidence collection with a failed efficacy gate.
The original execution, export, observer, result import and transfer/recovery
processes are terminal. The stale read-only SSH observer is closed. Stop at the
owner's requested boundary; no new diagnostic, product change, model training,
benchmark or confirmation is started. The overall efficiency goal remains
unachieved and is paused at the owner's request.
