# Memory quality benchmarks

AtMem ships an offline deterministic release gate for memory extraction,
contradiction handling, retrieval, withholding, injection safety, privacy,
poisoning resistance and fallback. It uses synthetic data and isolated temporary
databases. It does not read your real memory database.

## Run the release gate

```bash
atmem benchmark run --output benchmark.json
```

The command exits `0` when all gates pass and `1` when a gate fails. Safety is
absolute: privacy leaks, successful poisoning and incorrect injection must stay
at zero, and fallback cases must all complete. Extraction, contradiction and
retrieval metrics cannot fall below the checked-in floors. The complete report
is still written on a quality failure.

For machine-readable stdout:

```bash
atmem benchmark run --json
```

The report separates deterministic quality from measured latency. Its
`quality_sha256` excludes timestamps and durations, so two equivalent runs have
the same quality identity even when one machine is slower. Unknown model tokens
or cost are `null` with a reason; they are never reported as zero.

The normalized checked-in example is
[benchmark-deterministic-v1.json](examples/benchmark-deterministic-v1.json).

## Optional profiles

```bash
atmem benchmark profiles
```

For a configured local embedding model:

```bash
export ATMEM_BENCHMARK_LOCAL_EMBEDDINGS=1
export ATMEM_BENCHMARK_LOCAL_EMBEDDINGS_PROVIDER=sentence-transformers
export ATMEM_BENCHMARK_LOCAL_EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
atmem benchmark run --profile local-embeddings --output local-embeddings.json
```

For AtBot, configure and start the companion first, then opt into the matching
egress class:

```bash
atmem atbot setup
atmem atbot start
export ATMEM_BENCHMARK_LOCAL_ATBOT=1
atmem benchmark run --profile local-atbot --output local-atbot.json
```

If `atmem atbot setup` selected a hosted provider instead:

```bash
export ATMEM_BENCHMARK_HOSTED_ATBOT=1
atmem benchmark run --profile hosted-atbot --output hosted-atbot.json
```

Optional profiles require explicit configuration and opt-in. If unavailable,
the command returns a structured `skipped` report and exit code `2`; a skip is
never a pass. Hosted runs must retain their provider/model identity, egress
class, token accounting and explicit run-time pricing metadata. When those
measurements are unavailable, the report says so.

AtBot profiles use the companion for both extraction proposals and ranking.
AtMem captures the source, admits or quarantines each proposal, authorizes
candidates before AtBot sees them, and revalidates ranked record IDs before
context construction.

The deterministic gate imports no optional model SDK and needs no API key or
network connection.

## LongMemEval input

Obtain LongMemEval under its upstream terms and keep it outside this repository.
AtMem does not download or redistribute it.

```bash
atmem benchmark import-longmemeval /path/to/longmemeval.jsonl \
  --output longmemeval-normalized.json
```

The adapter accounts for every input row as supported, skipped or unsupported,
with reasons. Normalization alone is not an AtMem or competitor score.

## Mem0 OSS comparison

The reproducibility manifest pins `mem0ai==2.0.19`, its wheel digest and source
revision. Create a separate environment so Mem0's dependencies cannot change
AtMem's base installation:

```bash
python -m venv .venv-mem0-benchmark
.venv-mem0-benchmark/bin/python -m pip install mem0ai==2.0.19 ollama==0.6.2
```

Both systems must export `atmem-benchmark-external-results-v1` with the same
dataset digest, ordered case IDs, scoring format and relevant model
configuration. Then compare:

```bash
atmem benchmark compare atmem-external.json mem0-external.json \
  --output comparison.json
```

AtMem rejects mismatched inputs rather than calling them a fair comparison.
For compatible inputs it names the winner for every metric and gives one
overall result:

- `atmem_better`: AtMem is no worse on every comparable quality/safety metric
  and better on at least one;
- `mem0_better`: Mem0 meets the same rule;
- `equal`: every comparable quality/safety metric ties;
- `mixed`: each system wins at least one quality/safety metric.

The generated report states the result directly. When AtMem wins, it says:
“AtMem performed better than Mem0 on this benchmark.” No weighted score is
invented to hide a metric that the other system won.

The pinned package version and license were verified against the official
[mem0ai PyPI project](https://pypi.org/project/mem0ai/2.0.19/) on 2026-09-01.

### Recorded LongMemEval-S retrieval campaign

The checked-in result is
[`longmemeval-s-retrieval-12-v1.json`](examples/longmemeval-s-retrieval-12-v1.json).
It uses 12 deterministically selected questions—two from every LongMemEval-S
question category—against Mem0 OSS 2.0.19. Both systems receive the same raw
1,600-character chunks, query text, top-five cutoff, and local
`nomic-embed-text:latest` embeddings. The upstream dataset is pinned to commit
`98d7416c24c778c2fee6e6f3006e7a073259d48f` and SHA-256
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.

| Metric | AtMem | Mem0 OSS 2.0.19 | Winner |
|---|---:|---:|---|
| Any evidence-session recall@5 | 1.000 | 1.000 | Tie |
| All evidence-session recall@5 | 1.000 | 1.000 | Tie |
| Evidence-session MRR@5 | 0.958 | 1.000 | Mem0 |
| Search latency p50 | 130.0 ms | 47.8 ms | Mem0 |
| Search latency p95 | 193.1 ms | 57.9 ms | Mem0 |

**Outcome: Mem0 performed better than AtMem on this benchmark.** Both systems
found every required evidence session in the top five; Mem0 placed the first
relevant session slightly higher and returned results faster.

Reproduce it after obtaining the pinned `longmemeval_s_cleaned.json` file and
starting Ollama with `nomic-embed-text:latest`:

```bash
python -m venv /tmp/atmem-mem0-bench
/tmp/atmem-mem0-bench/bin/python -m pip install mem0ai==2.0.19 ollama==0.6.2

python tools/run_longmemeval_retrieval.py \
  --backend atmem --dataset /path/to/longmemeval_s_cleaned.json \
  --work-dir /tmp/longmemeval-atmem --output /tmp/atmem-result.json

PYTHONPATH="$PWD" /tmp/atmem-mem0-bench/bin/python \
  tools/run_longmemeval_retrieval.py \
  --backend mem0 --dataset /path/to/longmemeval_s_cleaned.json \
  --work-dir /tmp/longmemeval-mem0 --output /tmp/mem0-result.json

atmem benchmark compare /tmp/atmem-result.json /tmp/mem0-result.json
```

This campaign isolates semantic evidence-session retrieval with raw ingestion.
It does not replace the deterministic extraction, contradiction, injection,
privacy, poisoning, fallback, token, and cost release gate, and it is not the
complete 500-question answer-generation evaluation.

### Supporting-evidence ranking validation

The implementation recorded on 2026-09-02 adds deterministic, bounded support
signals after AtMem has authorized canonical candidates. Those signals feed
AtBot reranking in the product path, and AtMem still revalidates every returned
record ID before constructing context. If AtBot is unavailable, the aggregate
order is the local safe fallback.

The external LongMemEval runner deliberately measures the pre-AtBot stage:
vector candidates followed by supporting-chunk aggregation. On the fixed
12-case selection it retained recall-any@5 `1.000`, recall-all@5 `1.000`, and
MRR@5 `0.9583`. A separate, non-overlapping held-out selection—the third
SHA-256-ordered eligible case from each question category—scored `1.000` on all
three measures across six cases.

The focused temporal case `gpt4_d31cdae3` remained at reciprocal rank `0.5`.
Its generic travel decoy also has several highly similar supporting chunks, so
raising a repetition bonus would strengthen the wrong source. Resolving “a few
years ago” versus “last summer” belongs to AtBot's semantic/temporal reranking
stage, not to authorization or vector weighting. This is a measured limitation,
not a reason to hard-code the case or weaken AtMem's authority boundary.

The compact checked-in evidence is
[`longmemeval-s-support-ranking-2026-09-02.json`](examples/longmemeval-s-support-ranking-2026-09-02.json).
The generated external report retains full per-chunk scores and bounded
aggregation signals. Reproduce the focused case with:

```bash
python tools/run_longmemeval_retrieval.py \
  --backend atmem \
  --dataset /path/to/longmemeval_s_cleaned.json \
  --work-dir /tmp/longmemeval-focused \
  --output /tmp/longmemeval-focused.json \
  --case-id gpt4_d31cdae3
```

Repeat `--case-id` to run an explicit held-out set. Explicit selections are
reported separately and never merged into the fixed 12-case result.

## Reading the results

The deterministic report gives AtMem's regression and safety result. The
external report gives the direct AtMem-versus-Mem0 outcome for the matched
dataset, cases, scoring schema, models and configuration recorded in that
report. Different configurations are separate benchmark runs rather than a
reason to weaken or dismiss the measured result.
