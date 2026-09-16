# 2.3.3b1 pre-change baseline

**Date:** 2026-09-16. **Source:** branch `benchmark`, commit `00f36abe0381edcb6040de2d17b491bdbb19791f`, AtMem/bridge 2.3.2. This is a pre-change observation, not a 2.3.3 result.

## Fixed inputs and host

- LongMemEval-S cleaned public corpus: Hugging Face dataset `xiaowu0162/longmemeval-cleaned`, commit `98d7416c24c778c2fee6e6f3006e7a073259d48f`, file SHA-256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`. Local temporary copy: `/tmp/atmem-mem0-research.6BAkC2/longmemeval_s_cleaned.json`.
- 12 cases selected by the checked-in `sha256-question-id-stratified-v1` rule, two per question category. Equal raw 1,600-character chunks, local `nomic-embed-text:latest` embeddings, five returned session IDs. The runner's reported latency starts just before query embedding/search and excludes corpus admission and index build.
- Apple M2, 16 GiB RAM, macOS arm64; AtMem and Mem0 Python 3.12.2; Ollama 0.32.0. Model tag `nomic-embed-text:latest` is a mutable name; the installed model ID observed before the run was `0a109f422b47`.
- Mem0 2.0.20 runs in `/tmp/atmem-mem0-research.6BAkC2/mem0-py312`, separate from AtMem's environment. The inspected source clone at `0df3e4b87df20785f0741370c75e44428796193e` declares that package version; the installed wheel's code identity must still be verified for this comparison.

## Prior published historical result, kept separate

The existing [2.0.19 comparison](../../examples/longmemeval-s-retrieval-12-v1.json) reported recall-any@5 1.000 for both, recall-all@5 1.000 for both, MRR@5 0.958 AtMem versus 1.000 Mem0, and search p95 193.1 ms versus 57.9 ms. That result was measured earlier on a different run and is not a fresh 2.0.20 comparison.

## Pre-change deterministic release gate

`./.venv/bin/atmem benchmark run --json` passed before production edits. Quality digest: `sha256:426d3bdcdced658514839fce61a705a008892fea8de554d5fb8c373488087f88`. Reported extraction, contradiction and answerable recall were 1.0; no-answer correctness and fallback completion were 1.0; incorrect injections, poisoning success and privacy leaks were zero. Its observed p50/p95 were 69.349/169.955 ms on isolated synthetic cases. These durations are not directly comparable to the LongMemEval retrieval-only timing.

## Fresh pre-change head-to-head observation

**Retrospective correction (2026-09-17):** The runner used Mem0's unsupported
`limit` keyword instead of `top_k`, so Mem0 used its default 20 returned
results while AtMem nominated 100. The two paths also embedded different
preprocessed document/query bytes. The latency rows below are preserved as
historical traces but are **not** a fair matched comparison. See the corrected
[matched-input development comparison](matched-v2.md).

The frozen 12-case raw-ingestion profile was run before production edits. The
per-case reports are currently local, not checked in:
`/tmp/atmem-mem0-research.6BAkC2/baseline-atmem.json` and
`/tmp/atmem-mem0-research.6BAkC2/baseline-mem0.json`. They must be copied to
durable implementation evidence and repeated on a quiet host before a release
claim; the Mem0 run overlapped development tests on this machine.

| Retrieval-only metric | AtMem 2.3.2 | Mem0 OSS 2.0.20 |
| --- | ---: | ---: |
| Evidence-session recall-any@5 | 1.000 | 1.000 |
| Evidence-session recall-all@5 | 1.000 | 1.000 |
| Evidence-session MRR@5 | 1.000 | 1.000 |
| Search p50 | 157.1 ms | 62.7 ms |
| Search p95 | 259.6 ms | 135.7 ms |

This is an exploratory raw evidence-session retrieval comparison, **not** a
native `control_prepare`, ingestion, answer accuracy or verified 2× result.
Mem0's base isolated install emitted `spaCy not installed` and `fastembed not
installed - BM25 disabled`, so this run is explicitly **semantic-only Mem0**;
an enabled-hybrid run is required separately. The selected 12 cases are too
small for a general leaderboard claim. The current p95 target, if compared to
this run, is at most 67.9 ms, and remains unachieved and unverified.
