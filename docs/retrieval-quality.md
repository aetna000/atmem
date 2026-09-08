# Retrieval quality and semantic profiles

AtMem retrieval separates authorized candidate generation from permission to
inject memory. The shared `atmem-retrieval-decision-v1` result classifies the
original query as `direct_support`, `background_context`, or
`no_useful_memory`. Dashboard queries, control-plane turns, OpenClaw, Pydantic
AI, LangGraph, and the governed MCP `memory_recall_decision` tool use this
decision. Only direct support is injected by default.

## Signals and explanations

Every candidate exposes bounded, versioned lexical, typo-tolerant, semantic,
and candidate-prior contributions. Trust, recency, graph, fact-key, and AtBot
sources have registered versions as they become available. Priors can reorder
relevant candidates but cannot create relevance. Query expansion discovers
candidates only; the original query establishes support. Explanations contain
record identifiers, scores, versions, and reason codes, never hidden record
content.

Hashing vectors are diagnostic. Their similarity is reported but cannot make a
record eligible for prompt injection. When production semantic retrieval is
not healthy, lexical and fact-key retrieval continues with conservative
abstention.

## Activate a production semantic profile

Inspect recommendations and health before changing the active epoch:

```console
atmem semantic status MEMORY_DB --subject SUBJECT --json
atmem semantic setup MEMORY_DB --subject SUBJECT --json
```

For a local Sentence Transformers profile, explicitly approve the model
download and pin the artifact revision:

```console
atmem semantic setup MEMORY_DB --subject SUBJECT \
  --provider sentence-transformers --model BAAI/bge-small-en-v1.5 \
  --model-version EXACT_HUGGINGFACE_REVISION --allow-download --json
```

For Ollama, AtMem resolves and records the installed model's SHA-256 digest:

```console
atmem semantic setup MEMORY_DB --subject SUBJECT \
  --provider ollama --model nomic-embed-text --allow-download --json
```

The embedding identity binds provider, model revision/digest, dimensions,
cosine distance, L2 normalization, query/document prefixes, preprocessing,
quality class, license metadata, policy digest, and epoch. A compatibility
change cannot query an old epoch; rebuild and verification are required.

## Verification and rollback

Run the deterministic held-out gate and host tests before activation. The gate
contains separate calibration data and at least 20 answerable paraphrases plus
20 unrelated queries. It requires MRR@5 and no-answer accuracy of 1.0.

Rollback is derived-state only: stop using the incompatible semantic profile
and rebuild another verified epoch. Canonical memory is not migrated or
rewritten. If an embedder, AtBot, or reranker fails, AtMem falls back to
query-aware local scoring and may withhold; it does not widen eligibility.

The `memory_recall` MCP tool remains a legacy diagnostic search and must not be
used as injection authority. New MCP integrations should call
`memory_recall_decision`. Production embedding quality still depends on the
operator-selected model and the domain represented by the held-out evaluation;
the checked-in benchmark is deterministic evidence, not a universal quality
claim. Optional Mem0 comparisons use the pinned manifest in
`atmem/benchmark/data/mem0-oss-v1.json` and must report the actual result.
