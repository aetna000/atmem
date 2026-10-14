# Frontier-teacher labeling protocol

The conversation rows in this corpus are source-licensed, human-origin records.
The attached labels are machine-generated weak supervision; they are not human
labels and must never be described as ground truth.

## Immutable input

The immutable work database rejects generated dialogue, generated
continuations, synthetic paraphrases, translated replicas and hand-authored
conversation rows before judging. Each judge query returns only:

- a bounded sequence of original-language user/assistant turns;
- one marked candidate user turn;
- earlier raw user turns that may represent prior memory state;
- fixed language-neutral decision and category identifiers; and
- the frozen rubric version.

Dataset name, source name, country, detected language, source annotations and
expected labels are withheld from the teachers. Assistant statements cannot be
treated as user facts unless the user explicitly confirms them.

## Output schema

Each teacher must return strict JSON containing:

- `disposition`: `STORE`, `UPDATE`, `DUPLICATE`, `DO_NOT_STORE`, `FORGET`, or
  `REVIEW`;
- `memory_class`: `preference`, `durable_fact`, `procedure`, `commitment`,
  `relationship`, `episode`, `temporary_state`, `sensitive`, or `non_memory`;
- `evidence_turn_ids`: exact supplied turn IDs only;
- `supersedes_turn_ids`: exact earlier supplied user-turn IDs only;
- `duplicate_of_turn_ids`: exact earlier supplied user-turn IDs only;
- `normalized_memory`: a concise statement in the source language, or null;
- `meaning`: an evidence-bound structure containing subject, predicate/intent,
  value, scope, temporal validity, durability and relation to prior state;
- `confidence`: a number in `[0, 1]`; and
- `rationale`: a concise evidence-bound explanation, not hidden reasoning.

## Independent verification

1. The locally authenticated Codex CLI labels every eligible row from the frozen
   rubric through a restricted read-only database query surface.
2. The locally authenticated Claude CLI independently labels every eligible row
   without seeing Codex's annotations while its CLI allowance remains available.
   If that allowance is exhausted, the manifest switches explicitly to
   `codex_only_credit_exhausted`; it never fabricates Claude coverage.
3. Each judge audits its own first-pass decisions through four separately
   receipted views: exact/semantic duplicate clusters; same-scope chronology;
   language/class/risk/confidence strata; and contradiction/outlier searches.
4. Each audit stores the previous decision, revised decision, query/evidence
   references and concise change reason. Review repeats only while a declared
   pass changes eligible decisions and stops at the fixed pass limit or zero-
   change convergence. Repeated prompts are not majority votes.
5. In dual-judge mode, after both self-review loops freeze, deterministic code compares disposition,
   class, evidence and relationship targets and records explicit disagreements.
6. Exact dual-judge agreements pass only after deterministic validation.
   Codex-only rows pass only after all Codex review views converge and are
   identified as single-judge weak supervision. Disagreements go
   to a separately invoked adjudicator. Unresolved rows are rejected.
7. The retained row records CLI/model IDs, CLI versions, pass/view identity,
   prompt/schema/query hashes, output digests, latency and every state change.

Direct provider SDK/API labeling is prohibited for this corpus. The runner
removes `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` from both subprocess
environments so Codex and Claude must use their locally authenticated CLI
sessions. Both CLIs run non-interactively in a read-only sandbox with
schema-constrained output. The orchestrator, not either model, validates and
commits annotations.

## Full-corpus gates

- strict schema and finite-label membership;
- every evidence/supersession ID belongs to the supplied input;
- `UPDATE` requires a real earlier conflicting user turn;
- `FORGET` requires an explicit deletion/non-retention instruction;
- `STORE` cannot be sourced solely from assistant text;
- every actionable understanding has a valid disposition-compatible
  `relation_to_prior` and no invented semantic or temporal field;
- normalized memory cannot introduce unsupported entities or values;
- exact and near-duplicate rejection before splitting;
- secret, credential and residual PII scan before CLI model egress and publication;
- per-language teacher agreement and rejection reporting; and
- benchmark/decontamination hashes checked before training.

LongMemEval, DolphinBench and Multi3WOZ are evaluation-only. No evaluation
question, answer, annotation or translated variant is sent through the training
labeler or included in the training corpus.
