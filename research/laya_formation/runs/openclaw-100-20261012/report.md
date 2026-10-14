# OpenClaw 100-memory AtMem/Laya operational A/B

> This is a maintainer-run operational pilot over a frozen synthetic policy challenge set produced by the configured OpenClaw agent. It is not an independent, held-out, or statistically powered benchmark.

Corpus SHA-256: `612181e0084e4ae847b8e84548f4fc989117b7ffaa1c9d2e587cd0a8ad2bc23d`  
Model revision: `1698278c4b158fac30e4eb2fefd10ef8b8f873b3`  
Host: `macOS-26.5.2-arm64-arm-64bit`

| Measure | Deterministic | Laya active |
|---|---:|---:|
| Exact policy matches / 100 | 25 | 31 |
| Safe non-authoritative outcomes / 100 | 25 | 2 |
| Mean formation latency (ms) | 0.8 | 1465.2 |
| Formation decision audit events | 0 | 500 |

## Per expected disposition

| Expected | N | Deterministic exact | Laya exact | Deterministic semantic | Laya semantic |
|---|---:|---:|---:|---:|---:|
| STORE | 25 | 25 | 0 | 25 | 24 |
| UPDATE | 15 | 0 | 0 | 15 | 15 |
| DUPLICATE | 10 | 0 | 0 | 10 | 9 |
| DO_NOT_STORE | 20 | 0 | 2 | 20 | 17 |
| REVIEW | 30 | 0 | 29 | 30 | 29 |

## Evidence files

- `corpus.json`: exact frozen inputs and expected policy dispositions.
- `deterministic-records.jsonl`: every deterministic memory piece and receipt.
- `laya-records.jsonl`: every Laya decision, confidence receipt, final authority disposition, and memory piece.
- `summary.json`: machine-readable aggregate and artifact hashes.
