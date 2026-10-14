---
license: apache-2.0
base_model: convaiinnovations/laya-multilingual
pipeline_tag: text-classification
library_name: laya
tags:
- memory-decision
- state-transition
- multilingual
- research-only
- rejected-candidate
---

# Laya Memory Decision — Selective V3 Research Candidate

This is a portable, multilingual Laya checkpoint for one bounded memory
question: choose `STORE_NEW` or `DO_NOT_STORE` from an observation plus
authorized same-scope retrieved memory state. It is independent of AtMem: any
host can construct the versioned JSON request, keep the opaque option binding,
validate the probability vector, and retain final mutation authority.

**Outcome: rejected for automatic activation.** The checkpoint is public for
reproduction and inspection, not as a recommended production model. It
predicts `DO_NOT_STORE` too often and did not improve the matched operational
result over deterministic AtMem.

## Contract

Input:

```json
{
  "format": "laya-evaluation-request-v2",
  "schema_version": "2.0.0",
  "request_id": "opaque-request",
  "scope_id": "opaque-scope",
  "canonical_generation": 184,
  "observation": {
    "id": "opaque-observation",
    "content": "Actually, call me Sara from now on.",
    "speaker_role": "user",
    "source_digest": "sha256:..."
  },
  "retrieved_memories": [],
  "question": {
    "question_id": "formation.joint_transition.v3",
    "type": "choice",
    "instructions": "Select the one memory-state transition supported by the authorized observation and retrieved active memories.",
    "options": [
      {"id": "option_000", "description": "Create a distinct durable memory from the observation."},
      {"id": "option_001", "description": "Do not create persistent memory from the observation."}
    ]
  }
}
```

Output:

```json
{
  "format": "laya-choice-response-v2",
  "schema_version": "2.0.0",
  "request_id": "opaque-request",
  "question_id": "formation.joint_transition.v3",
  "type": "choice",
  "choice": "option_001",
  "probabilities": {"option_000": 0.04, "option_001": 0.96},
  "confidence": 0.96
}
```

Option meanings must be bound by the host request. The model does not write,
update, supersede, forget, or delete memory. It does not generate canonical
memory text.

## Training

- Base: `convaiinnovations/laya-multilingual` at
  `1720e3e3357cfe1e281542e223f8273b0890ca34`.
- Dataset: `atmem/stateful-memory-transitions-selective-v3-research` at
  `f46cdcd23c189cacdaa68abd2ec780752227e9f4`.
- Objective: soft cross-entropy, one epoch, seed `410239`.
- Device: Apple MPS research run; MPS scatter-reduce determinism is unavailable
  and recorded warn-only.
- Conversation content: authentic source conversations only; no generated
  conversation, LoCoMo, translation, or sealed-test label was used.
- Exact-packing policy: 218 train, 49 validation, and 58 calibration examples
  exceeded the 1,024-token serving budget and were excluded before optimization
  or scoring.
- Retained train coverage: 1,647 `DO_NOT_STORE` and 50 `STORE_NEW` distinct
  trajectories. The positive class is below the 100-trajectory activation
  minimum.
- Weights SHA-256:
  `93f1d0c623b956fbe9c92a25b57b4298a08ff8bf5e0b7f182635361d2c304104`.
- Training time: 1,136.37 seconds.
- No calibration bundle was issued because semantic coverage and overflow gates
  failed.

## Results

### Authentic validation subset that fits the serving budget

| Measure | Original Laya | Fine-tuned candidate |
|---|---:|---:|
| Evaluated transitions | 423 | 423 |
| Accuracy | 72.34% | 96.22% |
| Macro-F1 | 0.443 | 0.627 |
| Brier score | 0.3978 | 0.0727 |
| ECE | 0.0830 | 0.0361 |
| Predicted `STORE_NEW` | 105 | 4 |

Only about 3 of 18 positive validation examples were recovered. The apparent
aggregate gain is mostly improved `DO_NOT_STORE` precision, not strong durable
memory recall.

### Matched frozen 100-item operational replay

| Measure | Deterministic | Original Laya | Fine-tuned candidate |
|---|---:|---:|---:|
| Exact policy agreement / 100 | 30 | 30 | 20 |
| STORE correct / 25 | 25 | 0 | 0 |
| DO_NOT_STORE correct / 20 | 5 | 0 | 20 |
| UPDATE correct / 15 | 0 | 0 | 0 |
| DUPLICATE correct / 10 | 0 | 0 | 0 |
| REVIEW correct / 30 | 0 | 30 | 0 |
| Median end-to-end latency | 3.15 ms | 45.35 ms | 45.26 ms |
| p95 end-to-end latency | 4.73 ms | 52.55 ms | 52.84 ms |

The fine-tuned candidate returned `DO_NOT_STORE` for all 100 operational cases.
The operational corpus is a maintainer-created policy challenge, not an
independent scientific benchmark; its value here is the matched product
regression test.

## Intended use

Use this checkpoint to reproduce the negative result, test the strict V3 wire
contract, or study selective memory-decision training. Do not enable it as an
automatic memory authority. A future candidate needs materially more authentic
`STORE_NEW` coverage, relational transition coverage, tokenizer-budget-safe
state packing, per-action calibration, and a matched gain over deterministic
formation before activation.
