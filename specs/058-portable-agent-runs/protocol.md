# Portable agent runs

## Frozen evaluation

The original six cases are development data. Use the Atlas case to diagnose false abstention. Keep all ten new cases and their expected answers fixed. Compare single reader, mandatory review when feasible, and evidence-aware review on identical snapshots using qwen2.5:1.5b, a 4,096-byte evidence cap and at most two local model calls per task. Measure exact answers, false abstentions, correct abstentions, stale answers, erroneous answers on missing evidence, source references inspected, generation attempts, input and output tokens, and tokens per correct task. A generation error counts as an incorrect task. Report any incomplete metering.

The declared criterion for enabling automatic review is strictly more correct held-out tasks than the single reader, zero additional stale answers, and no increase in tokens per correct task. Keep review opt-in otherwise. A win on the development case alone is insufficient.
