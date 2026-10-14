# Deterministic AtMem, original Laya, and fine-tuned Laya V2

Matched Mac operational replay over the same ordered 100-item OpenClaw policy
challenge. Both model arms use the same V2 typed decision contract, AtMem
formation path, MPS device, fixed 0.5 research threshold, and strict contract
validation. The corpus is a maintainer operational challenge rather than an
independent generalization benchmark.

| Measure | Deterministic | Original Laya | Fine-tuned Laya V2 |
|---|---:|---:|---:|
| Correct decisions / 100 | **30** | 16 | 16 |
| Safe non-authoritative outcomes / 100 | **30** | 22 | 16 |
| Median end-to-end latency | **3.06 ms** | 90.55 ms | 86.82 ms |
| p95 end-to-end latency | **4.53 ms** | 199.88 ms | 704.73 ms |
| Mean end-to-end latency | **2.98 ms** | 120.66 ms | 143.42 ms |
| Runtime failures / 100 | **0** | 29 | 26 |

## Correct decisions by expected disposition

| Expected disposition | N | Deterministic | Original Laya | Fine-tuned Laya V2 |
|---|---:|---:|---:|---:|
| STORE | 25 | **25** | 0 | 0 |
| UPDATE | 15 | 0 | 0 | 0 |
| DUPLICATE | 10 | 0 | 0 | 0 |
| DO_NOT_STORE | 20 | 5 | 12 | **15** |
| REVIEW | 30 | 0 | **4** | 1 |

Original Laya failed 29 requests because its choice probabilities did not pass
the strict sum-to-one contract. Fine-tuned Laya failed 23 requests because the
complete retrieved state exceeded the tokenizer-exact budget and three because
score output validation failed.

Fine-tuning therefore improved DO_NOT_STORE recognition and reduced the median
by 3.73 ms, but it produced no net correctness gain, reduced safe outcomes,
increased mean and p95 latency, and still failed every STORE, UPDATE, and
DUPLICATE case. Neither model arm is suitable to replace deterministic AtMem.

The original model is `convaiinnovations/laya-multilingual` at revision
`1720e3e3357cfe1e281542e223f8273b0890ca34`. The fine-tuned artifact is
`atmem/laya-memory-decision-v2` with export digest
`448e72bb3bc59b778c677ea51b79b6825a895cbd5b5cc6fd24a50a6167f25e9b`.
