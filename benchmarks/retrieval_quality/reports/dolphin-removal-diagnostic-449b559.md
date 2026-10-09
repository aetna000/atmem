# DolphinBench 5% removal diagnostic — `449b559`

**Status:** no-cost development diagnostic only; not a benchmark score and not
evidence for a public quality or safety claim.

The clean installed `2.3.8b6` candidate at commit `449b559` ingested the full
official histories for the frozen 30-task development sample. Ingestion and
the removal controls made no model, provider or tool calls.

| Persona | Source sessions | Source message bytes | Encrypted checkpoint bytes |
|---|---:|---:|---:|
| Alex | 5,011 | 2,627,222 | 320,684,032 |
| Morgan | 3,400 | 2,481,362 | 394,510,336 |
| Riley | 5,128 | 2,618,819 | 312,737,792 |
| **Total** | **13,539** | **7,727,403** | **1,027,932,160** |

The encrypted checkpoint footprint is about **133.0x** the retained source
message bytes. This fails the storage gate. The existing Context Engine V3
storage report also returned zero source/view bytes because this adapter path
still wrote the observations through legacy canonical records rather than the
compact source-range generation. That is a product-path integration failure,
not a passing zero-storage result.

## Removal outcomes

| Outcome | Cases | Credited as safety success |
|---|---:|---:|
| Exact named `blocked_missing_requirement` | 18 | 18 |
| Missing obligation did not match removed requirement | 7 | 0 |
| Removal target was not atomic | 4 | 0 |
| Gate remained open after removal | 1 | 0 |
| Timeout, parse error, provider error or silent no-call | 0 | 0 |

All 30 cases remain in the denominator. The diagnostic therefore improved the
previous valid-block result from 14/30 to 18/30, but **12/30 controls still
fail**. `model_invocations=0` and `tool_calls=0` are necessary but not
sufficient: only the 18 receipts that name an obligation belonging to the
removed requirement are credited.

## Decision

Paid Dolphin execution remains blocked. The next candidate must:

1. retain source once in the compact V3 source/range generation;
2. expose independently removable source ranges without duplicating their text;
3. make product-derived obligations precise enough to attribute all 30
   removals; and
4. pass restored-evidence positive controls before Hermes is invoked.

Raw local evidence was produced under:
`/private/tmp/atmem-dolphin-5pct-run-449b559`,
`/private/tmp/atmem-dolphin-5pct-state-449b559`, and
`/private/tmp/atmem-dolphin-removal-5pct-449b559`. These paths are diagnostic
working data, not repository fixtures.
