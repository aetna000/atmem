# Retrieval quality qualification

This directory describes how AtMem's product retrieval path is measured. The
benchmark code is an inert client: it may submit source episodes, issue recall
requests and retain results, but it may not form memory, search AtMem storage,
inspect answers or repair context.

## Claim vocabulary

- **Fixture pass** — frozen, benchmark-neutral product cases passed. This
  validates contracts and local behavior, not leaderboard quality.
- **Development result** — a result on declared development question IDs. It
  may guide engineering and cannot be called held out.
- **Unseen-question confirmation** — the configuration was frozen before the
  precommitted confirmation IDs were evaluated and their answers were not
  inspected by product, adapter or tuning processes.
- **Complete official score** — every official case in a named workload was
  run with the pinned reader, judge and scorer. It is not necessarily held out.
- **Scale result** — the same questions were evaluated against a larger
  haystack. LongMemEval-V2 Medium is a scale result, not a new question set.
- **Pareto result** — the configuration is non-dominated for the declared
  quality, latency and cost dimensions among the compared matched runs.
- **Leaderboard submission** — the official validator accepted a complete
  package and the benchmark owner accepted or published it.

A missing corpus, incomplete domain/persona, changed scorer, unmatched model,
unavailable raw evidence or failed provider makes a production package invalid;
it is never silently counted as a skipped test.

## Product boundary

All feature behavior lives under `atmem/`. Removing this directory and every
external corpus must leave formation, recall, explanation, MCP, dashboard and
agent adapters functional. Heavy datasets, model caches and raw runs belong on
the configured external benchmark root. Only small protocols, fixtures,
schemas, manifests and reports are version controlled.

## Frozen split

`protocols/longmemeval-v2-question-split-v1.json` contains identifiers and
strata only—never question text or answers. It is generated from metadata by
`make_question_split.py`. Every previously inspected dev10 identifier is forced
into development. Small confirmation tests unseen questions; Medium reuses the
same confirmation IDs to measure larger-haystack behavior.

## Three-percent development pilots

The pilot is a cost and plumbing check, not an accuracy claim.

The first Runpod execution on 2026-09-28 stopped safely after seven paired
questions because later reader responses did not contain final answer text.
Its incomplete, development-only findings and reconciled costs are recorded in
[`reports/longmemeval-v2-development-pilot-20260928.md`](reports/longmemeval-v2-development-pilot-20260928.md).

- `longmemeval-v2-pilot-v1.json` selects 14 development questions: one from
  each frozen domain-by-ability stratum. It contains no confirmation IDs.
- `dolphinbench-task-split-v1.json` selects 6 of the 200 tasks for each of the
  three official personas (18/600 total) and freezes the remaining 582 for
  later confirmation.
- `2.3.8.yaml` pins upstream commits, model revisions, prompts/scorers,
  provider routes, hardware, retry limits, context/output limits and cost caps.
  `provider-route-probe-v1.json` is the content-free credentialed evidence for
  the exact dedicated Qwen, Scaleway and dated OpenAI routes. The validator checks
  its canonical digest and every successful route before permitting a pilot.
- The temporary authenticated Runpod Pod pins `Qwen/Qwen3.5-9B` at the protocol
  revision on one Secure Cloud L40S. The pod receipt establishes the configured
  repository revision; it is not a cryptographic attestation of loaded weights.
- Dolphin interactions and the LongMemEval pilot reserve their maximum
  permitted provider cost durably before network egress. A crash leaves the
  reservation in place and blocks a blind paid retry. The reviewed LongMemEval
  pilot disables provider retries, enforces request/token ceilings, accounts
  dedicated-reader cost from measured pod-active time, and terminates the
  temporary pod before releasing gated OpenAI judging. The audible completion signal
  occurs only after pod deletion succeeds. Provider-invoiced pod
  cost remains a later reconciliation field rather than a fabricated token fee.
  `no-retrieval` and `typed-local` are currently price-qualified; the official
  RAG comparator stays disabled until its per-trajectory indexing cost has a
  separately measured and frozen upper bound.
- The official RAG comparator reaches the pinned Scaleway embedding provider
  through a loopback-only OpenAI-compatible facade. The facade performs no
  ranking or benchmark compensation, retains no input, and is byte-pinned by
  the protocol. The official process receives a sanitized environment so
  inherited endpoint and Python import overrides cannot redirect the run.
- LLM-based grading uses a loopback-only single-egress proxy. It admits only
  the dated judge model, rejects an oversized request, prevents an SDK retry
  from creating a second paid call, and records only token counts and computed
  cost—not benchmark prompts, answers or credentials.
  During the paid pilot it also exposes a content-free waiting state and blocks
  upstream judging until all Qwen answers are durable and the Runpod pod is
  terminated.

After the pinned dataset is prepared on an external volume and the reviewed
adapter is installed into a clean pinned checkout, run the frozen two-arm pilot
only with explicit paid confirmation:

```bash
python research/production_benchmarks/run_longmem_pilot.py \
  --checkout /path/to/pinned/LongMemEval-V2 \
  --data-root /external/longmemeval-v2 \
  --output-root /external/runs/longmem-pilot-001 \
  --confirm-paid-run
```

The command refuses an existing output root, any non-development question ID,
an unpriced method, a changed adapter/proxy/protocol, or a missing credential.
It requires a temporary authenticated Runpod Pod created from the frozen image,
hardware and model settings, then deletes that exact pod through the Runpod API
in both success and failure paths. Use `--preflight-only` to run every
local/package/data/credential check without creating a pod.

## Official inert adapters

`research/production_benchmarks/longmemeval_v2.py` installs the thin AtMem
memory class into the pinned official LongMemEval-V2 checkout. It preserves
the allowlisted official trajectory fields, each complete ordered state and
original screenshot reference, then calls the
ordinary formation, candidate and Context Package V2 APIs.

`research/production_benchmarks/dolphinbench.py` implements DolphinBench's five
adapter methods. Each persona has a separate encrypted household; ingestion
uses ordinary episode formation, the test phase is read-only, checkpoints are
content-hashed, and model/tool execution remains with the configured agent
driver. Neither adapter can inspect answers, graders or split metadata.

For the frozen 18-task development slice, configure the official runner with
`research.production_benchmarks.dolphinbench:create_development`, complete its
normal prepare and ingestion stages, then run:

```bash
python research/production_benchmarks/run_dolphin_development.py \
  --checkout /external/dolphinbench \
  --config /external/dolphin-run/run.yaml \
  --checkpoint-root /external/dolphin-run \
  --finalization-manifest /external/dolphin-run/frozen-finalization.json \
  --finalization-gate /external/dolphin-run/passed-finalization.json \
  --confirm-paid-run
```

The manifest is a separately reviewed, pre-run JSON artifact with format
`atmem-dolphin-finalization-manifest-v1` and a complete `identity` object. The
runner derives the candidate commit, run-config digest, gate type and cost
authorization itself; it never accepts those expectations from the submitted
gate. Changing the model, grader, checkpoint, prompt or budgets therefore
requires a new reviewed manifest and a new finalization run.

The development runner selects the six precommitted IDs per persona before the
official `_execute` path creates side-effect markers. It uses the official
executor and grader, writes an explicit `18-of-600` development receipt, and
cannot create or package an official 600-task score.
