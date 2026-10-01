# Context Engine V3 trajectory

Date: 2026-10-01

Corpus: `research/reference_parity/fixtures/minimal-evidence-v1.json`

Cases: 12 (6 development, 6 sealed holdout)

Selection budget: 2 source ranges

Claim class: reader-free product-neutral diagnostic; not an official benchmark

| System | Evidence recall | Typed status | Holdout recall | Holdout status | Unauthorized | Median local latency |
|---|---:|---:|---:|---:|---:|---:|
| AtMem legacy control | 70.8% | 58.3% | 91.7% | 66.7% | 0 | 96.8 ms |
| Mem0 OSS raw offline | 83.3% | 58.3% | 100.0% | 50.0% | 0 | 27.2 ms |
| AgentRunbook-R index offline | 83.3% | 58.3% | 100.0% | 50.0% | 0 | 0.5 ms |
| AtMem `context-fast` candidate | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **0** | 17.8 ms |

## A to B

- Evidence recall: 70.8% → 100.0% (+29.2 points; +41.2% relative).
- Typed-status accuracy: 58.3% → 100.0% (+41.7 points; +71.4% relative).
- Median diagnostic latency: 96.8 ms → 17.8 ms (-81.6%).
- Candidate relative evidence-recall improvement over both frozen reference arms:
  20.0%.

## What changed

The candidate retains ordered source parts once, creates stable exact ranges,
projects additive source-linked evidence views, plans explicit obligations,
retrieves from independent persistent pools, reserves one evidence head per
obligation, detects source-backed contradiction/conflict, and packs evidence in
obligation order. Persistent semantic storage is fail-closed unless the
household is SQLCipher-encrypted.

## Limitations

- This corpus is intentionally small and benchmark-neutral. It is a paid-run
  gate, not evidence that AtMem leads LongMemEval-V2 or DolphinBench.
- The latency figures are single-machine diagnostics, not frozen-hardware
  performance evidence.
- AgentRunbook-C/V2 is model-directed and remains for the bounded cassette/live
  differential.
- Optional extraction/navigation, product-surface parity, 50k/100k performance,
  installed-artifact, and matched paid development gates remain incomplete.
- No website, release note, or dashboard may present this result as benchmark
  leadership.
