# Semantic search

AtMem always keeps canonical memory in SQLite. In 2.2, every
persistent memory database also gets a rebuildable vector sidecar. AtMem creates
and synchronizes a dependency-free local hashing epoch automatically; vectors
never become canonical memory or an authorization source.

The `semantic` extra and external model downloads are optional. They replace the
active hashing epoch with a higher-quality local embedding epoch; they do not
change who is allowed to see a record.

```bash
python -m pip install "atmem[semantic]"
atmem index build memories.db --subject user-1 --embedder sentence-transformers --model all-MiniLM-L6-v2
atmem index verify memories.db --subject user-1
atmem search memories.db "travel preference" --subject user-1 --mode hybrid
```

Ollama, loopback OpenAI-compatible, sentence-transformers, and deterministic
hashing providers are supported; use `atmem index build --help` for their exact
options. Automatic governed recall will not send memory to a remote embedding
endpoint.

## Where vectors are used

- `atmem search --mode semantic|hybrid` uses the selected verified epoch for
  investigator search.
- Dashboard memory query and adapter `control_prepare` use the active local
  epoch as one nomination signal alongside lexical, fact-key, graph, trust, and
  recency signals.
- A semantic match is never injected directly. AtMem reloads the canonical
  record, checks its digest and lifecycle, applies scope, exclusion,
  sensitivity, egress, generation, and budget policy, then revalidates any
  AtBot ranking before constructing context.
- If no valid epoch is available, lexical and graph recall remain the safe
  degraded path.

## Integrity model

- Vectors never become canonical memory.
- Every vector binds a record content digest, model identity, dimensions and index epoch.
- Search verifies the current epoch and revalidates every candidate against the canonical record.
- Purge and supersession invalidate or remove derived vectors.
- A dimension mismatch fails or skips safely; it is never silently truncated.
- Provider model versions or digests are preserved when the provider exposes them.

Semantic search improves reach but adds a model, tokenizer, preprocessing, numerical and index-state dependency to replay. Lexical results remain easier to explain by matched terms. Hybrid mode reports lexical rank, semantic rank, similarity and reciprocal-rank-fusion score so an investigator can see why a result appeared.

Semantic investigator queries can be logged by digest. An active index can
nominate candidates for governed agent recall, but it cannot promote a
quarantined memory, widen scope, admit a proposal, or bypass final AtMem
authorization.
