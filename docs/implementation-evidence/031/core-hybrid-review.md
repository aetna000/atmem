# Core hybrid review — 2026-09-17

## Design round 1 — Claude CLI, read-only

Invocation uses `--permission-mode plan --tools Read,Grep,Glob`; no write tools.
Verdict REVISE. Accepted: filter before rank normalization and quotas; do not use
legacy recall backfill/synthetic fact scores; define lexical and semantic threshold
scales; keep earliest expansion rather than compare cross-query RRF; define mixed
graph routing; emit actual ranks/status/version; use file-backed semantic tests.

Design choice: scoped FTS from all authorized active records, independent fact
and production semantic nominations, deterministic normalized RRF. Mixed graph
is explicitly deferred, not invisibly used or claimed implemented. Legacy graph
API stays unchanged. This scope limitation is in spec and plan; T006/T009 stay open.

Pre-change command: `./.venv/bin/python -m pytest -q tests/test_contracts_v1.py tests/test_retrieval_quality.py tests/test_semantic_search.py`
Result: 41 passed in 6.63s.

Compatibility refinement: preserve default legacy graph behavior. Expose core
fusion through a validated additive request strategy field. User was asked about
switching defaults at the expense of graph contributions; absent a choice no
such regression is authorized. Adapter activation remains separate work.

## Design round 2 — REVISE

Accepted explicit normalized composite scale for min_score (not raw BM25), a
separate 0.0 semantic nomination floor (0.72 remains support-only), and streamed
authorized corpus with 10,000-record / 8 MiB limit and explicit error on overflow.
FTS is built once per explicit call; existing adapter expansion loops remain on
legacy. No cross-call cache is added without separate invalidation work.

## Design round 3 — APPROVE

Claude approved the opt-in core strategy with legacy serialization preserved,
bounded corpus, explicit graph deferral and allowed-ID semantic restriction.
Accepted optional schema enum, graph-only validation, and strategy evidence.

## Code round 1 — REVISE

Claude identified an undisclosed supporting-session bonus in publication. Removed
it for core fusion; pure RRF scores now publish without aggregation. Added actual
channel ranks to audit, rejected core graph-only requests, and distinguished
corruption/egress denial/model incompatibility. Expanded fixtures cover missing
FTS, empty results, fact-only nomination, inactive/media-derived text, changed
canonical state and explicit self-age versus relative-age support.

The first 12-case comparison included the now-removed bonus and is invalid as a
pure-fusion comparison: legacy MRR .9375, prototype .9333; respective p95 63.84
and 69.38 ms. It is preserved here as a rejected prototype, not a release claim.
An intermediate rerun overlapped regression tests and is excluded from latency
evidence. Final timing must run without those tests in parallel.

Broader initial test attempt: 138 passed, then interrupted after 259.66 seconds
while blocked in `socket.py:707`; not counted as a completed transport suite.

## Code round 2 — REVISE (disclosure only)

Claude confirmed retrieval, scoping and revalidation logic. Requested audit-only
authorization-withheld counts and accurate lexical/fact threshold naming. Added
both with regression assertions; counts do not enter candidate signals/ranking.
Documented score comparability, schema versus runtime graph validation, and scoped
integrity limits. Completed final pure-RRF calibration and stored raw JSON;
MRR .8917 versus legacy .9375 blocks default rollout/quality claims.

## Final code review — APPROVE

Claude verified both disclosure fixes and their tests, with no remaining
substantive blockers for experimental opt-in use. Codex agrees only with this
bounded implementation approval, not quality clearance or Mem0 superiority.

Final core/contract/retrieval/semantic/graph suite: **100 passed in 12.88s**.
Separate delegated/context/framework/transport suite: **112 passed, 4 skipped
in 11.94s**. The interrupted delegated-control run remains uncompleted; no full
release-gate claim. A later focused fixture also verifies final context
construction from the new candidate set.

Spec Kit consistency: FR-021–024 mapped to T029–033, with follow-ups T034–035
explicitly retaining quality/default/graph rollout work. Four amendment requirements,
five implementation tasks, 100% task coverage; no unassigned amendment requirement
or constitutional blocker for the opt-in scope. Approval does not mark broad
T006/T009 or release tasks complete. Source/schema/benchmark docs name the same
strategy and disclose graph deferral, threshold scale and negative calibration.

No commit, push, installation or release performed. Existing unrelated research
and MemoryBench files preserved. NumPy matrix cache remains off by default.
