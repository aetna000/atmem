# Reproducing the AtMem 2.3.8 development benchmark

## What is frozen

| Component | Revision or identity |
|---|---|
| AtMem final Dolphin candidate | `b97d35e1df7ee6ef435928bafb8189ac99a1856d` |
| AtMem AGMI vendor candidate | `fdc63de4b5ced0029f2717ee542b9600730ce3fd` |
| Published AtMem wheel independently checked by AGMI maintainer | `2.3.8`, SHA-256 `05ca2c579be1af55de1da056ae257062417831b2e8eb4f2fda2a6413ba3ee923` |
| LongMemEval-V2 code | `2cc8c540bdb87fe6761629b585e727e1c4704520` |
| LongMemEval-V2 dataset | `xiaowu0162/longmemeval-v2@f152293e235517d504809563c833d7190b8c713b` |
| DolphinBench | `81cb6f8405b40a9e76089cef650806a80af06ea2` |
| Mem0 OSS | `d3891e48baa2c6e769f9cfa4003873bd6a85bc07` (declares 2.1.0) |
| AGMI | `115493a41a7b41952f92ec07e1ea0932926e194f` (0.6.3) |
| Reader | `Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| Judge | `gpt-5.2-2025-12-11`, reasoning effort `medium` |

The authoritative details are in `protocols/2.3.8.yaml`. The two complete AtMem source trees are preserved as deterministic Git archives in `source/`.

## 1. Download and verify this bundle

```bash
hf download atmem/atmem-2.3.8-benchmark \
  --repo-type dataset \
  --local-dir atmem-2.3.8-benchmark
cd atmem-2.3.8-benchmark
python3 scripts/verify_bundle.py --bundle .
```

## 2. Prepare pinned source and public benchmark data

Review the upstream licenses before downloading. Then run:

```bash
bash scripts/bootstrap_reproduction.sh ./reproduction-work
```

The script:

1. extracts both complete AtMem source snapshots;
2. checks out LongMemEval-V2, DolphinBench, Mem0 and AGMI at their pinned commits;
3. downloads LongMemEval-V2 at its pinned dataset revision;
4. verifies the recorded LongMem dataset hashes;
5. creates a Python 3.12 environment and installs the pinned controller dependencies.

It does not download the 9B reader weights, provision a GPU, access credentials, or start billable evaluation.

## 3. Required credentials and compute

- A Hugging Face account able to access the pinned Qwen model revision.
- An OpenAI API key able to call the dated judge snapshot.
- A GPU endpoint compatible with the frozen reader route. The recorded run used one secure A100 80 GB worker, the pinned container digest, and `vllm==0.29.0`.
- Python 3.12 for the controller environment.

Never place credentials in a run configuration or published artifact. Use the environment variables named by `protocols/2.3.8.yaml` and the upstream runner documentation.

## 4. Validate without paid calls

From the extracted `atmem-b97d35e` source tree:

```bash
. ../venv/bin/activate
python research/production_benchmarks/run_longmem_pilot.py \
  --checkout ../LongMemEval-V2 \
  --data-root ../longmemeval-v2-data \
  --output-root ../runs/longmem-preflight \
  --finalization-gate ../manifests/longmem-finalization.json \
  --preflight-only
```

The runner intentionally rejects changed source files, data hashes, split IDs, adapters, prompts, model revisions, hardware declarations, and missing finalization artifacts. Create fresh reviewed finalization manifests for a new run; old manifests bind old checkpoints and cost authorizations and must not be reused.

For DolphinBench, first validate the official release:

```bash
cd ../DolphinBench
python -m construction.validate_release
```

Then follow `benchmarks/retrieval_quality/README.md` in the AtMem source snapshot. Configure the official runner with:

- AtMem adapter: `research.production_benchmarks.dolphinbench:create_development`
- Mem0 adapter: `research.production_benchmarks.dolphinbench:create_mem0_development`
- Agent driver: `research.production_benchmarks.dolphin_openai_driver:run`
- the exact source, model, checkpoint, cost, and finalization identities required by the frozen protocol.

## 5. Run the frozen evaluations

Paid calls require the explicit flags built into the runners. The main entry points are:

```bash
# LongMemEval-V2, all matched arms
python research/production_benchmarks/run_longmem_pilot.py --help

# DolphinBench matched AtMem and Mem0 arms
python research/production_benchmarks/run_dolphin_matched.py --help

# DolphinBench removal and restored-evidence controls
python research/production_benchmarks/run_dolphin_removal_controls.py --help

# AGMI integrity evaluation, no model required
python research/production_benchmarks/run_agmi_integrity.py --help
```

Use the 23 LongMem question IDs and 30 Dolphin task IDs in the frozen development profiles. Retain every attempted case in the denominator. Do not use the confirmation IDs for development or tuning.

## 6. Compare outputs

The recorded aggregate artifacts are under `baselines/`. Their associated raw-output SHA-256 values are recorded in `benchmark-metadata.json` and `baselines/five-percent-results-20261010.json`.

```bash
python3 scripts/verify_bundle.py \
  --bundle . \
  --longmem-data ./reproduction-work/longmemeval-v2-data \
  --dolphin-checkout ./reproduction-work/DolphinBench
```

A new independent run should publish its per-case outputs, costs, system failures, source identities, and hashes. Do not treat a differing provider response as file corruption: model and judge services can remain nondeterministic even with pinned revisions and seeds.

## Known limits

- These are frozen development samples: 23/451 LongMem questions and 30/600 Dolphin tasks.
- The original raw per-case paid-provider transcripts are not in this bundle. The recorded hashes can verify an independently obtained copy but cannot reconstruct it.
- The Mem0 Dolphin arm lacked optional spaCy and `fastembed` extras.
- Aggregate counts are insufficient for a conventional paired significance claim.
- The AGMI maintainer independently reproduced the vendor results from the published PyPI wheel on Linux and macOS. Chain-only still cannot detect whole-store snapshot rollback without trusted external state.
