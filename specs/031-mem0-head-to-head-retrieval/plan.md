# Implementation Plan: 2.3.3 Beta Retrieval and Mem0 Comparison

**Spec:** [spec.md](spec.md)
**Constitution:** [AtMem Constitution](../../.specify/memory/constitution.md)
**Research input:** [pinned Mem0 2.0.20 source](https://github.com/mem0ai/mem0/tree/0df3e4b87df20785f0741370c75e44428796193e) and [benchmark baseline](../../docs/implementation-evidence/031/baseline.md)
**Target:** beta source candidate `2.3.3b1`; publication only after all release gates and an explicit release request.

## Technical context and baseline

AtMem 2.3.2 uses Python 3.10–3.13, SQLite canonical memory, an encrypted portable Home, a rebuildable SQLite vector sidecar, optional local or hosted embedders, AtBot as a proposal/ranking companion, and OpenClaw plus framework adapters. The OpenClaw bridge is a separate npm package; AtBot `0.1.0` is independently versioned. The benchmark runner is Python; the UI is the existing control dashboard. Mem0 stays in a separate temporary Python environment.

The previously published 12-case LongMemEval-S raw-retrieval comparison used Mem0 OSS 2.0.19 and `nomic-embed-text:latest`. AtMem and Mem0 tied on recall@5; Mem0 won MRR@5 (1.000 vs 0.958) and reported search p95 (57.9 ms vs 193.1 ms). Preserve that dated report. Before code changes, run the checked-in deterministic gate and rerun the pinned raw-retrieval campaign on this machine, recording the source/dataset hashes, complete timing boundary and any changed environment. A new comparison should pin current Mem0 `2.0.20` separately; a changed opponent version is a new experiment, not a revision of the old report.

The full native preparation path has a different budget, support gate and optional companion behavior from the raw benchmark. Build a native AtMem workload and a comparable Mem0 search plus bounded context assembly profile. If its authenticated delivery semantics cannot be matched, name only the common timed segment and leave full-preparation comparison unavailable. Raw retrieval, native context, end-to-end extraction/answer and host-observed delivery receive separate labels.

## Design and ownership

### Benchmark contract and evaluation

Extend `atmem/benchmark/` contracts and `tools/` runners, reusing the existing external result validator and comparison logic. Create immutable `benchmarks/2.3.3b1/` manifests or a new append-only evidence entry under `docs/implementation-evidence/031/`; user supplied datasets remain in temporary storage. The raw runner must record full mode, package versions, content hashes, cases, index parameters, retrieval limit, context budget, hardware/CPU, cold/warm state, independent timing boundaries, per-case source rank and the exact scorer. The native runner calls the service/control path used by adapters, checks the prepared context bytes and records authorization/exposure evidence separately. Mem0 uses only its public OSS APIs under a pinned environment with telemetry disabled and model endpoint declared. An external LLM answer judge is optional, declared and never silently substituted.

Freeze a calibration partition and a distinct held-out partition before adjusting relevance weights. Deterministic fixtures cover cases that LongMemEval does not: scope denial, model failure, corrections, media-derived text, misleading topical matches and non-Latin scripts. Report Pareto quality directions, paired case deltas and latency ratios. Do not combine sampling noise, different corpus sizes or different context budgets in one multiplier.

### Retrieval quality

In `atmem/retrieve/rank.py`, separate topical matching from requested relation/attribute support. Start with general question-intent slots and an explicit abstain on unsupported relations, then use a bounded optional verifier only when measured necessary. Any slot rule must be generic and tested on a held-out category. Unicode-aware lexical normalization must preserve useful letters/numbers across supported languages. Keep original-query scoring, direct/background/no-useful classes and diagnostic-embedding exclusion.

In `atmem/memory.py` and `atmem/store/sqlite.py`, nominate lexical, fact-key, semantic and bounded graph candidates independently. Fuse only after the same authority and lifecycle filters. Bound each channel and record its contribution. Do not allow an inaccessible record or count to influence visible ranking. Preserve the final `prepare_context_v1` reload and context digest.

### Fast path and derived state

Mirror AtBot 0.1.0's existing deterministic query expansion in a local pure function used by the AtMem client, with a parity test against the companion's versioned behavior. AtBot remains independently packaged; its existing endpoint remains compatible. For common direct facts, avoid companion health/request round trips, but retain the exact decision and delivery contracts. AtBot remains optional for ambiguous or complex ranking. Time the fallback and compare quality before enabling it broadly.

Integrate the existing `RetrievalDecisionCache` only after adding missing key identities and race tests. Cache selected identifiers and decisions, not long-lived plaintext; on hit verify generation, policy, membership, lifecycle, index and current record eligibility. Do not cache an unverified provider response or a prepared envelope across turns.

Implement embedding reuse in `atmem/semantic/index.py` by copying or referencing a prior compatible epoch's vector only after validating object ID, content hash, scope, model and preprocessing identity, and policy fingerprint. A changed record is re-embedded; a missing or incompatible prior entry is not reused. Stage a new epoch and activate after whole-source and generation validation. Preserve deletion and rebuild recovery semantics. Avoid schema changes if possible; if unavoidable, use the Spec 010 migration registry and real upgrade fixtures.

### User interface and documentation

Keep the dashboard's existing navigation. Add a compact diagnostic summary for semantic quality, last declared benchmark profile and withheld/direct support, with a click-through case view if a benchmark report is present. Reuse the same authenticated service read model as the CLI. Restrict plaintext to the existing investigator/evidence collector role policy; viewer sees aggregate metrics and hashes. No oversized settings panel or long scrolling report. Case evidence should fit keyboard and narrow screens.

Audit all tracked Markdown for live version and status claims, stale beta pins, broken relative links and contradictory current-scope text. Classify historical releases/reviews separately from current product docs; never rewrite a prior measurement. Update README, benchmarks guide, current status, roadmap, relevant active specs and beta release notes only with measured outcomes. A failed speed target remains a recorded failure, not a polished claim.

## Files and contracts

| Area | Intended changes |
| --- | --- |
| Benchmark | `atmem/benchmark/`, `tools/run_longmemeval_retrieval.py`, new matched native runner, versioned result schema, tests and manifests |
| Selection | `atmem/retrieve/rank.py`, `atmem/retrieve/calibration*.json`, `atmem/memory.py`, `atmem/store/sqlite.py` |
| Intelligence | `atmem/control/manager.py`, `atmem/control/atbot_companion.py`, `packages/atbot/src/atbot/companion.py` only if shared expansion contract needs it |
| Derived state | `atmem/retrieve/cache.py`, `atmem/semantic/index.py` |
| Host boundary | OpenClaw, Pydantic AI, LangChain/LangGraph and MCP contract tests; production adapter code only if a real regression appears |
| UI | Existing `atmem/control/assets/` diagnostics and accessible drilldown; common service read model |
| Docs/release | `docs/benchmarks.md`, `docs/current-status.md`, `docs/release-roadmap.md`, README, `docs/releases/v2.3.3b1.md` when candidate gates are met |

## Sequencing and validation

1. Freeze benchmark manifest, pre-change results and held-out cases; verify dataset and Mem0 source hashes.
2. Add failing independent quality, cache-race, index-reuse and cross-adapter tests. Run Spec Kit analysis before production edits.
3. Implement relation-aware/Unicode support and independent candidate nomination; rerun deterministic gate.
4. Optimize deterministic expansion, guarded cache and index reuse one at a time; measure each ablation. Revert any optimization that regresses safety or held-out quality.
5. Add stage timing and benchmark/CLI/UI read model, then rerun on the same hardware and pinned external configuration.
6. Run full Python, AtBot, OpenClaw build/typecheck/hooks, framework/MCP contracts, dashboard, docs, build metadata and installed-artifact gates. Audit persisted upgrade if a schema changed.
7. Prepare aligned beta version constants and release note only for a reviewed passing candidate. Under the repository release rule, no tag/push/publication occurs merely because a plan or candidate is complete.

Quality gate: zero unauthorized, stale or cross-scope exposures; existing floors do not regress; held-out relation nonanswer is withheld; beneficial recall remains. Speed gate: calculate the FR-006 ratio only when timed boundaries and configurations match; 2× is required for release-candidate clearance and 10× is stretch. If unmet, report the actual metric and keep the beta untagged until the implementation improves or the user explicitly revises the scope. Never tune on the held-out questions after looking at the results.

## Consistency decisions

- Spec 001 owns benchmark contracts and intentionally forbids production retrieval changes **within that spec**; Spec 031 owns the new production changes and consumes Spec 001 result formats.
- Spec 008's checked tasks document its earlier implementation; new regression cases and calibration revisions belong here without rewriting completed history. Spec 002 supporting evidence remains a ranking signal, not causal proof.
- Spec 005 owns semantic model/epoch identity. Spec 010 owns large-scale storage and migration contracts. This beta measures small/local and declared medium workloads; it does not claim Spec 010's million-record service target.
- Spec 009's entity graph is associative. Spec 026's temporal foundation and consolidation remain scheduled separately. This beta must not advertise historical temporal reasoning or causal what-if answers.
- Spec 003/004 delegated providers and signatures remain separate authority profiles. New native ranking must not alter provider-owned exact context or claim provider content was stored in canonical AtMem memory.
- Spec 022 owns broad dashboard navigation. This beta adds retrieval diagnostics within the existing information architecture, not a competing workspace design.
- The published 2.3.2 baseline remains true; beta 2.3.3 is an intervening maintenance/quality feature. The 2.4 multi-agent scope remains planned and unclaimed.
