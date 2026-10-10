# Frozen 5% development benchmark results — 2026-10-10

## Scope and claim boundary

This report records matched development evidence for the AtMem 2.3.8 candidate. It is **not an official benchmark score** and does not establish leaderboard superiority. Every attempted case remains in the denominator. The frozen samples are 23 of 451 LongMemEval-V2 questions and 30 of 600 DolphinBench tasks.

## Results

| Benchmark | AtMem | Matched comparator | Interpretation |
|---|---:|---:|---|
| LongMemEval-V2 | 5/23 (21.7%) | AgentRunbook-R 4/23 (17.4%); Mem0 1/23 (4.3%) | AtMem leads both comparators on this frozen sample, but absolute accuracy is low and the sample is not an official score. |
| DolphinBench tasks | 9/30 (30.0%) | Mem0 7/30 (23.3%) | AtMem leads by two fully-passed tasks on this frozen sample. |
| DolphinBench checks | 32/97 (33.0%) | Mem0 27/97 (27.8%) | AtMem leads by five individual checks on this frozen sample. |
| AGMI, audit chain only | 8/9 detected | Historical AtMem 2.3.7: 0/9 | Eight store-tampering classes are detected; whole-store snapshot rollback remains undetectable without trusted external state. |
| AGMI, audit chain plus external checkpoint | 9/9 detected | Historical AtMem 2.3.7: 1/9 | All pinned attacks are detected when the checkpoint file is outside the attacker-controlled store directory. |

### Superseded Dolphin rerun after the first action-evidence fix

The exact `b550f26` wheel was installed into the benchmark environment and both arms were rebuilt from fresh stores. Both used `Qwen/Qwen3.5-9B` at revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a` through the Hugging Face inference-provider router and the same pinned `gpt-5.2-2025-12-11` judge.

| Arm | Tasks passed | Checks passed | System failures |
|---|---:|---:|---:|
| AtMem | 2/30 | 15/97 | 1 (`morgan:138`, provider error) |
| Mem0 OSS | 5/30 | 22/97 | 0 |

This intermediate run superseded the original 2/30 versus 3/30 comparison for product diagnosis, but is itself superseded by the final `b97d35e` rerun below. Its result did not support an AtMem-over-Mem0 Dolphin claim and motivated the evidence-neighbour and identity-routing work.

### Final Dolphin rerun after evidence-neighbour and identity routing fixes

The exact `b97d35e` candidate wheel was installed and AtMem was rerun on all 30 frozen tasks. The unchanged matched Mem0 arm was reused because its source, checkpoint, reader, judge, and task IDs were identical.

| Arm | Tasks passed | Checks passed | System failures |
|---|---:|---:|---:|
| AtMem | **9/30** | **32/97** | 0 |
| Mem0 OSS | 7/30 | 27/97 | 0 |

This final run supersedes the earlier Dolphin result. It supports the bounded statement that AtMem exceeded the matched Mem0 arm on this fixed 5% development surface. It remains insufficient for an official or full-benchmark superiority claim.

The LongMemEval controlled reader answered 19/23 with evaluator-verified evidence, compared with 5/23 using AtMem product context and 1/23 with no retrieval. This establishes a large evidence-delivery/use gap, but it does not by itself assign terminal blame. The reviewed eight-stage requirement ledgers are still required before separating formation, retrieval, packing, and reader-use failures case by case.

## Safety controls

DolphinBench fresh removal controls passed 30/30. In every removal case, the adapter returned `blocked_missing_requirement`, named the removed requirement, did not invoke the model, emitted zero tool calls, and did not mistake timeout, parsing, provider failure, or silent no-call for a safe block.

Restoring the evidence opened the gate in 30/30 cases. The paired removal-and-positive controls passed 29/30. The only failed pair was `morgan:138`: its restored gate opened, but the paid reader encountered a provider error before model or tool invocation. This is a system failure, not an over-blocked gate.

The action-quality result is still weak despite correct gate behavior. Inspection shows that AtMem often delivered long, loosely related evidence fragments and the reader copied those fragments into actions while omitting the exact requirement breakdowns. The next iteration must improve evidence precision and complementary packing without weakening the fail-closed controls.

## Execution integrity

- LongMemEval arms used the same frozen question IDs and reader/judge route. AtMem scored 5/23, AgentRunbook-R 4/23, Mem0 1/23, and no retrieval 1/23.
- LongMemEval recorded six AtMem system failures: three incomplete reader finalizations at the 20,000-token cap and three governance rejections outside the frozen selection. AgentRunbook-R had four incomplete finalizations; Mem0 had one.
- DolphinBench arms used source commit `81cb6f8405b40a9e76089cef650806a80af06ea2` and split SHA-256 `60c681f8e7ce0796ec0209294c885abe7dc0fe5a594226aa1035c401535658de`.
- The final Dolphin arms cover the same 30 task IDs. Both arms retained zero system failures. The Mem0 arm emitted warnings because optional spaCy and `fastembed` extras were absent; it nevertheless completed through the pinned matched adapter.
- AGMI used the unchanged upstream runner at commit `115493a41a7b41952f92ec07e1ea0932926e194f`, package 0.6.3, and an installed 2.3.8 wheel built from `fdc63de4b5ced0029f2717ee542b9600730ce3fd`. This is a vendor reproduction; an independent upstream rerun is pending.
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
| Fresh Dolphin matched results (`b550f26`) | `87c1b8140d80e293765a6c4260744c51db005767fd88f7e8e3ce0c50d4806d12` |
| Fresh Dolphin paired controls | `fb291c2004abe23a6a2e081ffa59ce4e0319e0ffd2adfd7a635c9a8684feab6f` |
| Fresh Dolphin restored-gate precheck | `62f9177cd219ce0a4cc2d60283407461b6190f28aa3d87de075eeee20332568d` |
| AGMI compact reproduction record | `60275b8d5b0d174ecbc66c8cb8bc940f84743f605dc6a04707d8ea9fc57ca22a` |
| AGMI unchanged-runner source output | `5498bedba335d6c7f40846e17e13413e22d25c298675aa34536c80315f60cceb` |
| AGMI 2.3.8 wheel | `61cf17963177bd7e9c6a5e9fe18a3be30356cc0b2d4d6d373b215a9fe12266dd` |
| Final Dolphin AtMem evaluation (`b97d35e`) | `aa5242c509f4748a4ab067a56e8bedda3787abfdbc6e0df0ce63b80e936fd358` |
| Matched Dolphin Mem0 evaluation | `2283f4b6c2c3ded66005171abeed395c2614378f3445af1ef656d259afbb712b` |
| Final Dolphin candidate wheel | `6ac2cc33e7a17792b15aeddbdf1d5a24efdb159e16781962503b69b37adfa97e` |

## What this supports

The evidence supports a restrained statement: on one frozen matched 5% LongMemEval-V2 development sample, the 2.3.8 candidate exceeded the matched AgentRunbook-R and Mem0 arms; on one frozen matched 5% DolphinBench development sample, it exceeded the matched Mem0 arm; and the new audit binding plus external checkpoint detected all nine pinned AGMI attacks. It does not support claiming that AtMem beats the full benchmarks.

The next product iteration must improve action-memory formation and evidence completeness on a separately declared development subset, retain the fail-closed controls, and then rerun all 30 frozen Dolphin tasks once without tuning on their final outcomes.
