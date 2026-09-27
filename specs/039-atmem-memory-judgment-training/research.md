# Research Notes: AtMem Memory Judgment Training

## Existing evidence

The current comparison is an exploratory LoCoMo result with 1,986 questions
from ten conversations. Native AtMem order has MRR@5 0.4259, Recall@1 0.3399,
and Recall@10 0.6495. The historical Jev aggregate reported MRR@5 0.5868,
Recall@1 0.5423, and Recall@10 0.6495, but its artifact did not preserve
per-question rankings. A later authorized Jev 1.13.0 rerun provides the
case-level matched comparator: MRR@5 0.5880, Recall@1 0.5433, and Recall@10
0.6495. All arms used the same frozen top-ten candidate pool, so differences
measure ordering rather than candidate discovery.

The review reports four evidence-reference anomalies and identifies the result
as exploratory. Per-question outputs and the exact data digest exist in the
repository's `research/production_benchmarks/results/` and
`specs/035-production-memory-benchmarks/`. After spec approval, copy required
inputs to the external experiment root and verify their digests there. Do not
write generated study artifacts into those internal paths.

The stored historical Jev aggregate did not retain per-question Jev rankings.
After the user explicitly authorized benchmark-text egress, Jev 1.13.0 was
rerun against the exact frozen 1,986-question / 19,860-candidate pool in 40
batches of 50. It returned all candidate probabilities with no errors. The
fresh paired result is MRR@5 0.5880 and Recall@1 0.5433; the earlier aggregate
(0.5868 / 0.5423) remains historical context only. AtMem-MJM is below fresh Jev
with a conversation-cluster MRR difference interval of [-0.1355, -0.1110].

## Candidate starting points

- [Skywork Reward V2](https://arxiv.org/abs/2507.01352) reports eight general
  reward models from 0.6B to 8B parameters and describes its curated preference
  training mixture. The
  [Qwen3 0.6B checkpoint card](https://huggingface.co/Skywork/Skywork-Reward-V2-Qwen3-0.6B)
  identifies a sequence-classification reward model and an Apache-2.0 model
  license. This is the recommended common checkpoint: first use it as-is, then
  post-train it with AtMem-specific preferences. In the completed pilot,
  off-the-shelf MRR@5 was 0.4540 and AtMem-MJM reached 0.4632 on the same pool.
- [TRL RewardTrainer](https://huggingface.co/docs/trl/main/en/reward_trainer)
  accepts pairwise preference data and PEFT configuration. TRL was not present
  in the frozen local environment, so the pilot uses a transparent PyTorch
  Bradley--Terry pairwise-loss loop over the same chosen/rejected contract.
  This is an implementation adjustment, not a change in objective.
- [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) is a
  strong generic retrieval-ranking baseline. It is separate from the required
  four-arm scorecard; add it only as a clearly labelled optional fifth system if
  it can be evaluated without delaying the requested sequence.
- [Apple MLX-LM LoRA guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
  documents LoRA/QLoRA for supported causal language models. It does not by
  itself establish a drop-in training path for the Skywork reward head, so do
  not assume MLX can train this exact architecture.

## Data-design decision

Do not train on either LoCoMo or LongMemEval-V2 in this study. Keep the primary
LoCoMo benchmark and the already-staged LongMemEval-V2 corpus strictly for
evaluation. Generate AtMem-specific training preferences from controlled,
synthetic memory episodes with deterministic known support, temporal state,
source strength, conflicts, and distractors. Hold out full task templates and
scenario families, not merely randomized rows. Before broader or public use,
have the owner audit a sample and label edge cases. The pilot records
deterministic agent QA and marks owner review as pending; it does not claim
human adjudication. This avoids dependence on private user histories and
prevents an LLM teacher from being the sole ground truth.

## Input and scoring design

Use one versioned template for all three neural scoring conditions. Give the
model the task/query and one candidate memory at a time with the same visible
fields: content and explicitly trusted evidence metadata. Never include answer
text, gold evidence IDs, benchmark category names, conversation identity, or
split information. A scalar reward score orders candidates; a separate
development-only rule handles insufficient evidence. Do not describe the raw
score as a probability unless separately calibrated and verified.

AtMem selects from returned IDs and revalidates them against current canonical
state before context delivery. Candidate content cannot promote itself by
claiming to be trusted, current, high-confidence, or authoritative.

## Storage and execution

The inspected machine is an Apple M2 MacBook Air with 16 GB unified memory.
The `MEM` USB volume is exFAT and had about 236 GiB free at inspection. Use a
small LoRA run with conservative batch/sequence limits. External disk capacity
helps store model files and outputs but does not increase unified memory.

After the user approves the spec, put all experiment-owned files under
`/Volumes/MEM/AtMem-MJM/`, including the run environment, package caches,
Hugging Face cache, source snapshot, data, temporary files, and outputs. Use a
local run guard that verifies the mount and output root before work begins.
Because exFAT does not provide normal POSIX symlink and permission semantics,
use copy-based environments/caches where necessary and verify actual writes.
If storage fails, stop rather than falling back to internal paths.

## Claim limits

The target claim is a ranking comparison on one conversation-memory benchmark.
It does not establish better generated answers, better actions, improved
authorization, or broad memory quality. Ten conversation clusters limit the
strength of clustered uncertainty estimates. Preserve the per-question results,
known anomalies, and score differences; call a Jev victory only under the
predeclared interval rule in the specification.
