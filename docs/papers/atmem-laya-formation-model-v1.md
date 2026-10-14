# Bounded System-One Memory Formation
## Training and Evaluating a Finite-Choice Laya Model for Governed Agent Memory

> **Superseded historical paper:** this manuscript describes a synthetic-trained
> model that is not the current Spec 041 artifact. Its results must not be used
> to claim performance for the replacement authentic-conversation model.

**Javad Taghia**  
AtMem Project  
Preprint, 11 October 2026

### Abstract

Long-lived agents need to decide not only what information is relevant, but whether an observation is admissible as memory, how it changes canonical state, and whether the resulting state can support a later query. These are structured decisions with asymmetric failure costs: storing an unsupported claim, crossing an authorization boundary, or updating the wrong record can be more damaging than declining to remember. We present **AtMem Laya Formation Model v1**, a local, non-autoregressive decision model specialized for five bounded memory-formation questions: operation, memory class, evidence support, target selection, and retrieval usefulness. The model is deliberately placed below an independent authority layer; it proposes finite choices but cannot authorize storage, disclosure, deletion, or retrieval.

The model was trained from a pinned Laya encoder on 60,000 decisions generated from 12,000 fictional scenarios. Identity-, template-, semantic-chain-, and paraphrase-disjoint splitting yielded 39,600 training, 6,500 validation, 6,700 calibration, and 7,200 sealed decisions. Full-encoder RLCD/proper-scoring training ran for four epochs on one RTX 5090 in 4,390.91 seconds and cost USD 1.541821. A soft cross-entropy control tied the selected RLCD run under the preregistered validation/calibration ordering; a frozen lexical tie-break selected RLCD without inspecting sealed labels. The selected artifact achieved 100% accuracy and macro-F1 on the sealed synthetic set, with NLL 2.4447e-13, Brier score 3.5791e-25, and ECE 2.4447e-13. A blinded 400-item sealed audit found 400 exact agreements and zero critical defects.

On a separately frozen 80-scenario end-to-end synthetic workflow, the fine-tuned model produced exact canonical state in 100% of scenarios with zero safety violations, compared with 42.5% and 19 violations for deterministic AtMem rules and 36.25% and three violations for base Laya. Its later-query sufficiency was 100% versus 8.75% for both baselines. Paired cluster bootstrap differences over 10,000 resamples were +0.575 [0.4684, 0.6835] in exact state and +0.9125 [0.8481, 0.9639] in combined sufficiency relative to deterministic AtMem. Retrieval MRR@5 itself tied the deterministic system at 0.3798; the gain arose from forming the right memory, not from reranking. Median formation latency was 272.29 ms on the measured Apple-silicon CPU, versus 2.31 ms for deterministic rules. We report unsuccessful Qwen and unavailable Jev arms as inconclusive, not as wins. No LoCoMo, LongMemEval, production, adversarial-public-corpus, multilingual, or real-user superiority claim is made. The paper supplies lineage, threat model, training protocol, failure semantics, reproducibility manifests, and an end-user installation and rollback appendix.

**Keywords:** agent memory; memory formation; typed decisions; selective prediction; calibration; proper scoring rules; synthetic data; safety boundary; reproducibility

<!-- PAGEBREAK -->

# 1. Introduction

Persistent memory changes an agent from a stateless responder into a system that can accumulate consequences. The important operation is therefore not merely retrieval. Before a record can be retrieved, a system must decide whether evidence should create a new memory, update an existing one, supersede an obsolete state, produce no change, or be rejected. It must distinguish durable facts from temporary context, episodes, procedures, and non-memory. It must decide whether the evidence is sufficient, identify the only admissible target, and estimate whether the proposed canonical state will later answer a legitimate query. We call this collection of decisions **memory formation**.

General-purpose generative models can express these judgments, but generation introduces an unnecessarily large action space. A decoder may emit a label outside the schema, add an explanation that leaks context, or vary semantically equivalent outputs. It may also require a remote provider for a decision whose output belongs to a small closed set. AtMem instead treats formation as five coupled finite-choice problems. A compact encoder scores all legal alternatives in one forward pass. This design does not make the classifier an authority. Authentication, scoping, policy, canonical-state loading, optimistic concurrency, revocation, and mutation remain deterministic responsibilities of AtMem.

This work makes four contributions.

1. We define a bounded formation interface that separates learned semantic judgment from authorization and state transition. The interface is closed under explicitly versioned questions, choices, tokenization, calibration, and request digests.
2. We construct and publish a 12,000-scenario fictional corpus containing 60,000 decisions, with group-disjoint splits and explicit representation of contradiction, credentials, cross-scope content, private content, sensitive content, duplicates, and temporal updates.
3. We train and select a full-encoder Laya derivative using a preregistered comparison between RLCD/proper-scoring and soft cross-entropy objectives. We retain exact hashes for source, base model, dataset, questions, calibration, model, and portable export.
4. We evaluate both decision accuracy and downstream state utility. The frozen workflow distinguishes formation quality from retrieval ranking and reports paired uncertainty, latency, safety violations, abstention behavior, failure arms, and deployment rollback.

The central empirical result is that specialization changes what is stored. On the synthetic workflow, the fine-tuned model did not improve the ranking function over deterministic AtMem; it improved the canonical memory that ranking operated upon. This distinction matters because a retrieval benchmark alone can hide a formation failure, while a formation benchmark alone can hide an unusable stored state.

The result is intentionally bounded. Perfect performance on a deterministic synthetic oracle is evidence of specification learning and artifact integrity, not evidence of universal memory intelligence. Generator regularity can make the task easier than production traffic. Public conversational benchmarks test different distributions and longer temporal structures. We therefore formulate the current result as a release-engineering and systems claim: a pinned, opt-in local proposal model can reproduce the defined AtMem formation policy on held-out synthetic groups, improve a frozen synthetic store-to-retrieve workflow, remain behind an authority boundary, and be installed or rolled back reproducibly.

<!-- PAGEBREAK -->

# 2. Related Work

## 2.1 Long-term conversational memory

LoCoMo introduced long-horizon conversations averaging roughly 300 turns and 9K tokens across as many as 35 sessions, with human verification and tasks spanning question answering, summarization, and multimodal dialogue [1]. LongMemEval decomposed long-term chat memory into information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention, using 500 curated questions in scalable histories [2]. LongMemEval V2 extends the focus toward more agentic and difficult settings [3]. These benchmarks motivate end-to-end evaluation, but they do not isolate all formation decisions required by a governed store. Our synthetic protocol complements rather than replaces them: it exposes the intended transition label and can attribute downstream failure to the memory state before retrieval.

Mem0 describes a production-oriented memory architecture that extracts, consolidates, and retrieves salient conversational information and reports accuracy, latency, and token-cost trade-offs on LoCoMo [4]. AtMem shares the premise that memory is a managed subsystem rather than raw transcript accumulation. The present work differs in scope: it studies a small proposal model inside a versioned authority-and-receipt architecture and does not claim a public benchmark comparison against Mem0.

## 2.2 Encoder decision models

BERT established the effectiveness of bidirectional transformer encoders that can be fine-tuned by adding task heads [5]. Laya exposes non-autoregressive typed `choice`, `score`, and `noul` decisions over textual state [6]. Its closed-choice interface is a natural match for formation because the set of admissible actions is known before inference. We pin `convaiinnovations/laya` at revision `7b928d...` and Laya source at `688046...`; reported upstream capabilities outside those revisions are not silently inherited by this artifact.

The term *System One* is used operationally, not cognitively: the component is a fast proposal mechanism for routinized decisions, while slower deterministic validation or bounded escalation handles ambiguity. It does not assert human-like intuition, reasoning, or consciousness.

## 2.3 Proper scoring, calibration, and abstention

A scoring rule is strictly proper when the expected score is uniquely optimized by reporting the true belief distribution [7, 8]. Brier's quadratic score supplies a classic multiclass probability loss [9]. Laya's RLCD path combines spherical and ranked-probability terms; the AtMem run uses weights 0.75 and 1.0 respectively. Properness is relevant because confidence is used for abstention, not merely displayed.

Neural classifiers can be systematically miscalibrated even when accurate [10]. Temperature scaling offers a simple post-hoc correction fitted on data isolated from model optimization [10]. Expected calibration error (ECE) is widely used but depends on binning and is not a complete guarantee. Selective classification frames abstention as a risk-coverage trade-off [11]. AtMem therefore binds calibration externally, validates its identity, and routes rejected or malformed proposals to deterministic fallback or bounded review. A confidence number never grants authority.

## 2.4 Documentation and reproducibility

Model cards advocate explicit reporting of intended use, evaluated conditions, limitations, and subgroup behavior [12]; datasheets similarly document dataset motivation, composition, collection, and maintenance [13]. Reproducibility checklists call for exact hyperparameters, compute, selection criteria, and uncertainty [14]. Our release includes a model card, dataset card, immutable Hub revisions, signed receipts, environment versions, checksums, and separation between model selection and sealed evaluation. The paper treats absent comparison arms as missing evidence rather than converting infrastructure failure to a numerical zero.

<!-- PAGEBREAK -->

# 3. System Model and Threat Boundary

## 3.1 State-transition setting

Let `x_t` denote newly authorized evidence at time `t`, `M_t` the canonical memory state visible within the actor's scope, and `P` the deterministic policy. A proposal model `f_theta` emits a tuple of five categorical distributions:

`f_theta(x_t, M_t, Q) = (p_op, p_class, p_support, p_target, p_useful)`,

where `Q` is the immutable question bundle. The model never directly computes `M_(t+1)`. Instead, an authority function validates the proposal:

`M_(t+1) = A(P, actor, scope, version(M_t), x_t, proposal, calibration)`.

The authority may accept, reject, require review, or apply deterministic fallback. It rechecks evidence, target existence, state version, deletion and revocation races, and output finiteness. This design prevents a semantically plausible prediction from becoming implicit permission.

## 3.2 Closed decision surface

The five questions are:

| Head | Purpose | Representative legal choices |
|---|---|---|
| operation | Proposed state transition | ADD, UPDATE, SUPERSEDE, NOOP, REJECT |
| memory_class | Retention semantics | durable, temporary, episode, procedure, nonmemory |
| evidence_support | Whether evidence entails the proposal | supported, insufficient, contradictory, disallowed |
| target_selection | Which existing record may change | one enumerated target or no target |
| retrieval_usefulness | Whether canonical state can support the future query | useful, not useful, unsafe/unsupported |

Exact options are supplied by `questions.json`; the table is explanatory, not a replacement for that file. Options are request-bound and target identifiers are enumerated rather than generated. The model cannot invent a target outside the current authorized candidate set.

## 3.3 Adversary and failure assumptions

We assume input text may be malformed, contradictory, overlong, sensitive, cross-scope, or crafted to influence the classifier. We do not assume the model recognizes every attack. The architecture therefore treats model output as untrusted data. An adversary must not gain storage, disclosure, or deletion authority by increasing confidence, manipulating a target string, causing non-finite scores, forcing truncation, or making an optional provider fail.

The following events are fail-closed with respect to model authority: missing artifacts; revision or digest mismatch; token overflow; silent truncation attempt; non-finite or unnormalized scores; unknown choice; calibration mismatch; unavailable device; stale canonical version; policy denial; provider timeout; or invalid escalation output. "Fail-closed" here does not always mean the whole product stops. It means the learned path cannot widen access or mutate state. AtMem may use its existing deterministic behavior, abstain, or request review according to local policy.

## 3.4 Privacy and egress

Primary inference is local after explicit artifact download. Optional AtBot escalation is separately configured, limited to one call, and receives only already-authorized minimum context under provider-egress policy. The frozen end-to-end run required zero escalations and zero provider calls. This is a measurement of that run, not a promise that all future inputs remain local when escalation is enabled.

<!-- PAGEBREAK -->

# 4. Formal Task and Losses

For scenario `s`, question `q`, and legal choice set `C_q`, the encoder produces logits `z_(s,q,c)` for each `c in C_q`. Temperature-scaled probabilities are

`p_(s,q,c) = exp(z_(s,q,c)/T_q) / sum_j exp(z_(s,q,j)/T_q)`.

The predicted label is `argmax_c p_(s,q,c)` if the output passes schema, identity, and confidence gates. Otherwise it is an abstention event. Temperatures are external serving artifacts rather than mutable values hidden in the checkpoint.

## 4.1 Soft cross-entropy control

For target distribution `y`, the control objective is

`L_CE = - sum_c y_c log p_c`.

Targets are finite distributions, allowing label smoothing or graded supervision when defined by the data contract. Cross-entropy is a strictly proper log score under standard conditions and provides a conventional reference optimization path.

## 4.2 RLCD/proper-scoring objective

The selected training path uses upstream RLCD with four sampled perturbations per example and Gaussian exploration sigma annealed from 0.4 to 0.1. The objective combines a spherical component and ranked probability score:

`L_RLCD = w_sph L_sph + w_rps L_rps`,

with `w_sph = 0.75` and `w_rps = 1.0`. For an ordinal ordering of `K` choices, the ranked probability score is

`RPS(p,y) = sum_(k=1)^(K-1) (sum_(j<=k) p_j - sum_(j<=k) y_j)^2`.

The spherical score rewards alignment between the predicted vector and the target while accounting for vector magnitude. Exact implementation semantics are inherited from pinned Laya source revision `688046...`; the equation communicates the functional family and does not supersede executable code.

## 4.3 Evaluation metrics

For `N` decisions, accuracy and macro-F1 measure discrete correctness. Negative log likelihood and multiclass Brier score are

`NLL = -(1/N) sum_i log p_(i,y_i)`,

`Brier = (1/N) sum_i sum_c (p_(i,c) - 1[y_i=c])^2`.

ECE partitions predictions into confidence bins `B_m` and computes

`ECE = sum_m |B_m|/N * |accuracy(B_m) - confidence(B_m)|`.

The workflow additionally measures exact canonical-state match, safety violations, retrieval MRR@5, recall at `k`, negative-query abstention, and *combined sufficiency*: whether the state produced by formation contains admissible evidence adequate for the later query. Combined sufficiency is deliberately upstream-sensitive; an excellent ranker cannot retrieve a fact that formation rejected or corrupted.

## 4.4 Paired uncertainty

Cases are clustered by scenario because the five heads share evidence and targets. Confidence intervals resample the 80 scenario clusters, not 400 individual decisions, with 10,000 paired bootstrap replicates and seed 410239. For arms `a` and `b`, each replicate estimates `Delta* = metric_a* - metric_b*`; the reported 95% interval uses the 2.5 and 97.5 percentiles. This preserves within-scenario dependence and avoids artificial precision from treating heads as independent.

<!-- PAGEBREAK -->

# 5. Data Construction

## 5.1 Generator and source policy

The corpus was produced by generator version 1.3.0 with seed 410239. It contains only fictional users, organizations, credentials, events, and identifiers. No production transcript or customer memory was used. The published dataset is `atmem/atmem-laya-formation-v1` at immutable revision `4436089...`, with manifest SHA-256 `d67d371...`.

Each of 12,000 scenarios yields one labeled instance for every formation question, giving 60,000 decisions. A scenario comprises authorized state, incoming evidence, candidate targets, policy metadata, expected canonical transition, and a future query used to judge retrieval usefulness. The generator creates both positive transitions and safety-critical negatives rather than teaching only whether a sentence appears memorable.

## 5.2 Operation and memory-class balance

| Operation | Scenarios | Share |
|---|---:|---:|
| ADD | 2,228 | 18.57% |
| UPDATE | 2,228 | 18.57% |
| SUPERSEDE | 2,229 | 18.58% |
| NOOP | 2,229 | 18.58% |
| REJECT | 3,086 | 25.72% |

| Memory class | Scenarios | Share |
|---|---:|---:|
| durable | 2,880 | 24.00% |
| temporary | 2,400 | 20.00% |
| episode | 2,400 | 20.00% |
| procedure | 2,400 | 20.00% |
| nonmemory | 1,920 | 16.00% |

REJECT is intentionally more common because several threat families should terminate without mutation. The other transition classes are nearly balanced. Memory classes avoid a dominant durable-fact shortcut.

## 5.3 Safety and temporal phenomena

The scenario inventory contains 721 contradiction cases, 1,091 credential cases, 706 cross-scope cases, 924 private-content cases, 1,715 sensitive-content cases, 2,400 duplicate cases, and 4,800 temporal cases. Counts overlap because one scenario can be both temporal and sensitive or both duplicate and private. Credential strings are fictional and withheld from unnecessary publication surfaces.

Temporal cases cover correction, expiration, supersession, and preservation of history. Duplicate cases distinguish exact repetition, paraphrase, and evidence that appears similar but belongs to a different identity or scope. Cross-scope cases are essential: semantic relatedness does not create authorization. The correct label can be REJECT even when a target looks textually compatible.

## 5.4 Label generation and limitations

Labels are emitted by an executable oracle implementing the versioned formation policy. This produces perfect internal consistency but creates a real risk of shortcut learning. Models may infer generator templates or lexical cues rather than robust semantics. The mitigation is group-disjoint splitting and audit, not a claim that synthetic coverage equals reality. The dataset should be understood as an executable conformance suite with statistical scale, not a population sample of human memory behavior.

<!-- PAGEBREAK -->

# 6. Leakage Control, Splits, and Audit

## 6.1 Group-disjoint partitioning

The 60,000 decisions were partitioned as follows:

| Split | Decisions | Scenarios | Purpose |
|---|---:|---:|---|
| Train | 39,600 | 7,920 | Parameter optimization |
| Validation | 6,500 | 1,300 | Model and checkpoint ranking |
| Calibration | 6,700 | 1,340 | Temperature and abstention fitting |
| Sealed test | 7,200 | 1,440 | One-time final evaluation |

Every scenario contributes five heads to only one split. Partition keys jointly account for fictional identity, template family, semantic update chain, and paraphrase group. Exact and near-duplicate checks are applied after partitioning. This prevents a surface paraphrase of a training example from appearing in sealed evaluation and prevents adjacent events from one synthetic biography from crossing splits.

## 6.2 Why decision counts alone are misleading

If five decisions from one scenario were independently shuffled, a model could observe the same evidence and infer a held-out head from four training heads. Similarly, splitting individual temporal events could reveal an identity's prior state. Our unit of independence is therefore the whole semantic group. Evaluation reports both decision-level metrics for compatibility with classifiers and scenario-cluster bootstrap intervals for inference.

## 6.3 Nonsealed audit

A stratified 400-item audit was sampled from nonsealed data, with at least 60 high-risk examples. An independent review recorded 399 exact agreements (99.75%) and zero critical findings. The one noncritical disagreement is retained in the record; it was not silently rewritten to improve the audit statistic. This audit checks label intelligibility and policy alignment but cannot prove completeness.

## 6.4 Sealed audit

After model selection and calibration were frozen, a separately sampled sealed audit was presented blind to an independent `gpt-5.5` reviewer. It returned 400/400 exact agreements with zero critical findings. The signed result is bound by Ed25519 receipt. Neither audit output nor sealed model metric was used for optimization, checkpoint selection, or threshold fitting.

An LLM reviewer is not equivalent to human expert adjudication. The audit is evidence of consistency against a second model under a fixed rubric, not evidence of human preference or legal correctness. This limitation motivates the proposed public-corpus and human-usability phases in Section 13.

## 6.5 Artifact isolation

Sealed labels were unavailable to the training and selection process. The selected run was copied into a portable artifact containing Safetensors weights, tokenizer and encoder configuration, questions, calibration, training manifest, and artifact manifest. A clean environment reloaded that bundle without dependence on the training directory. The manifest binds filenames, hashes, identities, and expected runtime versions so an accidental mixture of model and calibration files becomes detectable.

<!-- PAGEBREAK -->

# 7. Model, Input Packing, and Training

## 7.1 Base checkpoint

The base is `convaiinnovations/laya` at revision `7b928d828b7b0e022f929d9bd2e44165aa270148`, base-model SHA-256 `891102d3...`. The tokenizer vocabulary contains 50,280 entries. The encoder consumes a task type, instructions, explicit options, and current state using the pinned sequence form:

`[CLS] type instructions [SEP] [MASK] option_1 ... option_K [SEP] state [SEP]`.

The governing total length is 512 tokens and the question-head allocation is 192. AtMem uses tokenizer-exact whole-range packing: the question and every option must remain intact. Overflow produces a typed failure receipt and deterministic fallback. Silent truncation is disabled because truncating a target list could convert an unauthorized candidate into the apparent only choice.

## 7.2 Optimization configuration

| Parameter | Value |
|---|---:|
| Seed | 410239 |
| Epochs | 4 |
| Micro-batch | 32 |
| Gradient accumulation | 2 |
| Effective batch | up to 64 |
| Encoder learning rate | 2.5e-5 |
| Head learning rate | 1.0e-4 |
| Minimum learning rate | 1.0e-6 |
| Weight decay | 0.01 |
| Gradient clip | 1.0 |
| RL samples | 4 |
| Exploration sigma | 0.4 to 0.1 |
| Spherical weight | 0.75 |
| RPS weight | 1.0 |
| Numeric precision | FP32 |

The encoder and question heads were trained jointly; this is not a low-rank adapter. FP32 was chosen after the upstream FP16 path skipped its initial optimizer update following overflow. Preserving optimization correctness was prioritized over throughput.

## 7.3 Compute and cost

Training used PyTorch 2.11.0+cu128 on a single RTX 5090. Wall time was 4,390.91 seconds, approximately 73.2 minutes. The Vast.ai instance cost USD 0.481111 per hour including storage; the complete training/recovery activity reduced prepaid credit by USD 1.541821, below the USD 20 budget. The instance was destroyed after artifact recovery and the active-instance count returned to zero.

Local Mac and Windows hosts were considered first under the compute protocol. Paid compute was used only after the local path was infeasible for timely full training. The cloud host was selected using price, RTX 5090 compatibility, on-demand availability, and reliability at or above 0.99. Later failed Qwen comparison attempts cost an additional USD 0.014924 under a separate evaluation budget and must not be conflated with model-training cost.

## 7.4 Portability

The clean verification environment used Python 3.12, Laya 0.4.2, PyTorch 2.11.0, Transformers 4.57.1, Safetensors 0.6.2, Hugging Face Hub 0.36.0, and NumPy 2.2.3. Linux CUDA was used for training; CPU and Apple MPS were used for independent reload checks. Product compatibility is mediated by the AtMem profile, which detects supported devices and retains deterministic fallback. Framework device names alone are not evidence of a completed operating-system support matrix.

<!-- PAGEBREAK -->

# 8. Selection, Calibration, and Artifact Freezing

## 8.1 Preregistered model selection

Two objectives were trained under matched data and core hyperparameters: soft cross-entropy and RLCD/proper scoring. Ranking used validation accuracy and calibration criteria defined before sealed evaluation. The runs tied exactly under that ordering. The predeclared final tie-break was stable lexical objective name, which selected `rlcd-410239-20261010T152813Z`. No sealed label or downstream workflow result influenced this choice.

The exact tie is scientifically important. Current evidence does **not** establish RLCD superiority over cross-entropy on this dataset. It establishes that the selected RLCD artifact meets the frozen criteria. Future work needs harder, non-saturated data to test whether proper-scoring optimization improves calibration or selective risk.

## 8.2 Calibration bundle

Calibration used only the 6,700-decision calibration split, 1,340 examples per question. The fitted type temperatures are `[1.0, 1.0, 1.0]`; the `choice:3-5` temperature is 1.0. The minimum-confidence threshold for `choice:3-5` is 1.0 at target error 0.10. A threshold of 1.0 is conservative and unusual: it accepts only predictions represented as fully confident after the pinned scoring path. All 7,200 sealed outputs met this threshold and were correct.

The data are saturated, so near-zero calibration errors should not be generalized. On a shifted distribution, a threshold calibrated on synthetic examples may accept an overconfident error or reject most traffic. The authority boundary and fallback therefore remain mandatory even when the calibration receipt is valid.

## 8.3 Cryptographic binding

| Artifact | Immutable identifier |
|---|---|
| Dataset revision | `4436089b38cbe3a5374aaaa92c4c77703cdbf668` |
| Dataset manifest | `d67d371c8c1d6de85a0293cded5aa5b3f7d078e92197130ce1f9edef68e863d4` |
| Selected run | `rlcd-410239-20261010T152813Z` |
| Model SHA-256 | `f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683` |
| Question digest | `7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e` |
| Calibration digest | `b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067` |
| Portable export | `6f7d53c18431c27baa617ab95ebcc4cad669917a6508145fa001eb7c8e799900` |

These identifiers convert "use the model" into a verifiable tuple. A weight file with a different question set is a different decision instrument, even if its model hash matches. Likewise, calibration is not fungible across questions or revisions.

## 8.4 Reload agreement

Two clean CPU reloads and one clean Apple MPS reload evaluated the same 100 nonsealed probes. Same-backend choice agreement was 1.0 with zero normalized-score delta. CPU/MPS choice agreement was 1.0; maximum normalized-score delta was 7.2023e-16 and aggregate accuracy delta was zero. This is strong evidence of numerical portability for the probe set, not proof that every input or future dependency combination is identical.

<!-- PAGEBREAK -->

# 9. Evaluation Protocol

## 9.1 Frozen formation packet

The downstream formation packet contains 400 decisions arranged as 80 complete five-question scenario clusters. Its logical digest is `sha256:6125d470...`. Expected labels were never included in model inputs. Four successful arms were compared:

- deterministic AtMem rules;
- pinned base Laya;
- fine-tuned Laya;
- fine-tuned Laya plus bounded AtBot escalation.

Two planned comparator arms were retained as failures. Pinned Qwen3.5-9B did not complete startup inside the frozen 15-minute ceiling after three infrastructure attempts. Jev authentication exposed aliases but not the required concrete `jev-1.13.0` identity, so the protocol authorized zero calls. Both arms are **inconclusive**. Treating their retained rows as zero performance would reward infrastructure failure and violate the comparison contract.

## 9.2 Frozen retrieval packet

The retrieval packet contains 80 queries with a fixed pool of ten candidate IDs each: 61 evidence-bearing positive queries and 19 negative queries. Its logical digest is `sha256:9c8b7e52...`. Each successful arm received identical ordered candidate membership. Only candidate content, retention, or abstention changed as a consequence of the preceding formation result.

This design controls the retriever's opportunity set. It does not measure open-corpus indexing throughput, approximate-nearest-neighbor recall, or long-context reading. It asks a narrower causal question: after a different formation decision, can the same retrieval procedure surface usable evidence?

## 9.3 Outcome definitions

**Exact state** requires the entire canonical state to match the frozen oracle, not merely the primary operation label. **Safety violation** counts an unauthorized or disallowed transition under the scenario policy. **Retrieval MRR@5** is reciprocal rank of the first relevant candidate for positive queries, truncated at five. **Recall@5** records whether any relevant candidate appears by rank five. **Negative abstention** requires returning no supporting memory for queries designed to lack admissible evidence. **Combined sufficiency** checks whether the final retrieved state is adequate to answer the future query without unsupported inference.

Latency measures end-to-end formation decision time on the measured Apple-silicon CPU. It is not a cross-hardware throughput comparison. The deterministic and neural paths have different fixed costs, and no GPU serving benchmark is inferred from the CPU result.

## 9.4 Safety gates

The protocol checks missing classes, prediction collapse, prior drift, truncation, failure count, non-finite values, and receipt completeness. The sealed classifier set had 1,440 decisions per question, zero failed decisions, zero truncation, no missing expected class, no collapse, and zero class-prior L1 drift. Evaluation runners refuse to overwrite prior evidence, forcing a new output directory or explicit archival.

<!-- PAGEBREAK -->

# 10. Results

## 10.1 Sealed synthetic classification

| Split | N | Accuracy | Macro-F1 | NLL | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 6,500 | 1.0000 | 1.0000 | 0 | 0 | 0 |
| Calibration | 6,700 | 1.0000 | 1.0000 | 0 | 0 | 0 |
| Sealed | 7,200 | 1.0000 | 1.0000 | 2.4447e-13 | 3.5791e-25 | 2.4447e-13 |

The absence of errors across all splits suggests the task is fully learnable by the chosen model and also indicates saturation. Because perfect validation preceded the sealed result, there is no evidence that sealed performance was selected indirectly. Nevertheless, the result should be read as conformance to the generator's policy family.

## 10.2 Store-and-retrieve workflow

| Arm | Exact state | Safety violations | Median formation | MRR@5 | Recall@5 | Combined sufficiency |
|---|---:|---:|---:|---:|---:|---:|
| Deterministic AtMem | 0.4250 | 19 | 2.31 ms | 0.3798 | 1.0000 | 0.0875 |
| Base Laya | 0.3625 | 3 | 273.59 ms | 0.2951 | 0.7705 | 0.0875 |
| Fine-tuned Laya | 1.0000 | 0 | 272.29 ms | 0.3798 | 1.0000 | 1.0000 |
| Fine-tuned + escalation | 1.0000 | 0 | 282.54 ms | 0.3798 | 1.0000 | 1.0000 |

All three AtMem/fine-tuned successful arms achieved 1.0 negative-query abstention. Base Laya made 14 positive-query abstention errors, explaining its 0.7705 evidence coverage. The fine-tuned model had no loss in any required operation or memory class and zero recorded safety violations.

## 10.3 What improved

Fine-tuning improved exact formation by 57.5 percentage points over deterministic rules and 63.75 points over base Laya. It did **not** improve MRR@5 over deterministic AtMem: both were 0.3798. Therefore the defensible mechanism is better canonical-state construction, not superior lexical ranking. Combined sufficiency rose by 91.25 points because the correct evidence survived formation in the right form.

This finding illustrates why memory quality is multiplicative. If `F` is the event that correct evidence is formed and `R` the event that a retriever ranks it adequately, then useful recall requires `F intersection R`. Improving `P(R | F)` cannot compensate when `P(F)` is low. The fine-tuned model primarily raises `P(F)`.

## 10.4 Cost of the gain

Median neural formation was approximately 118 times slower than deterministic rules on the measured CPU (`272.29 / 2.31`). The comparison is a latency ratio, not a claim about user-visible request time under batching or GPU serving. The optional profile is valuable when semantic correctness dominates a few hundred milliseconds of formation latency; it is inappropriate where every write must finish at deterministic-rule speed.

The escalation arm added roughly 10.25 ms median overhead but made zero remote calls because all model outputs passed. Its identical accuracy does not prove escalation quality; it only verifies that the enabled integration does not perturb accepted decisions in this packet.

<!-- PAGEBREAK -->

# 11. Statistical Analysis and Interpretation

## 11.1 Paired bootstrap comparisons

| Contrast | Metric difference | 95% cluster-bootstrap CI | Interpretation |
|---|---:|---:|---|
| Fine-tuned - deterministic | Exact state +0.5750 | [0.4684, 0.6835] | Improvement on frozen synthetic workflow |
| Fine-tuned - deterministic | MRR@5 0.0000 | [0.0000, 0.0000] | Tie under fixed retrieval packet |
| Fine-tuned - deterministic | Combined +0.9125 | [0.8481, 0.9639] | Improvement on frozen synthetic workflow |
| Fine-tuned - base Laya | Exact state +0.6375 | [0.5301, 0.7407] | Specialization benefit |
| Fine-tuned - base Laya | MRR@5 +0.0847 | [0.0055, 0.1598] | Fewer lost positive memories |
| Fine-tuned - base Laya | Combined +0.9125 | [0.8481, 0.9639] | Large workflow gain |

Intervals quantify sampling variation over the 80 synthetic clusters. They do not account for generator-family uncertainty, model-training seed uncertainty, reviewer uncertainty, or deployment shift. With only one primary training seed, variance across random initializations is unknown. Perfect sealed results also prevent meaningful error stratification.

## 11.2 Baseline interpretation

The deterministic baseline is extremely fast but encodes incomplete semantics, producing 19 safety violations and only 42.5% exact states. Base Laya reduces safety violations to three but has lower exact state and loses 14 positive memories through abstention. Fine-tuning therefore does more than reproduce the base encoder: it aligns question semantics, option boundaries, and AtMem policy.

The result does not justify saying the model "beats Qwen" or "beats Jev." The Qwen process never reached inference and the Jev identity gate prevented calls. A comparison requires successful paired outputs at pinned identities, equivalent context, and documented costs. Unavailable arms are reported to make the failed attempt auditable, not to create a favorable denominator.

## 11.3 Calibration interpretation

NLL, Brier, and ECE are effectively zero because the predictions are both correct and numerically saturated. This is internally consistent with the threshold accepting all items. It is also a warning sign for external validity. Calibration cannot be assessed where almost every example is easy and correct. Public adversarial and distribution-shifted sets must measure risk-coverage curves, class-conditional ECE, adaptive calibration error, and selective error rather than relying on one aggregate ECE.

## 11.4 Practical effect

For an end user, the likely benefit is fewer incorrect memories: duplicates are left unchanged, conflicts supersede the right record, temporary facts do not become durable identity claims, and unsupported or cross-scope content is rejected. Later requests then operate over a cleaner state. The user also gets local inference and an explicit rollback path. These are expected benefits under the tested policy family; production rates remain unknown until opt-in telemetry-free usability studies or user-controlled evaluation provide evidence.

<!-- PAGEBREAK -->

# 12. Deployment Architecture and Reproducibility

## 12.1 Runtime path

The production path is:

`authorized evidence -> exact packer -> Laya scores -> bound calibration -> confidence/schema gate -> AtMem authority -> canonical transaction -> receipt`

Any failure before the authority gate yields fallback, abstention, or review. The model directory is installed into an inactive profile first. Activation is a separate explicit operation. Doctor checks artifact identity and runtime readiness. Rollback restores the previous profile bytes, rather than merely changing a display flag.

## 12.2 Installed-profile verification

The release exercise verified preview without state change, setup with the profile still inactive, explicit activation, healthy doctor output, and byte-restoring rollback. CLI, MCP, and dashboard surfaces were checked through the same profile semantics. The final verification state was inactive with fallback ready, ensuring the optional model did not silently become the default.

One installed-runtime CPU probe measured approximately 199.56 ms for an inference, while the frozen workflow median was 272.29 ms. These numbers arise from different harnesses and must not be pooled. Neither is a throughput benchmark.

## 12.3 Cross-platform contract

AtMem 2.3.9b1 exposes the same commands on Windows, macOS, and Linux. Backends may differ: CPU is the compatibility floor, Apple MPS is verified on a clean probe, and CUDA supported training and Linux execution. Device selection is `auto` by default, but artifact validation and decision semantics do not change by backend. If the learned runtime cannot initialize, deterministic AtMem remains available.

Cross-platform support is achieved at the product layer through detection, optional dependencies, explicit activation, and fallback. It does not mean every accelerator/driver combination has been exhaustively benchmarked. A full installed-wheel matrix remains a release gate distinct from the scientific model result.

## 12.4 Evidence preservation

The repository stores immutable JSON receipts for preflight, objective selection, training, calibration, sealed evaluation, blinded audit, model reproduction, formation evaluation, retrieval evaluation, combined evaluation, statistics, installed runtime, and profile end-to-end behavior. The public model and dataset cards reproduce the claim boundary and hashes. Training archives and recovery copies were uploaded before cloud destruction.

This evidence hierarchy permits three levels of reproduction:

1. **Artifact verification:** download exact revisions and compare manifest hashes.
2. **Evaluation reproduction:** run frozen packets against the portable model without retraining.
3. **Training reproduction:** regenerate data from the pinned generator and seed, retrain with the recorded environment, recalibrate, export, and compare semantic metrics. Bitwise equality is not promised across GPU kernels.

<!-- PAGEBREAK -->

# 13. Limitations, Validity, Ethics, and Security

## 13.1 Internal validity

The split design, sealed labels, immutable identities, independent reload, and paired evaluation support the claim that the selected artifact learned the defined synthetic task. Threats remain. Only one primary seed is reported. The generator and oracle share a policy implementation, so an unnoticed oracle defect could affect every split. The exact tie between objectives and saturated metrics limit causal conclusions about RLCD. The blinded audit uses another language model rather than human domain experts.

## 13.2 External validity

No result is claimed for LoCoMo, LongMemEval, LongMemEval V2, production memories, adversarial public corpora, multilingual traffic, or real-user usability. Earlier AtMem repository results on those or related benchmarks belong to other configurations and cannot be reassigned to this model. The current synthetic distribution may omit slang, code-switching, implicit preferences, long causal chains, realistic identity ambiguity, policy evolution, malformed Unicode, prompt injection, and social-engineering patterns.

The model can confidently reproduce the synthetic oracle and still be wrong out of distribution. A 100% sealed score is therefore a reason to broaden evaluation, not to stop it.

## 13.3 Construct validity

Exact state is strict and useful for conformance, but it can penalize harmless alternative representations. Conversely, combined sufficiency may pass a state that answers one query while omitting information useful later. MRR@5 over ten frozen candidates does not characterize open-ended retrieval. Safety-violation counts reflect the encoded policy and are not a general security certification.

## 13.4 Ethical and privacy considerations

Persistent memory can amplify surveillance, incorrect profiling, and unwanted retention. A model that is better at formation is not automatically more respectful of users. Consent, purpose limitation, scope, deletion, and visibility must be enforced outside the classifier. The dataset is fictional to avoid exposing customer records, but fictional data also weakens representativeness. Future user studies should default to local, opt-in evaluation and avoid central collection of memory contents.

## 13.5 Security considerations

The model is not an identity oracle, policy engine, secret detector, or authorization mechanism. It must not consume unauthorized context simply to improve its prediction. Target enumeration, version checks, evidence binding, output normalization, and transaction-level revalidation remain mandatory. Optional escalation creates a potential egress channel and must be separately enabled, minimized, budgeted, and revalidated.

Safetensors reduces a class of arbitrary-code risks associated with model serialization, but does not establish semantic safety. Hash verification detects corruption or substitution only when trusted expected hashes are distributed correctly. Dependency and model supply chains still require routine vulnerability and provenance review.

<!-- PAGEBREAK -->

# 14. Required Next Experiments

The next evidence program is deliberately staged so that each phase answers a different question.

## 14.1 Public-corpus formation reconstruction

Construct a frozen adapter that maps LoCoMo and LongMemEval histories into formation events without exposing answer keys to the model. Store events incrementally, then evaluate the official downstream questions. Compare: deterministic AtMem, base Laya, fine-tuned Laya, fine-tuned plus escalation, a pinned generative baseline, Mem0 where its public interface permits, and a concrete Jev release if identity can be verified. Report official metrics, storage volume, provider tokens, wall time, and failure rate.

This phase tests whether the synthetic policy transfers to long conversations. It must not tune on the public test split. Development decisions should use public train/dev material or a separately generated corpus, and the final adapter commit and prompts should be frozen before test execution.

## 14.2 Adversarial public corpus

Create a public red-team set under a permissive license with paraphrase attacks, prompt injection inside remembered content, cross-user target collisions, Unicode confusables, credential-like strings, temporal contradictions, deletion races, and overlong options. Human annotators should independently label each case, with adjudication and inter-rater agreement. Report attack success rate, false-store rate, false-reject rate, selective risk, coverage, and policy-specific harm severity.

## 14.3 Production shadow evaluation

Run the model in shadow mode: it receives only locally authorized inputs and emits receipts, but does not influence canonical state. Compare its proposal with the existing path and with user corrections. Aggregate only privacy-preserving counters unless a user explicitly exports a case for diagnosis. Define stop conditions for elevated false-store or cross-scope proposals. Promotion to write influence should require a predeclared safety margin and rollback drill.

## 14.4 Real-user usability

Recruit consenting users for a crossover study comparing default AtMem and the optional formation profile. Primary outcomes should include incorrect-memory correction rate, task completion, trust calibration, perceived control, time to understand activation and rollback, and successful deletion. The study should distinguish model quality from installation friction. Qualitative interviews should ask whether users understand that the profile is optional and that escalation may create provider egress.

## 14.5 Robustness and efficiency

Run at least five training seeds; evaluate multilingual and code-switched inputs; plot risk-coverage under distribution shift; measure CPU, MPS, CUDA, memory, energy, batch throughput, and cold-start latency; and test quantized exports without inheriting calibration. A pinned successful Jev/Qwen comparator is necessary before any superiority statement. These phases can convert the current synthetic conformance result into a broader systems claim, but only after their receipts exist.

<!-- PAGEBREAK -->

# 15. Conclusion

AtMem Laya Formation Model v1 demonstrates that a small, bounded encoder can learn a versioned memory-formation policy and materially improve a frozen synthetic store-to-retrieve workflow without becoming the system's authority. The selected model achieved perfect held-out synthetic classification, perfect exact state on 80 downstream scenarios, zero recorded safety violations, and a 91.25-point gain in later-query sufficiency over deterministic rules. The retrieval ranker itself did not improve; the model's value came from deciding what canonical memory should exist.

The engineering result is as important as the metric. The artifact is linked to exact data, base-model, source, question, calibration, and export hashes. Sealed labels were isolated from selection. Failed comparator arms remain inconclusive. Local inference is optional, activation is explicit, and rollback is verified. The proposal is revalidated through AtMem's scope and transaction boundary.

The appropriate interpretation is neither "memory solved" nor "a universal model." It is that a finite-choice formation layer is a promising and reproducible component for governed memory. The next scientific burden is external validity: public long-memory corpora, adversarial human-labeled cases, production shadowing, multilingual robustness, multiple seeds, and real-user usability. Until then, the model is best used as an opt-in local decision aid with deterministic fallback and an auditable receipt trail.

# Appendix A. End-User Installation and Use

## A.1 Install the beta

Python 3.12 is the cleanly verified environment. Create or activate a virtual environment, then install the opt-in dependency group:

```bash
python -m pip install --upgrade --pre "atmem[laya-formation]==2.3.9b1"
```

The ordinary AtMem profile remains the default. Installing the package does not authorize a model download, activate the profile, or send memory to a provider.

## A.2 Preview, download, and verify

```bash
atmem formation preview --download
atmem formation setup --download --device auto --yes
atmem formation doctor
```

`preview` shows the planned artifact and profile changes. `setup` downloads the pinned public model, verifies the manifest, chooses an available local backend, and leaves the profile inactive. `doctor` verifies the artifact/calibration/question binding and runtime readiness.

## A.3 Activate and inspect

```bash
atmem formation activate --yes
atmem formation status
atmem formation doctor
```

After activation, AtMem may use the model for bounded formation proposals. AtMem still performs authorization, canonical-state reload, policy validation, and transactional mutation. Existing clients do not need to parse model-specific output; the profile is integrated behind AtMem's normal CLI, MCP, and dashboard behavior.

## A.4 Roll back

```bash
atmem formation rollback --yes
atmem formation status
```

Rollback restores the prior profile. Use it if local latency is unacceptable, device initialization fails, or behavior is unsuitable. Deterministic AtMem remains the offline fallback. Removing downloaded model files is separate from rollback and should be done only after confirming the profile is inactive.

<!-- PAGEBREAK -->

# Appendix B. Reproducing the Frozen Evaluation

Use immutable packets and a new output directory; runners refuse to overwrite prior evidence.

```bash
python tools/run_laya_formation_arm.py finetuned-laya \
  --packet-dir /path/AtMem-Laya-Evaluation-20261011-v2 \
  --output-dir /path/new-results \
  --model-dir /path/atmem-model-final-1698278 --device cpu

python tools/run_laya_retrieval_arm.py finetuned-laya \
  --packet-dir /path/AtMem-Laya-Retrieval-Evaluation-20261011-v1 \
  --formation-results-dir /path/new-results \
  --output-dir /path/new-results

python tools/run_laya_combined_arm.py finetuned-laya \
  --formation-packet-dir /path/AtMem-Laya-Evaluation-20261011-v2 \
  --retrieval-packet-dir /path/AtMem-Laya-Retrieval-Evaluation-20261011-v1 \
  --results-dir /path/new-results

python tools/analyze_laya_evaluation.py \
  --formation-packet-dir /path/AtMem-Laya-Evaluation-20261011-v2 \
  --retrieval-packet-dir /path/AtMem-Laya-Retrieval-Evaluation-20261011-v1 \
  --results-dir /path/new-results \
  --output /path/statistical-analysis.json
```

Minimum receipt inventory:

- `evaluation-preflight-20261011.json`
- `formation-evaluation-20261011.json`
- `retrieval-evaluation-20261011.json`
- `combined-evaluation-20261011.json`
- `statistical-analysis-20261011.json`
- `objective-selection`, `calibration`, `sealed-evaluation`, `sealed-audit`, and `model-reproduction` receipts

The evaluation model revision is `1698278c4b158fac30e4eb2fefd10ef8b8f873b3`. Verify the model SHA-256 and bound question/calibration digests before running. Do not replace a failed comparator with a zero metric.

# Appendix C. Artifact and Release Map

| Component | Public identity |
|---|---|
| AtMem package | `atmem==2.3.9b1` |
| AtBot companion | `atmem-atbot==0.1.1b1` |
| OpenClaw bridge | `openclaw-memory-atmem@2.3.9-beta.1` |
| Model | `atmem/atmem-laya-formation-model-v1` |
| Dataset | `atmem/atmem-laya-formation-v1` |
| License | Apache-2.0 |

<!-- PAGEBREAK -->

# References

[1] A. Maharana, D.-H. Lee, S. Tulyakov, M. Bansal, F. Barbieri, and Y. Fang. "Evaluating Very Long-Term Conversational Memory of LLM Agents." *ACL*, 2024. arXiv:2402.17753. https://arxiv.org/abs/2402.17753

[2] D. Wu, H. Wang, W. Yu, Y. Zhang, K.-W. Chang, and D. Yu. "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory." *ICLR*, 2025. arXiv:2410.10813. https://arxiv.org/abs/2410.10813

[3] D. Wu, Z. Ji, A. Kawatkar, B. Kwan, J.-C. Gu, N. Peng, and K.-W. Chang. "LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues." 2026. arXiv:2605.12493. https://arxiv.org/abs/2605.12493

[4] P. Chhikara, D. Khant, S. Aryan, T. Singh, and D. Yadav. "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory." 2025. arXiv:2504.19413. https://arxiv.org/abs/2504.19413

[5] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova. "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding." *NAACL*, 2019. arXiv:1810.04805. https://arxiv.org/abs/1810.04805

[6] N. Kishor. "Laya: Non-autoregressive System One decision engine." Source and documentation, pinned revision 68804629e8ccd9d616d48a40e87de9fabbeae069, 2026. https://github.com/NandhaKishorM/laya

[7] T. Gneiting and A. E. Raftery. "Strictly Proper Scoring Rules, Prediction, and Estimation." *Journal of the American Statistical Association*, 102(477):359-378, 2007. https://doi.org/10.1198/016214506000001437

[8] L. J. Savage. "Elicitation of Personal Probabilities and Expectations." *Journal of the American Statistical Association*, 66(336):783-801, 1971. https://doi.org/10.1080/01621459.1971.10482346

[9] G. W. Brier. "Verification of Forecasts Expressed in Terms of Probability." *Monthly Weather Review*, 78(1):1-3, 1950. https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2

[10] C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger. "On Calibration of Modern Neural Networks." *ICML*, PMLR 70:1321-1330, 2017. https://proceedings.mlr.press/v70/guo17a.html

[11] Y. Geifman and R. El-Yaniv. "Selective Classification for Deep Neural Networks." *NeurIPS*, 2017. arXiv:1705.08500. https://arxiv.org/abs/1705.08500

[12] M. Mitchell et al. "Model Cards for Model Reporting." *FAT* 2019. arXiv:1810.03993. https://arxiv.org/abs/1810.03993

[13] T. Gebru et al. "Datasheets for Datasets." *Communications of the ACM*, 64(12):86-92, 2021. arXiv:1803.09010. https://arxiv.org/abs/1803.09010

[14] J. Pineau et al. "Improving Reproducibility in Machine Learning Research." *Journal of Machine Learning Research*, 22(164):1-20, 2021. https://jmlr.org/papers/v22/20-303.html

[15] A. Kumar, S. Sarawagi, and U. Jain. "Trainable Calibration Measures for Neural Networks from Kernel Mean Embeddings." *ICML*, PMLR 80:2805-2814, 2018. https://proceedings.mlr.press/v80/kumar18a.html

[16] A. Pugnana, L. Perini, J. Davis, and S. Ruggieri. "Deep Neural Network Benchmarks for Selective Classification." 2024. arXiv:2401.12708. https://arxiv.org/abs/2401.12708

[17] A. Vaswani et al. "Attention Is All You Need." *NeurIPS*, 2017. arXiv:1706.03762. https://arxiv.org/abs/1706.03762

[18] A. Paszke et al. "PyTorch: An Imperative Style, High-Performance Deep Learning Library." *NeurIPS*, 2019. arXiv:1912.01703. https://arxiv.org/abs/1912.01703

[19] T. Wolf et al. "Transformers: State-of-the-Art Natural Language Processing." *EMNLP: System Demonstrations*, 2020. https://aclanthology.org/2020.emnlp-demos.6/

[20] Hugging Face. "Safetensors." Documentation and format repository. https://github.com/huggingface/safetensors

[21] AtMem Project. "AtMem Laya Formation Model v1: Model Card." Immutable release artifact, 2026. `research/laya_formation/publication/MODEL_CARD.md`.

[22] AtMem Project. "AtMem Laya Formation Dataset v1: Dataset Card." Immutable release artifact, 2026. `research/laya_formation/publication/DATASET_CARD.md`.

[23] AtMem Project. "AtMem Laya Formation Evaluation." Frozen evidence report, 11 October 2026. `research/laya_formation/reports/evaluation-report-20261011.md`.

[24] AtMem Project. "Compute Protocol and Vast Selection." Reproducibility records, 2026. `research/laya_formation/compute_protocol.md` and `research/laya_formation/vast-selection.md`.

[25] AtMem Project. "AtMem 2.3.9b1 Release Notes." Installation, migration, compatibility, and limitations, 2026. `docs/releases/v2.3.9b1.md`.

# Appendix D. Claim Checklist

| Claim | Status | Evidence |
|---|---|---|
| Learns five bounded formation questions | Supported | Sealed 7,200 decisions, all correct |
| Improves frozen synthetic exact state | Supported | +0.575 vs deterministic, paired CI excludes zero |
| Improves frozen combined sufficiency | Supported | +0.9125 vs deterministic |
| Improves deterministic retrieval ranking | Not supported | MRR@5 tie |
| Beats Jev or Qwen | Inconclusive | Jev identity unavailable; Qwen startup failed |
| Generalizes to LoCoMo/LongMemEval | Not evaluated | Required next experiment |
| Safe for autonomous authorization | Rejected by design | Proposal-only authority boundary |
| Production or real-user superiority | Not evaluated | Shadow and usability phases required |
| Installable and reversible | Supported | Profile end-to-end receipt and release commands |

