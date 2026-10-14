# Data Model: AtMem Memory Judgment Training

All records described here are experiment artifacts and are stored below
`/Volumes/MEM/AtMem-MJM/` after the specification is approved.

## Dataset splits

```text
data/
  source-manifest.json
  generator-config.json
  generated/
    train.jsonl
    validation.jsonl
    audit-sample.jsonl
  frozen/
    locomo-source-manifest.json
    locomo-candidate-pools.jsonl
    locomo-case-split.json
```

Training cases are synthetic and generated from versioned scenario families.
LoCoMo and LongMemEval-V2 content are evaluation-only and must not occur in
generated or reviewed preference splits.

## Preference example

Each JSONL row compares two candidate memories under the same task. The format
is intentionally compatible with a pairwise reward objective while retaining
enough provenance to audit labels.

```json
{
  "example_id": "mjm-train-000001",
  "scenario_family": "current_state_confirmation",
  "split": "train",
  "task": {
    "query": "What delivery address is currently confirmed?",
    "as_of": "2026-01-12T00:00:00Z"
  },
  "chosen": {
    "candidate_id": "mem-new",
    "text": "The customer confirmed 14 Oak St yesterday.",
    "evidence": {
      "source_kind": "direct_user_statement",
      "observed_at": "2026-01-11T00:00:00Z",
      "valid_from": "2026-01-11T00:00:00Z",
      "confidence_origin": "scenario_fixture"
    }
  },
  "rejected": {
    "candidate_id": "mem-old",
    "text": "An older delivery record lists 7 Pine Rd.",
    "evidence": {
      "source_kind": "historical_record",
      "observed_at": "2023-02-01T00:00:00Z",
      "valid_from": "2023-02-01T00:00:00Z",
      "confidence_origin": "scenario_fixture"
    }
  },
  "label": {
    "preferred": "chosen",
    "reason_code": "current_explicit_evidence",
    "support": "direct"
  },
  "provenance": {
    "generator_version": "mjm-synth-v1",
    "seed": 20260928,
    "review_status": "pending"
  }
}
```

The task and candidate fields above are examples only. Generator records use
synthetic entities and no real customer information. The reward-model input
template is a separate versioned artifact; it omits internal labels, split
names, scenario-family IDs, generator seeds, and gold references.

## Benchmark candidate record

Each frozen candidate-pool row binds one question to a dataset digest and
ordered AtMem candidates:

```json
{
  "case_id": "locomo:conversation-id:question-id",
  "dataset_sha256": "...",
  "candidate_pool_sha256": "...",
  "candidates": [
    {"candidate_id": "record-id", "content_sha256": "...", "rank": 1}
  ],
  "gold_evidence_ids": ["..."],
  "known_anomaly": false
}
```

`gold_evidence_ids` and `known_anomaly` are scorer-side only. They MUST be
stripped before candidate scoring. Every arm receives an identical projection
containing the task and authorized candidate data, never scorer-side fields.

## Model and run manifests

`model-manifest.json` records base model ID/revision, license, tokenizer/template
revision, score-head type, adapter digest, quantization/precision, and intended
use. `run-manifest.json` records code snapshot digest, dataset and split hashes,
candidate-pool hash, environment lock, seed, device, memory use, duration,
latency, errors, metric code revision, all arm IDs, and claim status. Credentials
and access tokens are prohibited from every manifest and log.
