# Implementation Plan: AtMem Memory Judgment Training

**Branch**: `039-atmem-memory-judgment-training`  
**Date**: 2026-09-28  
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from
`specs/039-atmem-memory-judgment-training/spec.md`

## Summary

Evaluate the published Skywork Reward V2 Qwen3 0.6B checkpoint on the existing
AtMem LoCoMo top-ten candidate pools, then post-train a memory-specific adapter
from that exact checkpoint using synthetic, audited pairwise preferences.
Compare Native order, Jev, unmodified Skywork, and AtMem-MJM on identical cases
and candidates. All experiment-owned storage is rooted on the external `MEM`
volume after spec approval.

## Technical Context

**Language/Version**: Python 3.12 (preferred) or 3.13 in an isolated environment.  
**Primary Dependencies**: PyTorch MPS, Transformers, PEFT; pinned Hugging Face Hub libraries. A small local pairwise-loss loop implements Bradley--Terry directly because TRL is absent from the frozen environment and the exact reward head requires an MPS precision check.  
**Storage**: `/Volumes/MEM/AtMem-MJM/` only for experiment-owned data, environments, model cache, logs, outputs, source snapshot, and checkpoints. Since the volume is exFAT, an APFS sparse bundle stored under this root provides the filesystem for high-file-count Python packages and caches; the mounted APFS volume is reached through a symlink under the experiment root.  
**Testing**: Small loader/scorer/data-manifest checks; paired benchmark evaluation; no AtMem product code changes are planned.  
**Target Platform**: Apple M2 MacBook Air, macOS arm64, 16 GB unified memory.  
**Project Type**: External research experiment and model artifact package; no new AtMem runtime integration.  
**Performance Goals**: Score the full 1,986-case LoCoMo pool and train a 0.6B LoRA adapter within available memory. Record actual p50/p95 latency, throughput, wall time, and peak memory; do not promise unmeasured limits.  
**Constraints**: No model/data project writes to internal storage after approval; no cloud compute; no task/candidate/answer/evidence/private-history egress; private Hugging Face upload of approved AtMem-authored/licensed synthetic training data and model artifacts is authorized after privacy, license, and visibility checks; no LoCoMo or LongMemEval training leakage.  
**Scale/Scope**: One 0.6B checkpoint, one synthetic pairwise training set, one full LoCoMo primary run, and an optional separately labelled LongMemEval-V2 confirmation only if a matched ranker adapter can be executed without changing the primary result.

## Constitution Check

- **Authority before intelligence**: Pass. The benchmark's AtMem candidate pool is
  already scoped; model outputs are only orderings of supplied IDs. AtMem
  revalidation remains in force for any later runtime use.
- **Provenance and evidence**: Pass. Source, model, dataset, split, candidate,
  code, and scoring versions are hashed and retained externally.
- **Safe defaults and reversibility**: Pass. This experiment does not activate
  an agent integration or alter memory. A failed scorer leaves native ranking.
- **Scope and deletion**: Pass. Evaluation candidates are frozen copies of
  authorized records; model cannot widen scope or restore deleted content.
- **Executable claims**: Pass with limitation. Reports are ranking research,
  not answer/action guarantees, and retain anomaly disclosure.
- **Local-first and egress**: Pass with a documented, user-approved exception.
  Skywork inference and training are local; private Hugging Face upload is
  limited to approved synthetic training data and model artifacts. Benchmark
  content remained local except for the explicitly authorized Jev API rerun on
  the frozen pool. Per-case Jev outputs and candidate identities are retained
  and verified on MEM; no credential is recorded.
- **Benchmark evidence**: Pass with exploratory status. LoCoMo is a legitimate
  documented corpus; existing four evidence-reference anomalies must remain
  visible and any confirmatory claim must follow the predeclared scorer rule.
- **Storage**: Pass subject to mount guard. A missing/insufficient `MEM` volume
  stops execution; no fallback writes to internal project paths.

## Architecture and decisions

### A. External experiment root

```text
/Volumes/MEM/AtMem-MJM/
├── source/                 # read-only snapshot of required AtMem/research code
├── env/                    # copy-based isolated Python environment
├── cache/                  # HF, datasets, Transformers, and package caches
├── data/                   # frozen benchmark inputs and synthetic preferences
├── baseline/skywork/       # off-the-shelf scores, manifests, logs
├── training/               # configs, checkpoints, adapter, curves, logs
├── benchmark/              # four-arm raw per-case outputs and aggregates
├── hf-export/              # model/dataset cards, manifests, upload staging
└── reports/                # scorecard and limitations
```

An execution guard checks that `/Volumes/MEM` is mounted, writable, has a
predeclared minimum free space, the APFS sparse bundle backing image is stored
under the root and mounted at the expected symlink, and every configured
data/cache/temp/output path resolves to that mounted external image. Set `HF_HOME`, `HF_HUB_CACHE`,
`HF_DATASETS_CACHE`, `TRANSFORMERS_CACHE`, `XDG_CACHE_HOME`, `TMPDIR`,
`UV_CACHE_DIR`, and Python bytecode/cache settings under the external root.
Use copy-based environment creation to avoid reliance on exFAT symlinks. Do not
install project dependencies into or generate build/cache files in the working
repository after approval. Read source from the repository only while constructing
the externally hashed source snapshot.

### B. Freeze code and benchmark inputs before measurement

Copy only the needed benchmark source, AtMem package source, manifests, and
historical Native/Jev per-case results to `source/` or `data/`. Record the
repository commit, dirty diff digest, relevant file manifest, dataset SHA-256,
candidate IDs, candidate content digests, and exact metric implementation. Keep
the active repository untouched. If the historical per-case artifacts do not
prove the required candidate identity, mark them reference-only and regenerate
all arms from a single frozen AtMem candidate-pool run.

LoCoMo drives the four-arm scorecard because it is the source of the existing
Native/Jev numbers. The external LongMemEval-V2 corpus remains evaluation-only
and is not used to train or label the model. Any LongMemEval result is a separate
table and cannot be compared numerically to LoCoMo or represented as a Jev
comparison without a matched Jev arm.

### C. Off-the-shelf Skywork baseline

Pin `Skywork-Reward-V2-Qwen3-0.6B` to a resolved Hub revision and verify its
license/model card. Before training, load the reward head locally and confirm
one finite scalar per task/candidate. Freeze an input template that sends the
task/query and candidate separately using the model's expected sequence
classification interface. All candidates within each case receive identical
trusted metadata fields and token budgets.

Run a scorer-only baseline over the frozen candidate pool, save raw scores and
rankings, and preserve it under `baseline/skywork/`. Stop if the expected reward
head cannot load or if any input includes gold evidence or answer fields.

### D. Synthetic AtMem preference data

Generate synthetic memory episodes with controlled entities, exact facts,
temporal updates, source types, contradictions, procedures, exceptions,
redundancy, and unsupported queries. Candidate pairs share the same task and
include known preference labels from the scenario generator. Split by complete
scenario template/family before generating pair variants. Audit a sample and all
ambiguous label classes. Never use LoCoMo or LongMemEval examples, labels, or
answers for training or teacher labeling.

This first pilot uses 120 controlled scenarios (72 train, 24 validation, and 24
audit pair rows) across ten whole template families. It is deliberately much
smaller than a general preference corpus; expand only after broader family
coverage, owner review, and held-out error analysis justify it. Separate
abstention examples are not inserted into ranking candidates.
Preference labels include direct evidence, time validity, entity/relation match,
conflict, complementarity, and insufficient evidence. Keep those labels out of
the model's runtime prompt.

### E. AtMem-MJM post-training

Use the same pinned Skywork sequence-classification reward checkpoint, pairwise
chosen/rejected samples, and LoRA/PEFT. The frozen environment did not include
TRL, so the pilot uses a transparent PyTorch pairwise-loss loop with the same
Bradley--Terry objective and chosen/rejected data contract. A half-precision MPS
backward probe produced NaNs; float32 training passed, while benchmark inference
used float16 to fit the Mac's shared-memory budget. Save the score head with the
adapter. Record only measured memory/runtime fields; if scoring completes but
post-processing is interrupted, mark unavailable measurements instead of
substituting a loader probe.

Before MPS measurement, inspect and record the actual macOS Metal/compiler
cache path. Prefer an external location where practical. The user has explicitly
permitted the OS-managed cache to remain internal if it cannot be redirected;
this exception does not extend to project-owned files.

No full fine-tune, larger model, quantization-dependent MPS QLoRA, or hosted GPU
is included in this experiment. If the exact reward head cannot train on MPS,
pause and return with a specific technical blocker; do not silently switch
architecture, cloud provider, or egress profile.

### F. Four-arm benchmark and analysis

For each frozen question, give Native, Jev, off-the-shelf Skywork, and
AtMem-MJM the identical top-ten candidate IDs and allowed candidate fields. Use
one scorer implementation for Recall@1/10 and MRR@5. Preserve per-case data and
model failure outcomes. A failed model call cannot silently become a different
ranker; use a declared fallback and count it.

Report full-corpus and separately predeclared anomaly-aware results. Calculate
paired metric differences against Jev, with bootstrap resampling at the
conversation level. With ten clusters, label uncertainty as coarse and avoid
making a superiority claim unless the predeclared interval criterion passes.
Recall@10 must remain 0.6495 for each reranking arm on the same candidate set.
The benchmark is evidence-ranking evaluation; no end-answer improvement claim
is made without a separately controlled fixed-reader study.

### G. Hugging Face artifacts

Create external staging with a model card, data card, license/source manifest,
training config, dataset split manifest, file digests, and results. Prepare
private model and dataset repositories only after benchmark validation. Publish
only AtMem-authored synthetic preference data and its permitted metadata, not
raw benchmark datasets, private histories, tokens, or secrets. Public release
is outside this feature. Use the preconfigured Hugging Face environment
credential; never print, copy into manifests, or retain it in experiment files.

## Project Structure

### Specification files (repository; prepared before approval)

```text
specs/039-atmem-memory-judgment-training/
├── spec.md
├── research.md
├── plan.md
├── data-model.md
└── tasks.md
```

### Experiment files (external volume, created only after spec approval)

```text
/Volumes/MEM/AtMem-MJM/
├── source/
├── env/
├── cache/
├── data/
├── baseline/skywork/
├── training/
├── benchmark/
├── hf-export/
└── reports/
```

**Structure Decision**: Keep the experiment separate from AtMem runtime code.
Snapshot the minimal required current code to `MEM`, execute from that external
root, and do not edit existing repository files as part of the benchmark.

## Execution Gates

1. **Spec gate**: User reviews and explicitly approves `spec.md`, `plan.md`, and
   `tasks.md`. No model download or benchmark execution before this gate.
2. **Storage and source gate**: Verify `MEM` mount/free space and route all
  caches, temporary files, environments, and outputs to the external root.
  Freeze code/data/model manifests. Include the actual macOS Metal cache path
  and apply the user's narrow exception if it remains on internal storage.
3. **Skywork gate**: Complete and save the unmodified Skywork baseline before
   constructing/training the AtMem-MJM adapter.
4. **Training gate**: Validate split separation and label quality, train one
   local adapter, and verify it reloads.
5. **Benchmark gate**: Run matched four-arm evaluation and report raw data,
   metrics, uncertainties, resource measurements, and known limitations.
6. **Artifact gate**: Prepare private Hugging Face repositories only if the
   user-approved privacy/license criteria and all manifests pass.

## Complexity Tracking

No constitution violations are proposed. The external-volume guard is required
because the user explicitly requires all experiment storage to use `MEM`.
