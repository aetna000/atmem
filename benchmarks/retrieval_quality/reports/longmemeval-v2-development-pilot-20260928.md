# LongMemEval-V2 development pilot — 2026-09-28

## Status

**Incomplete development evidence. This is not an official benchmark result, a
leaderboard score, or evidence for a paper claim.**

The frozen 14-question, two-arm pilot started on the official LongMemEval-V2
checkout, but only seven paired questions completed. The run stopped before
OpenAI judging when later Qwen responses contained reasoning tokens without a
final answer. The official harness correctly rejected the empty answer and the
runner cancelled sibling work. The temporary Runpod pod was then deleted.

## Frozen execution identity

| Item | Value |
| --- | --- |
| Official checkout | `2cc8c540bdb87fe6761629b585e727e1c4704520` |
| AtMem | installed wheel `2.3.8b6` |
| Wheel SHA-256 | `b2d0e4327cc29db21afbc226c6f11f3294826e4b43e9c2a5330bfe53f2e0a7f8` |
| Reader | `Qwen/Qwen3.5-9B` revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| Runtime | vLLM `0.29.0`, BF16, 262,144-token maximum context |
| Hardware | Runpod Secure Cloud, one NVIDIA L40S |
| Container | `vllm/vllm-openai:v0.29.0` (`sha256:c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1`) |
| OpenAI judge | Not invoked |

The no-egress preflight verified the official code and data hashes, all 14
selected questions, 200 trajectories, 5,095 screenshots, two question images,
the installed AtMem wheel, and the pinned Qwen processor before paid egress.

## Partial observations

Seven of fourteen question pairs completed deterministic grading:

| Arm | Correct | Completed | Directional accuracy |
| --- | ---: | ---: | ---: |
| `typed-local` | 1 | 7 | 14.3% |
| `no-retrieval` | 0 | 7 | 0.0% |

These denominators are incomplete and the sample is a development slice, so
the percentages must not be compared with published LongMemEval results. The
one positive paired difference only establishes that the AtMem path can change
an answer in the right direction on a real official case.

AtMem context sizes for the completed typed cases ranged from 8,517 to 52,989
tokens. Inspection of the failed cases found four actionable failure classes:

1. **Wrong-task contamination:** related UI evidence displaced the exact task.
2. **Missing answer-bearing evidence:** retrieval returned context but omitted
   the required fact or ordered step.
3. **Over-packing:** several contexts were tens of thousands of tokens, which
   increased latency and made the evidence harder for the reader to use.
4. **Reader finalization:** some generations exhausted the 20,000 completion
   token ceiling in reasoning or produced reasoning without final content.

The first three are AtMem product-quality findings. The fourth is a reader and
serving-path finding; the benchmark adapter must not turn hidden reasoning into
an answer or otherwise compensate for it.

## Cost and cleanup

| Cost | Amount |
| --- | ---: |
| This Runpod attempt | `$0.2346113264` |
| OpenAI judge calls | `0` |
| OpenAI judge cost | `$0.00` |
| Aggregate Runpod spend across retained setup attempts | `$1.1468239352` |

Runpod pod `etu5nxiiqwaibr` was deleted and a subsequent pod listing was empty.
The durable reader ledger is complete rather than reserved. All 28 OpenAI
reservations were reconciled to zero because the judge gate never opened.

Raw progress, per-case outputs, and cost ledgers remain on the external `MEM`
volume under `atmem-benchmarks/runs/longmem-3pct-runpod-r4-20260928`; they are
not committed because they include benchmark artifacts.

## Decision

Do not buy another full pilot yet. First improve answer-bearing evidence recall,
task isolation, and evidence-complete bounded packing on the frozen development
cases. Then rerun the local product and installed-artifact gates and perform a
small reader finalization probe. A paid retry is justified only after those
checks pass without benchmark-specific retrieval behavior.
