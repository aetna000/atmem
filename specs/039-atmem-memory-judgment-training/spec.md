# Feature Specification: Train and Evaluate AtMem Memory Judgment Model

**Feature Branch**: `039-atmem-memory-judgment-training`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: User request to compare the off-the-shelf Skywork Reward V2 Qwen3
0.6B model with AtMem-specific post-training, using `/Volumes/MEM` for storage,
then benchmark the result against existing Native-order and Jev LoCoMo results.

## Overview

AtMem currently has an exploratory LoCoMo reranking result where Jev improves
the ordering of AtMem's existing top-ten candidates. The user wants to determine
whether the off-the-shelf Skywork Reward V2 Qwen3 0.6B reward model can rank
those candidates, then train an AtMem-specific Memory Judgment Model
(AtMem-MJM) from that checkpoint and compare it on the same evaluation.

This feature is a bounded research experiment, not a production AtMem feature.
It produces a reproducible local baseline, an AtMem-MJM adapter, held-out
benchmark results, machine-readable evidence, and Hugging Face-ready model and
training-data artifacts. The experimental model only ranks candidates already
authorized by AtMem. AtMem remains the authority for eligibility, lifecycle,
scope, deletion, final validation, and context delivery.

All experiment-owned data and outputs after approval of this specification are
stored on the mounted external volume at `/Volumes/MEM/AtMem-MJM/`. Because
`MEM` is exFAT, high-file-count environments and caches use an APFS sparse
bundle whose backing image is inside that external experiment root; a path
under the experiment root resolves through its mount symlink to that image.
Training and
inference are local on the Apple M2 MacBook Air unless the local run proves
infeasible. No cloud execution is in scope. The user has authorized private
Hugging Face upload of AtMem-authored/licensed synthetic training data and
model artifacts after privacy, licensing, and visibility checks. No benchmark
questions, candidates, answers, evidence IDs, private histories, or credentials
may be uploaded or sent to hosted evaluators.

## Terms and comparison arms

- **Native order**: AtMem's frozen order for its retrieved candidates.
- **Jev reranking**: the historical Jev aggregate on the same benchmark
  protocol. The stored historical artifact has no per-question Jev rankings.
  After explicit user authorization, Jev 1.13.0 was rerun on the exact frozen
  candidate pool in 40 batches of 50; the new per-question results are retained
  on MEM and are the paired comparison arm. Historical aggregate values remain
  documented separately.
- **Skywork off-the-shelf**: the published Skywork Reward V2 Qwen3 0.6B reward
  checkpoint used without AtMem-specific training. It is already a trained
  general preference model, not raw Qwen3 base weights.
- **AtMem-MJM**: a memory-specific pairwise-preference adapter post-trained from
  the exact Skywork checkpoint revision used in the off-the-shelf arm.
- **Candidate pool**: the same frozen AtMem top-ten record IDs and evidence for
  each LoCoMo question, supplied to Jev, Skywork, and AtMem-MJM. The evaluators
  may reorder these IDs but may not add, remove, authorize, or rewrite memory.

## Primary scorecard

The comparison has four system columns plus the metric column. Existing values
are exploratory published results; `Pending` means the condition has not yet
been run under this feature's frozen protocol.

| Metric | Native order | Jev reranking | Skywork Reward V2 0.6B, off-the-shelf | AtMem-MJM, post-trained |
| --- | ---: | ---: | ---: | ---: |
| MRR@5 | 0.4259 | 0.5880 | 0.4540 | 0.4632 |
| Recall@1 | 0.3399 | 0.5433 | 0.3661 | 0.3741 |
| Recall@10 | 0.6495 | 0.6495 | 0.6495 | 0.6495 |

Primary evaluation is the same full LoCoMo corpus and candidate protocol used
for the existing results: 1,986 questions from ten conversations. The reference
dataset SHA-256 is
`79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4`.
The prior result reports four upstream evidence-reference anomalies and has
`exploratory` claim status. The replication MUST preserve and disclose them; a
cleaned or excluded-case analysis MUST be separately predeclared and reported.
It MUST NOT silently remove cases to improve results.

Recall@10 is a candidate-coverage invariant for the reranking arms. With
identical top-ten candidate IDs and evidence matching, the value must remain
0.6495. Any difference indicates a candidate-pool, data, or metric mismatch and
invalidates the head-to-head comparison until resolved.

## User Scenarios & Testing

### User Story 1 — Establish the unmodified Skywork baseline (Priority: P1)

As the researcher, I can score the frozen AtMem candidate pool with the
published Skywork reward model before training so I know what its general reward
knowledge achieves on memory ranking.

**Why this priority**: Without this condition, any later AtMem-MJM result cannot
separate existing generic reward-model capability from memory-specific training.

**Independent Test**: From the approved external experiment root and pinned
files, run the scorer over every frozen question; recover the same candidate
IDs, scores, metric outputs, model revision, and environment manifest on rerun.

**Acceptance Scenarios**:

1. **Given** a frozen LoCoMo question and authorized top-ten IDs, **When** the
   off-the-shelf checkpoint scores candidates, **Then** output contains only
   those IDs, their scalar scores/ranks, and a no-result/error state if scoring
   fails.
2. **Given** the baseline run is complete, **When** its manifest is reviewed,
   **Then** it identifies the dataset digest, candidate-pool digest, checkpoint
   revision, tokenizer, prompt/template, software versions, seed, storage root,
   and hardware without recording credentials.

### User Story 2 — Train AtMem-MJM from the frozen checkpoint (Priority: P1)

As the researcher, I can train a small adapter on AtMem-specific memory
preferences while keeping the LoCoMo and LongMemEval evaluation corpora out of
training, validation, and label generation.

**Why this priority**: This is the proposed contribution. Preventing benchmark
leakage is essential to a credible claim that the model learned reusable memory
judgment.

**Independent Test**: Train from the exact baseline checkpoint on a versioned,
reviewed pairwise dataset; verify its lineage, data splits, adapter reload, and
that benchmark question IDs, gold evidence, and answers do not occur in training
or validation.

**Acceptance Scenarios**:

1. **Given** a versioned training dataset with chosen/rejected memory candidates,
   **When** the adapter is trained, **Then** logs and outputs are stored under
   `/Volumes/MEM/AtMem-MJM/`, and the manifest binds the run to the base-model
   revision, dataset digest, split, training configuration, seed, and hardware.
2. **Given** a benchmark question or gold evidence item, **When** the frozen
   training and validation manifests are checked, **Then** no benchmark-derived
   prompt, candidate, answer, gold ID, or teacher judgment is present.
3. **Given** no useful candidate in the authorized set, **When** the model and
   selector process the case, **Then** the evaluation can record abstention or
   insufficient evidence instead of treating the least-bad candidate as
   necessarily useful.

### User Story 3 — Compare all four systems fairly (Priority: P1)

As the researcher, I can compare Native order, Jev reranking, off-the-shelf
Skywork, and AtMem-MJM on one frozen candidate pool and see whether
memory-specific training improves over Jev.

**Why this priority**: This is the decision the experiment is meant to inform.

**Independent Test**: The report validator accepts only a complete run whose
dataset/question set, candidate IDs, metric implementation, and primary
configuration match across all arms.

**Acceptance Scenarios**:

1. **Given** identical question and candidate-pool manifests, **When** each
   system ranks the candidates, **Then** all arms have the same Recall@10 and
   per-question eligible candidate IDs.
2. **Given** all four arms complete, **When** metrics are aggregated, **Then**
   the report includes MRR@5, Recall@1, Recall@10, per-question rows, paired
   differences from Jev, and conversation-clustered uncertainty.
3. **Given** an arm is missing, has an error, or used a different candidate
   pool, **When** the report is generated, **Then** it labels the comparison
   incomplete/invalid and does not state that AtMem-MJM beat Jev.
4. **Given** AtMem-MJM has a higher MRR@5 point estimate than Jev, **When** its
   paired conversation-level 95% bootstrap interval is calculated, **Then** a
   “beat Jev” claim is made only when the interval for the difference excludes
   zero; otherwise the result is reported as inconclusive.

### User Story 4 — Preserve external storage and prepare shareable artifacts (Priority: P2)

As the researcher, I can find datasets, environments, model snapshots, adapters,
logs, raw results, and reports on `MEM`, and prepare model and dataset
repositories on Hugging Face without exposing private or unlicensed data.

**Why this priority**: The user has asked for external storage and Hugging Face
availability; data lineage and licensing must travel with the weights.

**Independent Test**: Inspect the external experiment tree and machine-readable
manifests; confirm repository state and credentials are absent from artifacts,
the dataset has provenance/license metadata, and model/dataset artifacts are
ready for private Hugging Face repositories.

**Acceptance Scenarios**:

1. **Given** `/Volumes/MEM` is unavailable or lacks required space, **When** an
   experiment stage starts, **Then** it stops before downloading, training, or
   writing experiment artifacts elsewhere.
2. **Given** an artifact is prepared for Hugging Face, **When** provenance and
   licensing review is incomplete, **Then** it remains local/private and is
   not published publicly.
3. **Given** an artifact is ready for the agreed private repositories,
   **When** it is uploaded, **Then** the model card links the dataset revision
   and lists base model, training, intended use, limitations, and evaluation.

## Functional Requirements

- **FR-001**: The experiment MUST keep AtMem as sole authority for candidate
  eligibility, scope, sensitivity, lifecycle, deletion, and final delivery.
- **FR-002**: The intelligence models MUST receive only candidates that AtMem
  has authorized for the requesting scope; returned IDs MUST be revalidated by
  AtMem before any context is delivered.
- **FR-003**: The Skywork baseline MUST use the pinned published
  `Skywork-Reward-V2-Qwen3-0.6B` reward checkpoint without AtMem-specific
  training. The model revision, tokenizer, input format, scorer output, and
  runtime MUST be recorded.
- **FR-004**: AtMem-MJM MUST be post-trained from the exact Skywork revision
  used in FR-003. The initial objective MUST use pairwise preferences over
  task-plus-memory candidates and preserve an explicit insufficient-evidence
  case in data and evaluation.
- **FR-005**: Training MUST use only licensed/public-permitted, synthetic, or
  specifically authorized and de-identified training data. Raw private
  conversation histories, secrets, LoCoMo evaluation content, and
  LongMemEval-V2 evaluation content MUST NOT enter training or label generation.
- **FR-006**: Train, validation, and development cases MUST be separated by
  source conversation/person/template family before creating candidate pairs.
  Near duplicates and derived candidates from a single source MUST stay in one
  split.
- **FR-007**: Preference labels MUST follow a versioned rubric that distinguishes
  direct support, temporal applicability, wrong entity/relation, conflict,
  complementarity, redundancy, and insufficient evidence. LLM-generated labels
  alone MUST NOT be treated as ground truth.
- **FR-008**: The baseline and post-trained comparisons MUST use identical
  questions, eligible candidate IDs, candidate text/metadata fields, context
  limits, scoring template, evidence matching, and metric definitions.
- **FR-009**: The primary benchmark MUST be the same full LoCoMo corpus and
  question/evidence protocol as the existing Native/Jev reference, with its
  dataset digest and all known anomalies disclosed. Any cleaned/subset result
  MUST use a predeclared case manifest and be reported separately.
- **FR-010**: Primary measures MUST include MRR@5, Recall@1, and Recall@10.
  Recall@10 MUST be identical across reranking arms when candidate pools are
  identical; otherwise the comparison is invalid.
- **FR-011**: The report MUST retain per-question outputs for each locally
  evaluated arm and paired differences where both arms have case-level results.
  Uncertainty MUST be estimated at the conversation cluster level; question
  rows MUST NOT be treated as independent samples. If Jev case-level outputs
  remain unavailable, report its aggregate only and mark the paired difference
  and interval unavailable.
- **FR-012**: The result MAY be described as “AtMem-MJM beats Jev” only when
  AtMem-MJM MRR@5 exceeds Jev on the frozen common set and the paired
  conversation-clustered 95% interval for the difference excludes zero. All
  other cases MUST be described as no measured win or inconclusive.
- **FR-013**: Benchmark results MUST distinguish retrieval/evidence ranking
  from generated-answer or real-world task quality. The experiment MUST NOT
  claim answer accuracy improvement from rank metrics alone.
- **FR-014**: The initial local training profile MUST use LoRA/parameter-
  efficient adaptation on the 0.6B reward model with conservative batch and
  sequence settings suitable for an Apple M2 MacBook Air with 16 GB unified
  memory. Full fine-tuning and larger reward models are out of scope.
- **FR-015**: All experiment-owned source snapshots, datasets, model caches,
  Python environments, temporary files, checkpoints, logs, raw benchmark
  outputs, reports, and runtime-generated accelerator/compiler caches created
  after spec approval SHOULD be stored on the external `MEM` volume under
  `/Volumes/MEM/AtMem-MJM/` wherever configurable. The user explicitly permits
  macOS-managed Metal/compiler cache files to use their default internal system
  cache if redirection is not practical. This exception covers only OS-managed
  accelerator/compiler caches; all project-owned models, datasets, Python
  environments, caches, checkpoints, logs, and results MUST remain on `MEM`.
- **FR-016**: The experiment MUST pin and report Python/runtime package versions,
  model/dataset revisions and hashes, code snapshot digest, system/hardware,
  seed, training configuration, and metric implementation.
- **FR-017**: Training and benchmark inference MUST be local. No benchmark text,
  candidates, answers, evidence IDs, private histories, or credentials may be
  sent to third-party evaluators or hosted models. Only AtMem-authored/licensed
  synthetic training data and model artifacts may be uploaded to private
  Hugging Face repositories after privacy, license, and visibility checks,
  using the user's preconfigured environment credential without recording or
  exposing it. The existing Jev reference may be reused only after its input
  and candidate-pool identity match the frozen run; any Jev rerun requires a
  separate explicit egress decision. The user explicitly authorized and
  completed a same-pool rerun using `JEV_API`; its per-question scores are on
  MEM. No credential value was recorded.
- **FR-018**: The experiment MUST capture peak memory, training duration,
  inference latency, throughput, errors, and resource use alongside quality.
- **FR-019**: The experiment MUST preserve a pre-training copy of the
  off-the-shelf Skywork output and manifest so training cannot overwrite the
  baseline.
- **FR-020**: The dataset artifact MUST include schema, provenance, license/use
  terms, label instructions, split manifest, hashes, and a data card. Model and
  dataset Hugging Face repositories MUST initially be private; no public release
  is included without a later explicit approval after licensing and privacy
  review.
- **FR-021**: The model card and results MUST disclose the exploratory status of
  the historical Jev comparison, four known LoCoMo evidence anomalies, local
  hardware limits, label limitations, and any untested use cases.

## Key Entities

- **BenchmarkCase**: stable question ID, dataset/source version, task text,
  evidence references, and split membership.
- **CandidatePool**: the exact ordered and eligible candidate IDs and
  content/metadata digests supplied to every ranker for one case.
- **PreferencePair**: task state, chosen/rejected candidate IDs and content,
  adjudicated label/reason, provenance, reviewer state, and split.
- **ModelArtifact**: base checkpoint revision, adapter/reward head, tokenizer,
  configuration, hashes, license, and training lineage.
- **RunManifest**: code snapshot, dataset/pool hashes, environment, hardware,
  seed, metrics, raw output locations on `MEM`, and claim status.
- **Scorecard**: metrics for Native order, Jev reranking, off-the-shelf Skywork,
  and post-trained AtMem-MJM, with pending/invalid states represented explicitly.

## Edge Cases

- The `MEM` drive disconnects, fills, or becomes read-only during download,
  training, or output writing.
- macOS Metal writes accelerator/compiler cache files to its system-managed
  user cache directory. Prefer an external location when practical; the user
  has explicitly permitted this narrow system-cache exception when redirection
  is impractical.
- The selected Transformers/TRL/PyTorch stack cannot load or train the Skywork
  reward head on Apple MPS, or exceeds available unified memory.
- A candidate list is empty, contains fewer than ten items, has duplicate IDs,
  or becomes stale due to a lifecycle change.
- The reward model scores all candidates similarly, produces NaN/Inf, or gives a
  high score to a clearly unsupported candidate.
- The correct evidence is absent from AtMem's top ten; rerankers cannot repair
  candidate recall, and Recall@10 must expose this.
- The LoCoMo artifact digest, question order, four known anomaly cases, or
  evidence matcher differs from the historical Jev run.
- A generated preference pair leaks a benchmark question, answer, gold ID,
  benchmark split label, or source-specific template into training.
- Conversation-level bootstrapping is unstable because there are only ten
  LoCoMo clusters; report this limitation and do not interpret a nominal point
  win as decisive.
- Hugging Face upload credentials are unavailable, repository visibility is
  public, or dataset/model license review fails; keep artifacts on `MEM` and
  report the exact publication blocker.

## Success Criteria

- **SC-001**: The off-the-shelf Skywork condition completes on all valid frozen
  LoCoMo cases or reports each failure explicitly, with no unrecorded changes to
  candidates or metrics.
- **SC-002**: The training dataset has zero benchmark question/candidate/gold
  evidence leakage under exact and normalized deduplication plus manual review
  of flagged near matches.
- **SC-003**: AtMem-MJM adapter reloads from the pinned Skywork base and scores
  the fixed candidate set locally without hosted model evaluation or benchmark
  data egress.
- **SC-004**: The final scorecard contains all four arms, primary metrics,
  per-question outputs, resource measures, paired differences, uncertainty,
  and historical anomaly disclosure.
- **SC-005**: All reranking arms have identical candidate-pool hashes and
  Recall@10 of 0.6495 on the matched historical corpus, unless a documented
  upstream evidence correction changes the shared scoring rule for every arm.
- **SC-006**: A Jev advantage claim is supported only if MRR@5 is higher on the
  common set and the paired conversation-level 95% bootstrap interval for the
  difference excludes zero. If Jev per-question outputs are unavailable, make
  no statistical or superiority claim against Jev.
- **SC-007**: All generated project artifacts, caches, environment files,
  training data, model files, and outputs are on `/Volumes/MEM/AtMem-MJM/`; no
  training data or model files are written to internal storage.
- **SC-008**: Re-running from the recorded source/data/model manifests reproduces
  exact candidate IDs and materially identical deterministic scores, with
  stochastic results accompanied by recorded seeds and variation.
- **SC-009**: The experiment report explicitly limits conclusions to memory
  evidence ranking on the tested corpus unless an independently scored
  answer-generation arm is run.
- **SC-010**: Hugging Face-ready model and dataset artifacts include cards,
  license/provenance metadata, hashes, and matching revisions. Uploads remain
  private and public release remains outside this feature.

## Assumptions

- The user approves this draft and the completed Spec Kit artifacts before any
  model download, baseline inference, labeling, training, or benchmark run.
- The external volume remains mounted at `/Volumes/MEM` and has enough free
  space; free-space requirements will be measured before the first download.
- The existing LoCoMo source can be lawfully used for local evaluation. Its
  license and dataset terms will be verified before staging a copy.
- The existing per-question Jev results are reusable only if they contain the
  same candidate IDs, dataset digest, and scorer protocol; otherwise they remain
  historical reference values and the comparison is labelled exploratory.
- Preference training starts with a small reviewed set of synthetic,
  non-private memory tasks and expands only if held-out results justify it.
- A compatible local Transformers/TRL MPS path for the exact Skywork reward
  head can be established; otherwise the work pauses for a documented local
  fallback or user-approved compute change.
- Hugging Face artifacts are initially private. The user has authorized upload
  of newly authored/licensed AtMem synthetic preference data and model
  artifacts; benchmark evaluation corpora and private histories remain local.

## Review Gate

After the user approves this specification and its plan/tasks, execution follows
this order: (1) create the external project root and immutable environment/source
snapshot on `MEM`; (2) run and freeze the off-the-shelf Skywork baseline; (3)
construct and review AtMem preference data, then train AtMem-MJM from the pinned
Skywork checkpoint; (4) run the four-arm matched benchmark and analyze results;
(5) prepare private Hugging Face model/dataset artifacts if data and license
checks pass. No benchmark or training stage starts before specification approval.
