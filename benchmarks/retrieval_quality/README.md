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

- `longmemeval-v2-pilot-v1.json` selects 14 development questions: one from
  each frozen domain-by-ability stratum. It contains no confirmation IDs.
- `dolphinbench-task-split-v1.json` selects 6 of the 200 tasks for each of the
  three official personas (18/600 total) and freezes the remaining 582 for
  later confirmation.
- `2.3.8.yaml` pins upstream commits, model revisions, prompts/scorers,
  provider routes, hardware, retry limits, context/output limits and cost caps.
  `provider-route-probe-v1.json` is the content-free credentialed evidence for
  the exact DeepInfra, Scaleway and dated OpenAI routes. The validator checks
  its canonical digest and every successful route before permitting a pilot.
- The Hugging Face router identifies the served model and provider but does
  not attest the exact weights commit. The repository revisions are frozen
  reproducibility references, not a claim of cryptographic served-weight
  identity. A publication requiring that stronger claim must use an endpoint
  that exposes an attested revision or a locally hashed model artifact.
- Dolphin interactions and each LongMemEval pilot case reserve their maximum
  permitted provider cost durably before network egress. A crash leaves the
  reservation in place and blocks a blind paid retry. LongMemEval reports the
  reserved upper bound because its official reader/judge path does not expose a
  transactional provider debit; this is conservative budget evidence, not a
  claim about the provider's final invoice.
- The official RAG comparator reaches the pinned Scaleway embedding provider
  through a loopback-only OpenAI-compatible facade. The facade performs no
  ranking or benchmark compensation, retains no input, and is byte-pinned by
  the protocol. The official process receives a sanitized environment so
  inherited endpoint and Python import overrides cannot redirect the run.

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
