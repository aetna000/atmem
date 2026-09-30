# AtMem benchmark development runs — 2026-09-30

## Status

These are complete, frozen development slices. They are not official leaderboard
submissions and must not be presented as full-benchmark or paper results.

| Benchmark / arm | Sample | Passed | Accuracy | Additional signal |
| --- | ---: | ---: | ---: | --- |
| LongMemEval-V2 `no-retrieval` | 14 questions | 0 | 0.0% | Seven categories, two questions each |
| LongMemEval-V2 `typed-local` | 14 questions | 0 | 0.0% | Mean context 21,539 tokens; no lift over control |
| DolphinBench AtMem + Qwen agent | 18 tasks | 4 | 22.2% | 18/59 checks passed (30.5%) |

The Dolphin result was Alex 1/6, Morgan 3/6, and Riley 0/6. AtMem injected
context in 18/18 tasks. The result therefore measures a real end-to-end path,
but it is not yet competitive.

## Frozen identities

| Item | LongMemEval-V2 | DolphinBench |
| --- | --- | --- |
| Official source commit | `2cc8c540bdb87fe6761629b585e727e1c4704520` | `81cb6f8405b40a9e76089cef650806a80af06ea2` |
| Candidate | installed AtMem `2.3.8b6`, artifact `b2bdf272…` | branch commit `4438744cee3d137fa3224339ff796d5afb522541` over installed AtMem `2.3.8b6` |
| Reader / agent | Qwen 3.5 9B revision `c202236…` | Qwen 3.5 9B revision `c202236…` |
| Runtime | vLLM 0.29.0, BF16, A100-SXM4-80GB | vLLM 0.29.0, BF16, A100-SXM4-80GB, `qwen3_coder` tool parser |
| Judge | GPT-5.2 snapshot `gpt-5.2-2025-12-11`, medium | GPT-5.2 snapshot `gpt-5.2-2025-12-11`, medium |
| Claim | 14-question paired development pilot | frozen 18/600 development split |

The LongMemEval input preflight verified 14 questions, 200 trajectories, 5,095
screenshots, and two question images. Dolphin ingestion processed all 13,539
released history sessions before the frozen test slice.

## LongMemEval-V2 findings

Both arms scored 0/14. Each arm contained two cases from each of `static`,
`dynamic`, `procedure`, `gotchas`, and the three abstention variants, so there
was no category hidden by the aggregate.

The typed arm packed an average of 21,539 memory tokens per question, ranging
from 732 to 42,169. It used 306,157 reader prompt tokens versus 4,711 for the
no-retrieval control, yet produced no accuracy lift. Case inspection shows the
failure is not a lack of retrieved text: the system often retrieved adjacent UI
or procedural evidence but omitted the answer-bearing state, then made the
reader reason over tens of thousands of distracting tokens. For example, the
Magento toolbar case retrieved order-page evidence containing “Login as
Customer”, but not the customer-page state needed to establish the answer, and
the reader returned `UNKNOWN` after 2,275 completion tokens.

This invalidates the hypothesis that the current typed formation plus a large
context budget is sufficient. More context is currently amplifying incomplete
retrieval rather than repairing it.

## DolphinBench findings

| Persona | Tasks passed | Checks passed |
| --- | ---: | ---: |
| Alex | 1/6 | 6/23 |
| Morgan | 3/6 | 9/19 |
| Riley | 0/6 | 3/17 |
| **Total** | **4/18** | **18/59** |

The median agent interaction was 6.52 seconds (range 3.65–11.77 seconds), with
277,520 prompt tokens and 6,401 completion tokens across 18 tasks. Fourteen
semantic checks were graded by the pinned GPT-5.2 judge.

Formation completed processing for all 13,539 sessions, but only 11,986
(88.5%) were representation-complete and 9,097 (67.2%) were retrieval-ready.
Formation admitted 9,586 units, withheld 4,170, and rejected 2,824. The three
encrypted persona databases occupy about 1.2 GiB: 429 MiB for Alex, 340 MiB for
Morgan, and 444 MiB for Riley. That is too much storage for this history volume
and confirms that source, derived representation, and retrieval structures need
deduplication and lifecycle compaction.

Two adapter defects were found and fixed without repeating model calls:

1. Prompt-facing JSON strings had overridden structured MCP results, hiding
   `result.ok` from the official grader.
2. MCP validation added optional defaults to logged arguments, while the
   submission contract requires the model's exact arguments. The driver now
   retains exact model arguments alongside the structured MCP result.

The retained per-test MCP logs were used to reconcile the 18 completed traces,
and the invalid pre-reconciliation grades were preserved separately. The
corrected result is 4/18, not the invalid initial 0/18.

## Cost and cleanup

| Component | Cost evidence |
| --- | ---: |
| LongMemEval reader GPU | `$0.378399617` locally observed |
| LongMemEval GPT-5.2 grading | `$0.04011525` |
| Dolphin agent request-time ledger | `$0.052998187` |
| Dolphin GPT-5.2 semantic grading | `$0.05670525` |
| Dolphin GPT-5.2 health probes | `$0.00091875` |
| Dolphin successful corrected pod | about `$0.266` locally observed |
| Dolphin provisioning attempts including corrected pod | about `$1.39`; provider invoice not reconciled |

RunPod reported zero active pods after the run. The request-time Dolphin ledger
is useful for per-case comparison but is not a substitute for wall-clock GPU
billing, which included image download, model load, and failed provisioning
attempts.

## Trajectory

The earlier incomplete LongMemEval run reported 1/7 for `typed-local` and 0/7
for control. It stopped before the frozen sample and judging completed, so it is
not statistically or operationally comparable. The complete rerun is 0/14 for
both arms. There is no demonstrated improvement trajectory yet.

The new positive result is measurement quality: both official adapters now run
end to end, paid calls are bounded and retained, Dolphin tool traces survive the
submission contract, and the failures identify product work rather than
benchmark plumbing. The quality trajectory starts from this complete baseline.

## Highest-leverage next changes

1. **Answer-bearing formation coverage.** Preserve exact labels, values,
   polarity, temporal state, ordered steps, and applicability constraints from
   immutable source evidence. Track source sections that were not represented.
2. **Information-need routing.** Route exact fact, current state, transition,
   procedure, exception, and invalid-premise questions to different nomination
   and packing policies.
3. **Sufficiency-gated retrieval.** Require subject, relation, value, time,
   polarity, conditions, and conflicts as applicable; expose `sufficient`,
   `partial`, `conflicted`, or `unsupported` rather than treating similarity as
   completeness.
4. **Bounded evidence neighbourhoods.** Expand only to the source-linked prior
   state, transition, outcome, condition, or adjacent procedure step needed to
   complete the evidence.
5. **Aggressive complementary packing.** Replace 20k–42k token dumps with the
   smallest package that covers the information need. Measure answer-bearing
   evidence recall before reader accuracy.
6. **Action constraints for agents.** Deliver current, source-backed governing
   rules with applicability, required action, prohibited alternative, and
   validity, so Dolphin agents can execute exact tool arguments.
7. **Storage normalization.** Store immutable source once, reference it from
   typed units, compact superseded derived state, and keep vector/index payloads
   out of the primary encrypted row store where possible.

Do not run the full benchmarks yet. First make the frozen samples pass an
evidence-recall gate, reduce median packed context materially, and demonstrate
a reproducible gain over this baseline through ablation.

## Retained evidence

- LongMemEval run: `/Volumes/MEM/atmem-benchmarks/runs/longmem-3pct-a100-sxm-9af0e26-final`
- Dolphin evidence archive: `/Volumes/MEM/atmem-benchmarks/runs/dolphin-3pct-qwen-4438744-final.tar.gz`
- Dolphin encrypted state: `/Volumes/MEM/atmem-benchmarks/state/dolphin-3pct-qwen-4438744-final`

The Dolphin archive is a portable `tar.gz` rather than tens of thousands of
loose files; this avoids multi-gigabyte allocation overhead on the cross-platform
MEM filesystem. Its SHA-256 is
`20340fb964bbb4e46d61a396092b576f32b8c31a35c41e85bb64703401ba6acc`.
