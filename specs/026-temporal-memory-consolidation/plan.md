# Implementation Plan: Temporal Memory Consolidation and Health Review

**Feature**: `026-temporal-memory-consolidation`

**Date**: 2026-09-12

**Spec**: [spec.md](spec.md)

## Summary

Extend canonical memory with explicit temporal assertion semantics and deterministic derived values, then add an opt-in, bounded consolidation service that produces reviewable health findings. Reuse Spec 006 proposal validation and Spec 015 lifecycle transitions; do not give AtBot mutation authority. Ship the data/contract foundation with the 2.4 work, the common Memory Health projection with 2.5, investigation links with 2.6, and scheduled consolidation as a separately gated 2.8.0 capability.

## Technical context

**Language/version**: Python 3.10–3.13; browser UI in existing HTML/CSS/JavaScript; AtBot companion Python package.

**Primary dependencies**: Standard library and existing AtMem/AtBot contracts by default; optional configured AtBot model providers.

**Storage**: Canonical SQLite through the existing migration registry; vector/graph/cache remain derived and registered for invalidation. Production backends consume the same public contracts through Spec 010.

**Testing**: pytest, AtBot package tests, virtual trusted clocks, persisted upgrade fixtures, benchmark campaigns, API/CLI/MCP/dashboard parity and applicable installed-host/browser tests.

**Target platform**: Local library/CLI/MCP, AtMem service/dashboard and supported host adapters without requiring OpenClaw.

**Performance goals**: At least 10,000 records per bounded preview cycle on declared hardware; no more than 10 ms p95 added deterministic temporal filtering overhead. With Spec 019 policy enforcement and temporal filtering enabled together, directly measured added pre-model control overhead is no more than 35 ms p95; provider, network, retrieval-model and AtBot latency remain separate.

**Constraints**: Disabled by default, preview-only first activation, no model dependency for eligibility/expiry/exact duplicates, no semantic automatic deletion or correction, explicit egress, scope-safe aggregates, immutable evidence and additive/negotiated compatibility.

**Scale/scope**: One cycle evaluates one authorized memory space/subject partition in bounded pages; fleet scheduling is deferred to Spec 024.

## Constitution check

| Principle | Design response |
| --- | --- |
| I. Authority Before Intelligence | AtMem constructs authorized review packages and validates/commits typed proposals; AtBot only analyzes and proposes. |
| II. Provenance and Exact Evidence | Temporal assertions distinguish observed, received, valid and evaluated times; derivations and findings cite exact records/rules. |
| III. Safe Defaults and Reversibility | Scheduling defaults disabled, first enablement is preview-only, and accepted corrections retain lineage. |
| IV. Scope, Privacy and Verifiable Deletion | Selection and aggregation are scope-authorized; forgetting removes registered finding/proposal and model-input derivatives. |
| V. Contract-First Host Neutrality | New contracts are host-neutral and versioned; adapters only project capability/evidence. |
| VI. Executable Claims | Deterministic, optional-model, interface, upgrade, concurrency and installed-profile gates map to SC-001–SC-008. |
| VII. Local-First and Replaceable Intelligence | Eligibility, expiry, exact duplicate detection and age derivation work locally; AtBot failure cannot widen access. |

No constitutional exception is required. Re-check after contract and migration design: automatic effects must remain limited to explicit deterministic lifecycle policy, and no health aggregate may leak inaccessible records.

## Architecture and ownership

### 1. Temporal contracts and persistence

Add `atmem/temporal/` as the feature-owned host-neutral domain:

```text
atmem/temporal/
├── models.py          # temporal kinds, precision, assertion and derivation contracts
├── validation.py      # timezone, interval, precision and evidence validation
├── derivation.py      # deterministic registry; initial DOB-to-age rule
└── eligibility.py     # point-in-time/historical temporal evaluation helpers
```

Persist temporal meaning separately from immutable record content so legacy records and existing record serialization remain compatible. Allocate migration identifiers only after inspecting the shared registry. A temporal row keys to canonical subject/record and carries a generation; it never becomes a second record authority. Extend lifecycle inspection to return the joined projection while Spec 015 continues to own lifecycle state and transitions.

Use half-open intervals `[valid_from, valid_to)`. Do not default missing event/validity/evaluation time to `now`. Legacy records receive `unknown` precision/kind projection unless new evidence is explicitly admitted; migration performs no semantic inference.

### 2. Admission and correction integration

Version the Spec 006 extraction proposal contract additively or negotiate a new format for temporal fields. Deterministic validation checks interval ordering, timezone, precision, supported derivation identity and evidence. AtBot extraction may propose temporal interpretations but cannot set trusted timestamps or bypass review.

Conflict classification compares the same canonical fact key and authorized memory space while accounting for validity overlap. Non-overlapping assertions form history. Overlapping incompatible assertions produce a health finding and retrieval withholding unless an existing explicit correction supplies safe supersession evidence.

### 3. Deterministic derivation

`atmem/temporal/derivation.py` registers pure, versioned functions with declared input fact keys and precision requirements. The initial `date-of-birth-to-age-v1` rule:

- accepts a full authorized date of birth and explicit evaluation date/timezone;
- defines a documented leap-day policy;
- returns value, precision, rule version, input record IDs and assumptions;
- withholds for partial/ambiguous dates rather than guessing;
- materializes a context value only and does not persist a new assertion.

Retrieval and historical-query paths use the same evaluator; CLI/API/dashboard display the same result.

### 4. Consolidation service

Add a feature-owned orchestration package:

```text
atmem/consolidation/
├── models.py          # policy, cycle, finding and proposal contracts
├── service.py         # bounded scan and reconciliation
├── deterministic.py   # expiry and exact-duplicate checks
├── review.py          # authenticated review operations via existing proposal/lifecycle authority
├── scheduler.py       # disabled/preview/active scheduling and restart reconciliation
└── projection.py      # scope-safe Memory Health read model
```

The cycle captures scope, policy generation, evaluation time, temporal/lifecycle generation and AtBot capability version. Page through canonical storage using stable cursors and idempotency identities. Deterministic checks run locally. Semantic candidates are minimized and sent through `atmem/control/atbot_companion.py` only after authorization/egress checks.

AtBot adds versioned companion request/result contracts and implementation modules under `packages/atbot/src/atbot/health.py`. Returned IDs must be a subset of the package. Unknown IDs, malformed fields or capability mismatch invalidate the semantic result; deterministic findings remain independently usable.

### 5. Review and canonical effects

Reuse Spec 006 review semantics for content corrections and Spec 015 lifecycle transitions for eligibility changes. The feature service coordinates rather than duplicates them. Review binds authenticated actor, expected record/temporal/lifecycle generations, proposal digest and reason. Edit-and-approve creates a newly validated proposal. Accepted changes trigger the existing invalidation registry plus any new consolidation projections.

Automatic processing is limited to an explicitly configured deterministic expiry boundary. “Expired” is an eligibility/lifecycle result, not deletion. Semantic findings always require review in the first delivered profile.

### 6. Retrieval, service and UI

Integrate explicit evaluation time and bounded temporal signals after canonical authorization in `atmem/memory.py`, `atmem/retrieve/` and the Spec 019 native provider. Final preparation reloads lifecycle/temporal generations. Unresolved overlapping conflicts cause a reasoned withholding decision rather than selecting the newest or highest-confidence text automatically.

Expose common service operations through `atmem/service/application.py`, then adapt CLI/MCP and dashboard without creating interface-specific authority. Add Context → Memory Health to the Spec 022 shared shell in `atmem/control/assets/`; do not introduce another top-level destination. Investigation findings in 2.6 reference cycle/finding/proposal IDs through typed links owned by Spec 021.

### 7. Privacy, retention and deletion

Store only bounded proposal/finding evidence required for review and audit. Raw AtBot prompts/results are not default Black Box evidence. Register consolidation tables, caches and queued payloads with deletion/invalidation. Scope authorization applies to list, counts, filters, exports and evidence joins. Shared-space semantic similarity never merges ownership or reveals hidden membership.

## Contract and data changes

Planned versioned contracts:

- `atmem-temporal-assertion-v1`
- `atmem-temporal-derivation-v1`
- `atmem-memory-health-policy-v1`
- `atmem-consolidation-cycle-v1`
- `atmem-memory-health-finding-v1`
- `atmem-memory-health-proposal-v1`
- `atbot-memory-health-request-v1` / `atbot-memory-health-result-v1`

Planned persistence, with migration IDs allocated during implementation:

- temporal assertions/generation keyed by subject and canonical record;
- health policies and activation revisions keyed by memory space/scope;
- consolidation cycles/checkpoints/idempotency;
- findings/proposals/review decisions with content-minimized evidence references.

Closed existing formats remain byte-compatible. Public schemas use capability negotiation for temporal/consolidation fields. Backward readers either ignore additive optional projections or receive the legacy representation.

## Verification strategy

1. Contract tests for interval/precision/timezone/derivation/finding/proposal schemas.
2. Pure virtual-clock tests for half-open boundaries, leap day, partial dates, skew and missing time.
3. Extraction/update tests for overlap-aware conflict and immutable correction lineage.
4. Retrieval tests proving invalid records and unresolved conflicts never reach current context.
5. Authorization/egress tests proving inaccessible content or aggregates never reach AtBot or another user.
6. AtBot companion tests for bounded inputs, valid subset outputs, timeout/malformed fallback and exact capability versions.
7. Scheduler tests for disabled/preview/active modes, idempotency, cancellation and crash/restart.
8. Persisted upgrade and forward-recovery tests from every supported release floor.
9. API/CLI/MCP/dashboard parity, accessibility and two-viewport browser journeys.
10. Deterministic and optional hosted benchmark profiles plus declared installed-host coverage.

Append results under `docs/implementation-evidence/026/`; update `docs/current-status.md` only with linked observed evidence.

## Delivery and rollback

1. **2.4 foundation**: temporal contracts/storage, deterministic eligibility/derivation and manual review contracts; no scheduler activation.
2. **2.5 projection**: Memory Health read/review experience in the unified workspace.
3. **2.6 investigation integration**: typed links from memory-health evidence to affected executions without causal overclaim.
4. **2.8.0 complete capability**: opt-in preview scheduler, AtBot health capabilities and separately activated deterministic expiry automation after 2.7 invalidation/propagation gates.

Rollback disables new cycles and temporal-derived injection, preserves audit/history, and serves compatible legacy memory behavior. It cannot undo an already approved correction or prior model exposure; those are reported explicitly.

## Project structure

```text
atmem/temporal/                         # new temporal contracts and deterministic rules
atmem/consolidation/                    # new health-cycle orchestration and projection
atmem/extract/                          # proposal integration owned by Spec 006
atmem/lifecycle/                        # state/transition integration owned by Spec 015
atmem/retrieve/                         # post-authorization temporal ranking/filter integration
atmem/service/application.py            # common service surface
atmem/control/                          # companion client and dashboard projection
packages/atbot/src/atbot/health.py      # replaceable semantic reviewer
packages/atbot/tests/                   # companion contract/failure tests
tests/test_temporal_memory.py           # deterministic temporal behavior
tests/test_memory_consolidation.py      # cycles, review and concurrency
tests/fixtures/product/026/             # independent acceptance fixtures
docs/implementation-evidence/026/       # append-only results
```

**Structure decision**: Introduce narrow temporal and consolidation domain packages, while integrating canonical mutations through existing extraction/lifecycle owners and all interfaces through the shared service.

## Dependencies and sequencing

- Contract foundation depends on existing Spec 006 proposal and Spec 015 lifecycle services.
- Private/shared scheduling and review require the stable Spec 012 memory-space/membership authority planned for 2.4.
- Provider review packages consume Spec 019 policy/egress contracts; native local-only behavior remains independently testable.
- Unified UI consumes Spec 022; investigation links consume Spec 020/021 evidence contracts.
- Propagation assurance consumes Spec 023 and is required before the full 2.8.0 claim.
- Spec 001 owns cross-domain benchmark reporting; Spec 018 registers proven invariants after implementation evidence exists.

No part of this feature is a prerequisite for the scoped 2.3 investigation releases.
