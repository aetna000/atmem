# Spec 052 implementation and controlled public pilot

Date: 2026-11-18. State: one preregistered pilot completed; **the intervention failed**.
All 80 final condition trials completed with no unknown outcomes. The revision was
not selected and did not improve final accuracy or reward. No second revision,
model campaign, final-set-driven tuning or positive learning claim followed.

## Implemented and reviewed

Owner-only `AdaptationService` uses existing fixed FeedbackScope/owner transactions
and encrypted feedback ledger. Closed manifests bind exact case input/target hashes,
corpus/runtime/grader identities, phases and ceilings. Hidden targets never enter
task-agent callbacks. Exact requests/responses, read-only SQL observations, memories
and objective grades remain inspectable after the original process is gone.

The SDK durably reserves each task arm and every paid call before external effects.
A process loss/unknown call remains charged and cannot silently retry. Exactly one
revision and one construction call per policy purpose are permitted. Revision text
is validated before use. Validation selection requires higher reward without
accuracy loss; ties retain generic. Final policies and training-only snapshots
cannot change. Reports never authorize activation or production qualification.

Astra supplied a primary-literature review and a separate pre-pilot code/method review.
Its findings were addressed before source commit/pilot: structured evidence sampling,
abort reporting, malformed-agent failure classification, single-lineage uncertainty,
early revision validation, single-purpose reservations, remaining-time-aware HTTP
and post-call deadline rejection, implementation/actual provider identity binding.

## Frozen experiment

Implementation source:`a5b1bd9` (new source implementation, not a benchmark of an
already published wheel). Full corpus/runtime manifest SHA256:
`8ebf796ccce5c511feb421164c46e3249f2dda2f8339c165a13ebd66e699f558`.

Public CL-Bench source:`5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26`;
HF DB snapshot:`a0cc57eeb9a54f01c0490a1b46cb705b4e05aa19`.
DB/question hashes, exact memberships, implementation/grader pins and settings
are in the retained preregistration. Files are independently hash-checked and all
35 gold SQL queries were checked against their stored scalar labels before inference.

Train1–10; validation 11–15; final 16–30 plus drift101–105. First3 questions had been
viewed during research and were deliberately restricted to training. Final task
text/labels never informed the proposal. No answers, gold SQL or correctness labels
were sent to either note writer. Each writer receives the exact same bounded,
structured sampling of observed training evidence as the transcript control.

Agent:OpenRouter/OpenAI `openai/gpt-6-luna`, low reasoning,seed 52, explicit JSON
responses, no provider fallback. Native-style controls use the same fixed agent,
not native Codex/Claude/OpenClaw or normal AtMem recall. Tool execution is only
read-only immutable SQLite, maximum15 exploratory queries,50 rows/6000 bytes per
result,3-second query limit. No arbitrary shell, accounts or app tools are exposed.

The intervention changes LOAD/OFFLOAD instructions and derived notes together.
Final memory is frozen, not updated online. One database lineage supplies original
and drift strata; it is one independence cluster, so a broad confidence claim is
inconclusive. A strict scalar grader uses upstream numeric tolerance plus independent
SQL-oracle validation and records parser disagreements. It is not an LLM judge.

One revision was proposed. Both validation arms scored0/5 correct and zero
reward, so the preregistered tie rule retained **generic**. Validation supplied no
positive evidence for the revision; the final set was not used to change selection.
The low validation performance is a limitation of this pilot, not proof that the
optimizer identified a useful memory policy.


## Observed final results

| Condition | Strict scalar correct | Upstream parser correct | Mean strict reward | Final calls | Final USD |
|---|---:|---:|---:|---:|---:|
| No memory | 7/20 | 9/20 | 0.2400 | 118 | 0.016033 |
| Bounded training transcript | 5/20 | 7/20 | 0.2133 | 72 | 0.015724 |
| Generic notes (retained incumbent) | 6/20 | 7/20 | 0.2433 | 80 | 0.011141 |
| Revised instructions + notes (rejected) | 5/20 | 6/20 | 0.1700 | 105 | 0.015776 |

The two scorers and their disagreement recording were implemented before inference.
There were six final formatting-sensitive parser disagreements. Upstream accepts
the first extracted number; the primary strict criterion requires a scalar without
extra formatting. Both scoring views leave the revision below the stateless control.
The primary scorer/selection were not changed after inspecting final answers.

Original-schema strict correctness (15 cases):no-memory7, transcript 5, generic 5,
revised 5. Schema-drift strict correctness (5 cases):no-memory0, transcript 0,
generic 1, revised 0. Frozen notes did not establish reliable adaptation to drift.
Generic's tiny mean-reward difference over no-memory (0.0033) came with one fewer
correct answer and one shared independence cluster; it is not evidence of a reliable
improvement. The revision reduced reward and accuracy relative to generic.

This was a failure to improve memory use. It does not isolate whether instruction
choice, limited training coverage, model/task capability, context selection or schema
shift caused the errors. No additional costly search was used to manufacture a gain.

Machine-readable [preregistration](pilot-preregistration.json),
[all-phase/final results](pilot-results.json) and [per-condition outcomes](pilot-trials.json)
contain no task text, model answers, source rows, notes or credentials. Exact original
exchanges and grades remain encrypted in the dedicated owner Home. Re-executing SQL
requires the separately retained pinned benchmark DBs; the vault retains the captured
run story, not a copy of the entire database. No standalone DB replay is claimed.

## Meta comparison

| Dimension | Meta Self-Improving Memory | This AtMem pilot |
|---|---|---|
| Agent | Kimi-K2.6 | GPT-6 Luna, OpenAI route |
| Workload | Three Continual Learning Bench task streams | One adapted DB slice,20 final cases |
| Search | Four seeds and multiple revisions | One generic policy and one revision |
| Memory during test | LOAD/OFFLOAD across subtasks | Frozen training-only memory |
| Weight training | Separate LoRA distillation | None |
| Result interpretation | Reported selected-harness and distillation gains | Revision failed; no learning claim |

Meta's published 56.0 vs44.6 selected-harness and43.1 vs37.6 distillation scores
are from different conditions. They cannot be ranked against our numbers. Its public
project had no runnable implementation/checkpoint for a matched reproduction. The
comparison is methodological; no claim to beat, reproduce or refute Meta is made.
See [primary sources and inspected code](research.md).

## Measured resources

- Pilot:497 provider calls;1,087,450 reported tokens;USD 0.07761425.
- Phases:train 63 calls/USD 0.008510065; proposal+two note constructions3 calls/
  USD 0.002264025; validation 56 calls/USD 0.008165225; final 375 calls/USD 0.058674935.
- Actual response identities:OpenAI/openai/gpt-6-luna for all 497 calls; no fallback.
- Study wall time:3840.59s (64.01min), excluding download/setup/preflight. Two separate
  protocol-only attempts add one known USD 0.0000111 charge and one unknown maximum
  reservation ofUSD0.0005773; no unreported quality rerun occurred.
- Peak RSS:305,868,800 bytes on the recorded macOS interpreter (291.7MiB).
- Final condition-trial latency:p50 30.34s,p95 78.75s;0.0260 condition trials/s.
  These include model/ledger/SQL work and are not production performance estimates.
- Serialized evidence reservation counter:25,380,995 bytes (24.21MiB). Sum of Home
  file lengths at original summary:55,490,202 bytes (52.92MiB), including encryption/
  container history overhead. Later owner inspection adds audit records.
- Two external database snapshots:830,058,496 bytes. Task-owned synthetic test
  temporary directories were removed after their completed checks. Build caches
  and isolated environments are cleaned separately after publication verification.

## Resource and scope limits

One pilot,800 calls/2M tokens/USD 3/90min/32MiB serialized evidence reservations.
The storage budget excludes encrypted container/history overhead; final filesystem
size is reported separately. Exact unknown charges and all phases' costs are retained.
Data download, environment setup and protocol checks are separate from study wall
measurements. Two protocol-only attempts preceded freezing; see release-evidence.md.
All large artifacts are on external MEM0, not the nearly full internal disk.

Dataset-code license is Apache-2.0; the HF snapshot has no explicit dataset license
card and derives from Amazon Reviews 2023. Databases/labels are not redistributed,
no model weights are trained, and no production-level benchmark claim is made.
No DolphinBench campaign, native host reconfiguration or website deployment occurred.

## Verification

- 17 new actual encrypted-service, authorization, reservation/restart, split/selection,
  ciphertext-canary, strict-grader, SQL denial/bounds and CLI-opt-in tests passed.
- 9 release metadata tests passed after correcting the documented npm package pin.
- 21 unchanged AtBot tests passed. OpenClaw typecheck/build/test/smoke passed;
  latest2026.11.5 declarations were independently reviewed with a narrowly tested
  parser correction and declaration-only probe, without native authority expansion.
- Core suite:4014 passed,86 skipped,2 expected failures,3 environment failures.
  The two archive failures arose because their fixture keys were placed in the
  external TMPDIR; both passed with internal temporary keys. The optional Cognee
  parity failure used a stale non-Git directory; recovering the exact pinned
  upstream commit made the differential test pass. No product test was weakened.
- Fresh native arm64 installed wheel:dependency health, CLI, delegated context,
  HMAC transport and encrypted-storage smoke passed. Persisted upgrades from
  stable2.3.14 and beta2.3.15b1 passed. Wheel/sdist metadata/rebuild checks passed.
- Private website review import/build/gates/docs checks and84 browser tests passed;
  final public-main pin, owner-reviewed private PR and publication remain separate.

These overlapping suites are not an aggregate unique-test count. Skipped optional
framework/browser/platform journeys are not qualification passes. Hosted final-commit
checks and exact publication identifiers belong in release-evidence.md.
