# Production memory benchmarks

This track is designed for production-level evidence. It never downloads a
corpus implicitly and never checks benchmark data into the repository.

## LoCoMo

Obtain the official `data/locomo10.json` from
[`snap-research/locomo`](https://github.com/snap-research/locomo), review its
CC BY-NC 4.0 terms, and pass the local file explicitly:

```bash
python -m research.production_benchmarks.cli locomo \
  --data /path/to/locomo10.json \
  --sample 1 \
  --output /tmp/locomo-dev.json
```

`--sample` is an exploratory development run. It cannot receive production
status. A full run uses `--full-corpus`; before calling it production-candidate,
replace the manifest's blank `expected_sha256` with the verified SHA-256 of the
exact local file and retain the manifest with the result.

The first adapter measures retrieval and gold-evidence coverage, not answer
generation. It uses the real AtMem `Memory` engine and keeps the original
LoCoMo dialogue IDs in the result rows.

## Optional Jev comparison

To compare AtMem's deterministic order with Jev reranking on the same local
corpus, explicitly authorize benchmark egress:

```bash
set -a; source .env.atmem-c709e; set +a
python -m research.production_benchmarks.cli locomo \
  --data /path/to/locomo10.json \
  --full-corpus --allow-upstream-anomalies \
  --jev --allow-egress --jev-batch-size 50 \
  --output /tmp/locomo-jev.json
```

Jev can reorder only AtMem's nominated candidates. It cannot add records or
bypass AtMem eligibility. The full-corpus Jev run is therefore a reranking
comparison, not a complete end-to-end answer-quality benchmark.

LongMemEval and BEAM manifests are staged. Their adapters must preserve their
official scoring and long-history/workload contracts before production claims
are allowed.
