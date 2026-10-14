# Tasks: AtMem Memory Judgment Training

**Input**: [spec.md](spec.md), [research.md](research.md),
[plan.md](plan.md), [data-model.md](data-model.md)  
**Execution boundary**: Do not start any task that downloads a model or dataset,
creates the experiment environment, generates training data, trains, or runs a
benchmark until the user approves the spec, plan, and tasks. After approval,
all experiment-owned files go under `/Volumes/MEM/AtMem-MJM/`.

## Phase 1 — Freeze protocol and external storage

- [X] [T001] Record the user-approved scorecard, primary LoCoMo dataset digest,
  four-arm comparison definitions, anomaly policy, target metrics, clustering
  method, local-inference rule, and approved-private-Hugging-Face-egress rule in
  `/Volumes/MEM/AtMem-MJM/data/protocol.json` before model scoring (FR-008–FR-012,
  FR-017, SC-004–SC-006).
- [X] [T002] Add a run preflight that verifies `/Volumes/MEM` is mounted,
  writable, sufficiently free, and is the resolved parent of all configured
  cache/temp/data/output paths; verify the APFS sparse-bundle backing file is
  under `/Volumes/MEM/AtMem-MJM/` and the expected symlink resolves to its mount
  in
  `/Volumes/MEM/AtMem-MJM/source/run_guard.py` (FR-015, SC-007).
- [X] [T003] Create the isolated copy-based Python 3.12/3.13 environment and
  route package, Hugging Face, Transformers, dataset, temp, and bytecode caches
  under `/Volumes/MEM/AtMem-MJM/env/` and `/Volumes/MEM/AtMem-MJM/cache/`;
  retain an environment lock and storage manifest (FR-015–FR-016, SC-007).
- [X] [T004] Create a content-addressed, read-only source snapshot containing
  the exact AtMem benchmark adapter, necessary product source, existing
  Native/Jev per-case results, source revision/diff digests, and relevant
  manifests under `/Volumes/MEM/AtMem-MJM/source/` without modifying the
  working repository (FR-008–FR-009, FR-015–FR-016). Outcome: external snapshot hashes, repository head, and dirty-diff digest recorded.
- [X] [T005] Stage the licensed LoCoMo evaluation file and existing
  LongMemEval-V2 evaluation-only files on `MEM`; verify SHA-256, provenance,
  license/use terms, and split separation in
  `/Volumes/MEM/AtMem-MJM/data/` (FR-005–FR-006, FR-009, SC-002). Outcome: LoCoMo SHA verified; LongMemEval small-set hash recorded and remains evaluation-only on MEM.
- [X] [T006] Verify the historical Jev aggregate's dataset digest, question
  count, candidate protocol, and evidence scorer against the frozen inputs.
  The historical artifact has no per-question Jev rankings; retain it as a
  historical aggregate and use the separately authorized same-pool rerun for
  paired analysis (FR-008–FR-009, FR-011, FR-017).

## Phase 2 — Run the off-the-shelf Skywork baseline

- [X] [T007] Resolve and pin the Skywork Reward V2 Qwen3 0.6B checkpoint,
  tokenizer, model license, and scorer implementation; store snapshots and
  hashes on `MEM` (FR-003, FR-015–FR-016).
- [X] [T008] Confirm local MPS model loading, expected sequence-classification
  reward head, finite scalar output, peak-memory capture, and actual Metal
  compiler-cache write location on representative task/candidate inputs without
  training; prefer external Metal cache placement and record the actual path.
  The user permits the narrow OS-managed internal Metal-cache exception;
  project-owned artifacts remain on `MEM` (FR-003, FR-014, FR-015, FR-017–FR-018).
  Outcome: scalar smoke test passed; macOS used its system-managed cache.
- [X] [T009] Implement a versioned task-plus-one-candidate input template that
  exposes only the frozen task and eligible candidate fields and excludes
  answers, evidence IDs, split, and benchmark labels in
  `/Volumes/MEM/AtMem-MJM/source/score_candidates.py` (FR-002, FR-008).
- [X] [T010] Run the off-the-shelf Skywork scorer over every frozen LoCoMo pool;
  save raw scores, rankings, failures, latency, throughput, memory, model
  digest, and manifest under `/Volumes/MEM/AtMem-MJM/baseline/skywork/` before
  any AtMem-specific model training (FR-003, FR-018–FR-019, SC-001). Result:
  19,860 candidate scores, zero errors; MRR@5 0.4540, Recall@1 0.3661,
  Recall@10 0.6495. Full-run peak MPS memory was not captured; the recorded
  batch latency/throughput and loader-smoke RSS are documented in the external
  metrics report. The historical Jev aggregate is retained separately from the
  completed fresh per-case rerun.

## Phase 3 — Construct and validate memory-specific preferences

- [X] [T011] Implement a seeded synthetic memory-episode generator covering
  exact facts, temporal updates, source authority, conflicts, procedures,
  exceptions, redundancy, wrong entity/relation, and insufficient evidence
  under `/Volumes/MEM/AtMem-MJM/source/data/` (FR-005–FR-007). Outcome: ten fictional domains and eight deterministic preference rules, 120 scenarios.
- [X] [T012] Split by complete scenario template/family before generating
  pairwise variants and write train, validation, and audit manifests to
  `/Volumes/MEM/AtMem-MJM/data/generated/` (FR-005–FR-006, SC-002). Outcome: 72/24/24 train/validation/audit pairs split by ten disjoint scenario families; abstention examples separate.
- [X] [T013] Add exact and normalized leakage checks against LoCoMo and
  LongMemEval-V2 tasks, candidate content, answers, and evidence identifiers;
  report/resolve matches before training (FR-005–FR-006, SC-002). Outcome: zero exact or normalized text matches against staged LoCoMo and LongMemEval; benchmark content stayed local.
- [X] [T014] Audit generated preference labels and ambiguous/insufficient cases
  against the versioned rubric; record audit decisions and label provenance in
  `/Volumes/MEM/AtMem-MJM/data/generated/audit-sample.jsonl` (FR-007, SC-002). Outcome: deterministic agent QA across all eight rules; owner/human semantic review remains pending and is not claimed.
- [X] [T015] Build chosen/rejected pairs compatible with pairwise reward training plus AtMem-specific
  metadata/provenance sidecars; verify the model-facing template omits labels,
  split identity, hidden answers, gold evidence IDs, and benchmark vocabulary
  (FR-004–FR-008).

## Phase 4 — Train AtMem-MJM locally

- [X] [T016] Confirm the exact Skywork checkpoint and reward head can perform a
  backward pass on PyTorch MPS within the 16 GB device memory budget; stop and
  report the blocker if not (FR-014–FR-017).
- [X] [T017] Train one LoRA/PEFT adapter from the pinned Skywork reward
  checkpoint with a recorded seed, fixed split, conservative batch/sequence
  settings, score-head saving, and training-resource logging under
  `/Volumes/MEM/AtMem-MJM/training/` (FR-004, FR-014–FR-016, FR-018). Outcome: 3 epochs over 72 pairs; 574,464 trainable parameters; MPS float32; 2,408,610,816-byte peak allocated memory.
- [X] [T018] Reload the trained adapter from the external artifact, verify base
  and adapter digests, output shape, finite scores, and stable candidate-ID
  mapping; record validation metrics without looking at the final benchmark
  outcomes (FR-004, FR-016, SC-003). Outcome: adapter reload passed; 24 untouched audit pairs scored 24/24 correctly.
- [X] [T019] Review development errors and select any threshold or model
  settings using only the synthetic validation split; freeze config and hash
  before the LoCoMo evaluation is run (FR-006, FR-008, FR-016). Outcome: three-epoch config frozen using synthetic validation only.

## Phase 5 — Run the matched four-arm benchmark

- [X] [T020] Freeze one top-ten candidate-pool manifest and scorer protocol for
  all arms; prove per-case question and candidate-ID identity before scoring
  `/Volumes/MEM/AtMem-MJM/benchmark/` (FR-008–FR-010, SC-004–SC-005). Outcome: same 1,986 questions and 19,860 candidate IDs verified.
- [X] [T021] Produce per-question Native, Skywork, and AtMem-MJM scores/ranks
  over the same cases and candidates; include Jev's historical aggregate as a
  fresh Jev 1.13.0 per-case rerun on the exact pool; retain historical Jev
  aggregate separately. Keep failures and fallbacks visible in raw outputs
  (FR-008–FR-011, FR-017). Outcome: 1,986 successful Jev cases, all ten probabilities per case, zero errors; all 19,860 MJM scores and ranks saved.
- [X] [T022] Calculate MRR@5, Recall@1, Recall@10, paired differences where
  case-level arms are available, and conversation-clustered 95% intervals;
  use the fresh Jev per-case rerun for paired intervals, retain historical
  Jev aggregate as context, verify Recall@10 invariant and
  known anomaly handling, and generate the table in
  `/Volumes/MEM/AtMem-MJM/reports/scorecard.md` (FR-009–FR-013, SC-004–SC-006). Outcome: Native / Jev / Skywork / MJM MRR@5 = 0.4259 / 0.5880 / 0.4540 / 0.4632; Recall@1 = 0.3399 / 0.5433 / 0.3661 / 0.3741; Recall@10 = 0.6495 for all. Paired intervals computed for all arms. MJM full-run inference time and peak memory remain unavailable because the scorer was interrupted after persisting all candidate scores but before post-processing completed; no values were imputed.
- [X] [T023] Produce a separate anomaly-aware sensitivity report with all
  exclusions and case IDs predeclared from the existing validation evidence;
  preserve the all-case report and mark the result exploratory where required
  (FR-009, FR-021). Outcome: exactly four empty-gold-evidence cases excluded; Native / Jev / Skywork / MJM MRR@5 = 0.4268 / 0.5892 / 0.4549 / 0.4641; all-case result remains primary.
- [ ] [T024] Optionally run the held-out LongMemEval-V2 analysis as a separate
  benchmark only after the exact adapter and scoring contract are defined;
  report no Jev comparison unless a matched Jev arm exists (FR-005, FR-013).

## Phase 6 — Prepare Hugging Face artifacts and report

- [X] [T025] Build a model card, dataset card, license/provenance manifests,
  train/validation split hashes, model revision, adapter digest, and results
  summary in `/Volumes/MEM/AtMem-MJM/hf-export/` (FR-020–FR-021, SC-010).
- [X] [T026] Verify the dataset contains only AtMem-authored synthetic or
  otherwise explicitly permitted preference data and excludes private
  histories, benchmark evaluation corpora, answers, tokens, and secrets before
  any upload (FR-005, FR-020).
- [X] [T027] Prepare model and dataset uploads to private Hugging Face
  repositories, confirm visibility remains private, and retain repository
  revision/digests with the external final report. Use the preconfigured
  environment credential without printing or persisting it; upload only the
  approved synthetic dataset and model artifacts, never benchmark content
  (FR-017, FR-020, SC-010). Outcome: private model and dataset repositories uploaded and visibility rechecked; revision IDs are in `/Volumes/MEM/AtMem-MJM/hf-export/private-upload-manifest.json`.
- [X] [T028] Write the final reproducibility report with claims, limitations,
  resource measurements, failures, known anomalies, and exact artifact paths
  in `/Volumes/MEM/AtMem-MJM/reports/final.md` (FR-011–FR-021, SC-001–SC-010). Outcome: final reproducibility report generated on MEM; full-run MJM inference timing/peak memory explicitly unavailable.

- [X] [T029] Rerun Jev through the authorized API on the exact frozen 1,986-question, 19,860-candidate pool; persist raw per-case probabilities/ranks, request errors, latency, model/API metadata, verify candidate identity and Recall@10, then recompute four-arm paired conversation-cluster intervals. User authorized benchmark-text egress; `JEV_API` was loaded from `.env.atmem-c709e` without logging or copying its value. Outcome: Jev 1.13.0 completed in 40 batches of 50; 1,986/1,986 cases, zero errors or omitted probabilities; MRR@5 0.5880, Recall@1 0.5433, Recall@10 0.6495.
- [X] [T030] Publish a public, static Hugging Face Space leaderboard under `javadtaghia`, containing only aggregate metrics, paired intervals, and protocol limitations; verify public visibility and runtime (FR-020–FR-021). Outcome: Space is running at `https://huggingface.co/spaces/javadtaghia/atmem-mjm-leaderboard-20260928`; artifact files and revision are recorded on MEM.

## Dependencies and execution order

- Spec and plan approval precede all execution tasks.
- T001–T006 freeze protocol, external storage, and source/data identity.
- T007–T010 run and preserve the off-the-shelf Skywork baseline first.
- T011–T015 build and audit training preferences without evaluation leakage.
- T016–T019 train and freeze AtMem-MJM using the MPS resource gate.
- T020–T024 perform the matched benchmark and analysis only after training is
  complete; the optional LongMemEval run is a separately labelled result.
- T025–T028 package artifacts only after evaluation and licensing/privacy checks.

## Stop conditions

- Stop before any model/data download or experiment file creation if `MEM` is
  not mounted or the storage guard cannot route every experiment path externally.
- Stop before scoring if dataset, model revision, or candidate-pool digests do
  not match the frozen protocol.
- Stop before training if a benchmark-leakage match is unresolved or the label
  audit finds systematic rubric errors.
- Stop before the final benchmark if the adapter is not reproducibly reloadable
  or changes AtMem eligibility/candidate IDs.
- Stop before Hugging Face upload if model/data rights are unclear or repository
  visibility cannot be verified as private.
