# Implementation Plan: AtMem Context Engine

**Branch**: `bench/longmemeval-v2` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/040-atmem-context-engine/spec.md`

## Summary

Create a parallel Context Engine V3 that retains AtMem's public context-provider
role and governance authority while replacing formation, views, planning,
retrieval, navigation, sufficiency and packing. Reimplement the strongest
techniques observed in AgentRunbook-C/R and Mem0 against AtMem contracts. Keep
legacy retrieval as a frozen A/B and rollback profile. Promote V3 only after
reader-free, matched comparator, product, performance and governance gates.

## Technical Context

**Language/Version**: Python 3.10–3.13

**Primary Dependencies**: standard library and existing AtMem core; optional
SQLCipher, embedding provider and OpenAI-compatible navigation/extraction
provider remain separately installable and explicitly configured

**Storage**: existing encrypted SQLite household; additive source-range,
evidence-view-generation, compact view and index metadata; optional encrypted
vector store; heavy benchmark artifacts on `MEM`

**Testing**: pytest contract/property/integration/installed-artifact tests,
official LongMemEval-V2 and DolphinBench harnesses, neutral reference laboratory

**Target Platform**: macOS, Linux and Windows supported package paths; Hermes
uses its supported WSL path on Windows

**Project Type**: Python library, CLI, local service/dashboard, MCP server and
host adapters

**Performance Goals**: no whole-store query scans; CPU-only `context-fast` at
50k units p50 ≤500ms, p95 ≤2s and RSS ≤512MiB, and at 100k p95 ≤3s;
`context-navigate` p95 ≤30s and ≤USD 0.05/query; sampled shadow overhead ≤20%;
all derived storage including FTS/vectors ≤1.5x immutable source

**Constraints**: authority before intelligence, encrypted-at-rest semantic
metadata, exact source provenance, verified deletion, local deterministic
fallback, one total-input budget, no benchmark imports in product code

**Scale/Scope**: ≥100k evidence units per household, ≥10 simultaneous agent
bindings with isolated or explicitly shared scopes, full LongMemEval Small and
600 Dolphin tasks for applicable claims

## Constitution Check

| Principle | Design response | Gate |
|---|---|---|
| Authority before intelligence | Product boundary performs scoped nomination and canonical revalidation; engines cannot mutate authority | scope/noninterference and race tests |
| Provenance/full fidelity/replay | Source stored once; every unit/range links to immutable source; loss receipts explicit | dead-agent reconstruction and source-range round trips |
| Safe defaults/reversibility | V3 begins shadow; explicit activation; legacy rollback profile | installed activation/fault/restore tests |
| Scoped transparency/deletion/encryption | Derived views inherit scope/lifecycle, use encrypted store and participate in deletion | stolen-store, privilege and verified deletion gates |
| Contract-first neutrality | V3 contracts are host-neutral; adapters only translate delivery boundaries | CLI/MCP/dashboard/adapter golden tests |
| Executable claims | Matched held-out gates and exact installed artifact identity | qualification-package validator |
| Local-first/replaceable intelligence | deterministic fast path works without models; egress/model explicit | provider-offline suite |
| Production benchmark evidence | frozen splits, matched comparators, raw evidence and uncertainty | LongMem/Dolphin validation |

No constitutional exception is requested.

## Architecture

### 1. Governance shell

`ContextEngineService` owns authorization, generation binding, canonical reload,
revalidation, packaging audit and delivery. Engines see only scope-authorized
manifests/candidates and return opaque source/unit IDs plus bounded numeric/model
signals. This preserves Specs 003/019 and Constitution I.

### 2. Immutable source ledger and derived generations

Retain existing episode/evidence services as canonical source. Add stable source
ranges and a generation registry. Build compact evidence views in a new inactive
generation, verify coverage and indexes, then atomically expose it to shadow or
active profiles. Never rewrite source during engine migration.

### 3. Formation pipeline

1. Inventory ordered source text/media/tool regions.
2. Deterministically project exact raw-state slices and structural transitions.
3. Optionally run high-recall additive extraction over bounded regions.
4. Validate each proposed unit against exact source ranges and authority.
5. Reconcile facts/corrections/duplicates while retaining occurrences.
6. Persist compact units/links and an explicit coverage/loss receipt.

This combines Mem0's additive extraction/consolidation with AtMem authority and
AgentRunbook-R's distinct evidence pools.

### 4. Query and retrieval pipeline

1. Create explicit evidence obligations.
2. Allocate independent queries/quotas by view and obligation.
3. Nominate through persistent exact/FTS, semantic, temporal and link indexes.
4. Reserve one valid evidence head per required obligation.
5. Expand source/transition neighbours within a fixed budget.
6. If still partial and profile allows, navigate authorized manifests and exact
   spans using AgentRunbook-C-style operations.
7. Revalidate submitted ranges and decide sufficiency.
8. Pack complementary evidence under one total-input budget.

### 5. Intelligence profiles

- Deterministic planner and fallback are always installed.
- Optional query planner, extractor, reranker or navigator each has a pinned
  identity, prompt/schema, timeout, retry and egress policy.
- Model output can propose queries, units or IDs but never source truth,
  authorization or sufficiency.
- Spec 039 AtMem-MJM is evaluated only as an optional candidate-ranking
  ablation after V3 deterministic/reference gates pass.

### 6. Product integration

Expose V3 through the existing application service, then adapt CLI, MCP,
dashboard and hosts to the same contract. Dashboard shows engine profile,
formation coverage, sufficiency, sources, shadow deltas, limits and errors.
AtFlows receives content-free stage events only.

### 7. Benchmark and reference laboratory

Complete neutral AtMem, Mem0 and AgentRunbook adapters. The laboratory has:

1. no-model contract/property fixtures;
2. replayed pinned model cassettes;
3. reader-free minimal-evidence comparison;
4. small live model-backed differential;
5. frozen paid development/confirmation.

Official adapters invoke installed public APIs and cannot compensate for missing
product behavior.

The reference corpus is split into development and sealed holdout before any
system run. A pinned system-neutral output-to-source-span normalizer prevents
AtMem source-range output from receiving structural credit unavailable to Mem0
or AgentRunbook. This corpus is only a paid-run go/no-go gate, not leaderboard
evidence.

Each paid comparator arm has a frozen resource card covering formation LLM,
embedding, planner/navigator, reader, judge, prompts, top-k/context, maximum
calls/tokens/operations, repetitions/seeds, hardware and cost. Arms receive the
same-size development sweep and symmetric repeats; reports show per-run values,
means, paired bootstrap intervals and cost-normalized accuracy, never best-of.
For Dolphin, the persona checkpoint is frozen before scoring and results report
all 600 tasks and the 582 non-development tasks separately.

## Migration and Compatibility

- Additive schema migration creates V3 generations without changing current
  active retrieval or canonical source.
- Backfill is resumable, idempotent and reports uncovered legacy source.
- Context V2 remains available through a compatibility adapter.
- Shadow comparison is the default after backfill.
- Activation changes a profile pointer only after qualification.
- Rollback rebuilds the legacy derived state from current canonical source and
  verifies deletion/expiry/correction/revocation freshness before changing the
  pointer; V3 does not dual-maintain legacy indexes by default.
- Derived V3 state may be rebuilt and later deleted through verified deletion.

## Project Structure

```text
atmem/
  context_engine/
    contracts.py
    service.py
    formation.py
    coverage.py
    planner.py
    pools.py
    retrieval.py
    navigator.py
    sufficiency.py
    packing.py
    profiles.py
    telemetry.py
  store/
    sqlite.py
  contracts/
    models.py
  control/
    manager.py
  mcp/
    server.py
  cli.py

research/reference_parity/
  runner.py
  contracts.py
  adapters/
    atmem.py
    agentrunbook.py
    mem0.py

research/production_benchmarks/
  adapters/longmemeval_atmem.py
  run_longmem_pilot.py
  run_dolphin_development.py

benchmarks/retrieval_quality/
  protocols/
  reports/

tests/
  test_context_engine_contracts.py
  test_context_engine_formation.py
  test_context_engine_retrieval.py
  test_context_engine_navigation.py
  test_context_engine_governance.py
  test_context_engine_migration.py
  test_context_engine_performance.py
  test_reference_parity.py
```

**Structure Decision**: Use a new `atmem/context_engine/` package rather than
continuing to extend `atmem/retrieve/`. Only the product service connects it to
canonical store and public contracts. Reference/benchmark adapters remain
outside runtime.

## Verification and Iteration Order

1. Freeze current AtMem, Mem0 and AgentRunbook results on identical small
   evidence fixtures before implementation.
2. Build source/range/view contracts and governance shell.
3. Pass formation coverage and storage gates.
4. Pass deterministic obligation retrieval and sufficiency gates.
5. Add navigation and pass source-span tests.
6. Run reader-free reference parity; iterate until AtMem is at least 10%
   relatively better than both comparators on the frozen micro corpus.
7. Run a bounded live differential; freeze the best reproducible profile.
8. Run complete matched 14-question LongMem development and 18-task Dolphin
   development—never another AtMem-only paid run.
9. Only after development targets pass, run untouched confirmation/full gates.
10. Complete installed cross-platform product qualification and release decision.

Each iteration writes an A-to-B table with formation coverage, evidence recall,
sufficiency, reader/action accuracy, latency, bytes, storage and cost. Peaks and
non-reproduced results remain visible and cannot replace the confirmation arm.

## Complexity Tracking

No constitution violation. A parallel engine temporarily duplicates code, not
canonical source data. This is required to preserve a stable control and safe
rollback while avoiding legacy architecture constraints; the legacy engine is
retired only in a later separately reviewed compatibility change.
