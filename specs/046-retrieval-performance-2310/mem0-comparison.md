# Current Mem0 comparison boundary

Verified 2026-10-22 against the upstream release listing and documentation.
The current Python SDK release is **v2.2.1**, commit
`94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`.
This pin is a comparator input, not a completed qualification or score.

- Preserve the current additive extraction flow: `Memory.add(..., infer=True)`
  extracts facts through the configured LLM. Do not replace it with raw inserts,
  disabled inference or hash embeddings and call that the recommended baseline.
- The documented default configuration uses `gpt-5-mini`, real
  `text-embedding-3-small` embeddings, persistent Qdrant and SQLite history, and
  no reranker. Freeze actual SDK configuration and any deliberate provider
  substitutions before execution; substitutions are not stock defaults.
- Match reader, reasoning, source histories, host identity/application policy,
  tool opportunity, task denominator and grading when comparing systems. Report
  formation calls separately from reader and grading calls.
- The existing upstream benchmark reference uses the managed Mem0 platform.
  Its proprietary optimizations are not identical to the OSS SDK. An OSS run
  must be named OSS; a different-reader run cannot establish a matched win over
  the hosted reference. No managed Mem0 credential is configured for this run.
- No Mem0 installation, ingestion, billing or scored comparison is authorized by
  this metadata document alone; stage review, privacy and budget gates still apply.

Sources: [releases](https://github.com/mem0ai/mem0/releases),
[Python quickstart](https://github.com/mem0ai/mem0/blob/main/docs/open-source/python-quickstart.mdx),
[add-memory contract](https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/memory-operations/add.mdx),
[platform/OSS distinction](https://github.com/mem0ai/mem0).
