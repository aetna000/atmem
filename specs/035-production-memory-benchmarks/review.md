# Production benchmark review

## Implemented gates

- LoCoMo is loaded from a user-provided file; the dataset is not committed.
- The manifest pins the upstream source commit and the observed file SHA-256.
- The adapter uses the real AtMem `Memory` engine, not a mock retriever.
- The result includes MRR, Recall@1/5/10, evidence coverage, p50/p95 query
  latency, throughput, errors, Python/platform, and memory resource metadata.
- A sample or a run with unresolved upstream evidence cannot receive
  `production-candidate` status.

## Full-corpus observation

The complete ten-conversation LoCoMo file was evaluated locally without hosted
model egress. The resulting report is
`research/production_benchmarks/results/locomo-full-2026-09-19.json`.

Observed run (hardware and process load affect latency):

- 1,986 QA questions
- MRR@5: 0.4259
- Recall@1: 0.3399
- Recall@5: 0.5760
- Recall@10: 0.6495
- p50 query latency: 19.345 ms
- p95 query latency: 25.047 ms
- throughput: 44.629 questions/second
- four upstream evidence anomalies
- claim status: `exploratory`, not production-candidate

The four anomalies are retained as a visible validation issue rather than
silently repaired or excluded. This is why the result is real and useful, but
not yet a production-quality claim. A follow-up should agree on an official
cleaned LoCoMo revision or an explicit exclusion protocol before publishing a
production number.

## Jev comparison

The same full corpus was then rerun with Jev 1.13.0 reranking the AtMem top-10
candidate set. The run used 40 batched requests, explicit `--allow-egress`, and
had zero Jev transport errors. Raw output is
`research/production_benchmarks/results/locomo-full-jev-2026-09-19.json`.

| Metric | AtMem | AtMem + Jev | Change |
|---|---:|---:|---:|
| MRR@5 | 0.4259 | 0.5868 | +0.1609 |
| Recall@1 | 0.3399 | 0.5423 | +20.24 pp |
| Recall@5 | 0.5760 | 0.6420 | +6.60 pp |
| Recall@10 | 0.6495 | 0.6495 | unchanged |

This shows Jev improved ordering, not candidate coverage: Recall@10 and
evidence coverage are unchanged because Jev only reranked AtMem's nominated
top-10 candidates. The Jev batches had p50 latency of 3.32 seconds and p95 of
8.74 seconds, so this is a quality/latency trade-off rather than a speed win.
The report remains `exploratory` until the upstream evidence anomalies are
resolved under an explicit benchmark policy.
