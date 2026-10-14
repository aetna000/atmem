# AtMem Memory Judgment Model: a local, governed memory selector

Date: 28 September 2026 (Australia/Sydney)

Status: Research proposal. No new model has been trained, downloaded, or
benchmarked for this note. “AtMem-MJM” is a working name, not a released product.
This complements the proposed retrieval-quality gate; it does not replace or
modify that specification.

## Recommendation

Build an AtMem-specific memory judgment model using an existing small open-weight
backbone. Start by comparing adaptation of **Skywork Reward V2 Qwen3 0.6B** with
**Qwen3-Reranker-0.6B**, plus a same-size base-model initialization control.
Choose the initialization from measured memory-task results.

The objective is to select useful evidence from already admissible memory under
a limited context budget. Deterministic AtMem code retains authority over
eligibility, lifecycle, context construction, and delivery. The model provides
advisory scores and eventually bounded evidence-support predictions.

The central question is:

> Does memory-specific training improve evidence sufficiency and downstream task
> success beyond strong generic reranking, at a useful local operating cost?

## Clarify what Jev means

TypeSafe describes Jev as a general model for typed probabilistic decisions,
with a specialized architecture, parallel output sampling, and its RLCD training
method. It is not presented as a memory-specific model. We use it for that role
in the existing AtMem experiment.

Our proposal borrows the bounded decision interface, not an asserted reproduction
of Jev's architecture or training. A schema-valid choice may still be wrong;
structural output guarantees do not establish semantic correctness. Calibration
and speed claims require testing on our workload.

Sources: [TypeSafe introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
and [Choice primitive](https://docs.typesafe.ai/primitives/choice).

Use a separate AtMem model name so readers can distinguish our trained artifact
from TypeSafe's Jev and from the AtMem–Jev integration.

## Candidate models and their roles

| Family | Verified relevant sizes | Proposed role |
| --- | --- | --- |
| Skywork Reward V2 Qwen3 | 0.6B, 1.7B, 4B, 8B | Scalar reward initialization; 0.6B is the first adaptation candidate. |
| Skywork Reward V2 Llama | 1B, 3B, 8B | Alternative reward family for later comparison. |
| Qwen3-Reranker | 0.6B, 4B, 8B | Essential retrieval-trained baseline and competing initialization. |
| JudgeLRM | 3B and 7B in the cited release | Offline evaluator or independently checked labeling assistant. |
| Atla Selene 1 Mini | 8B | Offline scoring and critique baseline. |
| JudgeLM | 7B, 13B, 33B | Historical judge baseline; not the first local deployment choice. |
| ArmoRM | 8B | Architectural inspiration for multiple supervised judgment dimensions. |

Skywork reports training its V2 series on a curated 26-million-pair preference
mixture. Those are general response preferences, not memory-utility labels.
Transfer to memory selection is a hypothesis. The original Selene Mini model
card credits **Atla**; use its primary artifact rather than attributing the model
to NVIDIA from a secondary table.

Primary sources:
[Skywork model card](https://huggingface.co/Skywork/Skywork-Reward-V2-Qwen3-0.6B),
[Skywork paper](https://arxiv.org/abs/2507.01352),
[Qwen reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B),
[JudgeLRM](https://github.com/NuoJohnChen/JudgeLRM),
[Atla Selene Mini](https://huggingface.co/AtlaAI/Selene-1-Mini-Llama-3.1-8B),
[JudgeLM](https://github.com/baaivision/JudgeLM), and
[ArmoRM](https://huggingface.co/RLHFlow/ArmoRM-Llama3-8B-v0.1).

Pin checkpoint revisions, tokenizer/template, training-data provenance, and
applicable weight/base-model/data licenses before releasing a derived artifact.
Open weights do not establish identical redistribution terms across families.

## Existing AtMem evidence

The [19 September review](../specs/035-production-memory-benchmarks/review.md)
records an exploratory comparison on 1,986 LoCoMo questions in ten conversations:

| Metric | Native order | Jev reranking | Skywork Reward V2 0.6B, off-the-shelf | AtMem-MJM, post-trained |
| --- | ---: | ---: | ---: | ---: |
| MRR@5 | 0.4259 | 0.5868 | Pending | Pending |
| Recall@1 | 0.3399 | 0.5423 | Pending | Pending |
| Recall@10 | 0.6495 | 0.6495 | Pending | Pending |

The table has four evaluated systems plus the metric column. The Skywork column
means the published reward checkpoint used as-is, without memory-specific
fine-tuning. It is already a trained general preference model, not the raw
Qwen3-0.6B base model. AtMem-MJM is the same initialization after memory-specific
post-training. Keeping both columns lets us separate the benefit of Skywork's
existing reward model from the benefit of AtMem's training data and objective.
The existing native and Jev results are exploratory and use the same AtMem
top-ten pool; pending results have not been measured.

This is encouraging evidence for improving order within a retrieved pool.
It does not establish answer-quality improvement, new candidate coverage, or
superiority to a strong local reranker. Four evidence-reference anomalies remain
disclosed. The recorded 3.32-second median and 8.74-second p95 remote latencies
are per batch, not per agent turn. They cannot be directly compared with a vendor
single-request speed claim. No new replication is reported here.

See also the [existing article](2026-09-19-atmem-jev-article.md).

## Authority and model judgment

Proposed sequence:

1. AtMem authorizes the requesting identity and bounds candidate discovery.
2. Retrieval nominates records within that boundary.
3. AtMem filters eligible records and authorizes what the chosen local or hosted
   scorer may receive.
4. AtMem-MJM scores the supplied candidates using task state and evidence.
5. AtMem selects a budgeted evidence set, with redundancy handling and an
   explicit no-useful-evidence outcome.
6. AtMem revalidates current canonical state and policy before delivery and
   records the selected package and supported exposure evidence.

The initial eligibility gate is not a permanent grant. Deletion, source version,
scope, or policy can change during inference. Bind judgment to supplied IDs,
record versions/digests, and the request; reject stale or malformed results.
The model cannot create IDs, expand scope, approve an otherwise forbidden
record, or convert a relevance score into permission.

Separate deterministic policy application from uncertainty about the world.
AtMem can enforce a recorded expiry or issued principal's authority. It cannot
make an unknown source trustworthy just by implementing the rule in code.
Semantic support, inferred relevance, and uncertain source attributes require
honest uncertainty; unsupported attributes must not be silently treated as fact.

On model failure, use the existing governed fallback or withhold under the same
contract. Never relax eligibility to keep context nonempty. An empty eligible
pool needs no model call.

## What the model should learn

First version: scalar evidence-utility ranking. Input includes the original
question or task, relevant temporal target, candidate text, source-bound metadata,
and token cost. Distinguish observation time, ingestion time, and effective time.
Free text saying “verified” or “confidence 0.99” is candidate content, not trusted
metadata. Retain the origin and meaning of confidence estimates, including
missing or incomparable values.

Do not train blanket rules such as “newer always wins” or “user stated always
beats inferred.” Examples need contrasting tasks:

| Task | Evidence that may be preferred |
| --- | --- |
| What is the current confirmed delivery address? | Yesterday's explicit confirmation, when still valid |
| Where was the order delivered three years ago? | The contemporaneous delivery record |
| Which command fixed this exact error? | The matching successful execution and its conditions |
| What exceptions apply to this procedure? | The exception and triggering condition, even if a general rule is more similar |
| Which details remain unknown? | Evidence of missing confirmation; abstention may be appropriate |

The proposed A-versus-B example with confidence 0.46 versus 0.97 is therefore
underspecified. A high-confidence fact about the wrong customer, attribute,
period, or operation should not win. If A and B are inconsistent and neither is
decisive, selecting both with visible disagreement or withholding may be better.

Second version, only if supported by data: separate predictions for direct
support, background-only relevance, contradiction, and insufficient evidence.
These are advisory semantic judgments, not safety or authorization labels.
Auxiliary heads need separately labeled targets and calibration checks; adding
names to a score vector does not make it interpretable.

## Why scalar ranking is only the first step

The three individually highest-scoring memories may repeat the same fact while
omitting a prerequisite or exception. The intended objective is the utility of
the selected set under a token budget. Begin with independent scoring plus a
fixed diversity-aware packer. Then test whether conditioning on already selected
evidence improves marginal utility, including complementary evidence pairs.

A preference score is not automatically a probability that a memory is correct
or useful. Pairwise training can learn relative order without learning when all
candidates are poor. Include ties, neither-useful cases, explicit support labels,
and a separate held-out calibration set. Softmax alone does not establish
calibration or justify a no-evidence threshold.

The existing [retrieval-quality proposal](../specs/038-retrieval-quality-benchmark-gate/spec.md)
distinguishes formation, retrieval, sufficiency, and delivery. AtMem-MJM belongs
within that design. It cannot recover a missing UI value, lost temporal relation,
or procedure step that formation discarded, nor can reranking find evidence
absent from the candidate pool.

## Training data and experiment design

Start with a pilot of roughly 2,000 carefully reviewed cases to establish label
quality, failure types, and baseline gaps. This is a proposed planning size, not
an estimate of sufficient training data. Scale only if learning curves justify
the cost.

Combine controlled synthetic histories, properly licensed public examples, and
explicitly authorized traces. Use human-reviewed evidence labels, hard negatives,
and task outcomes from controlled interventions. Larger judges can propose
labels, but agreement with one teacher is not ground truth.

Useful hard negatives include wrong entity or relation, negation, historical
versus current state, incomplete procedure, missing exception, redundant
evidence, forged confidence claims, and instructions embedded in memory text.
Metadata swaps and candidate-order shuffles should reveal whether the model
learned shortcuts rather than the actual task.

Compare task outcomes after adding/removing or swapping evidence with the same
reader and budget. Such interventions are noisy estimates, especially where
memories work jointly; repeat them and preserve disagreement rather than
labeling every change causal proof. Usage counts are exposure-biased and cannot
be treated as independent evidence of usefulness.

Keep whole users, conversations, trajectories, source documents, and synthetic
template families separated across train/development/test. Do not turn our
existing LoCoMo evaluation questions into training data and still claim a held-out
comparison on them. Reserve calibration data separately; frozen final tests must
not become the source of repeated design decisions.

## Comparison with Jev and alternatives

Use two studies so training and integration changes are not confused:

1. **Frozen-pool ranking:** identical eligible candidates, metadata visibility,
   input limits, context budgets, and downstream packer. Compare native order,
   a simple metadata-aware ranker, generic Qwen reranking, unadapted Skywork,
   adapted Skywork, adapted Qwen reranking, a matched base initialization, and
   pinned Jev. Supply equivalent task criteria through each supported interface.
2. **End-task utility:** the same fixed reader/agent consumes the selected
   context; use independent answer or action scoring. Repeat on another reader
   to test whether improvements generalize.

Use LoCoMo for continuity with the earlier experiment, with an explicit anomaly
protocol, and LongMemEval/LongMemEval-V2 for temporal and experience-based tasks.
Verify each dataset's permitted use and splits when building the experiment.
Run authority and lifecycle conformance separately from utility measurement.

Report ranking metrics, all-required-evidence coverage, context sufficiency,
answer/action success, abstention quality, tokens, p50/p95 request and end-to-end
latency, peak memory, errors, and actual deployment cost. Compare outcome-defined
probabilities using reliability plots and Brier/log-loss where appropriate;
never relabel raw reward scores as calibrated probabilities.

Group uncertainty estimates by conversation or trajectory. Retain per-case
records, model revisions, prompt/templates, batching, truncation, hardware, and
precision. Distinguish warm inference, cold load, and remote transport. Remote
comparison inputs require their own egress authorization; current remote-service
responses should not be presumed permissible training data.

## Local deployment and a go/no-go decision

0.6 billion parameters at two bytes per parameter is roughly 1.2 GB of weight
storage before runtime overhead. Quantization can reduce weights, but actual
RAM, latency, and quality depend on sequence length, candidates, batching,
backend support, and hardware. Verify support for the chosen score head; a
backend capable of chatting with the base model need not serve that head.

Run judgment at context-selection points when needed, not continuously by
default. Bound input sizes and batch work. Cached scores must be bound to the
task, source version, model revision, and relevant metadata; final authority
checks still run on cache hits.

Advance to product integration only if the adapted model improves a predeclared
utility/cost operating point over strong local baselines, behaves acceptably on
no-evidence and adversarial cases, and preserves all deterministic boundaries.
If an off-the-shelf reranker is sufficient, ship that result rather than forcing
a proprietary model story.

The potential contribution is a tested memory-utility objective, a credible
preference/evidence dataset, and a compact model that helps agents use the right
admissible evidence. Its value comes from those results, not from calling a
generic reward model a new kind of judge.
