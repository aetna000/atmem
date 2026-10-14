# Training plan: AtMem Memory Judgment Model

Date: 28 September 2026 (Australia/Sydney)

Status: Proposed experiment plan. No dependencies have been installed and no
model training, evaluation, or upload has been run. The hardware description is
from a read-only inspection on this date and may change as the machine is used.

Related research proposal:
[AtMem Memory Judgment Model](2026-09-28-atmem-memory-judgment-model.md).

## Decision

Use the current MacBook Air M2 for the first training study. It has an Apple M2
with an eight-core GPU and 16 GB unified memory. At inspection, its internal
volume had about 23 GiB free. The attached external volume named `MEM` had about
236 GiB free and is formatted exFAT.

This machine is appropriate for data work, small-model inference, and a
parameter-efficient fine-tuning pilot on a 0.6B reward model. It is not a good
machine for full fine-tuning, repeated 3B–8B experiments, or large-scale reward
model training. Unified memory is shared by macOS, the GPU, model weights,
training activations, and optimizer state; external disk capacity cannot increase
the memory available for a training step. The fanless Air may also slow down
during long workloads.

## Recommended first stack

Use a dedicated native-ARM Python 3.12 or 3.13 environment, PyTorch with its MPS
backend, Transformers, TRL `RewardTrainer`, and PEFT LoRA. PyTorch and MLX are not
currently installed in the inspected Python 3.14 environment. Keep the experiment
environment separate from AtMem's application dependencies.

Start with the Hugging Face `AutoModelForSequenceClassification` form of
`Skywork-Reward-V2-Qwen3-0.6B`. TRL's reward trainer accepts paired chosen/rejected
examples and PEFT adapters. It also documents saving the `score` module with the
adapter for causal-LM-backed reward models. This maps directly to the proposed
pairwise objective. Confirm the exact Skywork checkpoint's Transformers model
class and score-head behavior before committing to this route.

The first alternative is a small Qwen base model plus a separately trained score
head. The next comparison is `Qwen3-Reranker-0.6B`, which is a useful retrieval
baseline but has a different training objective. Apple MLX supports LoRA and
QLoRA for listed model families, but its published guide does not document
training this sequence-classification reward head. Treat MLX as an alternate
implementation after confirming model/head compatibility, not as an assumed
drop-in trainer for Skywork.

Official implementation references:
[TRL RewardTrainer](https://huggingface.co/docs/trl/main/en/reward_trainer),
[Transformers Qwen3](https://huggingface.co/docs/transformers/main/en/model_doc/qwen3),
[Apple MLX-LM LoRA guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md),
[Skywork checkpoint](https://huggingface.co/Skywork/Skywork-Reward-V2-Qwen3-0.6B),
[Qwen reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B).

## Hardware and storage plan

The Skywork model is 0.6B parameters. At bfloat16, weights alone are roughly
1.2 GB decimal; the training process also needs gradients for trainable
parameters, optimizer state, activations, framework memory, and macOS headroom.
LoRA keeps optimizer state small, making short candidate/question sequences
plausible on 16 GB. This is an estimate; actual peak memory depends on backend,
sequence length, batching, attention implementation, and package versions.

Initial operating point:

- One pair per device batch; use gradient accumulation if needed.
- Truncate to 512–1,024 tokens for the pilot; inspect truncation before training.
- LoRA rank 8 as a starting point, with score head included in saved trainable
  modules. Record trainable parameter count.
- Use a small, fixed pilot run and check validation and peak memory before
  increasing sequence length, batch size, or number of steps.
- Avoid full fine-tuning and avoid quantization-dependent QLoRA on the first
  MPS run. First verify stable bf16/fp16 LoRA support for the exact model and
  training stack.

Use `/Volumes/MEM` for versioned datasets, Hugging Face model cache, logs,
checkpoints, and exports. Keep an active scratch copy of the current checkpoint
and small temporary files locally if disk space allows. The internal volume had
only about 23 GiB free, so monitor it. The external drive is exFAT: do not rely on
it for POSIX permissions or symlink behavior, avoid unplugging it during a run,
and keep a second copy of final adapters and manifests. Do not place unencrypted
private user conversations or secrets on it. Use synthetic, public-with-permitted-
use, or explicitly authorized and de-identified examples for this research.

If an install or trainer requires more memory than available, first reduce
sequence length and batch size. If the 0.6B LoRA run remains unstable or too
slow, use a temporary cloud GPU for the same pinned experiment rather than
spending time adapting unsupported kernels. No provider has been selected and
no cloud budget is assumed.

## Work plan

### 1. Freeze the evaluation before training

Define one task record as a query, task time, authorized candidate set, budget,
and evidence labels. Freeze train/development/test partitions by conversation,
user, and source document. Keep whole dialogue histories and synthetic template
families within one partition. Do not train on LoCoMo questions used for reported
test scores. Resolve or explicitly exclude the four reported LoCoMo evidence
anomalies before publishing a confirmatory comparison.

Record baseline candidate rankings for native AtMem, its deterministic
metadata-aware score, the off-the-shelf Skywork Reward V2 Qwen3-0.6B reward
checkpoint, Qwen3-Reranker-0.6B, and the existing Jev integration. Keep
candidate pools fixed in the reranking study. Separately test candidate
generation and the downstream fixed reader; a reranker cannot rescue an absent
candidate.

### 2. Build a small audited preference set

Start with approximately 500 hand-reviewed task cases and several hard negatives
per case. This is a pilot for label quality and separability, not a claim that
500 cases suffice to train a useful model. Scale toward a few thousand reviewed
cases only if the pilot shows stable disagreement patterns and improvement on a
held-out development set.

Each pair compares two candidate memories for the same task. Annotators label:

- which candidate is more useful evidence, or whether they tie;
- whether either candidate directly supports the requested answer/action;
- whether evidence is complementary, contradictory, stale for this task, or
  insufficient;
- why a choice depends on task time, entity, relation, or evidence source.

Keep eligibility and policy labels outside this learned target. Generate hard
negatives for wrong entity, wrong relation, polarity, historical/current state,
incomplete procedures, missing exceptions, redundant evidence, and instruction-
like text embedded in memories. Shuffle candidate order and swap untrusted
metadata fields in tests to detect shortcuts.

Use a fixed written rubric; double-label a subset and adjudicate disagreements.
An LLM judge can propose candidate labels but cannot be the only source of truth.
When possible, use controlled add/remove/swap experiments with a fixed reader
to estimate whether a memory changes task success. Treat single-run changes as
noisy evidence, especially when two memories work together.

### 3. Run local inference and training pilot

Create a fresh ARM Python environment, install pinned Transformers, TRL, PEFT,
and PyTorch versions, and confirm PyTorch sees the Apple MPS device. Download
the pinned model revision to the external cache. Load the reward model for one
forward pass, verify output shape, and measure peak memory on short and
representative examples.

Train a LoRA adapter with pairwise preference loss. Keep a fixed seed and log
package versions, model commit, tokenizer, data manifest, hardware, peak memory,
wall time, and trainable parameters. Save intermediate and final adapters plus
the training configuration. Validate adapter reload and scoring on held-out
pairs. This pilot checks the path and label learnability; training loss alone is
not evidence of memory judgment quality.

If the Skywork sequence-classification head or MPS backward pass is incompatible,
do not patch the model ad hoc and call it equivalent. Switch to a documented
Qwen causal-LM pairwise output setup supported by MLX LoRA, or use the pinned
PyTorch/TRL stack on a cloud GPU. Preserve the same data and evaluation protocol.

### 4. Compare and decide

Compare frozen native rankings, simple metadata-aware ranking, Skywork Reward V2
Qwen3-0.6B **off-the-shelf**, Qwen3-Reranker-0.6B, AtMem-MJM post-trained from
the pinned Skywork checkpoint, and Jev on identical candidate sets. This isolates
the value of the existing generic reward model from the additional value of
memory-specific post-training. Then pass selected context to the same fixed
reader and score final answers or actions independently.

Use this scorecard. Preserve the published native/Jev values as exploratory
references; replace `Pending` only after each named condition has actually run
under the same frozen candidate set and evaluation protocol.

| Metric | Native order | Jev reranking | Skywork Reward V2 0.6B, off-the-shelf | AtMem-MJM, post-trained |
| --- | ---: | ---: | ---: | ---: |
| MRR@5 | 0.4259 | 0.5868 | Pending | Pending |
| Recall@1 | 0.3399 | 0.5423 | Pending | Pending |
| Recall@10 | 0.6495 | 0.6495 | Pending | Pending |

This is five table columns: the metric plus four systems. Separating off-the-shelf
Skywork and post-trained AtMem-MJM is necessary to tell whether gains come from
the existing general reward model or from AtMem's memory-specific data and
training. Skywork Reward V2 has already been trained on general preference data;
“off-the-shelf” here means no additional AtMem memory training.

Report MRR and Recall at stated cutoffs, all-required-evidence coverage,
sufficiency, final task success, abstention quality, tokens, p50/p95 latency,
peak memory, errors, and inference cost. Estimate uncertainty by conversation
or trajectory rather than treating all questions as independent. Include
no-useful-candidate cases; selecting the least bad option must not look like
successful judgment.

Only propose product integration if the trained local model beats both generic
local ranking and metadata-aware baselines at a predeclared quality/latency
operating point, remains robust on held-out scenarios, and preserves AtMem's
eligibility and final validation boundaries. Otherwise, retain the stronger
generic ranker or deterministic path.

## Immediate next actions

1. Write the data schema, annotation rubric, and conversation-level split plan.
2. Resolve the LoCoMo anomaly policy and freeze a test subset not used for
   training.
3. Create a separate Python 3.12/3.13 environment and pin the software stack.
4. Check the Skywork reward head on MPS at inference, then one training batch.
5. Label the 500-case pilot and compare generic baselines before scaling labels.
6. Train one LoRA adapter, run held-out comparisons, and decide whether further
   data or a cloud GPU is justified.

No installation, model download, training run, or test was performed while
writing this plan.
