# Research: AtMem Context Engine

## Pinned references reviewed

| System | Revision | Relevant executable behavior | Adopted principle |
|---|---|---|---|
| AgentRunbook-C/C V2 | `2cc8c540bdb87fe6761629b585e727e1c4704520` | Concise/full trajectory manifests, targeted exact span inspection, agent-directed stopping, source-span submission, invalid-premise handling | Bounded evidence navigation over immutable source |
| AgentRunbook-R | same | Separate raw-state, transition, procedure and hint/gotcha pools; query bundle per pool; per-query merge caps; optional reranking | Independent evidence views, query-specific obligations and quotas |
| Mem0 OSS | `d3891e48baa2c6e769f9cfa4003873bd6a85bc07` | Additive extraction, fact update/consolidation, hybrid vector/BM25/entity scoring, user/agent/run scopes | High-recall additive formation and linked lifecycle-aware facts |
| DolphinBench | `81cb6f8405b40a9e76089cef650806a80af06ea2` | Hermes agent/action evaluation, persona stores, exact tool checks and published Mem0 result | End-to-end action quality with matched agent/model/tools |

All are Apache-2.0 at the recorded revisions. Techniques are reimplemented
against AtMem contracts; reference runtime code is not imported into product.

## Current AtMem evidence

- LongMemEval frozen 14-question run: 3/14 (21.4%).
- Seven-question enterprise baseline: 2/7 (28.6%).
- Best bounded diagnostic: 4/7 (57.1%), not reproduced.
- Confirmation diagnostic: 3/7 (42.9%).
- DolphinBench frozen 18-task run: 4/18 (22.2%).
- Same Dolphin task IDs, hosted Mem0 with a different model/service: 14/18
  (77.8%), context only rather than a matched local comparison.
- Reader-free investigation showed formation omissions, multi-entity packing
  loss, negative-premise weakness and unstable reader use.

### 2026-10-07 full-history Dolphin no-cost diagnostic

This is a formation/removal-control diagnostic, not a benchmark score. The
official histories for Alex (5,011 sessions), Morgan (3,400) and Riley (5,128)
were ingested into separate encrypted AtMem households before selecting the
frozen 30 tasks. The matched Mem0 checkpoint used the same 13,539 sessions.
Neither ingestion arm made a model call.

| Removal outcome | Cases | Interpretation |
|---|---:|---|
| Valid named pre-action block | 14 | Removed requirement named; model not invoked; zero tool calls |
| Source exists but no active represented unit | 10 | Formation failure: five pending governance review, five rejected typed proposals |
| Gate mismatch/non-atomic unit | 6 | Coarse source unit removed more than the intended requirement |

The five pending cases were withheld for sensitive, action-bearing or
non-durable review. The five rejected cases failed subject/relation grounding
or polarity validation despite retained immutable source. This establishes
that source retention alone is insufficient and that automatically loosening
the evaluator would create a false safety result. The next candidate must add
minimal source-linked units and an explicit audited import-review authority,
then rebuild checkpoints from scratch before paid scoring.

### `449b559` source-atomic follow-up

The clean installed follow-up rebuilt all 13,539 sessions and improved valid
named removal blocks from 14/30 to 18/30. Seven controls still named obligations
unrelated to the removed requirement, four could not isolate one requirement,
and one gate remained open after removal. No timeout, parse, provider or silent
no-call result was credited. The three encrypted checkpoints occupied
1,027,932,160 bytes for 7,727,403 bytes of source messages (about 133.0x).
Context Engine V3 storage accounting returned zero because the benchmark
adapter still used legacy canonical records: that is an integration failure,
not zero derived storage. Paid execution remains blocked. The complete table is
in `benchmarks/retrieval_quality/reports/dolphin-removal-diagnostic-449b559.md`.

### `8652889` compact V3 qualification attempt

The installed wheel rebuilt the complete 13,539-session Dolphin history in
three active encrypted Context Engine V3 generations with zero model calls.
Physical checkpoint storage fell to 245,264,384 bytes (76.1% below `449b559`),
logical derived/source ratios were 1.20x--1.28x, and no source body was
duplicated. The removal run was correctly rejected: 25/30 cases raised
`engine returned duplicate evidence identifiers` because one compact unit was
nominated through multiple typed views, while five targets remained
non-atomic. No outcome was credited. The fix must deduplicate at the retrieval
boundary while retaining cross-source diversity; the reader-free quality gate
must pass before the checkpoints are rebuilt again.

### 2026-10-07 bounded full-history retrieval diagnostic

The encrypted range lookup now materializes a bounded FTS shortlist before
joining the full generation, backed by generation/range indexes and a
full-generation authorization fast path. A representative full-history query
fell from 8.7--26.7 seconds to 0.08--0.20 seconds at the SQL retrieval layer.

The same frozen 30-case Dolphin development manifest was then used only as an
evaluator-side source-recall diagnostic. No evaluator requirement or source
reference entered the product query. With 32 bounded nominations and exact
neighbour expansion, the evaluator-verified source appeared in the delivered
package for 26/30 cases, up from 13/30 immediately before the breadth/ranking
change (and 8/28 in the earlier interrupted diagnostic). Median end-to-end
context preparation was 2.51 seconds and maximum was 4.11 seconds on the local
encrypted checkpoints. The remaining source misses were `alex:042`,
`alex:136`, `morgan:011`, and `morgan:097`.

This is not a benchmark score and does not satisfy T005L. All packages still
reported sufficient because the deterministic planner exposes too few semantic
obligations and the retriever can attach one generic obligation to a merely
similar candidate. A local no-cost embedding experiment also showed that
semantic reranking alone is insufficient: it rescued some lexical misses while
displacing exact matches. The next gate is independent
exact/lexical/temporal/semantic fusion plus obligation-grounded coverage, not a
larger undifferentiated top-k or a paid reader run.

The subsequent obligation/loss-ledger iteration decomposed explicit request
requirements, required lexical grounding for each nominated head, changed a
forgotten observation from `represented` to `withheld`, and emitted the actual
product obligation IDs and descriptions in the pre-action receipt. On the same
30 controls, 19 removals produced a pre-action block whose independently
evaluated product description matched the removed fact, with no model or tool
invocation. Six gates remained open and five targets remained non-atomic. The
six open cases contain either strong duplicate evidence elsewhere or a removed
range whose surviving source text cannot identify the missing need. They are
failures for this control run, not silent successes. The five composite ranges
still require bounded-clause formation. Paid execution remains blocked.

The next clean candidate keeps the immutable source body unchanged but permits
bounded predicate-bearing clauses to become separately source-linked units.
Where one evaluator requirement genuinely spans adjacent clauses, the removal
control may select the smallest set whose members are all exclusive to that
requirement. It may not delete a clause that materially supports another
requirement, and it records every removed unit identity. This is a formation
and evaluator-integrity correction; its result must come from a newly built,
installed wheel and newly formed checkpoints rather than the prior databases.

## Decisions

### R1 — Clean engine boundary

Build a new engine behind a versioned public context contract. Do not evolve
`hybrid.py` into the new architecture. Legacy remains a frozen control and
rollback implementation until migration and qualification pass.

### R2 — Source once, views many

Store immutable source episodes once. Every evidence view stores compact fields,
source ranges and searchable projections, not another full trajectory body.
Views are rebuildable generations and never authority.

### R3 — High-recall formation with an explicit loss ledger

Run deterministic projections for exact/raw surfaces and optional model-assisted
additive extraction for semantic facts, procedures, transitions and gotchas.
Validate every proposal against source ranges. Record uncovered ranges and
unsupported media instead of marking the episode complete.

### R4 — Obligation-first retrieval

Plan the evidence needed to answer, not merely alternative search strings.
Nominate independently per obligation and evidence view, reserve one valid head
for each required obligation, then add complementary support. This prevents a
dominant entity or pool from consuming the whole context.

### R5 — Two operating points

`context-fast` uses deterministic/query-model planning plus persistent indexes
and bounded neighbourhood expansion. `context-navigate` may use a pinned model
to inspect manifests and exact spans. Both return the same contract and enforce
the same authority and total-input budget.

### R6 — Sufficiency is source coverage

Similarity, reranker probability and model prose remain ranking evidence only.
Sufficiency requires grounded coverage of declared obligations and represents
conflict, staleness, partial support and absence explicitly.

### R7 — Comparators before claims

Implement neutral AgentRunbook and Mem0 adapters before further leaderboard
claims. Use reader-free minimal-evidence evaluation for rapid iteration, then a
bounded live micro differential, then full matched development/confirmation.

### R8 — Separate release safety from research leadership

Stable release qualification uses an absolute LongMem quality floor,
non-inferiority to legacy, LoCoMo no-regression, governance, performance,
storage and installed product gates. Benchmark-leading language additionally
requires a matched relative lead with paired uncertainty. Missing a claim gate
cannot waive safety, but it also cannot indefinitely block unrelated product
work; the candidate remains experimental/shadow and the result stays honest.

### R9 — Neutral, symmetric evaluation

Reader-free evaluation uses disjoint development/sealed-holdout fixtures and a
pre-frozen output-to-source-span normalizer shared by AtMem, Mem0 and
AgentRunbook. Paid arms declare complete model, prompt, embedding, resource and
cost cards, receive equal-size development sweeps and symmetric repetitions,
and report cost-normalized accuracy without best-of selection. Dolphin persona
memory is frozen before tasks; task holdout is reported separately from corpus
holdout.

## Rejected alternatives

- **Tune larger top-k on the existing hybrid ranker**: already produced unstable
  gains and larger incomplete contexts.
- **Copy reference code into AtMem runtime**: couples product behavior to
  benchmark implementations and weakens contract/governance ownership.
- **Use an LLM answer as memory context**: converts AtMem into an answerer and
  obscures evidence provenance.
- **Require model navigation for all queries**: violates local-first operation
  and imposes avoidable cost/latency on exact facts.
- **Use published numbers as the release comparator**: not matched and therefore
  insufficient for a leadership claim.
