# Auditing guide

## Verify integrity

```bash
atmem verify memories.db --incremental
atmem audit memories.db user-1
python tools/verify_audit.py memories.db --subject user-1
```

The built-in and independent verifier check the same hash-chain invariants. Keep the verifier with exported evidence when another party must reproduce the check.

## Investigate influence

Start with ordinary words, a time window, session, actor, event type or record ID. Then follow the record drawer from source and interpretation through admission, recall, context injection and response binding. A recall attempt is not proof that the model received the memory; use the context receipt. A context receipt is not proof that memory caused an outcome.

## Export

Export one flight with `atmem blackbox export RUN_ID --format text|json
--output FILE`. Export a filtered memory audit with `atmem control memory-audit
--format json|ndjson|csv|text --output FILE`. The dashboard exposes the same
formats. Preserve the database checkpoint and exported report digest together.

## Limits

- Hash chaining detects changes; it does not authenticate the actor by itself.
- Local timestamps are not trusted time.
- Imported historical memory may lack source-message or model evidence.
- AtMem cannot delete host-controlled media or provider logs.
- Subject IDs and investigator labels are meaningful only when the integrating host authenticates them.
