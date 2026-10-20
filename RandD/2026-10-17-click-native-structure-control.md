# Click: no memory versus current structural context

Fresh matched follow-up: five authentic historical tasks, one A/C pair each. Experience disabled in both.
Installed local preview (wheel metadata 2.3.8), not the public stable 2.3.8 artifact. Explicit benchmark integration, not normal Codex hooks.

| Measure | No structure/experience (A) | Structure only (C) |
| --- | ---: | ---: |
| All-test and run-budget passes / 5 | 4 | 4 |
| Functional default-suite passes / 5 | 5 | 4 |
| Infrastructure-invalid attempts | 0 | 0 |
| Median solver seconds | 23.64 | 23.59 |
| Median setup seconds | 1.34 | 1.91 |
| Median indexing seconds | 0.0 | 3.35 |
| Median context-planning seconds | 0.0 | 3.94 |
| Median measured path seconds (setup + index + context + solver) | 24.97 | 32.75 |
| Tool calls, total | 51 | 46 |
| Additional context bytes, total | 0 | 10858 |
| Completed usage receipts / 5 | 5 | 5 |
| Total input tokens (includes cached) | 1210665 | 976968 |
| Cached input tokens | 1106688 | 908544 |
| Total output tokens | 8737 | 6422 |

Measured path excludes protected-evidence I/O and grading; it is not complete request wall time. Each C snapshot is cold-indexed in a fresh database, not an amortized warm-service estimate.
Usage missing after a killed attempt is unknown, never zero. Cached tokens are a subset of input. Billing and remaining subscription quota are unknown; no API/GPU dispatch.

| Task | A result | C result | A solver s | C solver s | C context bytes |
| --- | --- | --- | ---: | ---: | ---: |
| b67832c | token_budget | passed | 51.63 | 22.25 | 3089 |
| 9c4dfda | passed | passed | 22.12 | 23.29 | 1628 |
| 150d107 | passed | passed | 21.49 | 25.14 | 2541 |
| fc5c7f4 | passed | checks_failed | 28.45 | 23.59 | 1562 |
| e1fd594 | passed | passed | 23.64 | 23.70 | 2038 |

Paired all-budget results: A_only=1, C_only=1, both_pass=3, neither_pass=0.

## Failures and interpretation

- click-ac-v3q-a-t1: token_budget; functional pass=True; grader summary={"deselected": 31001, "passed": 1868, "skipped": 25}; patch violations=[].
- click-ac-v3q-c-t4: checks_failed; functional pass=False; grader summary={"deselected": 31001, "failed": 1, "passed": 1967, "skipped": 25}; patch violations=[].

The comparison measures this fixed structural context pack versus native exploration. Both arms have ordinary source/search/Git/test tools; A has no AtMem context or memory tools. No prior experience reaches either arm.
The same five targets were inspected in the earlier C/D pilot. This follow-up uses corrected native Git/config isolation and fresh 2 GiB scratch in both arms; old results are not pooled or treated as matched controls.
AC/CA/AC/CA/AC partially alternates order; it does not fully balance position or provider drift. Five public tasks with one pair each cannot establish general superiority or significance. Public pretraining familiarity remains possible.
Model: subscription gpt-6-luna alias, low effort; CLI 0.162.1. The alias is not an immutable model-weight pin. Caps: 180s, 24 tool calls, 8192 extra context bytes, 500000 tokens audited after completion rather than provider-enforced. All attempts retained; no adaptive solve retries.
Exact declared prompts, contexts, patches, CLI events and hidden grades are retained in protected evidence. These are not independently observed full system/model inputs or a complete Agent Black Box.

Protocol SHA-256: `1143c194e0e02cacef5071828eaa7410a6e1dcae0d0e286d10cb46107dc14560`.
Frozen manifest: `/Volumes/MEM/AtMem-Code-Replay-20261017/click-ac-frozen-v3-qualified.json`.
Preflight attrition: the initial v3 package stopped before any solver dispatch because Xcode Git was outside the allocator's Command Line Tools-only allowlist. That failure and original manifest are retained; the qualified package explicitly permits the tested native Xcode Git binary. No model attempt was retried.


## Outcome and verification

The no-memory control solved all five tasks according to the frozen default test suite. Structure solved four. Both have four all-budget passes because the native task-1 run used 574,875 input plus 3,142 output tokens, exceeding the 500,000 audit threshold despite correct code.

Structure used 19.3% fewer total input tokens across these five attempts, including cached input, and 46 rather than 51 tool calls. It did not improve correctness. Median measured path time was 32.75s versus 24.97s; cold preparation outweighs the essentially identical median solver time. These measurements do not demonstrate a net user benefit from this structural pack.

Task legend: b67832c—help-name collision; 9c4dfda—help ordering; 150d107—progress final position; fc5c7f4—pager exception cleanup; e1fd594—PathLike editor input.

The structure task-4 failure is `test_tempfile_pager_closes_file_before_unlink`. Inspection of the retained patch shows that it closes the file in a first try/finally, then puts unlink in a second try/finally. If writing raises, the exception skips the second block, leaving the temporary file unremoved. This is a bounded cleanup error in that attempt, not proof that structural context caused it.

“Default suite” preserves the parent project's `-m 'not stress'` configuration: 31,000 stress cases are deselected upstream, plus the one frozen literal-/tmp case required by the sandbox. Counts of 31,001 deselections are genuine grader output, not 31,001 executed tests or a formatting artifact. Each task also reports its skips/expected failures. No tests were removed after seeing these outcomes.

Eleven recipient-encrypted archives were verified against exact vault events at `/Volumes/MEM/AtMem-Code-Replay-20261017/protected-results-ac-v3`. Private keys remain internal in the benchmark home; they are not on MEM. After ejecting the task-owned RAM volume (disposing of temporary solver homes/workspaces), a new process recovered 34 events and all ten terminal trials from archives and keys alone, without opening the vault. The task-started extraction VM was stopped. MEM remains mounted and was used only for the benchmark.

Verification: 90 replay tests and eight spec-task inventory checks pass; `git diff --check` passes. CI definition includes the new no-inference tests, but no remote CI result is claimed. Work stays on `feature/atmem-code-2.3.9`; no release, commit or push was made for this follow-up.

