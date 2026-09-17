# Scoped graph nomination implementation and review — 2026-09-17

**Status: implemented as an opt-in experiment; comparative quality not cleared.**
The user waived further Claude review after the session limit and authorized
implementation. Local review, regression tests and calibration are recorded below.
No default activation, commit, push, publication or deployment was performed.

## Scope

Spec 031 FR-025–FR-027 and tasks T036–T039 define an independently executable
addition to the experimental `core-rrf-v1` strategy. The plan derives an ephemeral
graph from already-authorized canonical records using the existing extractor,
rather than reusing global graph statistics, aliases or entity merges. It adds
bounded, independently nominated graph candidates with supporting paths; it does
not add causal inference or general natural-language relation extraction.

Defaults, matrix-cache settings, delegated providers, dependencies and release
versions remain unchanged. T035 remains open for reuse/scaling and activation;
T034 remains open for the measured fusion-ranking regression.

## Claude read-only review

Invoked Claude CLI with `--permission-mode plan --tools Read,Grep,Glob
--output-format text`. No edit or execution tools were enabled.

First review: **REVISE**. Claude considered the authorized-corpus architecture
sound and requested these explicit implementation commitments:

1. Permit graph-only requests in the opt-in contract.
2. Supply raw graph scores for every graph-nominated ID.
3. Revalidate the union of candidate IDs and every path-supporting record ID.
4. Use normalized surfaces, not entity kinds, to join ephemeral nodes.
5. Test a named-entity bridge, not a path through the user-root supernode.
6. Separate graph channel status from truncation and expose bounded counts.
7. Keep query-derived matched-seed text out of durable audit metadata.
8. Disclose that lexical/fact `min_score` does not threshold graph nominations.
9. Give the three benchmark profiles unique names, rotate execution order and
   report extraction/nominations coverage. Conversational calibration data may
   produce few or no graph edges; that cannot establish graph-quality benefit.

These commitments were added to the plan. Second design review returned:

> You've hit your session limit · resets 5:10pm (Australia/Sydney)

The limit was observed at approximately 13:46 Sydney time on 2026-09-17. No
second-review approval was obtained. The user subsequently instructed: "no need
to use claude implement it". T036/T039 were revised accordingly; the initial
feedback was retained and checked locally. This is not Claude approval.

## Cross-artifact check

Spec Kit prerequisites resolved the existing Spec 031 directory and its tasks.
FR-025 and FR-026 map to T036/T037/T039; FR-027 maps to T038/T039. The design
preserves authorization-before-intelligence, final validation and explicit
experimental activation. No constitutional amendment is required.

The status wording was reconciled to disabled/empty/active plus separate
truncation. No broad release-consistency clearance is claimed.

## Implementation and local review

- `atmem/retrieve/graph.py` derives one edge per extractable authorized record,
  joins normalized surfaces, and independently nominates through at most two
  edges. Entity kinds, persisted aliases/merges and global graph FTS cannot
  influence it. Canonical `User` and `you` are the same blocked fanout root.
- Limits: 16 seeds, 256 edge examinations (including repeats), at most 256 graph
  candidates and the request's lower quota. Cycles/self-loops are skipped;
  deterministic record-ID ties and a 0.75 per-additional-edge decay select one
  best discovered path. Truncation is explicit, not an exhaustive-search claim.
- `hybrid.collect` adds graph ranks/raw scores, rechecks every nominated and
  supporting record, and rejects stale content, exclusion, scope or generation.
  Existing original-query support and final preparation checks are unchanged.
- Canonical entity/relation paths are in authorized candidate signals. Audit
  metadata contains statuses/counts/bounds and supporting record IDs, not query
  text or matched seed tokens. Existing storage encryption policy still applies.
- Graph-only core requests now work. Use `retrieval_strategy="core-rrf-v1"`
  with `signals=("graph",)` or include graph with lexical/semantic. `min_score`
  still gates lexical/fact priors only; graph explicitly reports that it does not
  apply this threshold. Defaults and non-graph ranking are unchanged.

Local review verified the nine initial Claude findings against implementation.
An additional root-alias case (`User likes Sarah`) was fixed and tested so it
cannot bypass the supernode restriction. Tests cover a graph-recovered image-
derived text record, not raw visual/audio understanding. Persisted alias/merge
parity, language-wide extraction, ambiguous names and causal inference are not
claimed. Normalized surface joins retain the existing normalization limitations.

## Tests

Final command:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_retrieval_graph_fusion.py tests/test_retrieval_candidate_union.py \
  tests/test_contracts_v1.py tests/test_retrieval_quality.py \
  tests/test_retrieval_adapter_conformance.py tests/test_retrieval_signals_and_cache.py \
  tests/test_semantic_search.py tests/test_semantic_rebuild.py \
  tests/test_semantic_matrix_cache.py tests/test_graph.py tests/test_graph_quality.py \
  tests/test_graph_lifecycle.py tests/test_graph_aliases.py \
  tests/test_delegated_context.py tests/test_framework_delegated_adapters.py \
  tests/test_delegated_transport.py
```

**231 passed, 4 skipped in 26.61 seconds.** Graph fixtures include independent
two-edge recovery outside lexical nominations, seven denial modes, persisted
graph noninterference, cycles, both root forms, all budgets, deterministic order,
correction/forget, supporting-record mutation outside the nominated set, and
candidate invalidation before context preparation. `git diff --check` passed.
This is not the full release suite or an encrypted-backend performance test.
The earlier delegated-control stall was not reclassified as a passing gate.

## Frozen calibration ablation

```bash
./.venv/bin/python tools/benchmark_core_hybrid.py \
  --dataset /tmp/atmem-mem0-research.6BAkC2/longmemeval_s_cleaned.json \
  --source /tmp/atmem-mem0-research.6BAkC2/matched-v2-atmem-calibration \
  --output docs/implementation-evidence/031/graph-calibration-four-profile.json
```

The runner copies fixture databases, verifies canonical content/session sets
against the frozen manifest and never uses live user memory. Python 3.12.2,
local Nomic model ID `0a109f422b47`; source HEAD
`4fba0c1df051ebf2936c6d356857226cf6baa8f7` plus this uncommitted amendment and
earlier experimental changes. Dataset/model/full manifest identities remain as
recorded in [matched-v2](matched-v2.md); manifest hash is also in the raw report.

Twelve calibration cases, 338–364 records each, three calls/profile/case,
100 candidates per requested channel and 100 returned records. Deduplicate
sessions in candidate order and score top five. Profiles rotate by case and
repetition, sharing page/model caches; this is not isolated cold-start timing.
The fourth no-graph legacy control makes the prior experiment comparable.

| Candidate profile | MRR@5 | Recall-any@5 | Recall-all@5 | Median | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy, without graph | 0.938 | 1.000 | 0.917 | 57.94 ms | 87.34 ms |
| Legacy, with graph | 0.500 | 1.000 | 0.917 | 58.41 ms | 79.60 ms |
| Core fusion, without graph | 0.892 | 1.000 | 0.917 | 57.34 ms | 76.64 ms |
| Core fusion, with scoped graph | 0.683 | 1.000 | 0.917 | 69.00 ms | 90.65 ms |

Graph extraction found 34 edges across the 12 case corpora. Five queries each
received one graph nomination; seven received none. Graph decreased core MRR
in the five participating cases, despite successfully recovering connected facts
in targeted synthetic tests. A graph signal can promote a distracting candidate;
structural correctness is not ranking-quality clearance.

Raw results: [four-profile report](graph-calibration-four-profile.json).
The preceding [three-profile run](graph-calibration.json) is retained separately;
it produced the same profile quality values, with different noisy timings.
Neither report overwrites earlier evidence. No quality tuning was performed
after these measurements, and held-out cases remain unused by this amendment.

The measured boundary is `eligible_candidates`, including candidate evidence
writes, not answer support, final context, host delivery or answer quality.
Thirty-six correlated timings per profile are small-sample diagnostics, with no
confidence intervals or general speed claim. Mem0 was not rerun. Historical
4.46x semantic-index results are not transferable to this path.

## Recommendation for the next release

- Preserve shipping defaults for now; this sample does not justify an automatic
  global switch. Among the measured profiles, legacy without graph is the
  strongest ranking baseline, not legacy with graph. Do not conflate them.
- Keep scoped graph fusion opt-in. For the next development baseline, prioritize
  selective graph use and calibrated channel contributions, not unconditional
  equal-weight graph fusion. Prove that improvement on unseen cases first.
- Require graph-specific recovery/isolation tests, frozen held-out ranking and a
  newly matched Mem0 comparison before default activation or superiority claims.
- Address repeated corpus/index setup separately with scope-safe invalidation;
  keep NumPy matrix reuse off by default as requested.

This recommendation does not clear `2.3.3b1` for release. Existing Spec 031 quality,
speed, artifact, adapter and release gates remain binding. No commit, push, tag,
publication, installation or deployment was performed in this amendment.
