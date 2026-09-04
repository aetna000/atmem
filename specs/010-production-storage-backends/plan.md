# Implementation Plan: Production Storage Backends

**Branch**: `future/010-production-storage-backends` | **Date**: 2026-09-05 | **Spec**: `specs/010-production-storage-backends/spec.md`

**Input**: Feature specification from `specs/010-production-storage-backends/spec.md`

## Summary

Add capability-based production canonical and derived backends plus measured, scope-safe caching and performance evidence while retaining SQLite defaults.

## Technical Context

- **Language/Version**: Python 3.10–3.13; supported PostgreSQL/Qdrant services documented by version.
- **Dependencies**: Optional enterprise-compatible PostgreSQL, pgvector, and Qdrant drivers behind extras.
- **Storage**: SQLite/PostgreSQL canonical stores; local sidecar/pgvector/Qdrant derived indexes.
- **Testing/Target**: pytest conformance, optional container integration, recovery/deletion/load and licence gates.
- **Performance/Scale**: FR-006 reference profile—1M records, 10 query and 50 capture workers, numeric p95 gates.

Extract protocols from `atmem/core/storage.py` and `store/sqlite.py`; add optional `store/postgres.py`, `semantic/pgvector.py`, and `semantic/qdrant.py`. Add stage telemetry under `atmem/telemetry/` and a bounded cache layer near retrieval/context preparation. Drivers stay in extras.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Only canonical-store implementations commit authority; derived stores never authorize. |
| II. Provenance and Exact Evidence | PASS | Generations, transactions, backups, query plans, cache identities, and reports are bound. |
| III. Safe Defaults and Reversibility | PASS | SQLite remains default; optional backends are explicit and migrations have rollback. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Backend conformance and cache adversaries verify scope, lifecycle, and deletion. |
| V. Contract-First Host Neutrality | PASS | Versioned capability protocols isolate storage implementations from hosts. |
| VI. Executable Claims | PASS | Recovery, conformance, published-upgrade, and numeric p95 gates back every claim. |
| VII. Local-First and Explicit Egress | PASS | Local SQLite/sidecar remain useful; remote connections are explicit and attributable. |

Dependency gate: every optional Python driver MUST support Python 3.10–3.13 and carry Apache-2.0-compatible enterprise licensing. Any SQLite schema change MUST pass real persisted upgrades from published AtMem versions.

## Design

1. Freeze capability-based protocols and a backend conformance harness before adapters.
2. Implement PostgreSQL transactions, migrations, generations, and advisory/row concurrency semantics.
3. Implement pgvector/Qdrant as generation-bound rebuildable indexes.
4. Add stage spans with counts/timing and redacted identities.
5. Add bounded caches keyed by scope and every invalidating generation; revalidate hits.
6. Build datasets/load harnesses and publish cold/warm/degraded reports with query plans.

## Test Strategy

Protocol contract tests, optional container integration, crash/concurrency tests, backup/restore and migration rollback, deletion scans, index rebuild equivalence, cache invalidation adversaries, and repeatable load profiles.

## Rollout

Interfaces first with SQLite parity, then experimental optional backends, then supported status after conformance and recovery gates. No existing install changes backend automatically.

## Cross-Spec Dependencies

- **Spec 005**: semantic epoch compatibility and rebuild health used by derived vector backends.
- **Spec 008**: retrieval-stage and cache identity/invalidation contracts.

## Project Structure

Canonical adapters live in `atmem/store/`; derived indexes in `atmem/semantic/`; stage instrumentation in `atmem/telemetry/`; cache integration in `atmem/retrieve/`; conformance tests in `tests/storage/`.
