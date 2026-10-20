# Structural-context improvement loop

Owner authorization (2026-10-17): improve structural context, aiming for 50%
fewer total input tokens than native tools with equal or better functional task
passes; 20% is the fallback. This is an optimization target, not a guarantee.

## Diagnose → change → qualify → freeze → run → retain/reject

1. Inspect retained tool/usage receipts, not just context size. Long graph IDs,
   lexical substring matches and outline-only packs can add work rather than
   replace source reads. Model/tool-loop overhead counts in total input tokens.
2. Make generic source-backed packing changes in the product, never keyed to
   task IDs, issue numbers, future patches or hidden grader feedback. Preserve
   extraction, scope, secret screening, shared budget and final source rechecks.
3. Test ranking, complete versus bounded excerpts, deduplication, UTF-8 byte
   limits, authorization, corruption, staleness and existing Code behavior.
4. Build a separate local preview wheel; preserve every prior artifact/run.
   Freeze implementation/CLI/environment/task hashes before each cohort.
5. Run matched native/structural sessions with identical solver instructions,
   tools, source and limits. No experience, no model training, no paid API/GPU.
   Use the existing Luna subscription, encrypted evidence and volatile homes.
6. Retain every attempt. Compare **functional passes first**, separately from
   all-budget passes. Accept no token win that loses functional correctness.
   Primary saving = 1 - sum(C input tokens)/sum(A input tokens), including cache.
   Report output and uncached tokens, time, indexing and known/unknown usage too.
   On the reused tuning tasks, also require five functional/policy passes: do
   not accept matching a weaker stochastic native run after the earlier native
   control already solved all five. Confirmation compares matched new-task arms.
7. Start with the five already-inspected Click tasks as tuning only. A later
   frozen, separately qualified task set must assess transfer; repeat attempts
   on these same five do not become untouched confirmation. No pooled best-of.
8. Initial bound: up to three product candidates, at most 40 solver sessions
   including confirmation. Stop a cohort on authentication/quota failure; retain
   results and continue independent tests. No concealed retries or new spending.
   If neither target passes, report the best safe result and remaining gap.

Only the next candidate is selected from tuning results. No tuning after looking
at confirmation outcomes. A failed confirmation is a reported failure, not an
invitation to relabel it tuning and choose another confirmation winner.

Candidate-2 onward adds the identical scratch-policy reminder to both arms;
this prompt revision is a declared cohort difference. A candidate's native
control is measured fresh, not selected from whichever previous run used most
tokens. Quality/token acceptance uses the entire cohort, not best task patches.

No main-branch changes, owner installation, release, external publication, Laya
work or experience changes. MEM remains restricted to benchmark artifacts.
