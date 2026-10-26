# Dolphin fixed 20-task pilot — final report

**Outcome: complete and independently validated. 20/20 tasks executed and graded; 13/20 passed (65%), 7 failed.** The readiness workflow passed its declared checks. This does not mean all 20 domain tasks passed.

- Goal: verify isolated simulated-app routing, persisted writes, independent evidence, safe crash recovery and unchanged scientific configuration before considering another 600-task run.
- AtSys task: `task-fde52452-dc80-484c-875c-2e732bb6d5e2`; completed at `2026-10-26T04:46:03.636Z`.
- Selected original result: 3/20 passed. New diagnostic: 13/20 passed, with **10 recovered failures and zero control regressions**.
- All three original passing controls still pass. Nineteen tasks have independently recorded app activity; one retained fixture has none. A trace is not proof of semantic correctness.
- Full 600: **not launched**. Original published score remains **390/600 (65%)**. Conditional 390/517 = 75.4% remains a diagnostic, not a corrected score or projection.

## What changed and what was verified

The profile excludes unsupported local-app skills and routes actions through the benchmark's simulated application tools. Memory, retrieval, reader/judge routes and fixture checks remained frozen. Qualification exercised actual synthetic app writes, persisted state, independent logs and an intentional crash with zero model calls. It also captured the actual model-visible tool profile.

Recovery fixed numeric JSON representation comparison, standalone SQLite publication to ExFAT, and recovery run identity initialization. The supervisor diagnosed and repaired harness issues within bounded scope. MEM physically disconnected during acceptance; macOS checked and remounted it, its UUID was verified, and the original image was restored read-only before continuation. **194 implementation tests and actual retained task129 offline reconstruction passed.** Original completed executions/grades were reused; task129 was reconstructed from retained evidence without replaying bookings. Independent final validation checked all selected IDs, full original checks, app evidence, accounting and the handoff artifact.

## Cohort results

| Original cohort | Tasks | Now pass | Recovered failures |
|---|---:|---:|---:|
| pass | 3 | 3 | 0 |
| traced partial | 2 | 0 | 0 |
| traced zero | 3 | 1 | 1 |
| untraced zero | 12 | 9 | 9 |

The strongest measured improvement is in the originally untraced cohort: 9 of 12 now pass. Neither of the two partial-success cases recovered. These findings justify further inspection; they do not assign a retrieval/execution cause to every remaining failure.

## Per-task outcomes

| Task | Result | Checks passed | Independent trace | Original cohort |
|---|---|---:|---|---|
| alex/102 | PASS | 5/5 | yes | untraced zero |
| alex/120 | PASS | 2/2 | yes | untraced zero |
| alex/132 | PASS | 2/2 | yes | untraced zero |
| alex/139 | FAIL | 1/5 | yes | traced partial |
| morgan/023 | FAIL | 0/3 | yes | traced zero |
| morgan/085 | FAIL | 0/3 | yes | traced zero |
| morgan/129 | PASS | 4/4 | yes | untraced zero |
| morgan/130 | FAIL | 0/3 | no | untraced zero |
| morgan/152 | FAIL | 0/3 | yes | untraced zero |
| morgan/157 | PASS | 2/2 | yes | untraced zero |
| morgan/162 | FAIL | 0/2 | yes | untraced zero |
| morgan/172 | PASS | 3/3 | yes | untraced zero |
| morgan/180 | PASS | 2/2 | yes | pass |
| riley/009 | PASS | 2/2 | yes | untraced zero |
| riley/019 | PASS | 2/2 | yes | pass |
| riley/037 | PASS | 5/5 | yes | pass |
| riley/069 | PASS | 2/2 | yes | untraced zero |
| riley/095 | PASS | 5/5 | yes | traced zero |
| riley/125 | PASS | 2/2 | yes | untraced zero |
| riley/156 | FAIL | 2/6 | yes | traced partial |

## What still failed

Seven failures remain: alex/139, morgan/023, morgan/085, morgan/130, morgan/152, morgan/162 and riley/156.

- morgan/085 and morgan/130 are the documented send-email and Slack-DM fixture limitations; both remain in the denominator. The fixture was not patched to force success.
- morgan/023 sent an acceptance where the criterion required declining a non-urgent Friday vendor call. This is a content/policy outcome failure despite an app trace.
- morgan/162 created a note, but the checked text omitted the required strongly positive team response.
- riley/156 created brunch content without the required Salud venue; it passed two checks and failed others.
- alex/139 and morgan/152 still require transcript-level cause analysis. No retrieval cause is claimed from checks/trace alone.

## Frozen routes, costs and latency

- AtMem: published 2.3.10b1; deterministic storage, local memory/indexes and source-coherent retrieval; original frozen memory retained.
- Embedding: local Ollama nomic-embed-text with pinned digest; no paid embedding or reranker.
- Reader: gpt-5.6-luna, high reasoning, existing ChatGPT subscription through Hermes.
- Judge: gpt-5.6-sol, medium reasoning, max 8000 completion tokens, JSON, Azure-only through OpenRouter, no fallback.
- Recorded cumulative benchmark API spend: **USD 0.083317**, under the USD10 pilot cap. Ledger reports 85 reader calls and 17 judge calls, with zero outstanding reservations or uncertain calls. Reader incremental API cash is zero on the subscription route; subscription/compute are not free. Supervisor/review subscription usage is separate and not priced by this ledger.
- Median recorded task duration: **29.55 seconds**. The recovered129 duration excludes controller overhead; this is not a clean latency comparison to the published600.

## Limitations and conclusion

The 20 tasks were selected after inspecting the published results. This is a diagnostic, not a holdout or official submission. It spans three harness revisions through explicitly recorded recovery, with scientific configuration unchanged. The original report's `self_tested_unverified` and `official_submission:false` labels remain intact: AtSys independent validation means a separate local acceptance process, not external benchmark reproduction.

**Conclusion:** the isolated execution profile recovered 10 known failures while preserving the three passing controls. The pilot is accepted as a readiness diagnostic, not proof of a new600 score. Before the next full run, inspect the five non-fixture failures, confirm stable storage, freeze one final qualified harness/configuration and obtain the owner's explicit full600 authorization. Keep remaining failures and known fixture limits visible; do not reroll controls or infer 75.4%.

## Evidence

- Machine report: `/Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot20-recovered-20261026-6f7753bf37b73a6fa08b/pilot-report.json`
- Validated handoff: `/Users/javadtaghia/gitlab/atmem-dolphin-execution-audit-20261025/specs/048-dolphin-execution-readiness/atsys/pilot20-recovered-handoff.json`
- Handoff SHA-256 recorded by the independent validator: `14053f1dc6c0e67ae791392010d6174556d2f71eb964ebf4e6ce5465cb294c2a`
- Exact frozen condition and qualification receipts: `~/.local/share/atmem-dolphin-readiness-20261026/parent-recovery-v2/launch-00002.json`
- AtSys task/attempt/validation history: `http://127.0.0.1:4311/tasks/task-fde52452-dc80-484c-875c-2e732bb6d5e2`

Generated from retained report/handoff and the persisted validator receipt; no new model calls, grading or task actions.
