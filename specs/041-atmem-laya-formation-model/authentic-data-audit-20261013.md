# Authentic training/data audit — 2026-10-13

## Decision

Spec 041 now supersedes the earlier synthetic and mixed/generated training
lineages. The replacement model may train only on source-licensed,
human-origin conversations with machine weak-supervision annotations. LoCoMo is
excluded from the feature. Generated dialogue, generated continuations,
synthetic or hand-authored scenarios, paraphrase augmentation and translated
quota fill are forbidden as training conversation content.

The target is structured memory understanding, not a store/ignore text-dump
classifier. A row proposes meaning, scope, temporal validity, durability and a
relation to prior understanding, together with an evidence-bound state
transition. AtMem alone may authorize and apply the transition.

## Surfaces reviewed and corrected

| Surface | Result |
| --- | --- |
| Constitution | LoCoMo mandate removed for authentic-conversation claims; Amendment 2.3 requires held-out human-origin confirmation. |
| `spec.md` | Explicit zero-synthetic training rule, LoCoMo exclusion, structured meaning and independent multi-pass database review added. |
| `plan.md` | Prompt batches replaced by a corpus-wide immutable SQLite workflow and isolated Codex/Claude self-review loops. |
| `data-model.md` | Fictional scenario schema replaced by source/conversation/turn, duplicate graph, judge history, adjudication and final-label models. |
| Contract | Authentic Memory Understanding V2 defines living-state semantics and authoritative mapping. |
| Labeling protocol/schema | Six dispositions, structured meaning, exact evidence/relationship targets and four self-review views required. |
| Training entry point | Removed remote synthetic-v1 fallback and mixed/generated-v2 eligibility; final authentic manifest is mandatory. |
| Dataset publisher | Requires the same final-manifest validator before public upload. |
| Model publisher | Rejects a model whose training manifest is not bound to the authentic understanding schema. |
| Runtime artifact | Old synthetic-trained revision is marked superseded and cannot be resolved or loaded for activation. |
| Cards/templates | Old cards are marked historical; replacement templates require authentic provenance and dual-review evidence. |
| Release/website/README | Beta is explicitly blocked; old artifacts and scores no longer qualify the release. |
| Historical reports/paper/status | Retained for audit with supersession notices; not current evidence. |

## Machine-enforced final gates

`research/laya_memory_evidence/policy.py` is the shared validator for training
and dataset publication. It requires 20,000–100,000 accepted rows with an exact
count and stop reason below the target; zero
generated, translated and hand-authored conversation rows; complete source,
license and human-origin evidence; global duplicate graph and split isolation;
exact language allocation; privacy clearance; a complete Codex first pass; all
four self-review views; and, when authenticated allowance remains available,
an independent Claude pass frozen before comparison. A Claude-credit fallback
must be exposed as Codex-only weak supervision.

The immutable supersession registry is
`research/laya_memory_evidence/superseded-artifacts.json`.

## Historical material intentionally retained

`research/laya_formation/dataset/`, `dataset_v2/`, old receipts, OpenClaw
diagnostic runs, benchmark adapters and old publication cards remain in the
repository so prior work stays reproducible. They are not imported by the new
corpus builder and cannot satisfy the final-manifest validator. Removing them
would hide provenance without improving the new training data.

## Remaining blockers

- The database schema and restricted judge query service must be implemented.
- More than 100,000 eligible authentic candidates must be imported and globally
  clustered before judging.
- Both CLI judges must complete first-pass and all self-review loops.
- At least 20,000 and preferably 100,000 accepted rows must pass final quotas, privacy, licensing,
  deduplication, split and adjudication gates.
- Only then may replacement model training, held-out confirmation, Hugging Face
  publication or the 2.3.9b1 release proceed.

## Verification

Focused authentic-policy and labeling/export tests: `15 passed` on 2026-10-13.
