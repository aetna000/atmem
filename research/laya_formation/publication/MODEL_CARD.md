---
license: apache-2.0
base_model: convaiinnovations/laya-multilingual
library_name: laya
datasets:
  - atmem/stateful-memory-transitions-10pct-v2
tags: [laya, typed-decisions, memory, multilingual, research]
---

# Laya Memory Decision V2 — authentic-conversation research checkpoint

This is a portable multilingual classifier for memory-state decisions. A host
memory system supplies a new observation, its authorized retrieved memories,
and one bounded Choice, Noul, or Score question. The model returns a typed
probability distribution; it does not generate memory text or write a database.

The checkpoint is independent of AtMem. AtMem is one compatible host and owns
retrieval, authorization, mutation, provenance, and receipts. Other memory
systems can use the same JSON contract in `questions.json`.

## Status

**Research-only, uncalibrated checkpoint.** It is public for inspection and
experimentation, but is not qualified to authorize automatic memory mutation.
The calibration split lacks enough relational operations, and the frozen
production selector therefore returned `blocked`.

## Data and lineage

| Item | Frozen identity |
|---|---|
| Base model | `convaiinnovations/laya-multilingual@1720e3e3357cfe1e281542e223f8273b0890ca34` |
| Laya source | `NandhaKishorM/laya@68804629e8ccd9d616d48a40e87de9fabbeae069` |
| Dataset | `atmem/stateful-memory-transitions-10pct-v2@92a851b7f1811d3403f8d2282ac1275e6f957922` |
| Dataset manifest | `2cb6aac781b07f6734bbbc4a465260850363c77093e2a79c7ded4c98de2c4730` |
| Training run | `rlcd-410239-20261013T203312Z` |
| Model SHA-256 | `17c949572ecd43917ed8d0413c3e2c68252432ef1034623e57caf61d7920ada1` |
| Seed | `410239` |

The dataset contains only human-origin public conversation rows selected from
WildChat-1M and LUFY. It contains no generated, synthetic, translated, or
hand-authored conversation rows. Transition labels are contextual machine weak
supervision produced against frozen scoped SQLite and vector state; they are not
human ground truth. Users, conversations, scopes, chronological chains, and
duplicate clusters are split together to prevent cross-split leakage.

## Typed contract

The host sends a versioned request containing the observation, authorized
retrieved memories, canonical generation, and exactly one typed question:

```json
{
  "format": "laya-evaluation-request-v2",
  "schema_version": "2.0.0",
  "request_id": "req_01",
  "scope_id": "opaque-scope",
  "canonical_generation": 184,
  "observation": {"id": "obs_01", "speaker_role": "user", "content": "Actually, call me Sara rather than Mona."},
  "retrieved_memories": [{"id": "mem_41", "content": "The user prefers to be called Mona.", "lifecycle": "active"}],
  "question": {
    "question_id": "formation.operation.v2",
    "type": "choice",
    "instructions": "Select the supported memory-state operation.",
    "options": [
      {"id": "STORE_NEW", "description": "Create distinct durable memory."},
      {"id": "UPDATE_EXISTING", "description": "Add compatible detail."},
      {"id": "SUPERSEDE_EXISTING", "description": "Replace outdated memory."},
      {"id": "DUPLICATE", "description": "Meaning is already represented."},
      {"id": "DO_NOT_STORE", "description": "Do not create memory."},
      {"id": "FORGET_EXISTING", "description": "Retire an authorized target."}
    ]
  }
}
```

The output is projected to a strict Choice, Noul, or Score response with a full
probability distribution. `questions.json` contains the frozen definitions. A
host must preserve complete state, reject truncation, restrict target IDs to the
authorized retrieved set, and treat every output as a proposal.

## Loading

```python
from laya import Agent

agent = Agent("atmem/laya-memory-decision-v2", device="cpu")
result = agent.system_one(
    {
        "observation": {"id": "obs_01", "content": "Call me Sara."},
        "retrieved_memories": [],
    },
    {
        "formation.is_durable.v2": {
            "type": "noul",
            "statement": "The observation is likely to remain useful later."
        }
    },
    max_len=1024,
    head_max_len=256,
)
```

Pin the model revision in reproducible or governed deployments.

## Training

Training used upstream RLCD/proper scoring for four epochs on one RTX 3090,
micro-batch 8, gradient accumulation 8, encoder learning rate `2.5e-5`, head
learning rate `1e-4`, FP32, gradient clipping `1.0`, and seed `410239`. PyTorch
CUDA has no deterministic `cumsum` kernel used by the RLCD ordered-score reward;
the run records a warn-only exception for that operation while retaining fixed
seeds and deterministic settings elsewhere.

The predeclared production selector rejected both RLCD and soft-CE because of
input truncation, missing rare expected classes, and insufficient calibration
power. RLCD was nominated only for research comparison from non-sealed metrics.

## Frozen evaluation

The sealed split has 1,999 transitions after privacy exclusions: 1,821
`DO_NOT_STORE`, 107 `STORE_NEW`, 61 `REVIEW`, 8 `UPDATE_EXISTING`, and 2
`DUPLICATE`; it contains no `SUPERSEDE_EXISTING` or `FORGET_EXISTING` examples.

| Metric | Base Laya | Fine-tuned checkpoint |
|---|---:|---:|
| Fully correct transitions | 367 / 1,999 (18.36%) | 1,475 / 1,999 (73.79%) |
| Operation accuracy | 25.11% | 80.54% |
| Operation macro-F1 | 9.18% | 23.37% |
| Target accuracy | 0.00% | 10.00% |
| Runtime failures | 1,269 | 215 |
| False stores | 2 | 15 |
| Unsafe mutations | 10 | 9 |
| Brier score | 0.4957 | 0.1852 |
| ECE | 0.5653 | 0.4092 |

The paired fully-correct improvement is `+55.43` percentage points; paired
bootstrap 95% CI `[+53.18, +57.63]`. A constant `DO_NOT_STORE` classifier would
score 91.10% aggregate on this imbalanced split, so aggregate accuracy alone is
not evidence of a deployable decision model. The fine-tuned checkpoint improves
macro-F1 over base Laya but increases false storage and remains poorly
calibrated.

## Appropriate use

- Research on typed memory-decision contracts and state-aware classification.
- Offline comparison using the published frozen database and transition set.
- Proposal-only integration behind host validation and explicit review.

Do not use this checkpoint as an authorization oracle, autonomous database
writer, deletion authority, or calibrated production classifier.

## License

Apache-2.0. Source-dataset licenses and provenance are recorded per row in the
dataset card and manifest.
