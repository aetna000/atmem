# Three-way optional-code-tools validation

The frozen five-task campaign is terminal. Native tools and AtMem each solve
5/5 scheduled tasks. Cognee solves all four tasks that reach inference; SymPy
hits its 600-second graph-loading deadline before any model attempt. That is
an availability failure, not an incorrect model answer.

## Identical four-task comparison

These rows use only the four tasks with valid official grades and complete
usage in **all three** arms. All cache-read/write input tokens are counted.

| Measure | No memory | AtMem structure | Upstream Cognee CODE |
|---|---:|---:|---:|
| Tasks solved | 4/4 | 4/4 | 4/4 |
| Total input tokens | 86,885 | 110,055 | 86,433 |
| Total output tokens | 8,503 | 6,474 | 6,550 |
| Median solver-only seconds | 57.1 | 41.4 | 45.5 |
| Median measured setup + solver seconds | 74.5 | 106.0 | 391.8 |
| Total indexing seconds | 0 | 126.0 | 1,188.4 |
| Model-initiated graph-content queries | — | 0 | 0 |

AtMem uses **26.7% more input than native** on this common cohort. Its median
measured setup-plus-solver time is **72.9% lower than Cognee**, but higher than
native. Preparation includes benchmark workspace staging and actual transport
controls: these are measured harness times, not promised normal-CLI latency.
Solver-only time excludes preparation and must not be called end-to-end warm
latency, especially for a later automatic-context profile.

No model requests graph content in either graph arm. Therefore the timing and
repair differences cannot establish that retrieved graph knowledge helped.
This result supports tested indexing availability and a preparation-time
comparison, not memory-caused repair improvement or token savings.

### Actual indexed architecture-query controls

The retained pre-model transport controls request the same `architecture`
operation with `max_nodes=3`. These are actual provider calls, not solver uptake:

| Task | AtMem MCP seconds | Cognee MCP seconds |
|---|---:|---:|
| Sphinx 8595 | 9.46 | 8.27 |
| Matplotlib 24970 | 19.98 | 10.88 |
| Django 16229 | 25.27 | 10.30 |
| scikit-learn 12471 | 13.85 | 8.93 |
| Median, identical four tasks | 16.91 | 9.61 |

These first requests include provider query/validation and lazy initialization
as observed through the MCP bridge after initialization/listing. They are not
steady-state query-only timings or identical serialization algorithms. AtMem
reports a current dictionary envelope; upstream Cognee returns its supported
list shape. All nine graph controls, including AtMem's additional SymPy case,
return without tool errors. Cognee's unavailable SymPy case has no query time,
not a zero. These controls favor Cognee query latency despite AtMem's faster
measured preparation. The metadata projection is `receipt-audit.json` beside
the campaign, reconstructed from archived tool exchanges rather than new runs.

On all five tasks, native input is 99,119 tokens versus AtMem's 128,830; both
solve all five. Do not compare those five-task totals with Cognee's four-task
total or call its unavailable task a wrong answer. All fourteen model attempts
have complete normal receipts. The largest attempt uses seven tool requests,
below the fixed thirty-request cap.

## Configuration and retention

The same Windows/WSL executor, dataset revision, official harness, Claude
`claude-opus-5-5` medium subscription CLI, task sources, workspace tools and
budgets are used. Both graphs use the same source admission policy and pinned
offline Enola extractor. AtMem wheel:
`1314dc5a309cd19c7ac0e7704a4cc5d18a77d4596cffbb2fef0c6ae549d2629d`.
Actual upstream Cognee 1.6.4 is built from reviewed source commit
`f154b32a9e544dac73e7ddf2010327cf9988edcd`; wheel:
`38c76abc9553a345f798d24e08792f4a5b45d40415b2a31a2415c86fb2bc52c7`.
Its complete isolated dependency manifest is pinned in the runtime receipt.
Its supported CODE route uses no embedding or LLM extraction. A separate
supported in-process-backend probe passed but showed no useful speed-up; that
setting was not silently substituted into the scored campaign.

Protected root:
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swebench-threeway-validation-20261019`.
All model streams, tool exchanges, final patches and official grades are retained.
Eighteen complete upstream preparation logs were additionally retained encrypted.
The public numerical projection is
[the machine-readable report](2026-10-19-swebench-threeway-validation-live.json).
The source/qualification/model design is in
[the protocol](../specs/042-atmem-code/swebench-threeway-20261019.md).

This is reused-task engineering validation, not untouched confirmation or a full
SWE-bench score. The separately frozen automatic-source-pack validation starts
next with fresh native/AtMem attempts; it is not pooled with this equal-optional
comparison. The five broader product capabilities have separate
[installed controls](2026-10-19-code-five-benefits-controls.md), not evidence
inferred from these cold-start tasks.
