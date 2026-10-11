# Hugging Face Publication Contract

## Frozen repositories

- Dataset: `atmem/atmem-laya-formation-v1`, repository type `dataset`,
  license `apache-2.0`.
- Model: `atmem/atmem-laya-formation-model-v1`, repository type `model`,
  license `apache-2.0`, derived from the exact Laya revision in `sources.json`.

The `atmem` organization is the project-owned publication namespace. Reference
model publishers, including `cosmos98a`, are provenance inputs and are never
used as AtMem artifact owners.

Names may change only through an updated reviewed source lock before staging.
Dataset and model always have separate commits and publication receipts.

## Staging workflow

1. Create each repository private with a least-privilege write token read from
   `HF_TOKEN`; never print or persist its value.
2. Upload exactly the inventory manifest. Reject symlinks, pickle/joblib files,
   credentials, unlisted files and mutable external references. Hugging Face's
   repository-managed root `.gitattributes` is the sole permitted non-artifact
   file; verify its exact presence separately and record it in the receipt.
3. Download the resulting commit into a clean temporary directory without using
   the training workspace.
4. Verify every size/digest, JSON/JSONL/schema, license and card claim. For the
   model, perform a clean CPU load and frozen prediction smoke.
5. Record `private_staged` and a readiness receipt. Visibility remains private
   until the explicit public-publication task.
6. After explicit approval, change visibility, anonymously redownload the exact
   commit and repeat verification before recording `public_verified`.

Dataset, model, package, website PR and live website states are independent.

## Required inventory

The dataset contains `README.md`, `data/*.jsonl`, optional `data/*.parquet`,
`schemas/`, `manifests/`, `audits/` and `LICENSE`. The model contains
`README.md`, `LICENSE`, `model.safetensors`, `encoder/`, `tokenizer/`,
`rl_agent_config.json`, `questions.json`, `calibration.json`, `training-run.json`
and `evaluation.json`. Every file is listed in an inventory conforming to
`artifact-inventory-v1.schema.json`.
