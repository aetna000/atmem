# Context Engine V3 formation gate

Date: 2026-10-01

Corpus: frozen benchmark-neutral minimal-evidence v1

Claim class: structural/reader-free development diagnostic only

| Measure | Result | Gate |
|---|---:|---:|
| Ordered source parts retained | 17/17 (100%) | 100% |
| Evaluator answer-bearing ranges retained | 13/13 (100%) | 100% |
| Answer-bearing ranges reachable through an appropriate typed view | 13/13 (100%) | ≥98% |
| Silent uncovered ranges | 0 | 0 |
| Replay/idempotency failures | 0 | 0 |
| Unauthorized source exposure | 0 | 0 |
| Logical derived/source byte ratio | 0.456 | ≤1.5 |

The deterministic path always retains an exact raw-state range, then adds only
source-linked compact projections. Source, part, modality and view identity are
normalized columns rather than repeated JSON. Optional extraction is additive,
schema constrained, pinned to a producer identity, deadline bounded and rejected
when its ranges do not validate against retained canonical bytes.

Corrections retain both immutable source occurrences, add a `supersedes` link,
and move the prior derived fact out of active lifecycle. Exact duplicate
occurrences are linked rather than deleting provenance.

This gate does not measure answer quality on LongMemEval-V2 or action accuracy
on DolphinBench. It exists to prove that later retrieval evaluation is not
being rescued by benchmark-specific source loss or duplicated source bodies.
