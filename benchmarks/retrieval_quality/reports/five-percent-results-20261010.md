# Frozen 5% development benchmark results — 2026-10-10

## Scope and claim boundary

This report records matched development evidence for the AtMem 2.3.8 candidate. It is **not an official benchmark score** and does not establish leaderboard superiority. Every attempted case remains in the denominator. The frozen samples are 23 of 451 LongMemEval-V2 questions and 30 of 600 DolphinBench tasks.

## Results

| Benchmark | AtMem | Matched comparator | Interpretation |
|---|---:|---:|---|
| LongMemEval-V2 | 5/23 (21.7%) | AgentRunbook-R 4/23 (17.4%); Mem0 1/23 (4.3%) | AtMem leads both comparators on this frozen sample, but absolute accuracy is low and the sample is not an official score. |
| DolphinBench tasks | 2/30 (6.7%) | Mem0 3/30 (10.0%) | AtMem trails by one fully-passed task. |
| DolphinBench checks | 15/97 (15.5%) | Mem0 16/97 (16.5%) | AtMem trails by one individual check. |
| AGMI, audit chain only | 8/9 detected | Historical AtMem 2.3.7: 0/9 | Eight store-tampering classes are detected; whole-store snapshot rollback remains undetectable without trusted external state. |
| AGMI, audit chain plus external checkpoint | 9/9 detected | Historical AtMem 2.3.7: 1/9 | All pinned attacks are detected when the checkpoint file is outside the attacker-controlled store directory. |

The LongMemEval controlled reader answered 19/23 with evaluator-verified evidence, compared with 5/23 using AtMem product context and 1/23 with no retrieval. This establishes a large evidence-delivery/use gap, but it does not by itself assign terminal blame. The reviewed eight-stage requirement ledgers are still required before separating formation, retrieval, packing, and reader-use failures case by case.

## Safety controls

DolphinBench removal controls passed 30/30. In every removal case, the adapter returned `blocked_missing_requirement`, named the removed requirement, did not invoke the model, emitted zero tool calls, and did not mistake timeout, parsing, provider failure, or silent no-call for a safe block.

Restoring the evidence opened the gate in 28/30 cases. The paired removal-and-positive controls therefore passed 28/30. Two cases are over-blocked:

- `morgan:063`: restored evidence still did not satisfy the hiring-sequence obligation, so the expected `send_slack_message` action was never attempted.
- `morgan:138`: restored evidence still did not satisfy the integration-contact/copy-recipient obligations, so the expected `send_email` action was never attempted.

These two cases are the first frozen development cases for the Dolphin root-cause iteration. They expose a product defect—formation/retrieval does not produce a sufficient action package—not a provider or scoring failure.

## Execution integrity

- LongMemEval arms used the same frozen question IDs and reader/judge route. AtMem scored 5/23, AgentRunbook-R 4/23, Mem0 1/23, and no retrieval 1/23.
- LongMemEval recorded six AtMem system failures: three incomplete reader finalizations at the 20,000-token cap and three governance rejections outside the frozen selection. AgentRunbook-R had four incomplete finalizations; Mem0 had one.
- DolphinBench arms used source commit `81cb6f8405b40a9e76089cef650806a80af06ea2` and split SHA-256 `60c681f8e7ce0796ec0209294c885abe7dc0fe5a594226aa1035c401535658de`.
- Both Dolphin arms completed 30/30 tasks with zero system failures. The Mem0 arm emitted warnings because optional spaCy and `fastembed` extras were absent; it nevertheless completed through the pinned matched adapter.
- AGMI used upstream commit `115493a41a7b41952f92ec07e1ea0932926e194f`, package 0.6.3, and the installed 2.3.8b6 candidate.
- The paid RunPod reader was stopped after the final artifacts were written.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| LongMemEval matched results | `89c800219cfab38b34cfc406d764919b49c24b550827a30414cb49fb4c247fd8` |
| LongMemEval controlled reader | `26ba0c7d60b950ec0a5435813b6c7316a0b0badcd9050478b1ff0f262d3bddd6` |
| DolphinBench matched results | `84296c20aa11b998ddfeb5c80595d2fc58f9afd2b74ec42d2b018b5d92d40c62` |
| Dolphin paired controls | `42c86f80034250ec7ce1cd3bd606eac391793b12486f4f2358ef54449fd91d84` |
| Dolphin removal controls | `1cf48ae1ee5a4892aa044ee708fdaf1ca696b2b28b6bf2b36d1cb7eb401a6482` |
| Dolphin restored-gate precheck | `8ebf2e7eecc3a48768fbc67b0450da2f18c8fb14f738db910b151ad6aef9ff49` |
| AGMI remeasurement | `6cfbebdc4b8a20d95fd4c883ba88d8d385f10ceed20debc55724b6df0a984945` |

## What this supports

The evidence supports a restrained statement: on one frozen matched 5% LongMemEval-V2 development sample, the 2.3.8 candidate exceeded the matched AgentRunbook-R and Mem0 arms; on the frozen DolphinBench sample, it remained close to but behind Mem0; and the new audit binding plus external checkpoint detected all nine pinned AGMI attacks. It does not support claiming that AtMem beats the full benchmarks.

The next product iteration must improve action-memory formation and evidence completeness on a separately declared development subset, retain the fail-closed controls, and then rerun all 30 frozen Dolphin tasks once without tuning on their final outcomes.
