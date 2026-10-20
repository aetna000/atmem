# Corrective structural-context screen (CD1)

## Result

The corrective preview does **not** meet the fixed 20% TOTAL-input-token
fallback. Its 19 matched tasks use 9.317165272% fewer input tokens with six full
passes in each arm. These are reused development issues, not fresh confirmation.
The original v3 confirmation's 5.299941045% saving and 12/38 native versus 13/38
AtMem passes remain unchanged. Do not compare those old controls directly with
CD1's candidate or call the difference a measured effect of this correction.

| Metric | Native tools | AtMem structure |
| --- | ---: | ---: |
| Attempts / complete usage receipts / grades | 19 / 19 / 19 | 19 / 19 / 19 |
| Full tasks passed (tests and source-policy compliance) | 6/19 | 6/19 |
| TOTAL input tokens, including cached input | 3,914,549 | 3,549,824 |
| Uncached input tokens | 346,933 | 310,912 |
| Output tokens | 23,201 | 24,168 |
| Solver latency p50 | 23.130 s | 21.269 s |
| Solver latency p95 | 50.295 s | 46.312 s |
| Solver latency mean | 26.813 s | 29.679 s |
| Preparation latency mean | 0.467 s | 17.777 s |
| Mean preparation + solver time (not full end-to-end latency) | 27.280 s | 47.456 s |
| Source-policy violations | 2 | 1 |
| Completed Code MCP calls | 0 | 1 |
| Observed fix-check successes / failures | 8 / 17 | 9 / 16 |
| Observed preservation-check successes / failures | 1,752 / 91 | 1,842 / 1 |

The lower solver median does not establish lower user-experienced latency.
AtMem preparation is materially slower, and its long Xarray-3095 attempt raises
its mean. Preparation, solver and supervisor are separate recorded components;
this table does not claim a warm-cache or ordinary interactive-install latency.
Partial test counts are not independent task outcomes.

## Every repository, including regressions

| Repository | Tasks | Native input | AtMem input | Native full passes | AtMem full passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seaborn | 4 | 888,370 | 645,483 | 2 | 3 |
| Flask | 4 | 640,662 | 601,408 | 2 | 2 |
| Xarray | 4 | 852,575 | 981,980 | 1 | 0 |
| Pylint | 4 | 849,712 | 764,834 | 1 | 1 |
| PyVista | 3 | 683,230 | 556,119 | 0 | 0 |

Four tasks pass in both arms, two only with AtMem, two only with native tools,
and eleven in neither. Equal aggregate pass counts are not equivalence evidence.
The issue-cluster percentile sensitivity interval for token saving is
[-9.009%, 24.437%]; repository clustering gives [-5.132%, 22.407%], with only
five repository clusters. The corresponding task-rate difference intervals are
[-21.053, 21.053] and [-15, 15] percentage points. These are sensitivity analyses,
not proof of generalization, noninferiority or causality.

## Frozen design and provenance

Nineteen original v3 issue identities, one fresh native/corrective pair each;
38 total attempts, unchanged low-effort model/CLI, public/private tests,
4,096-byte initial source budget, 600-second/100-tool caps and one model worker.
All 38 actual MCP/sandbox controls qualified before inference. The corrective
wheel is `f1f92fe34f2d4c5ed2413ad6445cfdeb54fbb616cdba7f91777487189dcab7a2`;
only `packing.py` differs from the frozen compatibility baseline. Its digest is
`159e4b0f1c52c3bd0752d38ddaa5e2764927b4daa39adc400baeaeddb2d85042`.

The change fixes compound-name false matches, symbol-type ownership and observed
Python import-alias nomination. Those are tested generic localization fixes,
not a demonstrated >=20% efficiency improvement. Only one completed Code MCP
call appears in the tools arm; the graph's availability does not demonstrate
routine progressive use. Low uptake and initial-pack relevance remain diagnostic
hypotheses, not experimentally isolated causes.

Authoritative report:
`external-windows-corrective-development-comparison-v1-20261018`,
`external.v3_comparison_completed` (2026-10-18T05:48:04.007140Z).
Its protected payload retains all 38 per-attempt rows, usage, trace summaries,
grades and sensitivity calculations. No model or private-grade outcome was
rerun. After SSH loss, 14 missing parent summaries were reconstructed from
already-retained private results, comparing the existing 24 exactly first.
All 38 private results and actual public-evidence recoveries are terminal.

## Evidence packaging and remaining work

The original export stops
after its plan with both destination directories empty; retained helper modules
are absent from the remote operator installation. A guarded export-only recovery
loads the exact retained helpers and preserves the original 332-run membership.
No partial files may be overwritten and no model/private test is executed.

The guarded export subsequently completes all 332 members. The recovery transfer
verifies the retained archive/grader reader digests before copying; encrypted
archives go only to MEM and key exports only to the internal benchmark directory.
The transfer and independent recovery subsequently finish successfully. The complete
local replay/knowledge regression group passes 696 checks in 38.68 seconds;
the overlapping corrective/specification group passes 45. Recovery modules also
pass Python 3.10 grammar checks. CI configuration includes the new gates; no
remote CI run is claimed.

Independent recovery verifies 332 runs, 1,660 events, 152 full streams, all 38
candidates, private grades and public vaults. The archive-only original-request
audit verifies all 38 requests, six chunked, totaling 401,072,102 canonical bytes,
against the original frozen grader, source and stopped candidate. Original
vaults are not opened; zero models or private grades are repeated.
Authenticated collection digest:
`c46f9d9cf5cf792882b92c6533deb50815cff75ba5943629db403a2b6938c6d7`.

Encrypted archive:
`/Volumes/MEM/AtMem-Code-Replay-20261017/corrective-development-protected-20261018`.
Key exports remain in the separate internal benchmark directory, not MEM.
Local recovery evidence:
`external-windows-corrective-development-MEM-transfer-recovery-v1-20261018`,
`external.v3_MEM_recovery_completed`.
T092 is complete as execution/report/recovery, not efficiency acceptance.

## All-case archive-only trace diagnostic

T093 independently reads all 38 original model exchanges from the recovered
archive, with operational-vault access disabled in the reader. Every original
normal usage receipt matches its comparison row; no inference, grading or
product change occurs. Protected derived records are retained under
`external-windows-corrective-development-trace-audit-v1-20261018`.

| Descriptive trace measure | Native | AtMem structure |
| --- | ---: | ---: |
| Shell commands (all kinds, not exclusively source browsing) | 141 | 120 |
| Shell-command returned UTF-8 bytes | 601,343 | 419,303 |
| Exactly repeated output bytes, outputs >=1 KB | 9,795 | 5,602 |
| Completed agent-message items | 77 | 70 |
| Completed Code MCP calls | 0 | 1 |
| Attempts with nontrivial initial-pack text also returned by shell commands | N/A | 9/19 |

The tools arm has fewer shell commands and fewer returned bytes, but those
are not model-token measurements or proof of a causal exploration benefit.
Some commands edit or test code. The initial-pack overlap sums to 7,175
per-attempt distinct matching UTF-8 line bytes, after display-line-number
normalization and excluding short boilerplate. Matching text does not prove
same-file rereading, waste or model attention; inspecting fuller source can be
necessary before editing. Only one Code MCP call means availability alone has
not established routine progressive retrieval. Eleven overlapping new-audit/
original-audit/spec-inventory fixtures pass. T093 is complete as a descriptive
diagnostic; the 20% target remains unmet.

T062 and the overall efficiency goal remain open. Do not launch another scored
iteration merely to search for a favorable draw: first establish a generic,
independently testable product change and prospective protocol. Any selected
candidate requires fresh confirmation; CD1 cannot serve that role.
