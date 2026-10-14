# Deterministic AtMem versus fine-tuned Laya V2

> Matched maintainer operational pilot; the 100-item OpenClaw corpus is a
> synthetic policy challenge, not an independent generalization benchmark.
> The Laya checkpoint is research-only and uncalibrated.

| User-facing measure | Deterministic | Fine-tuned Laya V2 | Difference |
|---|---:|---:|---:|
| Correct storage decisions / 100 | 30 | 16 | -14 |
| Safe non-authoritative outcomes / 100 | 30 | 22 | -8 |
| Median end-to-end formation latency | 3.04 ms | 90.55 ms | 30x |
| p95 end-to-end formation latency | 4.59 ms | 199.88 ms |  |
| Mean end-to-end formation latency | 2.99 ms | 120.66 ms |  |
| Runtime failures / 100 | 0 | 29 |  |

**Operational conclusion:** this checkpoint provides no demonstrated user benefit. It makes fewer correct decisions and adds material latency, so it must not replace the deterministic profile.

## Per expected disposition

| Expected | N | Deterministic correct | Fine-tuned Laya correct |
|---|---:|---:|---:|
| STORE | 25 | 25 | 0 |
| UPDATE | 15 | 0 | 0 |
| DUPLICATE | 10 | 0 | 0 |
| DO_NOT_STORE | 20 | 5 | 12 |
| REVIEW | 30 | 0 | 4 |

Corpus SHA-256: `612181e0084e4ae847b8e84548f4fc989117b7ffaa1c9d2e587cd0a8ad2bc23d`
