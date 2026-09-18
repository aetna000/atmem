# AtMem × MemoryBench

An external harness integration, not a self-scored leaderboard. The provider
uses real AtMem admission, persisted memory, hybrid retrieval, candidate-set
authorization and governed context packaging. AtMem appears as `atmem` in the
patched harness. This overlay has **not** been accepted upstream and no public
leaderboard placement is claimed.

## Reproduce

Use a separate checkout and environment; do not point this at your live AtMem
directory. Commands below assume Bun and Python 3.12 are installed. Run from the
AtMem repository on branch `benchmark`:

```sh
python3.12 -m venv /tmp/atmem-benchmark-env
/tmp/atmem-benchmark-env/bin/python -m pip install -e .
git clone https://github.com/supermemoryai/memorybench.git /tmp/atmem-memorybench
git -C /tmp/atmem-memorybench checkout 94e2af54b661d90e77dddbd8fa4fa5b28c07a24e
/tmp/atmem-benchmark-env/bin/python integrations/memorybench/install.py /tmp/atmem-memorybench
cp integrations/memorybench/atmem.test.ts /tmp/atmem-memorybench/atmem.test.ts
cp integrations/memorybench/locomo-smoke.ts /tmp/atmem-memorybench/locomo-smoke.ts
export ATMEM_BENCHMARK_PYTHON=/tmp/atmem-benchmark-env/bin/python
cd /tmp/atmem-memorybench
bun install --frozen-lockfile
bun test atmem.test.ts
bunx tsc --noEmit
bun run src/index.ts help providers
bun run locomo-smoke.ts
```

The test selects diagnostic hashing embeddings and synthetic input, never a
paid model. It exercises the actual TypeScript-to-Python provider lifecycle.
The separate LoCoMo smoke downloads public benchmark data, imports the haystack
for five questions and checks context retrieval without answering or judging.
It prints the dataset checksum and explicitly reports no accuracy score.
The installer refuses unexpected source markers or a different existing AtMem
provider rather than blindly overwriting an unrelated upstream implementation.

## OpenAI pilot (paid; not run automatically)

Set `OPENAI_API_KEY` through your environment or secret manager; do not commit
it. No AtBot or local LLM is required. OpenAI receives corpus chunks for
embedding and questions/retrieved context for answering and judging.

```sh
export ATMEM_BENCHMARK_EMBEDDING=openai
export ATMEM_BENCHMARK_ROOT=/tmp/atmem-benchmark-data
bun run src/index.ts run -p atmem -b locomo \
  -r atmem-locomo-pilot-v1 -m gpt-4.1-mini -j gpt-4.1-mini \
  --limit 5 --sample-type consecutive --concurrency 1
```

`--limit 5` limits questions, **not ingestion cost**: a question may require an
entire conversation. The harness does not implement a dollar spending cap.
Configure provider-side limits and review corpus size before running. Keep all
checkpoints and result artifacts. A five-question pilot is a functional check,
not a meaningful quality score. Use the same question IDs, reader, judge,
retrieval limits and corpus for every comparative provider run; do not compare
this cheap pilot against published scores from different protocols.

## Fixed retrieval profile

`atmem-memorybench-raw-hybrid-v1`:

- Explicitly admitted raw conversation documents; no LLM fact extraction.
- Message bodies chunked at up to 1,600 characters, each with session/date
  provenance and a deterministic source identifier. No reference answers,
  question labels or arbitrary metadata are imported.
- `text-embedding-3-small`, 1,536 dimensions, batches of 32. Missing credentials
  fail; no silent switch to diagnostic embeddings.
- AtMem lexical recall plus semantic retrieval (100 candidates each), reciprocal
  rank fusion with constant 60, up to 10 selected records by default.
- Upstream's threshold (default 0.3) applies to semantic cosine similarity;
  lexical candidates are independently eligible.
- Governed context budget 16,000 characters. Override only as a separately
  reported profile using `ATMEM_BENCHMARK_CONTEXT_CHARS`.
- Only the resulting governed context is returned as content, alongside source
  identifiers. The upstream reader serializes this result as JSON; this adapter
  does not claim proof of exact model-input delivery or full flight recording.

Separate hashed containers isolate each corpus. Restart and exact ingestion
retry are supported. Use a new run/container when changing the corpus or
embedding profile; do not reuse a checkpoint across configurations. Benchmark
databases and upstream checkpoints contain plaintext public benchmark data;
they are not a test of production encrypted multimodal capture or access roles.

## Publication gates

1. Run and inspect a paid pilot, including retrieved context and failed answers.
2. Freeze source revisions, dataset checksum, question IDs, model identifiers,
   prompts, context budget, embedding profile and all configuration.
3. Resolve upstream evaluation issues before claiming comparable category
   scores: this pinned LoCoMo loader has category-mapping concerns; LongMemEval
   abstention grading and random sampling also need protocol review. This
   overlay intentionally does not silently modify the evaluator.
4. Run a complete agreed evaluation with costs/latencies and failures retained,
   and publish reproducible artifacts rather than selected successes.
5. Submit the provider integration/results to the maintainers. Upstream
   acceptance and leaderboard publication are separate steps.

LongMemEval-V2 is a separate submission target, not the `longmemeval` dataset
in this harness. Its official protocol requires its prescribed reader/judge,
web and enterprise coverage and submission artifacts. This MemoryBench overlay
does not meet those gates by itself.

Sources: [MemoryBench](https://github.com/supermemoryai/memorybench),
[LongMemEval-V2 submission requirements](https://github.com/xiaowu0162/LongMemEval-V2/blob/main/leaderboard/README.md).
