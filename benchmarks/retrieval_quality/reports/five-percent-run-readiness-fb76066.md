# Five-percent run readiness at `fb76066`

**Status:** checkpoint readiness only. No paid LongMemEval-V2 or DolphinBench
case has been scored by this checkpoint-preparation run, and this document is
not benchmark evidence.

## Completed and retained

The frozen 23-question LongMemEval-V2 development sample has complete,
digest-verified checkpoints on `MEM` for the no-memory control, AtMem web and
enterprise domains, and Mem0 OSS web and enterprise domains. Their immutable
receipt is
`/Volumes/MEM/atmem-benchmarks/feature-040/fb76066/checkpoint-readiness.json`.
AgentRunbook-R formation is incomplete and must not be scored or compared.

The frozen 30-task DolphinBench development sample has complete AtMem and
Mem0 OSS persona checkpoints on `MEM`. All three AtMem logical checkpoint
receipts and all three Mem0 record receipts were revalidated after copying.
The combined checkpoint trees are bound by the following digests:

| Arm | Checkpoint tree SHA-256 |
| --- | --- |
| AtMem | `sha256:1482144ea4a5c3c37be53ab8f91ae4dca112344a305bf2b5d7235e28995468cb` |
| Mem0 OSS | `sha256:83129a448b74b44dccc05b783004c2c1478a34f6ee81ec4c2a35f4eb9f5858cf` |

The machine-readable receipt is
`/Volumes/MEM/atmem-benchmarks/feature-040/fb76066/dolphin-checkpoint-readiness.json`.

## Paid-run blocker

At the final balance check, RunPod reported `$1.5068385899` and zero active
pods. That is not enough to complete the pinned AgentRunbook-R per-transition
formation, the configuration-specific finalization probes, and both matched
five-percent evaluations. No pod was started, preventing another incomplete
paid run.

The remaining order is fixed:

1. Add sufficient RunPod credit without changing the pinned Qwen route.
2. Resume only the incomplete AgentRunbook-R checkpoint arm.
3. Produce and validate configuration-specific finalization evidence.
4. Run all 23 LongMemEval-V2 questions for every required matched arm.
5. Run all 30 DolphinBench tasks for AtMem and Mem0 OSS.
6. Build the complete attribution ledgers and matched tables before making any
   quality claim.

Failures, timeouts, provider errors, parse errors, and missing outcomes remain
in the denominator. A partial run cannot be promoted to a score.
