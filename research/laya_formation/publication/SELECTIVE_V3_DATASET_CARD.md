---
pretty_name: Stateful Memory Transitions — Selective V3 Research
license: other
task_categories:
- text-classification
language:
- multilingual
tags:
- authentic-conversation
- memory-decision
- state-transition
- laya
configs:
- config_name: transitions
  data_files:
  - split: train
    path: records/decisions-train.jsonl
  - split: validation
    path: records/decisions-validation.jsonl
  - split: calibration
    path: records/decisions-calibration.jsonl
---

# Stateful Memory Transitions — Selective V3 Research

A portable two-action memory-decision dataset derived from authentic,
original-language human–AI conversations. Each row asks one bounded question:
should the new observation become a distinct durable memory (`STORE_NEW`), or
should it not be retained (`DO_NOT_STORE`)?

The input is stateful: the observation is accompanied by the same-scope memories
retrieved from a frozen SQLite/vector baseline. The model returns an opaque
finite Choice; the `v3_option_bindings` field maps that choice to its semantic
operation for the host memory system. No AtMem installation is needed to read or
train on the contract.

## Data preview

| ID | Expected | Language | Observation | Retrieved state |
|---|---|---|---|---:|
| transition_022f14f64ced0b0204f7e28a | STORE_NEW | Chinese | 我的名称缩写是yyh | bounded same-scope memories |
| transition_000f40768a09aa1f1de8a93d | DO_NOT_STORE | English | A one-off application debugging request | bounded same-scope memories |
| transition_0140cec46c28764c75de28d3 | DO_NOT_STORE | Chinese | 感觉好累呜呜 | bounded same-scope memories |
| transition_5375c012166e727b4bdd74aa | STORE_NEW | Chinese | An explicit ongoing writing preference | bounded same-scope memories |

The Dataset Viewer exposes the full original observation, bounded retrieved
state, exact question and choices, expected response, operation binding,
post-state digest, provenance, language, and adjudication metadata.

## Splits and coverage

| Split | STORE_NEW | DO_NOT_STORE | Total |
|---|---:|---:|---:|
| train | 60 | 1,855 | 1,915 |
| validation | 24 | 448 | 472 |
| calibration | 16 | 467 | 483 |

Rows for `UPDATE_EXISTING`, `SUPERSEDE_EXISTING`, `DUPLICATE`, `REVIEW`, and
forgetting are deliberately absent from this specialist view. Those operations
remain deterministic until authentic stateful coverage is sufficient.

The current train split has only 60 distinct `STORE_NEW` trajectories, below the
100-trajectory activation minimum. This version is therefore suitable for
reproducible research and data inspection, but not for automatic production
activation. Exact tokenizer packing also identifies over-budget observations;
training code excludes them before optimization and records their IDs.

## Provenance and labels

The parent dataset is
[`atmem/stateful-memory-transitions-10pct-v2`](https://huggingface.co/datasets/atmem/stateful-memory-transitions-10pct-v2),
manifest `sha256:932cae1ba059027c820786075093c97b2165129066ea28bcc3c26496ec8e8eb8`.
Its conversation sources are pinned WildChat-1M (ODC-By 1.0) and LUFY
(CC BY 4.0) revisions. This V3 artifact changes only the bounded question and
option representation: it does not generate, translate, paraphrase, or relabel
conversation content.

Expected transitions are contextual machine-adjudicated weak supervision, not
human ground truth. Splits remain isolated by source conversation, scope,
chronology, and duplicate component. The artifact includes no generated
conversation, hand-authored replacement, translated replica, LoCoMo row, or
sealed-test label.

## Minimal use

```python
import json

row = json.loads(next(open("records/decisions-train.jsonl")))
request = row["request"]
expected_choice = row["expected_response"]["choice"]
binding = next(
    item for item in row["v3_option_bindings"]
    if item["option_id"] == expected_choice
)
print(request["observation"]["content"], binding["operation"])
```

The model-visible request contains opaque target and option identifiers. A host
must keep the binding server-side, validate the returned probability vector,
recheck scope and database generation, and retain final mutation authority.
