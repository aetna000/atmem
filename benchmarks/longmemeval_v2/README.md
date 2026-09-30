# LongMemEval-V2 development qualification

This directory records AtMem's integration with the upstream
[LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2) benchmark. The
benchmark remains an inert test rig: trajectories are passed through the
upstream `Memory.insert()` interface, questions through `Memory.query()`, and
the upstream reader and deterministic scorers are not modified.

## Frozen development protocol

- Upstream code: `xiaowu0162/LongMemEval-V2` commit
  `2cc8c540bdb87fe6761629b585e727e1c4704520`.
- Dataset: `xiaowu0162/LongMemEval-V2` Hugging Face revision
  `f152293e235517d504809563c833d7190b8c713b`.
- Tier: `small`, whose five questions in each domain share one 100-trajectory
  haystack.
- Domains: `enterprise` and `web`.
- Arms: upstream `no_retrieval` and AtMem, with the same reader settings.
- Reader: local Ollama `qwen3:4b`, temperature `0`, at most 512 completion
  tokens. This is not the leaderboard's required `Qwen/Qwen3.5-9B` reader.
- Scoring: only questions with an upstream deterministic scorer. No local
  substitute for the official GPT-5.2 judge is introduced.
- Retrieval: local Ollama `mxbai-embed-large`, verified by its local model
  digest, top four governed records, text-only trajectory evidence. Four keeps
  the injected context inside this local reader's 4K-token window.
- Cost: zero paid API calls.

The ten-question slice is selected without reading answers: within each domain,
question IDs using deterministic upstream scoring are sorted by
`SHA-256(question_id)`. The first two static, first two dynamic, and first one
procedure question are used. The exact IDs are frozen in `selection.json`.

AtMem stores one bounded record per observed state plus bounded trajectory
summaries. Each record is at most 1,800 characters. The adapter uses goals,
actions, outcomes, URLs, thoughts, and salient accessibility-tree text; it does
not read question records, expected answers, or scorer output during insertion
or retrieval.

## Interpretation

This run is a reproducible development comparison, not a LongMemEval-V2
leaderboard submission. An official claim requires both complete domains, the
upstream fixed reader and judge models, all required visual inputs, and the
upstream submission checks. The development slice answers the narrower first
question: does adding AtMem retrieve useful information from the same real
long-running agent histories that the no-memory reader cannot see?

Raw upstream outputs and a machine-readable comparison are copied into
`results/dev10/` after the matched runs finish. They retain per-question
answers, scores, token counts, retrieval timings, run arguments, and content
hashes needed to audit the report.
