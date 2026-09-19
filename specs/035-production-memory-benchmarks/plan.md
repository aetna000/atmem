# Production memory benchmark plan

## Architecture

- `research/production_benchmarks/manifest.py`: strict manifest and claim-gate
  validation.
- `research/production_benchmarks/metrics.py`: ranking, evidence coverage,
  latency, throughput, and resource metrics.
- `research/production_benchmarks/locomo.py`: official LoCoMo loader and real
  AtMem ingestion/recall runner.
- `research/production_benchmarks/cli.py`: `locomo`, `validate-manifest`, and
  `status` commands; no implicit downloads.
- `research/production_benchmarks/manifests/*.json`: source/license metadata for
  LoCoMo, LongMemEval, and BEAM.
- `research/production_benchmarks/README.md`: acquisition, licensing, commands,
  output contract, and claim policy.

## LoCoMo evaluation profile

The adapter reads the official `locomo10.json`, creates an isolated AtMem
subject per conversation, ingests every dialogue turn as a benchmark-bound
interpreted observation keyed to its original `dia_id`, then recalls for every
QA item. This measures the retrieval layer and maps gold evidence IDs directly;
it does not use a hosted LLM to judge answers. A development sample is allowed,
but its report status is `exploratory`, never production.

## Claim gates

1. Source path exists and parses as the expected format.
2. SHA-256 matches the manifest or the run is rejected.
3. Dataset license and source URL are recorded.
4. Full corpus or an explicitly declared held-out split is used.
5. AtMem version, Python version, platform, seed, config, and resource sample
   are recorded.
6. Results include quality plus p50/p95 latency, throughput, and errors.

## Safety and reproducibility

No corpus data is checked in. The runner never calls Jev or another hosted model
unless a future adapter explicitly receives an egress flag. Each run writes a
manifest copy, input digest, raw per-question rows, and aggregate metrics.
