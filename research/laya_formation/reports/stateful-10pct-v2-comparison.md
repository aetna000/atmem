# Stateful authentic-conversation comparison (10% pilot)

Frozen sealed set: 1,999 state transitions after privacy exclusions. Labels are
contextual machine weak supervision over frozen scoped SQLite and vector state,
not human ground truth.

| System | Fully correct | Operation accuracy | Operation macro-F1 | Runtime failures | False stores | Unsafe mutations | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Constant `DO_NOT_STORE` control | 1,821 / 1,999 (91.10%) | 91.10% | 19.07% | 0 | 0 | 0 | n/a | n/a |
| Base Laya multilingual | 367 / 1,999 (18.36%) | 25.11% | 9.18% | 1,269 | 2 | 10 | 0.4957 | 0.5653 |
| Fine-tuned Laya RLCD | 1,475 / 1,999 (73.79%) | 80.54% | 23.37% | 215 | 15 | 9 | 0.1852 | 0.4092 |
| AtMem 2.3.8 deterministic path | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

AtMem 2.3.8 retains governed source evidence but does not emit the V2 typed
state-transition rulings evaluated here, so assigning it a V2 score would be a
fabricated comparison. The constant control is included because the sealed set
is heavily imbalanced: 1,821 `DO_NOT_STORE`, 107 `STORE_NEW`, 61 `REVIEW`, 8
`UPDATE_EXISTING`, and 2 `DUPLICATE`, with no `SUPERSEDE_EXISTING` or
`FORGET_EXISTING` cases.

The fine-tuned model improves fully-correct transitions over base Laya by
55.43 percentage points (paired bootstrap 95% CI 53.18–57.63), and improves
operation macro-F1 from 9.18% to 23.37%. It does not beat the constant control
on aggregate accuracy, increases false stores from 2 to 15, remains poorly
calibrated, and is not approved for automatic mutation or an AtMem beta release.

Artifacts:

- Database: https://huggingface.co/datasets/atmem/stateful-memory-database-10pct-v2
- Transitions: https://huggingface.co/datasets/atmem/stateful-memory-transitions-10pct-v2
- Research model: https://huggingface.co/atmem/laya-memory-decision-v2
