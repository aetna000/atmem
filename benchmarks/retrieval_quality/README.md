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
