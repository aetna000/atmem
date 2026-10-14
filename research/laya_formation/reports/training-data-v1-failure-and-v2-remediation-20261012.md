# Laya formation v1 failure analysis and v2 data remediation

> **Superseded proposal:** the mixed/generated v2 remediation described here is
> rejected. The replacement policy permits authentic human-origin conversation
> rows only; see `research/laya_memory_evidence/AUTHENTIC_DATA_POLICY.md`.

Date: 2026-10-12  
Status: maintainer diagnosis; v1 model is not eligible for default activation or a quality claim

## Decision

The published v1 training distribution does not test or teach the live formation task. Do not
repair the v1 artifact by lowering its abstention threshold, adding more rows from the same
generator, or reporting its synthetic held-out accuracy. Train a separately versioned v2 model
from the v2 live-state schema and keep the current model fail-closed.

## Direct evidence

The v1 generator writes answer-bearing phrases into the input. Examples include “No prior
canonical record exists”, “A later correction changes it”, “explicitly supersedes”, “Duplicate
evidence repeats it”, and “must not be stored”. A literal-rule baseline recovered all five v1
targets with 100% accuracy on train, validation, and calibration data. Therefore the reported
100% model metrics measured generator-cue recovery, not formation judgment.

The v1 train and serve representations are different. Training receives `scope`,
`initial_state`, and `evidence`; the live packer supplies only `authorized_ranges`. Candidate
digests were authorized but candidate contents were absent from the model input. Consequently,
the model could not compare a new claim with the active memory needed to distinguish a new
memory, a correction, and a duplicate.

The calibration threshold was 1.0 for three-to-five-choice heads. Five independently blocking
heads compounded abstentions. In the original 100-item OpenClaw replay, 94 items reached review.
After a diagnostic threshold override of 0.0, the model still achieved only 25/100 exact policy
matches: 0/25 expected stores, 0/15 expected updates, and only one item retained semantic views.
Observed decisions were 63 review, 25 do-not-store, 11 duplicate, and 1 store. This proves that
calibration was not the primary defect.

Evidence artifacts:

- `research/laya_formation/runs/openclaw-100-20261012/corpus.json`
- `research/laya_formation/runs/openclaw-100-20261012-after-fail-closed/summary.json`
- `research/laya_formation/runs/openclaw-100-20261012-threshold-zero-diagnostic/summary.json`

## V2 correction

The v2 dataset uses one canonical state envelope, `atmem-laya-live-state-v2`, produced by
`atmem.laya_formation.packing.build_authorized_state_v2`. It contains authenticated scope,
authorized evidence text and provenance, and the content—not merely the digest—of authorized
active candidates. Both generated training examples and the governance adapter use this same
builder; a byte-equivalence test protects structural parity.

The replacement learned artifact has one holistic disposition head: `STORE`, `UPDATE`,
`DUPLICATE`, `REVIEW`, or `DO_NOT_STORE`. Memory-class annotations remain in the dataset, but
they are not trained in this iteration: the available natural LAPS augmentation is dominated by
preferences and would make that head materially imbalanced. Existing deterministic formation
continues to type retained memory.

Concrete update targeting is intentionally excluded from model classification. The runtime must
resolve a target deterministically from the authorized candidate set and require review when it
cannot find one exact target.

Each semantic family contains all five counterfactual dispositions. For the three core cases,
the evidence sentence is identical: only the presence and content of authorized candidates
changes. Review cases cover contradictory authoritative claims, ambiguous referents, unconsented
third-party claims, sensitive third-party content, and insufficient provenance. Non-retention
cases cover explicit scope limits, secret-shaped values, turn ephemera, untrusted embedded
instructions, and utterances without memory content.

## Generated corpus and gates

The generated-only diagnostic export is stored outside the repository at
`/Volumes/MEM/atmem-laya-formation-v2-training-20261012`. The mixed candidate corpus is stored at
`/Volumes/MEM/atmem-laya-formation-v2-mixed-20261012`. It combines generated cases with natural
preference utterances from the MIT-licensed LAPS corpus pinned at revision
`ac9c1f5b2d2878d85ed9638ed7418f1523922005`.

The generated component represents:

- 2,000 semantic families and 10,000 scenario examples;
- exactly 2,000 examples per disposition;
- group-disjoint train, validation, and calibration splits;
- no frozen OpenClaw row in training or calibration;
- maximum exact semantic repetition of five;
- 0.0 maximum five-word-shingle Jaccard similarity to the frozen 100-item corpus;
- 76.3211% validation accuracy for a deliberately shallow token/label lookup baseline.

The balanced mixed training split has 6,965 scenario rows: exactly 1,393 per disposition. It uses
2,230 LAPS-grounded STORE/DUPLICATE rows and 4,735 generated rows. LAPS is not used for UPDATE:
many preference categories are multi-valued, so a different preference is not evidence that an
older preference was replaced. DUPLICATE candidates bind the full natural utterance, avoiding a
false duplicate label when one utterance expresses multiple preferences. LAPS validation/test
workers that overlap with training workers are removed; the remaining transfer partitions contain
1,664 validation and 3,360 test examples. These are kept out of training.

The data qualification evaluation now also requires zero disposition words in model-visible
identifiers. This gate caught and removed an early defect where range IDs contained disposition
names. An evidence-only lexical classifier scores 33.3333% on STORE/UPDATE/DUPLICATE because
those counterfactuals intentionally use identical evidence.

The lexical baseline is a leakage alarm, not a quality benchmark. The 100 OpenClaw items were
inspected and directly informed the v2 taxonomy, so they are a regression corpus, not an
independent or untouched test set. No generalization claim may be made from them. Model selection
requires a separately sourced, preregistered confirmation set that remains inaccessible during
generation, training, calibration, and threshold selection.

## Required gates before retraining or publication

1. Independently review a stratified sample of v2 labels and record disagreements.
2. Add a separately sourced confirmation corpus with documented provenance and consent or a
   compatible public license; freeze its hash before training begins.
3. Run exact duplication, normalized shingle, and semantic-neighbour contamination checks across
   every split and confirmation source.
4. Train v2 from a clean base checkpoint. Do not continue from the v1 adapter.
5. Select checkpoints using validation only, fit calibration only on the calibration split, and
   open the confirmation set once after the model and thresholds are frozen.
6. Require per-class precision, recall, macro-F1, confusion matrices, abstention coverage/risk,
   and repeated-seed confidence intervals. Overall accuracy alone is insufficient.
7. Compare against deterministic AtMem and transparent rule/embedding baselines on identical
   authorized inputs. The v2 model must improve useful retention without weakening non-retention
   and review safety.
8. Keep the v1 model opt-in and fail-closed until the replacement passes the operational gates.

Synthetic/generated examples are training material only. They are not evidence for a paper's
real-world effectiveness, usability, benchmark superiority, or generalization claims.
