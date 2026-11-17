# Plan — actual installed-package comparison

Use a standalone worker (`tools/matched_memory_worker.py`) launched via Python -I
from explicitly isolated original/candidate environments. Its public APIs match
the shipped evidence-discovery example: encrypted HouseholdApplication, scoped
history-import authority, form_context_episode, freeze_context_engine and default
prepare_context_v3(context-fast). No engine replacement or custom ranker.

An owner-only comparison harness reads only Spec052's original training traces,
frozen revision and frozen derived notes from the encrypted vault. It builds each
memory once, obtains actual per-case context, freezes the complete protocol before
paid inference, and uses the same SQL agent and objective grader in all conditions.
The experiment retains full model/tool/context traces in a new encrypted feedback
ledger with durable cost reservations; summaries contain no questions or answers.

Published AtMem2.3.14 is installed from PyPI in a separate environment; candidate
2.3.15b2 is installed from the retained wheel and identified as unpublished source
artifact. Each subprocess attests package metadata and implementation digest.
Existing final cases remain historical; only unused post-drift IDs106–120 are scored.
The fixed first-three feasibility stop prevents another unproductive campaign.

Verify real workers locally without model calls, then reservation/leakage/version/
context/grade guards. Freeze source commit before live inference. No release tag
or efficacy announcement until the actual comparison and required release checks.
