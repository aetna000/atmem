# Context engine pre-change reader-free comparison

**Status:** partial development diagnostic, recorded 2026-10-01. This is not a
LongMemEval-V2 or DolphinBench score and does not support a leadership claim.

The frozen neutral corpus contains twelve cases, eight shared distractors and a
two-source output budget. The same evaluator-owned source-range normalizer
scores every arm. All arms run without a reader or paid model.

| Arm | Evidence recall | Typed status | Holdout evidence | Unauthorized exposure |
|---|---:|---:|---:|---:|
| AtMem legacy public control path | 70.8% | 58.3% | 91.7% | 0 |
| Mem0 OSS raw offline path | 83.3% | 58.3% | 100.0% | 0 |
| AgentRunbook-R pinned index primitive | 83.3% | 58.3% | 100.0% | 0 |

AtMem misses the answer-bearing correction, both sides of a comparison and the
failure/gotcha case; it retrieves only one side of a conflict. Every arm also
shows why typed sufficiency is a distinct problem: raw retrieval cannot identify
negative-premise contradiction, evidence conflict or policy withholding merely
because some text was returned.

The Mem0 arm uses the real pinned OSS add/search path with `infer=false`, local
Qdrant and a deterministic hash embedding. It is not the hosted Mem0 service.
The AgentRunbook-R arm imports the pinned upstream implementation and calls its
real `_search_entries` primitive over independent pools, but replaces model
formation and query rewriting with identity formation/all-pool routing. It is
not a reproduction of published AgentRunbook-R/C scores.

The aggregate is checksum-bound in
`baselines/context-engine-reader-free-prechange-partial.json`; full per-case
outputs and a checksum manifest are retained under
`/Volumes/MEM/atmem-benchmarks/baselines/context-engine-prechange-20261001`.
Spec 040 T004 remains open until AgentRunbook-C/V2 navigation, a cryptographic
manifest signature and frozen-hardware repetitions are present.
