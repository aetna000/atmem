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
official LongMemEval-V2 and DolphinBench harnesses, pinned AGMI T1–T9 at-rest
suite, neutral reference laboratory

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
| Executable integrity claims | record-to-chain verification plus honest external rollback anchor | AGMI T1–T9 validation |

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

The paid development profile is a nested five-percent expansion of the retained
historical calibration: 23 of 451 LongMemEval-V2 questions and 30 of 600
DolphinBench tasks. Selection uses public identifiers and pinned salts only;
the old 14/18 manifests and results remain immutable historical artifacts.
Case selection is the sole reduced dimension: each selected case follows the
full-run formation, retrieval, modality, reader/agent, tool, prompt, budget,
retry, judge/grader, telemetry, raw-evidence and reporting path. A generated
equivalence receipt compares the effective development configuration with the
frozen full-run configuration after removing only the case-ID field and fails
closed on every other difference.
Every paid runner imports the exact candidate checkout ahead of site packages,
executes in an isolated environment, records the resolved module and wheel
digest, and refuses a globally installed or mismatched AtMem artifact.

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

Before scoring, evaluator-only manifests enumerate the evidence requirements
for all 23 LongMemEval questions and action prerequisites for all 30 Dolphin
tasks. Per-requirement stage ledgers distinguish source, formation, nomination,
neighbour expansion, packing, delivery, reader use and action. LongMem uses the
same pinned reader on product context, verified minimal evidence and no-memory
control to separate memory-pipeline failures from reading failures. Dolphin
removal tests pass only on a named pre-action missing-requirement receipt with
no model invocation and no tool call; transport, timeout, parsing and generic
no-call outcomes remain separately failed.

The evaluator manifest uses stable requirement identifiers and the complete
class vocabulary from FR-040. It is loaded only by evaluation/reporting code,
never by AtMem formation, retrieval, packing, the memory adapter, or the host
agent. A requirement ledger records the eight ordered stages from source
existence through reflected answer/action with four-state observations
(`passed`, `failed`, `not_reached`, `not_applicable`). A deterministic
classifier emits exactly one terminal outcome per case and rejects missing,
unknown, contradictory or silently defaulted evidence.
The checksum-bound evaluator-only `attribution-review-protocol-v1` defines the
per-stage evidence rules. Review packets begin unsigned with invalid
`unreviewed` states and can be finalized only after every requirement/stage has
an artifact citation or explicit non-pass reason and every case has one known
terminal outcome. `used_by_reader` is an observable response/controlled-input
proxy, never a claim about hidden model cognition.

LongMem attribution executes three reader inputs for every selected question:
the byte-identical product package, a verified evaluator-owned minimal evidence
package, and no memory. The runner binds all three to one reader identity,
prompt, sampling configuration and budget. Dolphin action evaluation adds a
host-side pre-action gate: removed evidence must yield a named
`blocked_missing_requirement` receipt before model invocation, while restored
evidence must open the gate and reach the expected tool path. Error and
no-call outcomes remain failed observations rather than safety blocks.

The retained twelve-case reader-free fixture is reanalysed from its frozen raw
results into a separate requirement-class table. Its report is explicitly a
small historical diagnostic and is not merged into five-percent aggregates.

AGMI is a third, orthogonal qualification family rather than a retrieval score.
Pin the upstream repository, package, adapter and T1–T9 attack implementations,
then execute both published AtMem profiles from an installed candidate. Each
case retains proof that the edit landed, whether the read path emitted altered
memory, the explicit verification result and the detection point. Development
runs may relax only AGMI's exact AtMem version assertion; they cannot be called
an official re-measurement until upstream pins the released version.

The integrity design adds a compact authenticated record commitment keyed by
stable record identity and covering content digest, subject/scope, ordering and
security-relevant metadata. Reads validate selected records against canonical
commitments before context delivery; indexed roots avoid a whole-store scan.
The anchored profile uses a recoverable two-phase store/root commit and a
monotonic checkpoint placed outside the store attack domain. A chain entirely
inside the rolled-back store cannot detect a whole-store snapshot rollback, so
chain-only T9 remains explicitly `unanchored`; this is a technical boundary,
not a benchmark exception.

The first full-history Dolphin no-cost checkpoint exposed three distinct
product failures that are now hard gates rather than evaluator exceptions. Of
30 removal controls, 14 produced a valid named pre-action block, 10 selected
source episodes had no active represented unit, and 6 removed a coarse unit
whose gate failure could not be attributed to the intended fact. The 10
formation gaps divide into five pending-review episodes and five episodes with
typed grounding/polarity rejection. These numbers are development diagnostics,
not benchmark scores.

Formation therefore preserves minimal exact source-linked observations beside
semantic views, and removal controls require a one-requirement unit rather than
deleting an entire message. Reserved schema labels such as the structural
observation subject/relation are validated as schema, while the carried value,
offsets and polarity remain source-derived. Bulk history review is permitted
only through an explicitly configured, scope-bound operator authority and the
ordinary audited review service; it is answer-blind and evaluator manifests
remain inaccessible. A rebuilt checkpoint and all no-cost removal gates must
pass before any paid reader or Hermes invocation.

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
  adapters/longmemeval_mem0.py
  matched_results.py
  run_longmem_pilot.py
  run_dolphin_development.py
  run_agmi_integrity.py

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
  test_official_benchmark_adapters.py
  test_retrieval_quality_protocol.py
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
7. Run the immutable six-question LongMem stage with the complete production
   pipeline and every matched arm. Unlock the remaining five-percent cases only
   when AtMem is strictly above AgentRunbook-R; a tie or loss returns to the
   earliest attributed implementation stage and reruns the identical six.
8. Reproduce the published AGMI 2.3.7 rows, implement record-to-chain and
   external-checkpoint verification, then pass the pinned T1–T9 development
   gate without weakening retrieval or governance.
9. After the six-question gate passes, run complete matched 23-question LongMem development and 30-task Dolphin
   development—never another AtMem-only paid run.
10. Only after development targets pass, run untouched confirmation/full gates.
11. Complete installed cross-platform product qualification and release decision.
12. Build the next beta from that exact reviewed commit and rerun the
    release-associated LongMemEval-V2, DolphinBench and AGMI qualification
    against the installed artifact. Bind every retained row to the beta version
    and wheel SHA-256; source-checkout rows remain diagnostic.
13. Keep mutable benchmark databases, vector indexes and per-case runtime state
    on the host's local performance filesystem. Use the external `MEM` volume
    only for immutable datasets/checkpoints and durable logs, receipts and final
    evidence; clean each case's local runtime state immediately after that case,
    not only after the complete run.

Each iteration writes an A-to-B table with formation coverage, evidence recall,
sufficiency, reader/action accuracy, latency, bytes, storage and cost. Peaks and
non-reproduced results remain visible and cannot replace the confirmation arm.

## Complexity Tracking

No constitution violation. A parallel engine temporarily duplicates code, not
canonical source data. This is required to preserve a stable control and safe
rollback while avoiding legacy architecture constraints; the legacy engine is
retired only in a later separately reviewed compatibility change.
