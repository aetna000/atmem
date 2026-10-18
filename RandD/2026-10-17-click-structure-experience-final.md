# Click structure versus structure + experience

Reduced historical pilot; installed local preview, not a published release or general superiority result.
Benchmark integration through product services, not normal Codex automatic hooks. Two five-task trajectories per arm.

| Measure | Structure (C) | Structure + experience (D) |
| --- | ---: | ---: |
| Planned attempts | 10 | 10 |
| Completed attempts | 10 | 10 |
| All-check passes | 7 | 6 |
| Failed attempts | 3 | 4 |
| Infrastructure-invalid | 0 | 0 |
| Missing attempts | 0 | 0 |
| Median solver seconds | 34.59 | 23.73 |
| Sample p95 solver seconds | 66.32 | 64.56 |
| Median context-planning seconds | 2.16 | 2.52 |
| Sample p95 context-planning seconds | 2.76 | 3.44 |
| Median measured product/setup overhead seconds | 4.9 | 5.55 |
| Summed measured stage seconds, excluding grading/evidence I/O | 413.42 | 367.11 |
| Input tokens, including cached | unknown | unknown |
| Cached input tokens | unknown | unknown |
| Output tokens | unknown | unknown |
| Prior memory records submitted | 0 | 0 |
| Attempts with completed usage receipts | 9 | 8 |
| Observed input-token subtotal, incomplete coverage | 2155680 | 1246684 |
| Observed output-token subtotal, incomplete coverage | 16512 | 9862 |
| Experience candidates | 0 | 8 |
| Admitted observations | 0 | 8 |

Billing and remaining subscription quota are unknown; no API/GPU dispatch was used. Cached tokens are a subset of input, not extra tokens.
Sample p95 uses nearest rank on at most ten observations per arm; it is not a production tail-latency estimate. Summed stage timing omits uninstrumented protected-evidence I/O and is not complete request wall time.

| Rep | Task | C | D | C solver s | D solver s | D prior memories |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 1 | click-b67832c | failed | failed | 66.32 | 60.14 | 0 |
| 1 | click-9c4dfda | passed | passed | 34.35 | 22.99 | 0 |
| 1 | click-150d107 | failed | failed | 24.42 | 28.01 | 0 |
| 1 | click-fc5c7f4 | passed | passed | 27.32 | 17.39 | 0 |
| 1 | click-e1fd594 | passed | passed | 34.82 | 33.4 | 0 |
| 2 | click-b67832c | failed | failed | 46.34 | 64.56 | 0 |
| 2 | click-9c4dfda | passed | passed | 43.86 | 21.18 | 0 |
| 2 | click-150d107 | passed | failed | 23.4 | 14.89 | 0 |
| 2 | click-fc5c7f4 | passed | passed | 40.24 | 23.44 | 0 |
| 2 | click-e1fd594 | passed | passed | 20.65 | 24.02 | 0 |

## Interpretation

Task 1 is cold in each trajectory; later tasks use only their own earlier attempts.
No hidden grade is fed into memory. Stored attempt reports have unknown outcome unless separately verified.
Whole-file anchor freshness is conservative; a changed file can withhold a still-useful lesson.
Operational constraints: some agent reports record denied ambient Git configuration reads. The final D attempt of repetition 1 also reports scratch exhaustion during its public test run, before the later staging failure. Hidden grades ran separately, but these conditions limit ordinary-user latency/quality interpretation. Future-only Git-environment normalization is not retroactively counted as tested in these attempts.
Applicability reason counts: {"ANCHOR_CHANGED_OR_MISSING": 12}.
Paired context byte-digests identical: 10/10 completed C/D pairs (not a claim about the unobserved full model input).
Five public historical tasks and two trajectories do not establish population-level benefit; provider drift and pretraining familiarity remain possible.
CLI prompt/tool streams are retained as declared events, not complete independently observed model/system input.

Protocol SHA-256: `c18f4802c426e316b0a5ca1f58a61188755f61fd92cdd179c106a1a988959d1d`.

No earlier memory reached D in these observed attempts. Any quality/timing difference therefore cannot be attributed to useful recalled experience.
