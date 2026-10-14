# Selective Laya V3 matched operational comparison

> Frozen 100-item operational corpus; this is not an independent scientific benchmark.
> Every arm starts from the same empty canonical baseline and replays the same
> ordered observations on the same Mac. Each resulting SQLite database and raw
> per-item receipt is retained beside this report.

| Measure | Deterministic | Original Laya | Fine-tuned selective Laya |
|---|---:|---:|---:|
| Correct / 100 | 30 | 30 | 20 |
| Safe / 100 | 30 | 75 | 20 |
| Median latency (ms) | 3.15 | 45.35 | 45.26 |
| p95 latency (ms) | 4.73 | 52.55 | 52.84 |
| Runtime failures | 0 | 0 | 0 |

## Per expected disposition

| Expected | N | Deterministic | Original Laya | Fine-tuned Laya |
|---|---:|---:|---:|---:|
| STORE | 25 | 25 | 0 | 0 |
| UPDATE | 15 | 0 | 0 | 0 |
| DUPLICATE | 10 | 0 | 0 | 0 |
| DO_NOT_STORE | 20 | 5 | 0 | 20 |
| REVIEW | 30 | 0 | 30 | 0 |

The tuned candidate emitted `DO_NOT_STORE` for all 100 observations. It
therefore regresses exact policy agreement by 10 points, loses all 25 durable
memories, and adds about 42 ms to median formation latency. It fails the V3
activation gate and remains a rejected research checkpoint.

- Dataset: `atmem/stateful-memory-transitions-selective-v3-research@f46cdcd23c189cacdaa68abd2ec780752227e9f4`
- Model: `atmem/laya-memory-decision-selective-v3-research@df99531c1e9aa076176a6340737c30f334083076`
- Weights SHA-256: `93f1d0c623b956fbe9c92a25b57b4298a08ff8bf5e0b7f182635361d2c304104`
