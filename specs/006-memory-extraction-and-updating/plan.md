# Implementation Plan: Memory Extraction and Updating

**Branch**: `future/006-memory-extraction-and-updating` | **Date**: 2026-09-05 | **Spec**: `specs/006-memory-extraction-and-updating/spec.md`

**Input**: Feature specification from `specs/006-memory-extraction-and-updating/spec.md`

## Summary

Normalize rule and AtBot extraction into typed, evidence-linked proposals that AtMem alone validates, reviews, and commits.

## Technical Context

- **Language/Version**: Python 3.10–3.13; optional AtBot Python package.
- **Dependencies**: Existing rules and optional configured model providers; no new base SDK.
- **Storage**: SQLite canonical proposals, reviews, and immutable lineage through additive migrations.
- **Testing/Target**: pytest contract/property/security/migration tests on supported local and service platforms.
- **Constraints/Scale**: Bounded context, authorization before model access, deterministic fallback, atomic generation checks.

Extend `atmem/extract/`, canonical fact keys, `Memory` admission, AtBot extraction contracts, and the existing review/control surfaces. Add proposal schemas under `atmem/schemas/v1/` and migrations only for immutable proposal/review metadata.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | AtBot proposes only; AtMem validates and atomically commits authorized mutations. |
| II. Provenance and Exact Evidence | PASS | Every proposal and revision retains source spans, actor, reason, and lineage. |
| III. Safe Defaults and Reversibility | PASS | Uncertain/sensitive changes enter review; deterministic fallback and history remain. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Resolution uses bounded eligible memory and cannot cross scope or revive deleted data. |
| V. Contract-First Host Neutrality | PASS | Typed proposal/review contracts do not depend on one host. |
| VI. Executable Claims | PASS | Action/class/correction/poison/privacy and published-upgrade tests are required. |
| VII. Local-First, Explicit Egress, and Replaceable Intelligence | PASS | Rule fallback remains local; AtBot is replaceable, owns no canonical or independent authority database, and its provider/egress is explicit. |

Re-check after design: any SQLite schema addition MUST pass upgrades from published persisted fixtures on Python 3.10–3.13 and rollback tests.

## Design

1. Introduce `MemoryClass`, `ProposalAction`, evidence references, preconditions, and stable reason codes.
2. Build authorized bounded resolution context from recent captures and eligible fact-key matches.
3. Normalize AtBot and rule output into the same validator; reject unsupported or evidence-free claims.
4. Apply accepted mutations transactionally with generation checks and immutable lineage.
5. Reuse one review service/API for CLI and dashboard; redact proposal content by viewer scope.

## Test Strategy

Contract-test typed outcomes; property-test state transitions; adversarial-test injections and cross-scope aliases; test AtBot failure fallback; migration/rollback tests; benchmark extraction and contradiction metrics by mode.

## Rollout

Land contracts and shadow proposals first. Enable policy-selected admission only after review telemetry and deterministic gates pass; preserve current rule extraction as fallback.

## Project Structure

Contracts and logic live under `atmem/extract/`; canonical commits remain in `atmem/memory.py` and `atmem/store/sqlite.py`; AtBot normalization stays in `packages/atbot/`; tests and docs use existing repository roots.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, implement the Spec 022 six-section target with legacy-route migration, and follow `specs/integration-ownership.md`: Spec 022 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions.


## Unified product integration plan — 2026-09-09

Implement memory admission integration against the new contract owners (Specs 019, 021); use [integration ownership](../integration-ownership.md) and [roadmap order](../product-roadmap.md). Baseline prerequisites refer to existing implementations, not completion of all later amendments.

Touch points (existing or proposed tests): `atmem/extract/`, `atmem/memory.py`, `tests/test_extract_upgrade.py`. Add optional execution provenance to explicit native capture. Reuse the existing application service and authoritative capability response. Public fields are additive/versioned; persisted changes require allocated migrations, real published-floor upgrade/recovery tests and no inferred historical relationships. UI shell ownership transfers to Spec 022; this feature supplies its view models.

Verification: write boundary fixtures for FR-012, FR-013, SC-005 before integration, then run the affected native/delegated, scope, fallback and interface regressions. Missing live-provider or real-host evidence is reported as unavailable, never substituted by a mock pass. Constitution I–VII remain binding; this amendment does not change the constitution or delegate canonical memory authority.
