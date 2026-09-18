# Local validation — 2026-09-14

AtMem branch: `benchmark`, based on
`00f36abe0381edcb6040de2d17b491bdbb19791f`.
Upstream MemoryBench: `94e2af54b661d90e77dddbd8fa4fa5b28c07a24e` plus this overlay.
Python 3.12; Bun 1.4.2. No live AtMem data/configuration was used or modified.

| Gate | Observed result |
| --- | --- |
| Focused Python adapter, benchmark and semantic suites | 60 passed |
| Upstream Bun provider lifecycle test | 1 passed, 5 assertions |
| Upstream TypeScript `tsc --noEmit` | Passed |
| Provider registry and CLI help | `atmem` available |
| Overlay installer repeated invocation | Passed (idempotent) |
| Public LoCoMo corpus smoke | 19 sessions, 49 admitted chunks; context returned for all 5 queries |
| OpenAI-scored evaluation | Not run: credential unavailable |
| Upstream submission / leaderboard acceptance | Not submitted |

LoCoMo source: upstream's download of
`https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json`.
SHA-256: `79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4`.
Questions: `conv-26-q0` through `conv-26-q4`, original order. Only conversation
sessions entered ingestion, not question reference answers.

Diagnostic hashing smoke observed 777 ms ingestion/indexing and query times
309, 313, 316, 314 and 314 ms, including Python subprocess startup. These are
single-run local plumbing observations, **not** OpenAI latency estimates,
accuracy measurements or competitive performance claims. Returned context
was checked for presence, not answer correctness. No paid API calls were made.

See README for the OpenAI pilot and honest publication requirements. The
OpenAI documentation skill guided use of the existing official-endpoint
embedding adapter; no AtBot or local generative model was introduced.
